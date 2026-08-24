"""The MQTT binding, against a real broker.

Needs `docker compose up -d` in this directory. Proves the same contract
runs over MQTT unchanged, and that presence works the way the specification
claims: a retained message, cleared by a Last Will.

    uv run --with paho-mqtt python3 tests/test_mqtt_binding.py
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "host"))
from obp import BodyClient, MqttConnection, MqttTransport, Registry  # noqa: E402
from obp.naming import mcp_tool_name  # noqa: E402

BODY = Path(__file__).parent.parent / "host" / "mqtt_fake_body.py"
fails = 0


def check(cond, msg):
    global fails
    print(("  ok:   " if cond else "  FAIL: ") + msg)
    if not cond:
        fails += 1


def start_body(body_id: str) -> subprocess.Popen:
    p = subprocess.Popen([sys.executable, str(BODY), "--id", body_id],
                         stderr=subprocess.DEVNULL)
    time.sleep(1.2)
    return p


def wait_for(fn, timeout=5.0, interval=0.1):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if fn():
            return True
        time.sleep(interval)
    return False


conn = MqttConnection()
conn.connect()

print("presence is announced, not polled")
b1 = start_body("fake-mqtt-1")
check(wait_for(lambda: "fake-mqtt-1" in conn.bodies()),
      "a body that connects appears in the retained set")

print("the contract is unchanged over this binding")
reg = Registry()
client = BodyClient(MqttTransport(conn, "fake-mqtt-1"))
client.transport.open()
info = reg.add(client)
check(info.id == "fake-mqtt-1", f"describe answered: {info.name}")
check([t.name for t in info.tools] == ["set_led", "blink", "reboot"],
      "same verbs, same shapes as the USB bodies")
check(any(t.user_only for t in info.tools), "userOnly survives the binding")

r = reg.call(mcp_tool_name("fake-mqtt-1", "set_led"), {"on": True})
check(r["isError"] is False and "on" in r["content"][0]["text"], "a call round-trips")
r = reg.call(mcp_tool_name("fake-mqtt-1", "blink"), {"times": 99})
check(r["isError"] is True, "a rejection is still a result, not a fault")

print("two bodies on one broker")
b2 = start_body("fake-mqtt-2")
check(wait_for(lambda: "fake-mqtt-2" in conn.bodies()), "the second body appears")
c2 = BodyClient(MqttTransport(conn, "fake-mqtt-2"))
c2.transport.open()
reg.add(c2)
names = [t["name"] for t in reg.tools()]
check(len([n for n in names if n.startswith("fake-mqtt-1__")]) == 2, "body 1 contributes its verbs")
check(len([n for n in names if n.startswith("fake-mqtt-2__")]) == 2, "body 2 contributes its own")
check(names == sorted(names), "and the combined list is still sorted")

print("a reply must carry the request's id verbatim (B8a)")
# The Pico W firmware read this id as a long, so every string id came back as
# 0 and the reply was unmatchable -- the body answered correctly and looked
# silent. Nothing in the suite caught it, because the fake body echoes ids for
# free and every example in the spec used a number.
import json  # noqa: E402
import queue  # noqa: E402

for probe_id in ("probe-string-1", 7, "01J8XRQ2F7ZK"):
    q = conn._replies.setdefault("fake-mqtt-2", queue.Queue())
    while not q.empty():
        q.get_nowait()
    conn.client.publish("obp/body/fake-mqtt-2/rpc",
                        json.dumps({"jsonrpc": "2.0", "id": probe_id,
                                    "method": "ping"}), qos=1)
    try:
        reply = q.get(timeout=5)
    except queue.Empty:
        check(False, f"no reply to id {probe_id!r}")
        continue
    check(reply.get("id") == probe_id,
          f"id {probe_id!r} echoed as {reply.get('id')!r}, same type "
          f"({type(reply.get('id')).__name__})")

print("a Last Will clears the retained presence")
b1.kill()                                   # no goodbye: the broker must notice
check(wait_for(lambda: "fake-mqtt-1" not in conn.bodies(), timeout=20),
      "the killed body left the retained set")
check("fake-mqtt-2" in conn.bodies(), "and the survivor is untouched")

r = reg.call(mcp_tool_name("fake-mqtt-1", "set_led"), {"on": False})
check(r["isError"] is True, "calling the departed body returns a result, not a fault")

print("a fresh host is told the truth by the broker")
conn2 = MqttConnection(client_id="obp-host-2")
conn2.connect()
time.sleep(0.5)
check("fake-mqtt-2" in conn2.bodies(), "retained presence replays to a host that just started")
check("fake-mqtt-1" not in conn2.bodies(), "and the departed body is not replayed")
conn2.close()

b2.terminate(); b2.wait(timeout=5)
conn.close()
print("\n" + ("FAILURES" if fails else "all passed"))
sys.exit(1 if fails else 0)
