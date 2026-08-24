"""Drive the MCP server the way an agent would, and check the mapping.

Speaks MCP over a pipe to host/obp_mcp.py --fake, so it needs no hardware
and no agent. Checks conformance items M1, M4, M5, M6, M7 and the handshake.

    python3 tests/test_mcp_server.py
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

HOST = Path(__file__).parent.parent / "host" / "obp_mcp.py"
LEGAL_NAME = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
fails = 0


def check(cond, msg):
    global fails
    print(("  ok:   " if cond else "  FAIL: ") + msg)
    if not cond:
        fails += 1


class Client:
    def __init__(self) -> None:
        self.p = subprocess.Popen(
            [sys.executable, str(HOST), "--fake"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, bufsize=1)
        self.n = 0

    def request(self, method, params=None):
        self.n += 1
        msg = {"jsonrpc": "2.0", "id": self.n, "method": method}
        if params is not None:
            msg["params"] = params
        self.p.stdin.write(json.dumps(msg) + "\n")
        self.p.stdin.flush()
        while True:
            line = self.p.stdout.readline()
            if not line:
                raise SystemExit("server closed the connection")
            reply = json.loads(line)
            if reply.get("id") == self.n:
                return reply

    def notify(self, method, params=None):
        msg = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            msg["params"] = params
        self.p.stdin.write(json.dumps(msg) + "\n")
        self.p.stdin.flush()

    def close(self):
        self.p.terminate()
        self.p.wait(timeout=5)


c = Client()

print("handshake")
r = c.request("initialize", {"protocolVersion": "2025-06-18",
                             "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}})
res = r.get("result", {})
check(res.get("protocolVersion") == "2025-06-18", "echoes the client's protocol revision")
check(res.get("capabilities", {}).get("tools", {}).get("listChanged") is True,
      "declares tools.listChanged (M6)")
check(res.get("serverInfo", {}).get("name") == "obp", "identifies itself")
c.notify("notifications/initialized")

print("an unknown revision falls back rather than failing")
c2 = Client()
r2 = c2.request("initialize", {"protocolVersion": "1999-01-01", "capabilities": {}})
check("result" in r2 and r2["result"]["protocolVersion"] != "1999-01-01",
      "offers its own revision instead")
c2.close()

print("tools/list")
tools = c.request("tools/list")["result"]["tools"]
names = [t["name"] for t in tools]
check(len(tools) > 0, f"{len(tools)} tools offered")
check(all(LEGAL_NAME.match(n) for n in names), "every name matches ^[a-zA-Z0-9_-]{1,64}$ (M1)")
check(all("__" in n for n in names), "every name is namespaced by body (M1)")
check(names == sorted(names), "sorted deterministically (H2)")
check(not any(n.endswith("__reboot") for n in names), "userOnly verb withheld (M4)")
check(all(t["description"].startswith("[") for t in tools),
      "descriptions name their body, so two bodies are distinguishable")
check(all("inputSchema" in t and t["inputSchema"].get("type") == "object" for t in tools),
      "schemas passed through (M5)")

print("tools/list is stable across calls")
again = [t["name"] for t in c.request("tools/list")["result"]["tools"]]
check(again == names, "same order twice — a reshuffle would bust a prompt cache")

print("tools/call")
target = next(n for n in names if n.endswith("__set_brightness"))
r = c.request("tools/call", {"name": target, "arguments": {"level": 40}})["result"]
check(r.get("isError") is False, "a good call succeeds")
check("40" in r["content"][0]["text"], f"body's own text passes through: {r['content'][0]['text']!r}")

print("a rejected call is a result, not a fault (M5)")
r = c.request("tools/call", {"name": target, "arguments": {"level": 150}})["result"]
check(r.get("isError") is True, "isError is true")
check("0..100" in r["content"][0]["text"], "the body's reason reaches the caller")

print("an unknown tool is a result, not a fault (M7)")
r = c.request("tools/call", {"name": "nosuchbody__nosuchverb", "arguments": {}})
check("result" in r and r["result"]["isError"] is True, "isError result, no protocol error")

print("unknown methods")
r = c.request("tools/definitely_not_a_method")
check(r.get("error", {}).get("code") == -32601, "JSON-RPC -32601 for a method we do not implement")

print("ping")
check("result" in c.request("ping"), "answers ping")

c.close()
print("\n" + ("FAILURES" if fails else "all passed"))
sys.exit(1 if fails else 0)
