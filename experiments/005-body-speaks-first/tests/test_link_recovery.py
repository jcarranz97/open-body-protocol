"""A body whose link drops mid-call keeps its place in the tool surface.

Part C found this the hard way. The Pico re-enumerated during a blink, the
serial write failed with [Errno 5], and the registry detached the body. The
host then did everything right -- list_changed fired, obp__status re-attached
it, the client refetched, and the verbs really were restored -- and the model,
composing its reply in that same turn, still reported "its four verbs are gone
from my tool surface" and never retried.

The host was correct and the agent was wrong, which is not a comfortable way
to be right. The fix is to stop creating the situation: a link that can be
repaired is repaired, the body never leaves the tool surface, and there is
nothing stale for anyone to reason about.

What is deliberately NOT done is re-issuing the call. The write failed, but
"failed" and "did not happen" are different claims and this layer cannot tell
them apart.

    uv run python3 tests/test_link_recovery.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "host"))
from obp import BodyClient, Registry, SubprocessTransport  # noqa: E402
from obp.naming import mcp_tool_name  # noqa: E402

FAKE = Path(__file__).parent.parent / "host" / "fake_body.py"
fails = 0


def check(cond, msg):
    global fails
    print(("  ok:   " if cond else "  FAIL: ") + msg)
    if not cond:
        fails += 1


changes = []
reg = Registry(on_change=lambda: changes.append(1))
c = BodyClient(SubprocessTransport([sys.executable, str(FAKE)],
                                   env=dict(os.environ, OBP_ID="flappy")))
c.transport.open()
reg.add(c)
blink = mcp_tool_name("fake-flappy", "blink")
check(reg.call(blink, {"times": 1}).get("isError") is not True, "the body works")

print("the link drops mid-call")
n_before = len(changes)
c.transport.proc.kill()                    # the board re-enumerates
c.transport.proc.wait(timeout=5)
r = reg.call(blink, {"times": 1})

check(r.get("isError") is True, "the failed call is reported as a result, not a fault")
text = r["content"][0]["text"]
check("re-established" in text, f"and says the link was repaired: {text[:64]}...")
check("retry" in text, "and hands the retry decision back to the caller")
check("may not have run" in text,
      "without claiming the call did or did not happen -- it cannot know")

print("the body never left")
check(len(reg.bodies) == 1, "it is still attached")
check(mcp_tool_name("fake-flappy", "blink") in {t["name"] for t in reg.tools()},
      "its verbs never left the tool surface, so nothing went stale")
check(len(changes) == n_before,
      "and no list_changed was emitted -- no prompt cache thrown away for a blip")

print("and it works on the retry the caller chooses to make")
r = reg.call(blink, {"times": 2})
check(r.get("isError") is not True, f"retry succeeds: {r['content'][0]['text']}")

print("a body that is really gone is still detached")
c.transport.proc.kill()
c.transport.proc.wait(timeout=5)
c.transport.argv = ["/nonexistent-binary"]   # cannot be reopened
r = reg.call(blink, {"times": 1})
check(r.get("isError") is True, "the call fails")
check("detached" in r["content"][0]["text"], "and the body is detached for real")
check(len(reg.bodies) == 0, "so its verbs are withdrawn (H5)")
check(len(changes) > n_before, "and that change IS announced")

reg.close()
print("\n" + ("FAILURES" if fails else "all passed"))
sys.exit(1 if fails else 0)
