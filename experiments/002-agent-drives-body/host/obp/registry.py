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


class Registry:
    """Holds the bodies currently present and the verbs they offer."""

    def __init__(self, on_change: Callable[[], None] | None = None) -> None:
        self._bodies: dict[str, Entry] = {}
        self._on_change = on_change

    # ---------------------------------------------------------- lifecycle

    def add(self, client: BodyClient) -> BodyInfo:
        """Connect, describe, and register. Raises BodyError on failure."""
        info = client.describe()
        entry = Entry(client=client, info=info)
        for tool in info.tools:
            if tool.user_only:
                continue                       # H4: never offered onward
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

    def call(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Invoke a verb, returning an OBP/MCP result. Never raises."""
        found = self.find(tool_name)
        if found is None:
            # H6: an unknown or departed body is a readable result, not an
            # exception, so the model can adapt instead of seeing a crash.
            return _error(f"no body currently offers '{tool_name}'")
        entry, verb = found
        try:
            return entry.client.call(verb, arguments)
        except BodyError as exc:
            self.remove(entry.info.id)
            return _error(f"the body '{entry.info.name}' is not responding: {exc}")


def _error(text: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": text}], "isError": True}
