"""The body speaking first.

Experiments 001-004 are entirely brain-to-body: every message on the wire
answers something the host asked. This is the other direction -- a button
nobody asked about -- and until now the host discarded all of it. `_request`
skipped any message without an `id`; the MQTT transport subscribed to the
event topic and dropped what arrived.

    uv run python3 tests/test_events.py
"""
from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "host"))
from obp import BodyClient, Registry, SubprocessTransport  # noqa: E402
from obp.events import EventLog  # noqa: E402
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
    return reg.add(c), c


reg = Registry()
info, client = spawn(reg, "0001")

print("a body can say something nobody asked for")
r = reg.call(mcp_tool_name("fake-0001", "press_button"), {"hold_ms": 250},
             autonomous=False)
check(r.get("isError") is not True, "the press is triggered")
events, cursor = reg.events.since(0)
check(len(events) == 1, f"and one event reached the host ({len(events)})")
e = events[0]
check(e.type == "button" and e.payload.get("hold_ms") == 250,
      f"carrying what happened: {e.describe()}")
check(e.body_id == "fake-0001", "attributed to the body that sent it")

print("an event that arrives mid-call does not disturb the call")
r = reg.call(mcp_tool_name("fake-0001", "press_button"), {"hold_ms": 40},
             autonomous=False)
check(r.get("isError") is not True and "40ms" in r["content"][0]["text"],
      "the reply is still matched correctly past the interleaved notification")
check(len(reg.events.since(0)[0]) == 2, "and the event was kept, not skipped")

print("an agent may not manufacture its own input")
offered = {t["name"] for t in reg.tools()}
check(mcp_tool_name("fake-0001", "press_button") not in offered,
      "press_button is userOnly, so it is not offered to an autonomous caller")
r = reg.call(mcp_tool_name("fake-0001", "press_button"), {}, autonomous=True)
check(r.get("isError") is True, "and an agent calling it anyway is refused")

print("events are deduplicated by id, as a reconnect will redeliver them")
log = EventLog()
p = {"id": "01J8XRQ2F7", "ts": "2026-08-24T09:14:02Z", "type": "button",
     "name": "gpio14", "payload": {"hold_ms": 120}}
check(log.record("b", p) is not None, "the first copy is kept")
check(log.record("b", p) is None, "the second is dropped")
check(log.dropped_duplicates == 1, "and the drop is counted, not hidden")
check(len(log) == 1, "so one press is one event")

print("a body that admits its clock is wrong is not believed")
log = EventLog()
e = log.record("pico", {"id": "a", "ts": "1970-01-01T00:00:05.000Z",
                        "clock_confident": False, "type": "button"})
check("(arrival)" in e.when(),
      f"an unconfident timestamp falls back to arrival time: {e.when()}")
check("1970" not in e.when(), "and the body's uptime clock is not shown as truth")
e2 = log.record("hub", {"id": "b", "ts": "2026-08-24T09:14:02Z",
                        "clock_confident": True, "type": "button"})
check(e2.when() == "2026-08-24T09:14:02Z", "a confident body is believed")

print("two callers reading the log do not steal each other's events")
log = EventLog()
for i in range(3):
    log.record("b", {"id": f"e{i}", "type": "button", "payload": {"n": i}})
a_events, a_cursor = log.since(0)
b_events, _ = log.since(0)
check(len(a_events) == len(b_events) == 3, "both see all three")
log.record("b", {"id": "e3", "type": "button", "payload": {"n": 3}})
new, _ = log.since(a_cursor)
check(len(new) == 1 and new[0].payload["n"] == 3,
      "and a cursor returns only what is new")

print("waiting for a press is expressible, which is how MCP can ask at all")
log = EventLog()
got: list = []


def waiter():
    evs, _ = log.wait(timeout=5.0, cursor=0)
    got.extend(evs)


t = threading.Thread(target=waiter)
t.start()
time.sleep(0.3)
log.record("b", {"id": "later", "type": "button", "payload": {"hold_ms": 90}})
t.join(timeout=6)
check(len(got) == 1, "a blocked waiter is woken by the press it was waiting for")

start = time.monotonic()
log.wait(timeout=0.5, cursor=99)
check(time.monotonic() - start < 2.0, "and a wait with nothing coming times out")

reg.close()
print("\n" + ("FAILURES" if fails else "all passed"))
sys.exit(1 if fails else 0)
