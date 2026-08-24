#!/usr/bin/env python3
"""A house's lights as ONE body, with rooms as arguments.

This is the shape the aggregate case takes in OBP. Fifty-two bulbs are not
fifty-two bodies -- a single bulb is too small to be worth its own identity,
connection and presence lifecycle. They are one body whose verbs take a room,
and the fan-out happens in here, where B13 already says execution belongs.

Nothing in the protocol had to change for this. `room` is a string with an
enum, which is inside the restricted schema subset a microcontroller can
build with a table. The host never learns there are 52 bulbs.

Two things the research says a body like this should do, neither of them
protocol rules -- they are just how not to lie to whoever is asking:

  * Report both halves. Home Assistant's light group computes availability as
    `any(member available)`, so it reads healthy with five of fifty-two dead.
    Say "47 on, 5 unreachable", never just "on".
  * Stay idempotent. Verbs that fan out take an absolute state, so a retry
    after a partial failure is safe. There is deliberately no `toggle_room`:
    a toggle that reached 47 of 52 bulbs leaves the house in a state no
    second command can repair.
"""
from __future__ import annotations

import json
import sys

ROOMS = {
    "room1":   ["bed_1", "bed_2", "desk"],
    "kitchen": ["ceiling", "counter_1", "counter_2"],
    "hall":    ["hall_1", "hall_2"],
}
# Two bulbs that will not answer, so the honest-reporting path is exercised
# rather than merely described.
UNREACHABLE = {"counter_2", "hall_2"}

STATE: dict[str, bool] = {b: False for bulbs in ROOMS.values() for b in bulbs}
FW = "obp-lights-0.1.0"

TOOLS = [
    {"name": "set_room_lights",
     "description": ("Turn every light in one room on or off. Use 'all' for the "
                     "whole house. Absolute, so repeating it is safe."),
     "inputSchema": {"type": "object", "properties": {
         "room": {"type": "string", "enum": [*ROOMS, "all"],
                  "description": "Which room, or 'all' for the house."},
         "on": {"type": "boolean", "description": "True for on."}},
         "required": ["room", "on"]}},
    {"name": "room_status",
     "description": "How many lights are on in a room, and which are unreachable.",
     "inputSchema": {"type": "object", "properties": {
         "room": {"type": "string", "enum": [*ROOMS, "all"]}},
         "required": ["room"]}},
]


def bulbs(room: str) -> list[str]:
    return [b for bs in ROOMS.values() for b in bs] if room == "all" else ROOMS[room]


def ok(text, is_error=False):
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


def handle(name, args):
    room = args.get("room")
    if room is not None and room != "all" and room not in ROOMS:
        # A room the caller *named* fails loudly. Home Assistant's split is
        # the one to copy: an explicitly named target that does not exist is
        # an error, while a target reached by expansion is skipped quietly.
        return ok(f"no such room {room!r}; known rooms: {', '.join(ROOMS)}", True)

    if name == "set_room_lights":
        if "on" not in args:
            return ok("set_room_lights requires 'on'", True)
        want, done, missed = bool(args["on"]), [], []
        for b in bulbs(room):
            (missed if b in UNREACHABLE else done).append(b)
            if b not in UNREACHABLE:
                STATE[b] = want
        word = "on" if want else "off"
        if not missed:
            return ok(f"{len(done)} lights {word} in {room}")
        # Both halves, always -- "5 unreachable" alone reads as total failure.
        return ok(f"{len(done)} lights {word} in {room}; "
                  f"{len(missed)} unreachable: {', '.join(missed)}")

    if name == "room_status":
        lit = [b for b in bulbs(room) if STATE[b]]
        missed = [b for b in bulbs(room) if b in UNREACHABLE]
        return ok(f"{len(lit)} of {len(bulbs(room))} on in {room}"
                  + (f"; unreachable: {', '.join(missed)}" if missed else ""))

    return ok(f"no such tool: {name}", True)


def main() -> int:
    print(json.dumps({"jsonrpc": "2.0", "method": "notifications/body/online",
                      "params": {"id": "house-lights", "fw": FW}}), flush=True)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        msg = json.loads(line)
        rid, method = msg.get("id"), msg.get("method")
        if method == "body/describe":
            result = {"v": 0,
                      "body": {"id": "house-lights", "name": "House lights",
                               "fw": FW, "caps": ["light"]},
                      "tools": TOOLS}
        elif method == "tools/call":
            p = msg.get("params") or {}
            result = handle(p.get("name", ""), p.get("arguments") or {})
        elif method == "ping":
            result = {}
        else:
            print(json.dumps({"jsonrpc": "2.0", "id": rid,
                              "error": {"code": -32601, "message": "method not found"}}),
                  flush=True)
            continue
        print(json.dumps({"jsonrpc": "2.0", "id": rid, "result": result}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
