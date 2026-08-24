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
from .events import Event, EventLog
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
        #: The body an unqualified instruction means. Host-side state, never
        #: sent to a body and never a filter -- see select().
        self._selected: str | None = None
        #: Everything every body has said unprompted, in one place. One log
        #: rather than one per body: "what has happened?" is a question about
        #: the room, not about a particular machine in it.
        self.events = EventLog()

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
        # Route this body's unprompted messages into the shared log. Done
        # before the duplicate check so a refused newcomer never becomes a
        # source of events attributed to the body that is already here.
        client.on_notification = lambda msg, _c=client: self._on_notification(_c, msg)
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

    # ------------------------------------------------------------ events

    def _on_notification(self, client: BodyClient, msg: dict[str, Any]) -> None:
        if msg.get("method") != "notifications/body/event":
            return
        body_id = client.info.id if client.info else "unknown"
        self.events.record(body_id, msg.get("params") or {})

    def poll_events(self, timeout: float = 0.0) -> int:
        """Look for anything the bodies have said since anyone last asked.

        Only serial and subprocess bodies need this: nothing reads those
        transports unless a call is in flight, so a press between calls waits
        in a buffer. An MQTT body has a broker client running its own thread
        and its events arrive without being asked for -- which is a real
        difference between the bindings, not an implementation detail.
        """
        seen = 0
        for entry in list(self._bodies.values()):
            if hasattr(entry.client.transport, "kind") and \
                    entry.client.transport.kind == "mqtt":
                continue
            try:
                seen += entry.client.poll(timeout)
            except Exception:
                pass          # a body that died is presence's problem, not this
        return seen

    # --------------------------------------------------------- selection

    def select(self, body_id: str | None) -> str | None:
        """Point unqualified instructions at one body. Returns the selection.

        Selection is **host-side state and nothing else**. It does not filter
        `tools()`, does not rename a verb, and is never sent to a body. Three
        separate reasons, and any one of them is sufficient:

        * MCP 2026-07-28 (SEP-2567) requires that `tools/list` not depend on
          per-connection or prior-call state, so a list that changed with a
          selection would not be conformant.
        * Tool definitions sit at the very front of a model's cache prefix,
          so swapping them invalidates the tools block, the system prompt and
          the whole conversation. Selecting a body five times costs more than
          showing every body's verbs all session.
        * A filtered list makes the interesting case impossible. With the arm
          selected, "turn on the lights in room1" must still work -- and it
          only can if the lights body's verbs were never taken away.

        What selection buys is a *default*, so a person can say "blink" and
        mean the thing in front of them.

        An id that is not present is still accepted. Bodies flap, presence
        debouncing exists for that reason, and forgetting the selection
        because a cable was nudged is worse than holding a stale one -- which
        `selection_note()` reports honestly.
        """
        self._selected = body_id
        return self._selected

    @property
    def selected(self) -> str | None:
        return self._selected

    def selected_present(self) -> bool:
        return self._selected is not None and self._selected in self._bodies

    def selection_note(self) -> str:
        if self._selected is None:
            return "no body is selected; name one explicitly or select it"
        entry = self._bodies.get(self._selected)
        if entry is None:
            return (f"selected: {self._selected} -- NOT present right now, so "
                    f"unqualified instructions cannot be carried out")
        return f"selected: {entry.info.name} [{self._selected}]"

    def offers(self, verb: str) -> list[str]:
        """Which present bodies advertise this bare verb name."""
        return [e.info.id for e in self._bodies.values() if e.info.tool(verb)]

    def resolve(self, verb: str, body_id: str | None = None) -> tuple[str | None, str]:
        """Pick the body for a bare verb: explicit, else selected, else fail.

        Returns `(body_id, note)`. `body_id` is None when the caller must be
        told something instead -- and the note names the bodies that *do*
        offer the verb, because "no" is much more useful with "but these can"
        attached to it. Anthropic's tool guidance and every disambiguation
        study say the same thing: an error that names the alternative costs
        one round trip, where a silent refusal costs the task.

        This never retargets a physical action on its own. `move` on a drone
        and `move` on an arm are the same word and very different outcomes,
        so a body that cannot do the thing is reported, not swapped.
        """
        candidates = self.offers(verb)
        if body_id is not None:
            if body_id not in self._bodies:
                return None, f"'{body_id}' is not present"
            if body_id not in candidates:
                alt = ", ".join(candidates) if candidates else "no present body"
                return None, f"'{body_id}' does not offer '{verb}'; {alt} does"
            return body_id, ""

        if self._selected is not None and self._selected in candidates:
            # Say that the selection was what decided this. kubectl gets this
            # backwards -- its scope warning fires only when you typed
            # --namespace, so the implicit case, the one that needs telling,
            # is the silent one. An explicitly named body needs no note; an
            # implicitly chosen one does.
            return self._selected, f"used the selected body '{self._selected}'"

        if not candidates:
            return None, f"no present body offers '{verb}'"

        if self._selected is None:
            if len(candidates) == 1:
                return candidates[0], f"no body selected; used {candidates[0]}"
            return None, (f"no body is selected and {len(candidates)} bodies offer "
                          f"'{verb}': {', '.join(candidates)}. Select one, or name it.")

        # Selected, but it cannot do this. Say so, and say who can.
        return None, (f"the selected body '{self._selected}' does not offer "
                      f"'{verb}'. {', '.join(candidates)} "
                      f"{'does' if len(candidates) == 1 else 'do'}. "
                      f"Name it explicitly, or select it.")

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
            # A board that re-enumerates -- unplugged and back, or reset --
            # raises here, and detaching it immediately is what made Part C
            # go wrong: the verbs left the agent's tool surface, and even
            # after obp__status put them back the model was still reasoning
            # about a list it had already refreshed. presence.md says a body
            # that disappears and returns within a short window is the same
            # body; the by-id path this transport was opened with is exactly
            # what survives re-enumeration, so try it once before giving up.
            #
            # What is NOT done is re-issuing the call. The write failed, but
            # "failed" and "did not happen" are different claims, and this is
            # the layer that cannot tell them apart. Blink twice is harmless;
            # move twice is not. So the link is repaired, the body keeps its
            # verbs, and the decision to retry goes back to the caller.
            try:
                entry.client.transport.close()
                entry.client.transport.open()
                entry.client._request("ping")
            except Exception:
                pass
            else:
                return _error(
                    f"the link to '{entry.info.name}' dropped during this call "
                    f"and has been re-established ({type(exc).__name__}). The "
                    f"call may not have run. Its verbs are still available, so "
                    f"retry if you still want it.")
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
