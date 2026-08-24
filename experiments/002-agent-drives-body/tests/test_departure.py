"""A body that leaves mid-session must produce a result, not a fault.

Experiment 002 lost a session to this: a Pico re-enumerated from ttyACM0 to
ttyACM1, every serial write then raised OSError, and the failure escaped as
JSON-RPC -32603 while obp__status still reported the body as attached with
all four verbs.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "host"))
from obp import BodyClient, Registry, SubprocessTransport  # noqa: E402
from obp.naming import mcp_tool_name  # noqa: E402

FAKE = Path(__file__).parent.parent / "host" / "fake_body.py"
fails = 0


def _kill(client):
    """Yank the cable: no warning, and no lingering pipes to grumble at exit."""
    proc = client.transport.proc
    proc.kill()
    proc.wait(timeout=5)
    for stream in (proc.stdin, proc.stdout):
        if stream is not None:
            try:
                stream.close()
            except (BrokenPipeError, OSError):
                pass


def check(cond, msg):
    global fails
    print(("  ok:   " if cond else "  FAIL: ") + msg)
    if not cond:
        fails += 1


changes = []
reg = Registry(on_change=lambda: changes.append(1))
client = BodyClient(SubprocessTransport([sys.executable, str(FAKE)]))
client.transport.open()
info = reg.add(client)
verb = mcp_tool_name(info.id, "set_led")

check(len(reg.tools()) > 0, "the body is attached and offering verbs")
before = len(changes)

# Kill it the way a yanked cable does: without warning.
_kill(client)

print("a call to a body that has gone")
r = reg.call(verb, {"on": True})
check(isinstance(r, dict) and "content" in r, "returns a result, not an exception")
check(r["isError"] is True, "isError is true")
text = r["content"][0]["text"]
check("stopped responding" in text or "detached" in text, f"and says so: {text[:60]}...")

print("presence follows")
check(reg.tools() == [], "its verbs are withdrawn (H5)")
check(len(changes) > before, "a change was signalled, so tools/list_changed fires (M6)")

print("verify() drops a silent corpse without needing a call")
reg2 = Registry()
c2 = BodyClient(SubprocessTransport([sys.executable, str(FAKE)]))
c2.transport.open()
reg2.add(c2)
_kill(c2)
gone = reg2.verify()
check(len(gone) == 1, "verify reports the departure")
check(reg2.tools() == [], "and the verbs are gone — status cannot report a lie")

print("\n" + ("FAILURES" if fails else "all passed"))
sys.exit(1 if fails else 0)
