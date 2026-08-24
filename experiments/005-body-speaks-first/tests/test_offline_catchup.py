"""A body speaks while the brain is not there.

This is the autonomous-body case: a robot with its own long-lived agent, no
human typing, and an event that happens during a restart, a redeploy, or a
crash. If the press is lost, the robot's whole reason for speaking is lost
with it.

Nothing new was invented for this. MQTT has had persistent sessions since
before any of this existed: `Clean Start = 0` plus a `Session Expiry
Interval`, and the broker holds the subscription and queues QoS 1 messages
for a client that is not connected. OBP's MQTT binding was one CONNECT flag
away from it.

Three things have to be right together, and getting any one wrong makes the
mechanism silently do nothing:

  * **A stable client id.** The session is keyed on it, so a randomised id
    per start looks like a brand-new client every time. This is the usual
    reason people conclude persistent sessions do not work.
  * **QoS 1 at both ends.** QoS 0 has no acknowledgement, so there is nothing
    to queue; brokers drop it for offline clients by default.
  * **A subscription made before leaving.** The broker queues against a
    subscription, not against a topic.

Needs the broker: (cd ../003-mqtt-binding && docker compose up -d)

    uv run --with paho-mqtt python3 tests/test_offline_catchup.py
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "host"))
from obp import MqttConnection  # noqa: E402

BROKER_DIR = Path(__file__).parent.parent.parent / "003-mqtt-binding"
fails = 0


def check(cond, msg):
    global fails
    print(("  ok:   " if cond else "  FAIL: ") + msg)
    if not cond:
        fails += 1


def publish(topic: str, payload: str, qos: str = "1") -> None:
    subprocess.run(["docker", "compose", "exec", "-T", "broker",
                    "mosquitto_pub", "-q", qos, "-t", topic, "-m", payload],
                   cwd=BROKER_DIR, check=True, capture_output=True)


def event(eid: str, hold: int) -> str:
    return json.dumps({"jsonrpc": "2.0", "method": "notifications/body/event",
                       "params": {"id": eid, "ts": "2026-08-24T10:00:00Z",
                                  "type": "button", "name": "gpio14",
                                  "payload": {"hold_ms": hold}}})


CID = "obp-test-catchup"
BODY = "test-ghost"
got: list = []


def wipe(client_id: str) -> None:
    """Discard any session the broker is holding for this id.

    A persistent session outlives the process that made it -- that is the
    entire point -- so it also outlives a test run. The first version of this
    file left a subscribed session behind, which then collected the event the
    *next* section publishes and delivered it on the following run, failing a
    test whose code had not changed. Connecting once with Clean Start and no
    expiry is how you throw a session away.
    """
    c = MqttConnection(client_id=client_id, session_expiry=0)
    c.connect()
    time.sleep(0.3)
    c.close()


wipe(CID)
wipe("obp-test-clean")

print("a host with a persistent session leaves")
c = MqttConnection(client_id=CID)
c.on_event = lambda bid, p: got.append((bid, p))
c.connect()
time.sleep(0.5)
c.subscribe_body(BODY)
time.sleep(0.3)
c.close()

print("the body reports two presses while nobody is connected")
publish(f"obp/body/{BODY}/event", event("01CATCH_A", 300))
publish(f"obp/body/{BODY}/event", event("01CATCH_B", 80))

print("the host comes back with the same client id")
c2 = MqttConnection(client_id=CID)
c2.on_event = lambda bid, p: got.append((bid, p))
c2.connect()
time.sleep(2.0)

check(c2.session_resumed, "the broker resumed the session it was holding")
check(len(got) == 2, f"both presses were delivered on reconnect ({len(got)})")
holds = sorted(p["payload"]["hold_ms"] for _, p in got)
check(holds == [80, 300], f"with their payloads intact: {holds}")
c2.close()
# Stop this session collecting what the next section publishes.
wipe(CID)

print("a host that asks for no session gets no backlog")
fresh_id = "obp-test-clean"
c3 = MqttConnection(client_id=fresh_id, session_expiry=0)
c3.connect()
time.sleep(0.5)
c3.subscribe_body(BODY)
time.sleep(0.3)
c3.close()
publish(f"obp/body/{BODY}/event", event("01CATCH_C", 500))
missed: list = []
c4 = MqttConnection(client_id=fresh_id, session_expiry=0)
c4.on_event = lambda bid, p: missed.append(p)
c4.connect()
time.sleep(1.5)
check(not c4.session_resumed, "no session was kept, as asked")
check(len(missed) == 0,
      "and the press that happened while it was away is gone — which is the "
      "behaviour every OBP host had until now")
c4.close()
wipe(CID)
wipe("obp-test-clean")

print("\n" + ("FAILURES" if fails else "all passed"))
sys.exit(1 if fails else 0)
