"""userOnly is about *who is asking*, not about what exists.

An agent must never be offered the verb; a person at a terminal may use it.
Conflating those two made the reference CLI unable to reboot its own board,
which is how this test came to exist.
"""
from __future__ import annotations

import subprocess
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


reg = Registry()
client = BodyClient(SubprocessTransport([sys.executable, str(FAKE)]))
client.transport.open()
info = reg.add(client)

name = mcp_tool_name(info.id, "reboot")
offered = [t["name"] for t in reg.tools()]

check(name not in offered, "reboot is absent from the offered tool list (M4)")
check(reg.find(name) is not None, "but it is still routable by the host")

r = reg.call(name, {}, autonomous=True)
check(r["isError"] is True, "an autonomous caller is refused")
check("userOnly" in r["content"][0]["text"], "and told why")

r = reg.call(name, {}, autonomous=False)
check(r["isError"] is False, "a person is allowed")

reg.close()
print("\n" + ("FAILURES" if fails else "all passed"))
sys.exit(1 if fails else 0)
