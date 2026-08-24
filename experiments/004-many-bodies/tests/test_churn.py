"""Bodies arriving and leaving while the brain stays connected.

Experiment 003 attached a fixed set once. A real desk does not hold still: a
board is unplugged, a battery dies, someone brings a second robot into the
room. The question here is whether one brain notices -- and whether the
bodies that stayed carry on working while one of them goes.

    uv run python3 tests/test_churn.py
"""
from __future__ import annotations

import io
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "host"))
from obp import BodyClient, Registry, SubprocessTransport  # noqa: E402
from obp.mcp import McpServer  # noqa: E402
from obp.naming import mcp_tool_name  # noqa: E402

FAKE = Path(__file__).parent.parent / "host" / "fake_body.py"
fails = 0


def check(cond, msg):
    global fails
    print(("  ok:   " if cond else "  FAIL: ") + msg)
    if not cond:
        fails += 1


def spawn(reg, oid):
    c = BodyClient(SubprocessTransport([sys.executable, str(FAKE)],
                                       env=dict(os.environ, OBP_ID=oid)))
    c.transport.open()
    return reg.add(c)


out = io.StringIO()
reg = Registry()
server = McpServer(reg, out=out)


def sent() -> list[dict]:
    msgs = [json.loads(line) for line in out.getvalue().splitlines() if line.strip()]
    return [m for m in msgs if m.get("method") == "notifications/tools/list_changed"]


def ask(method, params=None, mid=1):
    server.handle({"jsonrpc": "2.0", "id": mid, "method": method,
                   **({"params": params} if params else {})})
    last = [json.loads(l) for l in out.getvalue().splitlines() if l.strip()][-1]
    return last.get("result", last)


print("a brain connects to three bodies")
for oid in ("0001", "0002", "0003"):
    spawn(reg, oid)
ask("initialize")
before = len(sent())
tools = ask("tools/list", mid=2)["tools"]
check(len(reg.bodies) == 3, "three bodies attached")
check(any(t["name"] == mcp_tool_name("fake-0002", "blink") for t in tools),
      "the middle body's verbs are offered")

print("a fourth body arrives mid-session")
spawn(reg, "0004")
check(len(sent()) == before + 1,
      "the agent is told its tool list changed, not left to poll")
tools = ask("tools/list", mid=3)["tools"]
check(any(t["name"] == mcp_tool_name("fake-0004", "blink") for t in tools),
      "and the newcomer's verbs are in the refreshed list")

print("one body leaves; the others must not notice")
n = len(sent())
reg.remove("fake-0002")
check(len(sent()) == n + 1, "the departure is announced too")
tools = ask("tools/list", mid=4)["tools"]
names = {t["name"] for t in tools}
check(mcp_tool_name("fake-0002", "blink") not in names,
      "the departed body's verbs are withdrawn")
check(mcp_tool_name("fake-0001", "blink") in names, "body 1 keeps its verbs")
check(mcp_tool_name("fake-0004", "blink") in names, "body 4 keeps its verbs")

r = ask("tools/call", {"name": mcp_tool_name("fake-0001", "blink"),
                       "arguments": {"times": 2}}, mid=5)
check(r.get("isError") is not True,
      "a surviving body still answers after another one left")

print("calling the body that left is a result, not a crash")
r = ask("tools/call", {"name": mcp_tool_name("fake-0002", "blink"),
                       "arguments": {"times": 2}}, mid=6)
check(r.get("isError") is True,
      f"refused with a readable reason: {r['content'][0]['text'][:60]}")

print("a body that comes back is usable again")
spawn(reg, "0002")
tools = ask("tools/list", mid=7)["tools"]
check(mcp_tool_name("fake-0002", "blink") in {t["name"] for t in tools},
      "its verbs return without restarting the brain")
r = ask("tools/call", {"name": mcp_tool_name("fake-0002", "blink"),
                       "arguments": {"times": 1}}, mid=8)
check(r.get("isError") is not True, "and it answers again")

reg.close()
print("\n" + ("FAILURES" if fails else "all passed"))
sys.exit(1 if fails else 0)
