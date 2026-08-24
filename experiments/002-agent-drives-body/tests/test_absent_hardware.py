"""A body must not report success for something it did not do (B4a).

The reference firmware advertised `move` on a board with no drivetrain and
answered "acknowledged move forward 10cm (simulated: no drivetrain attached)"
with isError false. The disclaimer is honest and completely invisible: a host
reads isError, so an agent asking a wheel-less board to move was told it
moved. It survived experiments 001 and 002 because nothing here asserted it.

A body that refuses is recoverable. A body that lies about acting corrupts
everything the brain believes about the world, and no care in the brain can
detect it.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "host"))
from obp import BodyClient, SubprocessTransport  # noqa: E402

FAKE = Path(__file__).parent.parent / "host" / "fake_body.py"
fails = 0


def check(cond, msg):
    global fails
    print(("  ok:   " if cond else "  FAIL: ") + msg)
    if not cond:
        fails += 1


client = BodyClient(SubprocessTransport([sys.executable, str(FAKE)]))
client.transport.open()
info = client.describe()
caps = set(info.caps)

print("a verb with no hardware behind it refuses, and says so machine-readably")
r = client.call("move", {"direction": "forward", "distance_cm": 15})
check("drivetrain" not in caps, f"the body claims no drivetrain (caps: {sorted(caps)})")
check(r.get("isError") is True,
      f"move returns isError true, not a success with a disclaimer "
      f"(got isError={r.get('isError')!r}: {r['content'][0]['text']!r})")

print("refusing is not the same as being broken")
r2 = client.call("move", {"direction": "sideways"})
check(r2.get("isError") is True, "an invalid direction is still refused")
r3 = client.call("blink", {"times": 2})
check(r3.get("isError") is not True, "a verb the hardware does have still works")

print("every advertised verb either works or refuses -- none pretends")
for tool in client._request("body/describe")["tools"]:
    if tool.get("userOnly"):
        continue
    res = client.call(tool["name"], {})
    text = res["content"][0]["text"].lower()
    pretends = res.get("isError") is not True and (
        "simulat" in text or "no drivetrain" in text or "has no " in text)
    check(not pretends, f"{tool['name']}: does not claim success while admitting it cannot")

client.transport.close()
print("\n" + ("FAILURES" if fails else "all passed"))
sys.exit(1 if fails else 0)
