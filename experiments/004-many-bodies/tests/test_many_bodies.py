"""One brain, many bodies: routing, naming and hardware differences.

Experiment 003 proved two bodies could share a registry. This asks what
happens once the set is genuinely plural: does every verb reach the body it
names, does the list stay stable enough for a prompt cache, and does a body
with different hardware stay different?

    uv run python3 tests/test_many_bodies.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "host"))
from obp import BodyClient, Registry, SubprocessTransport  # noqa: E402
from obp.naming import mcp_tool_name, split_tool_name  # noqa: E402
from obp.registry import DuplicateBodyId  # noqa: E402

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


reg = Registry()

# An explicit plan, so the expectations cannot drift from what was asked for.
# The first version of this test recomputed the rule in the assertions and got
# it wrong -- it failed against bodies that were behaving correctly.
PLAN = [
    ("0001", False, True),    # led, dimmable
    ("0002", True,  False),   # led, servo
    ("0003", False, True),
    ("0004", True,  True),    # led, dimmable, servo
    ("0005", False, False),   # led only
    ("0006", True,  True),
    ("0007", False, True),
    ("0008", True,  False),
]

print("eight bodies, four shapes of hardware")
for oid, servo, dimmable in PLAN:
    spawn(reg, oid, servo=servo, dimmable=dimmable)
check(len(reg.bodies) == len(PLAN), f"all eight registered ({len(reg.bodies)})")

caps = {b.id: set(b.caps) for b in reg.bodies}
mismatched = []
for oid, servo, dimmable in PLAN:
    want = {"led"} | ({"servo"} if servo else set()) | ({"dimmable"} if dimmable else set())
    if caps[f"fake-{oid}"] != want:
        mismatched.append((oid, want, caps[f"fake-{oid}"]))
check(not mismatched, f"each body reports the hardware it was given ({mismatched})")
check(len({frozenset(c) for c in caps.values()}) == 4,
      "four distinct hardware profiles, not eight copies of one")

print("every verb names exactly one body")
names = [t["name"] for t in reg.tools()]
check(len(names) == len(set(names)), f"no duplicate tool names across {len(names)} verbs")
check(names == sorted(names), "the list is sorted, so a prompt cache survives")
owners = {split_tool_name(n)[0] for n in names}
check(owners == {b.id for b in reg.bodies}, "every body contributes, none is shadowed")

print("a call reaches the body it names, and no other")
r = reg.call(mcp_tool_name("fake-0002", "servo_angle"), {"angle": 45})
check(r.get("isError") is not True, f"the body with a servo moves it: {r['content'][0]['text']}")
# fake-0005 has neither servo nor dimming; it should not offer either verb.
offered = {t["name"] for t in reg.tools()}
check(mcp_tool_name("fake-0005", "set_brightness") not in offered,
      "a body that cannot dim never offers set_brightness")
r = reg.call(mcp_tool_name("fake-0005", "set_brightness"), {"level": 50})
check(r.get("isError") is True, "and calling it anyway is refused, not routed")

print("identity is the body id, and two bodies may not share one")
try:
    spawn(reg, "0004")
    check(False, "a duplicate id was accepted")
except DuplicateBodyId as exc:
    check("already registered" in str(exc), f"refused: {str(exc)[:60]}...")
check(len(reg.bodies) == 8, "the incumbent survived the collision")
r = reg.call(mcp_tool_name("fake-0004", "blink"), {"times": 1})
check(r.get("isError") is not True, "and still answers after refusing its twin")

reg.close()
print("\n" + ("FAILURES" if fails else "all passed"))
sys.exit(1 if fails else 0)
