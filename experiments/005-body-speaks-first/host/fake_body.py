#!/usr/bin/env python3
"""A body with no hardware, speaking the body contract over stdin/stdout.

It exists so the host half can be run and tested by anyone, and so the claim
"the contract does not care about the transport" is demonstrable rather than
asserted: this file and firmware/main.py answer identically, over a pipe and
over a USB cable respectively.

Set OBP_SERVO=0 to watch capability gating work -- servo_angle simply
stops being advertised, and the host never learns such a verb exists.
"""

from __future__ import annotations

import json
import os
import sys

FW = "fake-0.1.0"
BODY_ID = "fake-" + os.environ.get("OBP_ID", "0001")
HAS_SERVO = os.environ.get("OBP_SERVO", "0") != "0"
# Mirrors the real hardware split: a plain Pico can dim its LED, a Pico W cannot.
DIMMABLE = os.environ.get("OBP_DIMMABLE", "1") != "0"

state = {"led": False, "level": 0, "angle": 90}


def tools() -> list[dict]:
    specs = [
        {
            "name": "set_led",
            "description": "Turn the body's indicator light on or off.",
            "inputSchema": {
                "type": "object",
                "properties": {"on": {"type": "boolean", "description": "True for on."}},
                "required": ["on"],
            },
        },
        {
            # A test fixture: it makes this body do what a real one does when
            # somebody presses its button, so the return path is testable with
            # nobody's finger involved. userOnly because an agent manufacturing
            # its own input would be a strange thing to permit -- and a neat
            # demonstration of what the flag is actually for.
            "name": "press_button",
            "description": "Report a button press, as if someone had pressed it.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "hold_ms": {"type": "integer", "minimum": 1, "maximum": 5000,
                                "default": 120},
                    "name": {"type": "string", "description": "Which button."},
                },
            },
            "userOnly": True,
        },
        {
            "name": "blink",
            "description": "Blink the indicator light. Use to acknowledge something without speaking.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "times": {"type": "integer", "minimum": 1, "maximum": 10, "default": 3},
                    "interval_ms": {"type": "integer", "minimum": 50, "maximum": 2000, "default": 200},
                },
            },
        },
        {
            "name": "move",
            "description": "Move the body in a direction. Distances are approximate; the body decides how.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "direction": {"type": "string", "enum": ["forward", "back", "left", "right"]},
                    "distance_cm": {"type": "number", "minimum": 1, "maximum": 50, "default": 10},
                },
                "required": ["direction"],
            },
        },
    ]
    if DIMMABLE:
        specs.append(
            {
                "name": "set_brightness",
                "description": "Set how brightly the indicator light glows, as a percentage. "
                               "Use for mood: dim when calm, bright when alert.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "level": {"type": "integer", "minimum": 0, "maximum": 100,
                                  "description": "0 is off, 100 is full."},
                    },
                    "required": ["level"],
                },
            }
        )
    if HAS_SERVO:
        specs.append(
            {
                "name": "servo_angle",
                "description": "Point the servo at an absolute angle in degrees.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"angle": {"type": "integer", "minimum": 0, "maximum": 180}},
                    "required": ["angle"],
                },
            }
        )
    specs.append(
        {
            "name": "reboot",
            "description": "Restart the body. Disconnects it briefly.",
            "inputSchema": {"type": "object", "properties": {}},
            "userOnly": True,
        }
    )
    return specs


def emit(msg: dict) -> None:
    """Say something nobody asked for."""
    print(json.dumps(msg), flush=True)


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def ok(text: str) -> dict:
    return {"content": [{"type": "text", "text": text}], "isError": False}


def err(text: str) -> dict:
    return {"content": [{"type": "text", "text": text}], "isError": True}


def call(name: str, args: dict) -> dict:
    if name == "set_led":
        if "on" not in args:
            return err("set_led requires 'on'")
        state["led"] = bool(args["on"])
        return ok("light on" if state["led"] else "light off")
    if name == "set_brightness":
        if not DIMMABLE:
            return err("this body's light cannot be dimmed")
        level = int(args.get("level", -1))
        if not 0 <= level <= 100:
            return err("level must be 0..100")
        state["level"] = level
        return ok(f"brightness {level}%")
    if name == "blink":
        times = int(args.get("times", 3))
        if not 1 <= times <= 10:
            return err("times must be between 1 and 10")
        return ok(f"blinked {times} times")
    if name == "move":
        direction = args.get("direction")
        if direction not in {"forward", "back", "left", "right"}:
            return err(f"unknown direction {direction!r}")
        dist = float(args.get("distance_cm", 10))
        return ok(f"moved {direction} {dist:g}cm (simulated: this body has no wheels)")
    if name == "press_button":
        # A test fixture: it makes this body do what a real one does when
        # somebody presses its button. Marked userOnly because an agent
        # inventing its own input would be a strange thing to allow -- and a
        # good demonstration of what userOnly is for.
        import uuid
        hold = int(args.get("hold_ms", 120))
        emit({"jsonrpc": "2.0", "method": "notifications/body/event",
              "params": {"id": str(uuid.uuid4()), "ts": _now(),
                         "clock_confident": True, "type": "button",
                         "name": args.get("name", "gpio14"),
                         "payload": {"hold_ms": hold}}})
        return ok(f"button reported after {hold}ms")

    if name == "servo_angle":
        if not HAS_SERVO:
            return err("this body has no servo")
        angle = int(args.get("angle", 90))
        if not 0 <= angle <= 180:
            return err("angle must be 0..180")
        state["angle"] = angle
        return ok(f"servo at {angle} degrees")
    if name == "reboot":
        return ok("pretending to reboot")
    return err(f"no such tool: {name}")


def main() -> None:
    # Presence, announced rather than polled. Over a pipe or a serial link the
    # equivalent of MQTT's retained message is simply "the process is alive".
    print(json.dumps({
        "jsonrpc": "2.0",
        "method": "notifications/body/online",
        "params": {"id": BODY_ID, "fw": FW},
    }), flush=True)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        req_id, method = msg.get("id"), msg.get("method")
        params = msg.get("params") or {}

        if method == "body/describe":
            result = {
                "body": {
                    "id": BODY_ID,
                    "name": "Fake body (no hardware)",
                    "fw": FW,
                    "caps": ["led"] + (["dimmable"] if DIMMABLE else []) + (["servo"] if HAS_SERVO else []),
                },
                "tools": tools(),
            }
        elif method == "tools/call":
            result = call(params.get("name", ""), params.get("arguments") or {})
        elif method == "ping":
            result = {}
        else:
            print(json.dumps({
                "jsonrpc": "2.0", "id": req_id,
                "error": {"code": -32601, "message": f"method not found: {method}"},
            }), flush=True)
            continue

        print(json.dumps({"jsonrpc": "2.0", "id": req_id, "result": result}), flush=True)


if __name__ == "__main__":
    main()
