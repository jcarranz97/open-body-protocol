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
- **Many bodies over one broker at distance.** Everything is on one LAN.
- **Scale past a dozen.** Eight is enough to break naming and routing; it is
  not a load test.
- **A body that is present but wedged.** Presence says it is there. Only
  `ping` says it is listening, and that timing is experiment 005's problem.
