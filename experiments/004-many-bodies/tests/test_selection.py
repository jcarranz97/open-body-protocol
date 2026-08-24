"""Selecting a body, without taking the others away.

"I am operating the arm" should make an unqualified instruction mean the arm.
The naive implementation filters the tool list down to the selected body, and
it is wrong three times over:

  * MCP 2026-07-28 (SEP-2567) requires tools/list not to depend on
    per-connection or prior-call state, so a filtered list is not conformant.
  * Tool definitions sit at the front of a model's cache prefix, so swapping
    them invalidates the tools block, the system prompt and the entire
    conversation history.
  * It makes the interesting case impossible. With the arm selected, "turn on
    the lights in room1" must still work.

So selection here is host-side state and nothing else: a default for an
unqualified instruction, never a filter.

    uv run python3 tests/test_selection.py
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


def spawn(reg, oid, servo=False, dimmable=True):
    env = dict(os.environ, OBP_ID=oid,
               OBP_SERVO="1" if servo else "0",
               OBP_DIMMABLE="1" if dimmable else "0")
    c = BodyClient(SubprocessTransport([sys.executable, str(FAKE)], env=env))
    c.transport.open()
    return reg.add(c)


out = io.StringIO()
reg = Registry()
server = McpServer(reg, out=out)


def replies():
    return [json.loads(l) for l in out.getvalue().splitlines() if l.strip()]


def ask(method, params=None, mid=1):
    server.handle({"jsonrpc": "2.0", "id": mid, "method": method,
                   **({"params": params} if params else {})})
    return replies()[-1].get("result", {})


def call_tool(name, args=None, mid=99):
    return ask("tools/call", {"name": name, "arguments": args or {}}, mid=mid)


spawn(reg, "arm", servo=True)        # the thing on the desk
spawn(reg, "drone", dimmable=False)  # the thing in the air
spawn(reg, "lights")                 # a hub speaking for a house
ask("initialize")

print("selecting a body does not change what exists")
before = [t["name"] for t in ask("tools/list", mid=2)["tools"]]
n_changed = len([m for m in replies()
                 if m.get("method") == "notifications/tools/list_changed"])
r = call_tool("obp__use", {"body": "fake-arm"}, mid=3)
check(r.get("isError") is not True, f"selected: {r['content'][0]['text'][:52]}")
after = [t["name"] for t in ask("tools/list", mid=4)["tools"]]
check(before == after, "the tool list is byte-identical before and after (SEP-2567)")
check(len([m for m in replies()
           if m.get("method") == "notifications/tools/list_changed"]) == n_changed,
      "and no list_changed was emitted, so no prompt cache was thrown away")

print("the unselected bodies are still reachable by name")
r = call_tool(mcp_tool_name("fake-lights", "blink"), {"times": 1}, mid=5)
check(r.get("isError") is not True,
      "'turn on the lights' works with the arm selected -- selection is not a filter")
r = call_tool(mcp_tool_name("fake-drone", "blink"), {"times": 1}, mid=6)
check(r.get("isError") is not True, "so does the drone")

print("an unqualified instruction goes to the selection")
body, note = reg.resolve("blink")
check(body == "fake-arm", f"blink resolves to the arm ({note})")
check(note.startswith("used the selected body"),
      f"and the host says the selection is what decided it: {note!r}")

print("a verb the selected body lacks is refused, and names who can")
# The drone has no dimmable light; the arm and the lights hub do. (An arm
# with a servo lacks nothing, which is why the first version of this test
# passed against a body that was behaving correctly.)
reg.select("fake-drone")
body, note = reg.resolve("set_brightness")
check(body is None, "not silently retargeted -- move on a drone is not move on an arm")
check("fake-drone" in note and "fake-arm" in note and "fake-lights" in note,
      f"the refusal names both the failure and the remedy: {note}")
reg.select("fake-arm")

print("a failed selection clears, IMAP-style, rather than leaving a stale one")
r = call_tool("obp__use", {"body": "fake-nonexistent"}, mid=7)
check(r.get("isError") is True, "selecting something absent is an error")
check(reg.selected is None,
      "and nothing is selected now -- a stale selection would send the next "
      "unqualified instruction to the wrong machine")
body, note = reg.resolve("blink")
check(body is None and "no body is selected" in note,
      f"so an unqualified instruction fails loudly: {note}")

print("selection survives a body flapping, because presence flaps")
reg.select("fake-drone")
reg.remove("fake-drone")
check(reg.selected == "fake-drone", "the selection is kept when the body goes")
check(reg.selected_present() is False, "but it is not reported as present")
check("NOT present" in reg.selection_note(),
      f"and status says so plainly: {reg.selection_note()}")

print("clearing is explicit")
r = call_tool("obp__use", {}, mid=8)
check(reg.selected is None, f"empty body clears: {r['content'][0]['text'][:44]}")

reg.close()
print("\n" + ("FAILURES" if fails else "all passed"))
sys.exit(1 if fails else 0)
