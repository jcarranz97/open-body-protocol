# Experiment 004 — one brain, many bodies

Experiment 003 put two bodies in one registry and proved the mechanics:
namespaced verbs, a sorted list, per-body capabilities. It attached a fixed
set, once, and never disturbed it.

A real desk does not hold still. A board is unplugged mid-sentence, a battery
dies, someone carries a second robot into the room, two boards get flashed with
the same identity. This experiment asks what one brain does when its body set
is **plural, changing, and occasionally wrong**.

Three questions 003 could not reach with two hardware-derived ids:

1. **Does every verb still reach exactly the body that named it**, when eight
   bodies with four different hardware profiles are present at once?
2. **Does the brain notice the set changing** while it is connected — a body
   arriving, one leaving, one coming back — or does it work from a list that
   quietly went stale?
3. **What happens when two bodies claim the same id?** The host cannot tell one
   body reached twice from two boards flashed alike: identical firmware
   produces identical descriptors.
4. **Can a person put one body in focus** -- "I am operating the arm" -- without
   the others becoming unreachable? And what should happen when the body in
   focus cannot do what was asked?

## Requirements

Part A needs nothing — no hardware, no broker, no `paho-mqtt`. Parts B and C
reuse whatever you already have from 001–003.

```bash
cd experiments/004-many-bodies
uv run python3 tests/test_many_bodies.py        # eight bodies, routing, identity
uv run python3 tests/test_churn.py              # bodies arriving and leaving
```

For Part B, start the broker from experiment 003 (there is only one, and it
binds 1883 — do not run a second):

```bash
cd ../003-mqtt-binding && docker compose up -d
```

## Part A — no hardware

`--fake N` spawns N local bodies as subprocesses, each with different
hardware, so a multi-body list is not one body copied N times:

```bash
uv run python3 host/obp_cli.py --fake 4 bodies
uv run python3 host/obp_cli.py --fake-id twin --fake-id twin --fake-id lone bodies
```

The second command asks two bodies to claim one id, on purpose.

## Part B — the real ones, alongside the fakes

```bash
sg dialout -c "uv run --with paho-mqtt --with pyserial python3 \
    host/obp_cli.py --mqtt --port auto --fake 2 bodies"
```

Three bindings in one list: a subprocess, a USB cable and a WiFi broker.

## Part C — an agent driving several bodies

Point Claude Code or OpenCode at `host/obp_mcp.py` as in experiment 002, with
more than one body attached, and ask it to do something involving a particular
one. What is being tested is not the transport — 002 settled that — but
whether an agent handed a dozen near-identical verbs picks the right body, and
whether it recovers when one of them leaves mid-task.

## Part D — selecting a body

```bash
uv run python3 tests/test_selection.py

# the CLI refuses to guess when several bodies offer a verb
uv run python3 host/obp_cli.py --fake-id arm --fake-id drone call blink times=2

# selection is per-shell, like adb's $ANDROID_SERIAL
OBP_BODY=fake-arm uv run python3 host/obp_cli.py \
    --fake-id arm --fake-id drone call blink times=2
```

`host/lights_body.py` is a house's lights as one body, for the case where the
thing you want to address is not the thing in focus:

```bash
uv run python3 host/obp_cli.py --fake-id arm call set_room_lights room=room1 on=true
```

Over MCP the same selection is `obp__use`, and `obp__status` reports it.

---

## Results

### Part A ✅ 2026-08-24

```text
$ obp_cli.py --fake 4 bodies
fake-0001            Fake body (no hardware)        4 verbs  via local  caps: led, dimmable
fake-0002            Fake body (no hardware)        5 verbs  via local  caps: led, dimmable, servo
fake-0003            Fake body (no hardware)        3 verbs  via local  caps: led
fake-0004            Fake body (no hardware)        5 verbs  via local  caps: led, dimmable, servo
```

`tests/test_many_bodies.py` — eight bodies, four hardware profiles, **all
passed**:

| Check | Result |
|---|---|
| Eight bodies registered, each reporting the hardware it was given | ✅ |
| 33 verbs, no duplicate names, list sorted (a prompt cache survives) | ✅ |
| Every body contributes verbs; none is shadowed | ✅ |
| A call reaches the body it names — the one with a servo moves it | ✅ |
| A body that cannot dim never offers `set_brightness`, and a call is refused | ✅ |
| A duplicate id is refused; the incumbent survives and still answers | ✅ |

`tests/test_churn.py` — the set changing under a connected brain, **all
passed**:

| Check | Result |
|---|---|
| A body arriving mid-session sends `notifications/tools/list_changed` | ✅ |
| The newcomer's verbs appear in the refreshed list | ✅ |
| A departure is announced too, and its verbs are withdrawn | ✅ |
| The bodies that stayed keep their verbs and keep answering | ✅ |
| Calling the departed body is a result, not a crash | ✅ |
| A body that comes back is usable without restarting the brain | ✅ |

### Part B ✅ 2026-08-24

Two real boards and two fakes, three bindings, one brain. The Pico W was on a
5 V charger — its only route to this computer is WiFi.

```text
4 bodies, 14 verbs, one brain
  picow-7c6e37     via mqtt
  pico-3f5022      via usb
  fake-0001        via local
  fake-0002        via local

one instruction, every body that can obey it:
  picow-7c6e37     blinked 2 times      <- over WiFi
  pico-3f5022      blinked 2 times      <- over USB
  fake-0001        blinked 2 times      <- a subprocess
  fake-0002        blinked 2 times
```

Both boards blinked. Nothing in the host distinguishes the three bindings past
the transport object.

### Part C ⏳

```text

```

### Part D — selecting a body ✅ 2026-08-24

Three bodies: the Pico on USB standing in for an arm, the Pico W over WiFi for
a drone, and a `house-lights` hub. The arm is selected; the lights still work.

```text
3 bodies, 8 verbs offered to the agent
  picow-7c6e37     via mqtt   ['set_led', 'blink', 'reboot']
  pico-3f5022      via usb    ['set_led', 'blink', 'set_brightness']
  house-lights     via local  ['set_room_lights', 'room_status']

--- selecting the arm: pico-3f5022 ---
   selected: Raspberry Pi Pico body (pico-sdk) [pico-3f5022]

unqualified "blink" goes to the arm:
   -> pico-3f5022   (used the selected body 'pico-3f5022')
    blinked 2 times

"turn on the lights in room1" -- with the arm still selected:
    3 lights on in room1
    6 lights on in all; 2 unreachable: counter_2, hall_2
```

From the CLI, where selection is an environment variable:

```text
$ obp_cli.py --fake-id arm --fake-id drone call blink times=2
no body is selected and 2 bodies offer 'blink': fake-arm, fake-drone. Select one, or name it.

$ OBP_BODY=fake-arm obp_cli.py ... call blink times=2
(used the selected body 'fake-arm')
blinked 2 times

$ OBP_BODY=fake-arm obp_cli.py ... call servo_angle angle=45
the selected body 'fake-arm' does not offer 'servo_angle'. fake-drone does.
Name it explicitly, or select it.
```

`tests/test_selection.py` — **all passed**:

| Check | Result |
|---|---|
| Selecting a body leaves the tool list byte-identical | ✅ |
| No `list_changed` is emitted, so no prompt cache is discarded | ✅ |
| Unselected bodies stay callable — the lights work with the arm selected | ✅ |
| An unqualified verb goes to the selection, and the host says so | ✅ |
| A verb the selection lacks is refused, naming the bodies that have it | ✅ |
| A failed selection **clears**, rather than leaving a stale one | ✅ |
| A selected body that departs is kept but reported as absent | ✅ |

## The design, and why it is shaped like this

**Selection is host-side state and nothing else.** It does not filter the tool
list, does not rename a verb, and is never sent to a body. Three independent
reasons, any one of which is decisive:

- **MCP forbids the alternative.** The 2026-07-28 revision (SEP-2567) requires
  that `tools/list` not depend on per-connection or prior-tool-call state,
  precisely so clients can cache it. A list that changed with the selection
  would not be conformant.
- **It would be the most expensive thing we could do.** Tool definitions sit at
  the front of a model's cache prefix, and changes at one level invalidate that
  level and every later one — so swapping the tool set discards the tools
  block, the system prompt *and* the whole conversation. Selecting five times
  costs more than showing every body's verbs all session.
- **It would break the case that motivated the feature.** With the arm
  selected, "turn on the lights in room1" has to work. It only can if the
  lights body's verbs were never taken away.

Anthropic's own guidance says the same in one line: *if you need modes, do not
swap the tool set — give the model a tool that records the mode transition.*
That tool is `obp__use`, and its result is ordinary conversation the model
reads.

**A failed selection clears; it does not leave the previous one standing.**
IMAP settled this decades ago — *"if a mailbox is selected and a SELECT command
that fails is attempted, no mailbox is selected."* POSIX `chdir` does the
opposite, and a failed `cd` leaving a live stale selection is ShellCheck SC2164
and the Steam `rm -rf "$STEAMROOT/"*` incident. For a body the difference is
physical: ask for the drone, miss, keep the arm selected, and the next
unqualified `move` drives the arm.

**Selection is refused, never silently retargeted.** `move` on a drone and
`move` on an arm are the same word and very different outcomes. The refusal
names the bodies that *can* do it, because "no" is far more useful with "but
these can" attached — one round trip instead of one wrong motion.

**The implicit path narrates itself, the explicit one does not.** `kubectl` has
this backwards: its cluster-scope warning fires only when you typed
`--namespace`, so the ambient case, the one that needs telling, is the silent
one. Here, a body chosen *by selection* says so; a body named outright does not
need a commentary.

**The CLI keeps selection in `$OBP_BODY`, not a state file.** This is `adb`'s
model — `$ANDROID_SERIAL` plus `-s`, and a flat refusal to guess when several
devices match. A state file would be `kubectl`'s `current-context`: one global
mutable pointer shared by every terminal, so the same command means different
things in two windows.

## The lights, and why they are one body

`host/lights_body.py` is a house's lighting as **one** body with rooms as verb
arguments:

```json
{"name": "set_room_lights",
 "inputSchema": {"type": "object", "properties": {
   "room": {"type": "string", "enum": ["room1", "kitchen", "hall", "all"]},
   "on": {"type": "boolean"}}, "required": ["room", "on"]}}
```

**No protocol change was needed.** `enum` on a string is already inside the
[restricted subset](../../docs/spec/descriptors.md) a microcontroller can build
with a table, and the fan-out happens inside the body, where `B13` already puts
execution. The host never learns there are fifty-two bulbs.

The alternative — bulbs as bodies, or a `units` array in the descriptor — would
have rebuilt the Zigbee-cluster / Matter-endpoint model that
[`rationale.md`](../../docs/rationale.md) explicitly rejects, and would have run
straight into `B14`. Every protocol that does fan out at the transport layer
(Matter, Zigbee, Bluetooth Mesh, MAVLink) makes fan-out and feedback *mutually
exclusive* by hard requirement: a groupcast gets no acknowledgement, because
fifty-two replies would flood the network. Keeping the fan-out inside one body
means one call and one honest answer.

Two things that body does are worth copying, and neither is a protocol rule:

- **It reports both halves** — `6 lights on in all; 2 unreachable: counter_2,
  hall_2`. Home Assistant's light group computes availability as `any(member
  available)`, so it reads healthy with five of fifty-two members dead. And a
  message naming only the failures reads as total failure.
- **It has no `toggle_room`.** Anything that fans out takes an absolute state,
  so a retry after a partial failure is safe. A toggle that reached 47 of 52
  bulbs leaves a house no second command can repair.

The boundary this suggests is not "is it a robot" — a terminal is a body too.
It is **granularity**: a body is one thing with a single presence and one
coherent set of verbs. A bulb fails that not for being unrobotic but for being
too small to be worth its own identity, connection and presence lifecycle.


---

## What came out of building it

**Two bodies may not share an id, and the host now says so.** The registry did
`self._bodies[info.id] = entry`, so a second body with the same id silently
displaced a working one and its connection was never closed. Two hardware ids
never collide, which is why 003 could not find this.

The incumbent now wins and the newcomer is refused with a diagnostic naming
both transports. That choice is worth stating plainly, because the opposite is
defensible: a host cannot distinguish one body reached twice from two boards
flashed alike, since identical firmware yields identical descriptors. Both
readings argue for refusing, though. If it is one body, a second route adds
nothing. If it is two boards, merging them means every command reaches an
arbitrary one of the pair — which, for anything with motors, is the worst
outcome available.

**This is a host behaviour, not a rule for bodies.** `B2` already asks for an
id stable across restarts and derived from hardware. Whether the specification
should say anything about *collisions* — and whether the right answer is
"refuse", "prefer the older", or "let the host disambiguate by transport" — is
an [open question](../../docs/open-questions.md), not something this experiment
decided.

**A binding nobody asked for should not stop the host starting.** `obp/__init__`
imported the MQTT module eagerly, so Part A — whose whole point is no hardware
and no broker — died on a missing `paho-mqtt`. The import is now lazy.

**The body list was labelled by guesswork.** It printed `via mqtt` if the
broker happened to know the id and `via usb` otherwise, which labelled every
subprocess `usb`. Transports now say what they are.

**A test that duplicates the rule it is checking will get it wrong.** The first
`test_many_bodies.py` recomputed each body's expected capabilities in the
assertions, fumbled the arithmetic, and failed against bodies behaving
perfectly. It now declares a plan and derives both the spawning and the
expectations from it.

## What this does not test

- **Two bodies acting together on one task** — a leg here and a leg there. The
  registry routes; it does not coordinate, and nothing here needs it to.
- **Whether a model actually honours the selection.** Part D proves the host
  offers, refuses and reports correctly. Whether an agent handed a stated
  selection and a dozen near-identical verbs then picks the right one is Part
  C, and it is still open.
- **Selection with more than one caller.** One registry holds one selection.
  Two people driving one host would want one each, which is the request-scoped
  design ([NFSv4's current filehandle](../../docs/open-questions.md)) rather
  than the process-scoped one built here.
- **Many bodies over one broker at distance.** Everything is on one LAN.
- **Scale past a dozen.** Eight is enough to break naming and routing; it is
  not a load test.
- **A body that is present but wedged.** Presence says it is there. Only
  `ping` says it is listening, and that timing is experiment 005's problem.
