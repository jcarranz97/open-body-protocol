"""An MCP server over stdio, exposing OBP bodies as tools.

Hand-written rather than built on an SDK, for two reasons: the experiment is
partly *about* the mapping, so the mapping should be visible; and it keeps
the whole thing dependency-free, which matters when the point is that a
maker can run it.

Every inbound method is logged, including ones we do not implement, so the
experiment can record which MCP dialect a given agent actually speaks
instead of guessing.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, TextIO

from .registry import Registry

SERVER_NAME = "obp"
SERVER_VERSION = "0.1.0"

#: Revisions we are willing to echo back. A client asking for something else
#: gets our newest, which is what the spec tells servers to do.
KNOWN_REVISIONS = {
    "2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25", "2026-07-28",
}
DEFAULT_REVISION = "2025-06-18"


class McpServer:
    def __init__(self, registry: Registry, log_path: Path | None = None,
                 out: TextIO | None = None,
                 attach: "Callable[[], list[str]] | None" = None) -> None:
        self.registry = registry
        #: called by the status verb to retry attaching; returns problems
        self.attach = attach
        self.problems: list[str] = []
        self.out = out or sys.stdout
        self.log_path = log_path
        self.initialised = False
        registry._on_change = self._notify_tools_changed

    # --------------------------------------------------------------- io

    def _log(self, direction: str, payload: Any) -> None:
        line = f"{datetime.now(timezone.utc).isoformat()} {direction} {json.dumps(payload)[:400]}"
        print(line, file=sys.stderr)
        if self.log_path:
            with self.log_path.open("a") as fh:
                fh.write(line + "\n")

    def _send(self, msg: dict[str, Any]) -> None:
        self.out.write(json.dumps(msg) + "\n")
        self.out.flush()
        self._log("-->", msg)

    def _reply(self, req_id: Any, result: Any) -> None:
        self._send({"jsonrpc": "2.0", "id": req_id, "result": result})

    def _fail(self, req_id: Any, code: int, message: str) -> None:
        self._send({"jsonrpc": "2.0", "id": req_id,
                    "error": {"code": code, "message": message}})

    def _notify_tools_changed(self) -> None:
        """M6: presence changed, so the agent's tool list has too."""
        if self.initialised:
            self._send({"jsonrpc": "2.0", "method": "notifications/tools/list_changed"})

    # --------------------------------------------------------- handlers

    #: Always present, even with nothing attached. Without it a host whose
    #: bodies all failed to attach is indistinguishable from a broken server.
    STATUS_TOOL = {
        "name": "obp__status",
        "description": ("[host] Which bodies are attached right now, and why any "
                        "are not. Call this first if no body verbs are available, "
                        "or after fixing a problem to retry attaching."),
        "inputSchema": {"type": "object", "properties": {}},
    }

    def _tool_list(self) -> dict[str, Any]:
        return {"tools": sorted(self.registry.tools() + [self.STATUS_TOOL],
                                key=lambda t: t["name"])}

    def _status(self) -> dict[str, Any]:
        # Liveness first: a body that has silently gone must not be reported
        # as attached, and dropping it withdraws its verbs (M6).
        departed = self.registry.verify()
        if self.attach is not None:
            self.problems = self.attach()      # retry; a fixed problem clears
        for note in departed:
            self.problems.insert(0, note)
        lines = []
        for info in self.registry.bodies:
            verbs = ", ".join(t.name for t in info.tools if not t.user_only)
            lines.append(f"attached: {info.name} [{info.id}] — {verbs}")
        if self.problems:
            lines.append("")
            lines += self.problems
        if not lines:
            # "nothing attached, no errors" is true and useless. Say what was
            # looked for, so the answer is actionable.
            from .ports import BY_ID, stable_ports
            seen = stable_ports()
            if seen:
                lines = ["No bodies attached. USB serial devices present:"]
                lines += [f"    {s}" for s in seen]
                lines.append("None of them answered body/describe — check the "
                             "firmware is running, and that this process can "
                             "open the device.")
            else:
                lines = [f"No bodies attached, and no USB serial devices found "
                         f"under {BY_ID}. Plug a body in and ask again."]
        return {"content": [{"type": "text", "text": "\n".join(lines)}],
                "isError": bool(self.problems and not self.registry.bodies)}

    def handle(self, msg: dict[str, Any]) -> None:
        method = msg.get("method")
        req_id = msg.get("id")
        params = msg.get("params") or {}
        self._log("<--", msg)

        if method == "initialize":
            asked = params.get("protocolVersion")
            version = asked if asked in KNOWN_REVISIONS else DEFAULT_REVISION
            self.initialised = True
            self._reply(req_id, {
                "protocolVersion": version,
                "capabilities": {"tools": {"listChanged": True}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            })
            return

        if method in ("notifications/initialized", "initialized"):
            return                                    # notification, no reply

        # 2026-07-28 dropped the handshake in favour of a discovery call.
        if method == "server/discover":
            self.initialised = True
            self._reply(req_id, {
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                "capabilities": {"tools": {"listChanged": True}},
                **self._tool_list(),
            })
            return

        if method == "tools/list":
            self._reply(req_id, self._tool_list())
            return

        if method == "tools/call":
            name = params.get("name", "")
            args = params.get("arguments") or {}
            if name == self.STATUS_TOOL["name"]:
                self._reply(req_id, self._status())
                return
            # M5/M7: the body's own result passes through unchanged, and a
            # body that has gone produces an isError result, never a fault.
            self._reply(req_id, self.registry.call(name, args))
            return

        if method == "ping":
            self._reply(req_id, {})
            return

        if req_id is None:
            return                                    # unknown notification
        self._fail(req_id, -32601, f"method not found: {method}")

    # ------------------------------------------------------------- loop

    def serve(self, stream: TextIO | None = None) -> None:
        stream = stream or sys.stdin
        for line in stream:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except ValueError:
                self._log("<--", {"unparseable": line[:200]})
                continue
            try:
                self.handle(msg)
            except Exception as exc:                  # never die on one message
                self._log("!!!", {"error": repr(exc)})
                if msg.get("id") is not None:
                    self._fail(msg["id"], -32603, f"internal error: {exc}")
