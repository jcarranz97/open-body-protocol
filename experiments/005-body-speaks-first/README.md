# Experiment 005 — the body speaks first

Experiments 001–004 are entirely brain-to-body. Every message on the wire so
far answers something the host asked: describe, call, ping, reply. A body has
never once started a conversation.

That is a strange shape for something with a physical presence. A robot on a
desk is touched, picked up, pressed, blocked, bumped — and none of that has
had anywhere to go. This experiment adds the return path: a push button on a
GPIO, and everything between it and an agent noticing.

The specification already defines the message, and its canonical example is
literally this button:

```json
{"jsonrpc": "2.0", "method": "notifications/body/event",
 "params": {"id": "01J8XR…", "ts": "2026-08-24T09:14:02Z",
            "type": "button", "name": "top", "payload": {"hold_ms": 120}}}
```

It also says *"events are the body's only way to speak first"*. What did not
exist was any implementation: the host skipped every message without an `id`
and dropped it, the MQTT transport subscribed to the event topic and discarded
what arrived, and the conformance list has **no requirements at all** for the
Events level. Declared on both sides, implemented on neither.

## Wiring

**GP14 — physical pin 19.** Physical pin 18, immediately next to it, is GND,
so a push button spans the two adjacent holes with no jumper wire. The pull-up
is internal: the pin idles high, and pressing pulls it low.

```
   pin 18  GND ──┐
                 ├── push button
   pin 19  GP14 ─┘
```

No resistor and no other parts. The same pin is free on both the Pico and the
Pico W, so one wiring diagram covers both firmwares.

The BOOTSEL button can be read at runtime instead, and this deliberately does
not: sampling it stalls execution from flash, on a board that is also
servicing USB, and it is the button you need working when a flash goes wrong.

## Requirements

Part A needs nothing but a terminal. Parts B and C need a board with a button.

```bash
uv run python3 tests/test_events.py
```

## Part A — no hardware

The fake body has a `press_button` verb that makes it report a press as though
someone had pressed one:

```bash
uv run python3 host/obp_cli.py --fake-id desk call press_button hold_ms=250 --body fake-desk
```

```text
button reported after 250ms
  event: 2026-08-24T16:20:11.402+00:00  fake-desk  button gpio14  hold_ms=250
```

The event is shown by the same command that caused it, because a fake body
lives and dies with the process that spawned it — a second `events` run would
start a *new* body with an empty log and report nothing, which is true and
misleading. A real board outlives the CLI, which is what `watch` is for.

`press_button` is `userOnly`, so an agent cannot manufacture its own input —
which is what that flag is for, and a neat demonstration of it.

## Part B — a real button

```bash
cd firmware/usb    # or firmware/mqtt for the Pico W
export PICO_SDK_PATH=~/repos/pico-sdk
cmake -B build -DPICO_BOARD=pico && cmake --build build
```

Flash, then watch:

```bash
sg dialout -c "uv run --with pyserial python3 host/obp_cli.py --port auto watch"
```

Press the button.

## Part C — an agent that notices

```bash
claude mcp add obp -- sg dialout -c "uv run --no-project \
    --with paho-mqtt --with pyserial python3 $PWD/host/obp_mcp.py --log /tmp/obp-005.log"
```

Two host tools carry events, and the difference between them is the whole
question:

- **`obp__events`** returns immediately with whatever has happened since a
  cursor. Cheap, and only sees a press when the agent happens to look.
- **`obp__wait_for_event`** blocks until something happens or a timeout
  expires. This is what makes *"tell me when someone presses the button"*
  expressible at all — but it parks a tool call to do it.

Neither is the thing you actually want, which is for the press to reach a
model that is not currently looking. MCP has no mechanism for that: the
2026-07-28 revision removed server-initiated requests entirely, so a server
cannot push anything into a session. `prior-art.md` notes that Claude Code
**Channels** are exactly a server pushing external events into a running
session, and that is the shape a real answer takes.

---

## Results

### Part A ✅ 2026-08-24

`tests/test_events.py` — **all passed**:

| Check | Result |
|---|---|
| A body can say something nobody asked for, and it reaches the host | ✅ |
| An event arriving mid-call does not disturb the call | ✅ |
| `press_button` is `userOnly`, so an agent cannot fake its own input | ✅ |
| Events are deduplicated by id, and the drop is counted rather than hidden | ✅ |
| A body admitting `clock_confident: false` is not believed; arrival time is used | ✅ |
| A confident body's own timestamp *is* used | ✅ |
| Two readers with separate cursors do not steal each other's events | ✅ |
| A blocked waiter is woken by the press it was waiting for | ✅ |
| And a wait with nothing coming times out rather than hanging | ✅ |

The four suites inherited from 004 still pass unchanged.

### Offline catch-up ✅ 2026-08-24

The autonomous-body case: a robot with its own long-lived agent, nobody
typing, and a press that happens while the brain is restarting.

```text
a host with a persistent session leaves
the body reports two presses while nobody is connected
the host comes back with the same client id
  ok:   the broker resumed the session it was holding
  ok:   both presses were delivered on reconnect (2)
  ok:   with their payloads intact: [80, 300]
a host that asks for no session gets no backlog
  ok:   and the press that happened while it was away is gone — which is the
        behaviour every OBP host had until now
```

Nothing was invented. MQTT has had persistent sessions for twenty-five years:
`Clean Start = 0` plus a `Session Expiry Interval`, and the broker holds the
subscription and queues QoS 1 messages for a client that is not connected. The
binding was one CONNECT flag away.

Three things must be right together, and any one wrong makes it silently do
nothing: **a stable client id** (the session is keyed on it, so a randomised
one per start looks like a new client every time — the usual reason people
conclude this does not work), **QoS 1 at both ends** (QoS 0 has no ack, so
there is nothing to queue), and **a subscription made before leaving** (the
broker queues against a subscription, not a topic).

The control case is the part worth keeping: with `session_expiry=0` the press
is simply gone, which is what every OBP host did until now.

Writing the test taught the same lesson twice. The first version left a
subscribed session behind — a session outliving its process being the whole
point — which then collected the event the *next* section published and
delivered it on the following run, failing a test whose code had not changed.

### Part B — a real button ⏳

```text

```

### Part C ⏳

```text

```

---

## What this does not test

- **A body that emits faster than anyone reads.** The log is bounded and drops
  the oldest, which is a policy, not a solution.
- **Events over a reconnect.** Dedup by id is implemented and unit-tested;
  nobody has yet pulled the cable mid-press.
- **Anything but a button.** A sensor threshold, a completed motion and a
  stall all use the same message, and none is exercised here.
