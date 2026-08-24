"""OBP body contract on a Raspberry Pi Pico (MicroPython).

Copy this to the Pico as main.py. It speaks newline-delimited JSON-RPC 2.0
over the USB CDC serial link -- the same messages host/fake_body.py speaks
over a pipe, which is the point of the experiment.

Works on a bare Pico with nothing attached: the LED tools are real, `move`
refuses because there is no drivetrain, and `servo_angle` is only advertised
when SERVO_PIN is set -- so a body's tool list reflects the hardware it
actually has, with no configuration on the host side.
"""

import json
import select
import sys
import time

import os

from machine import PWM, Pin, unique_id

FW = "pico-0.1.0"

# Set to a GPIO number (e.g. 15) if a hobby servo is wired up. Leave as None
# on a bare Pico and the host will never see a servo verb.
SERVO_PIN = None

# On W boards the LED hangs off the wireless chip and can only be switched;
# on a plain Pico it is GPIO 25 and can be dimmed with PWM. Same firmware,
# different board, different tool list -- capability gating driven by real
# hardware rather than by a config flag.
_IS_W = " W" in os.uname().machine

if _IS_W:
    _led = Pin("LED", Pin.OUT)
    _led_pwm = None
else:
    _led = Pin(25, Pin.OUT)
    _led_pwm = PWM(_led)
    _led_pwm.freq(500)                  # no visible flicker

LED_DIMMABLE = _led_pwm is not None


def _led_level(pct):
    """The brain asks for a percentage; the body decides what that means.

    Perceived brightness is roughly the square of duty cycle, so a linear
    duty would make "50" look like 70-something. Squaring here is the
    smallest possible example of the rule that intent belongs to the brain
    and implementation belongs to the body.
    """
    pct = max(0, min(100, int(pct)))
    _led_pwm.duty_u16(pct * pct * 65535 // 10000)


def _led_set(on):
    if LED_DIMMABLE:
        _led_level(100 if on else 0)
    else:
        _led.value(1 if on else 0)

_servo = None
if SERVO_PIN is not None:
    _servo = PWM(Pin(SERVO_PIN))
    _servo.freq(50)


def body_id():
    return "pico-" + "".join("%02x" % b for b in unique_id()[-3:])


def _caps():
    caps = ["led"]
    if LED_DIMMABLE:
        caps.append("dimmable")
    if _servo is not None:
        caps.append("servo")
    return caps


def _tools():
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
    if LED_DIMMABLE:
        specs.append({
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
        })
    if _servo is not None:
        specs.append({
            "name": "servo_angle",
            "description": "Point the servo at an absolute angle in degrees.",
            "inputSchema": {
                "type": "object",
                "properties": {"angle": {"type": "integer", "minimum": 0, "maximum": 180}},
                "required": ["angle"],
            },
        })
    specs.append({
        "name": "reboot",
        "description": "Restart the body. Disconnects it briefly.",
        "inputSchema": {"type": "object", "properties": {}},
        "userOnly": True,
    })
    return specs


def _ok(text):
    return {"content": [{"type": "text", "text": text}], "isError": False}


def _err(text):
    return {"content": [{"type": "text", "text": text}], "isError": True}


def _set_servo(angle):
    # 0.5ms..2.5ms pulse inside a 20ms frame.
    pulse_ms = 0.5 + (angle / 180.0) * 2.0
    _servo.duty_u16(int(65535 * pulse_ms / 20.0))


def _call(name, args):
    if name == "set_led":
        if "on" not in args:
            return _err("set_led requires 'on'")
        _led_set(bool(args["on"]))
        return _ok("light on" if args["on"] else "light off")

    if name == "set_brightness":
        if not LED_DIMMABLE:
            return _err("this body's light cannot be dimmed")
        if "level" not in args:
            return _err("set_brightness requires 'level'")
        level = int(args["level"])
        if level < 0 or level > 100:
            return _err("level must be 0..100")
        _led_level(level)
        return _ok("brightness %d%%" % level)

    if name == "blink":
        times = int(args.get("times", 3))
        interval = int(args.get("interval_ms", 200))
        if times < 1 or times > 10:
            return _err("times must be between 1 and 10")
        for _ in range(times):
            _led_set(True)
            time.sleep_ms(interval)
            _led_set(False)
            time.sleep_ms(interval)
        return _ok("blinked %d times" % times)

    if name == "move":
        direction = args.get("direction")
        if direction not in ("forward", "back", "left", "right"):
            return _err("unknown direction: %s" % direction)
        dist = args.get("distance_cm", 10)
        # No wheels on a bare Pico -- so this MUST NOT report success (B4a).
        # It used to say "simulated: no drivetrain attached" and return
        # isError False, which is honest only to a human reading the text. A
        # host reads isError, so an agent asking this body to move was told it
        # moved. servo_angle below has always got this right; move did not.
        for _ in range(2):
            _led_set(True)
            time.sleep_ms(80)
            _led_set(False)
            time.sleep_ms(80)
        return _err("no drivetrain attached: cannot move %s %scm" % (direction, dist))

    if name == "servo_angle":
        if _servo is None:
            return _err("this body has no servo")
        angle = int(args.get("angle", 90))
        if angle < 0 or angle > 180:
            return _err("angle must be 0..180")
        _set_servo(angle)
        return _ok("servo at %d degrees" % angle)

    if name == "reboot":
        import machine
        _send({"jsonrpc": "2.0", "method": "notifications/body/offline",
               "params": {"id": body_id(), "reason": "reboot"}})
        time.sleep_ms(100)
        machine.reset()

    return _err("no such tool: %s" % name)


def _send(obj):
    print(json.dumps(obj))


def main():
    _send({"jsonrpc": "2.0", "method": "notifications/body/online",
           "params": {"id": body_id(), "fw": FW}})

    poller = select.poll()
    poller.register(sys.stdin, select.POLLIN)

    while True:
        if not poller.poll(200):
            continue
        line = sys.stdin.readline()
        if not line:
            continue
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            continue

        req_id = msg.get("id")
        method = msg.get("method")
        params = msg.get("params") or {}

        if method == "body/describe":
            result = {
                "body": {"id": body_id(), "name": "Raspberry Pi Pico body",
                         "fw": FW, "caps": _caps()},
                "tools": _tools(),
            }
        elif method == "tools/call":
            result = _call(params.get("name", ""), params.get("arguments") or {})
        elif method == "ping":
            result = {}
        else:
            _send({"jsonrpc": "2.0", "id": req_id,
                   "error": {"code": -32601, "message": "method not found: %s" % method}})
            continue

        _send({"jsonrpc": "2.0", "id": req_id, "result": result})


main()
