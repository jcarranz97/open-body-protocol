#!/usr/bin/env python3
"""A body with no hardware, speaking OBP over MQTT.

Same contract as the USB bodies in experiments 001 and 002, same verbs,
different binding — which is the claim under test. It also demonstrates the
presence mechanism honestly: a retained message on connect, and a Last Will
with an empty payload so that dying clears it.

    uv run --with paho-mqtt python3 host/mqtt_fake_body.py --id fake-mqtt-1
"""
from __future__ import annotations

import argparse
import json
import signal
import sys
import time

import paho.mqtt.client as mqtt

FW = "fake-mqtt-0.1.0"
ROOT = "obp/body"


def tools() -> list[dict]:
    return [
        {"name": "set_led",
         "description": "Turn the body's indicator light on or off.",
         "inputSchema": {"type": "object",
                         "properties": {"on": {"type": "boolean",
                                               "description": "True for on."}},
                         "required": ["on"]}},
        {"name": "blink",
         "description": "Blink the indicator light. Use to acknowledge "
                        "something without speaking.",
         "inputSchema": {"type": "object",
                         "properties": {
                             "times": {"type": "integer", "minimum": 1,
                                       "maximum": 10, "default": 3},
                             "interval_ms": {"type": "integer", "minimum": 50,
                                             "maximum": 2000, "default": 200}}}},
        {"name": "reboot",
         "description": "Restart the body. Disconnects it briefly.",
         "inputSchema": {"type": "object", "properties": {}},
         "userOnly": True},
    ]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--id", default="fake-mqtt-1")
    p.add_argument("--broker", default="127.0.0.1")
    p.add_argument("--port", type=int, default=1883)
    p.add_argument("--name", default=None)
    args = p.parse_args()

    body_id = args.id
    name = args.name or f"Fake MQTT body ({body_id})"
    state = {"led": False}

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"body-{body_id}")

    # The whole presence mechanism, in two lines: a retained announcement,
    # and a will that clears it by publishing nothing to the same topic.
    presence = f"{ROOT}/{body_id}/presence"
    client.will_set(presence, payload=b"", qos=1, retain=True)

    def ok(text):
        return {"content": [{"type": "text", "text": text}], "isError": False}

    def err(text):
        return {"content": [{"type": "text", "text": text}], "isError": True}

    def call(tool, a):
        if tool == "set_led":
            if "on" not in a:
                return err("set_led requires 'on'")
            state["led"] = bool(a["on"])
            return ok("light on" if state["led"] else "light off")
        if tool == "blink":
            times = int(a.get("times", 3))
            if not 1 <= times <= 10:
                return err("times must be between 1 and 10")
            return ok(f"blinked {times} times")
        if tool == "reboot":
            return ok("pretending to reboot")
        return err(f"no such tool: {tool}")

    def on_connect(c, u, flags, rc, props=None):  # noqa: ANN001
        c.subscribe(f"{ROOT}/{body_id}/rpc", qos=1)
        c.publish(presence, json.dumps({"id": body_id, "fw": FW, "name": name}),
                  qos=1, retain=True)
        print(f"{body_id}: online", file=sys.stderr)

    def on_message(c, u, msg):  # noqa: ANN001
        try:
            req = json.loads(msg.payload)
        except ValueError:
            return
        method, req_id = req.get("method"), req.get("id")
        params = req.get("params") or {}

        if method == "body/describe":
            result = {"v": 0,
                      "body": {"id": body_id, "name": name, "fw": FW,
                               "caps": ["led"]},
                      "tools": tools()}
        elif method == "tools/call":
            result = call(params.get("name", ""), params.get("arguments") or {})
        elif method == "ping":
            result = {}
        else:
            c.publish(f"{ROOT}/{body_id}/rpc/reply",
                      json.dumps({"jsonrpc": "2.0", "id": req_id,
                                  "error": {"code": -32601,
                                            "message": f"method not found: {method}"}}),
                      qos=1)
            return
        c.publish(f"{ROOT}/{body_id}/rpc/reply",
                  json.dumps({"jsonrpc": "2.0", "id": req_id, "result": result}), qos=1)

    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(args.broker, args.port, keepalive=15)

    def goodbye(*_):
        # A clean departure publishes the same empty payload the will would.
        client.publish(presence, payload=b"", qos=1, retain=True)
        time.sleep(0.2)
        client.loop_stop()
        sys.exit(0)

    signal.signal(signal.SIGTERM, goodbye)
    signal.signal(signal.SIGINT, goodbye)
    client.loop_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
