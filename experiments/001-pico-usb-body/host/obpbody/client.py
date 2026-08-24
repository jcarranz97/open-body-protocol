"""The body contract, host side.

Wire format (v0), newline-delimited JSON-RPC 2.0 in both directions:

    -> {"jsonrpc":"2.0","id":1,"method":"body/describe"}
    <- {"jsonrpc":"2.0","id":1,"result":{"body":{...},"tools":[...]}}

    -> {"jsonrpc":"2.0","id":2,"method":"tools/call",
        "params":{"name":"set_led","arguments":{"on":true}}}
    <- {"jsonrpc":"2.0","id":2,"result":{"content":[{"type":"text","text":"..."}],
                                         "isError":false}}

    <- {"jsonrpc":"2.0","method":"notifications/body/online","params":{...}}

Tool descriptors and call results are deliberately MCP-shaped (`name`,
`description`, `inputSchema`; `content[]` + `isError`) so that re-exposing a
body as an MCP server is a relabelling rather than a translation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .transport import Transport


class BodyError(RuntimeError):
    """The body answered, and the answer was a protocol-level error."""


@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]
    #: Privileged actions a model must never invoke on its own initiative.
    #: Borrowed from xiaozhi's AddUserOnlyTool: "reboot" is a very different
    #: kind of verb from "wave", and the schema cannot express that difference.
    user_only: bool = False

    @classmethod
    def from_wire(cls, raw: dict[str, Any]) -> ToolSpec:
        return cls(
            name=raw["name"],
            description=raw.get("description", ""),
            input_schema=raw.get("inputSchema", {"type": "object"}),
            user_only=bool(raw.get("userOnly", False)),
        )


@dataclass
class BodyInfo:
    id: str
    name: str
    firmware: str
    caps: list[str] = field(default_factory=list)
    tools: list[ToolSpec] = field(default_factory=list)

    def tool(self, name: str) -> ToolSpec | None:
        return next((t for t in self.tools if t.name == name), None)


class BodyClient:
    def __init__(self, transport: Transport, timeout: float = 5.0) -> None:
        self.transport = transport
        self.timeout = timeout
        self._next_id = 0
        self.info: BodyInfo | None = None

    def __enter__(self) -> BodyClient:
        self.transport.open()
        return self

    def __exit__(self, *exc: object) -> None:
        self.transport.close()

    def _request(self, method: str, params: dict[str, Any] | None = None) -> Any:
        self._next_id += 1
        req_id = self._next_id
        msg: dict[str, Any] = {"jsonrpc": "2.0", "id": req_id, "method": method}
        if params is not None:
            msg["params"] = params
        self.transport.send(msg)

        # Notifications may arrive interleaved with our reply; skip past them.
        while True:
            reply = self.transport.recv(self.timeout)
            if reply is None:
                raise BodyError(f"no response to {method} within {self.timeout}s")
            if "id" not in reply:
                continue
            if reply["id"] != req_id:
                continue
            if "error" in reply:
                err = reply["error"]
                raise BodyError(f"{method}: {err.get('message')} ({err.get('code')})")
            return reply.get("result")

    def describe(self) -> BodyInfo:
        """One round trip for identity + capabilities + tools.

        Deliberately not MCP's `initialize` + `tools/list` two-step: on a
        serial link every round trip costs, and the 2026-07-28 MCP revision
        retired that handshake anyway.
        """
        result = self._request("body/describe")
        body = result.get("body", {})
        self.info = BodyInfo(
            id=body.get("id", "unknown"),
            name=body.get("name", "unnamed body"),
            firmware=body.get("fw", "?"),
            caps=list(body.get("caps", [])),
            tools=[ToolSpec.from_wire(t) for t in result.get("tools", [])],
        )
        return self.info

    def call(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._request(
            "tools/call", {"name": name, "arguments": arguments or {}}
        )


def render_result(result: dict[str, Any]) -> str:
    parts = [c.get("text", "") for c in result.get("content", []) if c.get("type") == "text"]
    text = " ".join(p for p in parts if p) or "(no content)"
    return f"{'ERROR: ' if result.get('isError') else ''}{text}"
