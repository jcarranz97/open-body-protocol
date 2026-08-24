"""A minimal body registry: presence, discovery, deterministic ordering.

Implements the host requirements from the OBP conformance list that matter
for driving bodies from an agent: sort deterministically (H2), namespace
per body (H3), withhold userOnly verbs (H4), withdraw verbs when presence is
lost (H5), and never hang on a departed body (H6).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from .client import BodyClient, BodyError, BodyInfo, ToolSpec
from .naming import mcp_tool_name


@dataclass
class Entry:
    client: BodyClient
    info: BodyInfo
    #: mcp tool name -> (body id, verb)
    routes: dict[str, tuple[str, str]] = field(default_factory=dict)


class DuplicateBodyId(BodyError):
    """A second body claimed an id that is already registered."""


class Registry:
    """Holds the bodies currently present and the verbs they offer."""

    def __init__(self, on_change: Callable[[], None] | None = None) -> None:
        self._bodies: dict[str, Entry] = {}
        self._on_change = on_change

    # ---------------------------------------------------------- lifecycle

    def add(self, client: BodyClient) -> BodyInfo:
        """Connect, describe, and register. Raises BodyError on failure.

        A body already registered under this id is kept, and the newcomer is
        refused. Two things claiming one id is either one body reachable two
        ways or two boards flashed with the same identity, and a host cannot
        tell which: identical firmware produces identical descriptors. Both
        readings argue for refusing. If it is one body, a second route adds
        nothing; if it is two boards, silently merging them means every command
        reaches an arbitrary one of the pair, which for something with motors
        is the worst outcome available.

        The previous behaviour was `self._bodies[info.id] = entry` -- the
        newcomer displaced a working body and its transport was never closed.
        """
        info = client.describe()
        incumbent = self._bodies.get(info.id)
        if incumbent is not None and incumbent.client is not client:
            client.transport.close()   # do not leak the refused connection
            raise DuplicateBodyId(
                f"{info.id} is already registered via "
                f"{incumbent.client.transport.describe()}; refusing the same id "
                f"via {client.transport.describe()}. Two boards sharing an id "
                f"cannot both be addressed -- give one of them its own.")
        entry = Entry(client=client, info=info)
        # Every verb is routable; whether it is *offered* depends on who is
        # asking. H4 is about autonomous callers, not about the host.
        for tool in info.tools:
            entry.routes[mcp_tool_name(info.id, tool.name)] = (info.id, tool.name)
        self._bodies[info.id] = entry
        self._changed()
        return info

    def remove(self, body_id: str) -> None:
        """H5: presence lost, verbs withdrawn."""
        if self._bodies.pop(body_id, None) is not None:
            self._changed()

    def close(self) -> None:
        for entry in list(self._bodies.values()):
            entry.client.transport.close()
        self._bodies.clear()

    def _changed(self) -> None:
        if self._on_change:
            self._on_change()

    # ------------------------------------------------------------- query

    def transport_of(self, body_id: str) -> str:
        """The short binding name of a body, for display: local/usb/mqtt."""
        entry = self._bodies.get(body_id)
        return getattr(entry.client.transport, "kind", "?") if entry else "?"

    @property
    def bodies(self) -> list[BodyInfo]:
        return [e.info for e in self._bodies.values()]

    def tools(self) -> list[dict[str, Any]]:
        """Every present body's verbs, as MCP tool definitions.

        H2: sorted deterministically. A body may emit verbs in any order and
        two firmwares of the same body have been observed to disagree; an
        unstable order invalidates a model's prompt cache.
        """
        out: list[dict[str, Any]] = []
        for entry in self._bodies.values():
            for tool in entry.info.tools:
                if tool.user_only:
                    continue
                out.append({
                    "name": mcp_tool_name(entry.info.id, tool.name),
                    # the body's name is prefixed so a model can tell two
                    # otherwise identical bodies apart
                    "description": f"[{entry.info.name}] {tool.description}",
                    "inputSchema": tool.input_schema,
                })
        return sorted(out, key=lambda t: t["name"])

    def find(self, tool_name: str) -> tuple[Entry, str] | None:
        for entry in self._bodies.values():
            route = entry.routes.get(tool_name)
            if route is not None:
                return entry, route[1]
        return None

    # ------------------------------------------------------------- calls

    def call(self, tool_name: str, arguments: dict[str, Any],
             *, autonomous: bool = True) -> dict[str, Any]:
        """Invoke a verb, returning an OBP/MCP result. Never raises.

        `autonomous` is the caller's nature, not a permission flag: an agent
        passes True and a person at a terminal passes False. Only the first
        is subject to H4, because `userOnly` exists to stop a model doing
        something surprising — not to stop an owner rebooting their board.
        """
        found = self.find(tool_name)
        if found is None:
            # H6: an unknown or departed body is a readable result, not an
            # exception, so the model can adapt instead of seeing a crash.
            return _error(f"no body currently offers '{tool_name}'")
        entry, verb = found
        spec = entry.info.tool(verb)
        if autonomous and spec is not None and spec.user_only:
            return _error(f"'{verb}' is marked userOnly and may not be invoked autonomously")
        try:
            return entry.client.call(verb, arguments)
        except Exception as exc:
            # Deliberately broad. Anything that goes wrong talking to a body
            # is a *presence* signal, and the caller must receive a result it
            # can read rather than a transport fault. A serial write to a
            # re-enumerated device raises OSError, not BodyError, and letting
            # that escape produced a JSON-RPC -32603 in experiment 002.
            self.remove(entry.info.id)
            return _error(
                f"the body '{entry.info.name}' stopped responding and has been "
                f"detached ({type(exc).__name__}: {exc}). Its verbs are no longer "
                f"available; ask for status to look for it again.")

    def verify(self) -> list[str]:
        """Ping every body and drop the ones that do not answer.

        Attachment is not presence. A host that reports its attach-time
        inventory while every write fails is lying, which is what experiment
        002 caught obp__status doing.
        """
        gone = []
        for body_id, entry in list(self._bodies.items()):
            try:
                entry.client._request("ping")
            except Exception:
                gone.append(f"{entry.info.name} [{body_id}] stopped responding")
                self.remove(body_id)
        return gone


def _error(text: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": text}], "isError": True}
