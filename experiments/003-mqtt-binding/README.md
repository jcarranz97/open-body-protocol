# Experiment 003 — the MQTT binding

**Goal:** run the identical contract over MQTT to a body with no cable, and
confirm that transport is a **binding** rather than the architecture.

Experiments 001 and 002 proved a body can describe itself and be driven by an
agent, both over a wire. If the same descriptors, the same verbs and the same
results work unchanged over a broker — and if presence works the way the
specification claims — then the deployment topologies in the docs are real
and not aspirational.

**Time:** ~5 minutes for Part A. ~20 for the Pico W.

---

## Part A — no hardware

A real broker, and a body with no hardware speaking OBP over it.

```bash
cd ~/repos/open-body-protocol/experiments/003-mqtt-binding
docker compose up -d                      # Mosquitto on 1883 and 9001
uv run --with paho-mqtt python3 tests/test_mqtt_binding.py
```

The suite starts two bodies, drives them, kills one without warning and
checks the broker cleans up after it. **Passing as of 2026-08-24** — see
Results.

Drive one by hand if you like:

```bash
uv run --with paho-mqtt python3 host/mqtt_fake_body.py --id fake-mqtt-1 &
uv run --with paho-mqtt python3 host/obp_cli.py --mqtt bodies
uv run --with paho-mqtt python3 host/obp_cli.py --mqtt call blink times=3
```

## Part B — a Pico W

### Requirements

- A Raspberry Pi Pico W or Pico 2 W. **A plain Pico will not do**: this body
  needs wireless.
- The broker from Part A, reachable on your LAN. It is already bound to
  `0.0.0.0:1883`, so the Pico can reach it at this machine's address —
  **`192.168.1.225`** on the run recorded below.

### The SDK needs two more submodules

Same trap as TinyUSB in experiment 001, with two different names. WiFi and
lwIP will fail to build until:

```bash
git -C ~/repos/pico-sdk submodule update --init lib/lwip lib/cyw43-driver
```

### Build

Credentials go on the command line and are compiled into the binary. That is
acceptable for a body on a desk and is **not** how a real one should be
provisioned — nothing secret is committed here.

```bash
cd firmware/pico-w
export PICO_SDK_PATH=~/repos/pico-sdk
cmake -B build -DPICO_BOARD=pico_w \
      -DWIFI_SSID="your-ssid" \
      -DWIFI_PASSWORD="your-password" \
      -DMQTT_BROKER="192.168.1.225"
cmake --build build -j4
```

`-DPICO_BOARD=pico2_w` for a Pico 2 W.

### Flash

Hold **BOOTSEL**, plug in, then copy. On this machine the drive mounts under
`/run/media/$USER/`, not `/media/$USER/`:

```bash
findmnt -no TARGET -S LABEL=RPI-RP2       # confirm where it landed
cp build/obp_body_mqtt.uf2 /run/media/$USER/RPI-RP2/ && sync
```

### Watch it join

The body logs to USB serial, so the same CLI port trick works:

```bash
sg dialout -c "python3 -c \"
import serial,glob
p=glob.glob('/dev/serial/by-id/*Pico*')[0]
s=serial.Serial(p,115200,timeout=30)
[print(s.readline().decode(errors='replace').rstrip()) for _ in range(8)]\""
```

Expect roughly:

```text
body picow-xxxxxx
joining your-ssid ...
wifi ok, ip 192.168.1.xx
mqtt connected
```

Three quick flashes mean connected, subscribed and announced.

### Drive it

```bash
uv run --with paho-mqtt python3 host/obp_cli.py --mqtt bodies
uv run --with paho-mqtt python3 host/obp_cli.py --mqtt call blink times=5
uv run --with paho-mqtt python3 host/obp_cli.py --mqtt call set_led on=true
```

### The capability difference is the point

**A Pico W drives its LED through the wireless chip, which cannot be
PWM'd.** So this body advertises **two verbs plus `reboot`**, with no
`set_brightness`, and `caps: ["led"]` without `dimmable` — while the
identical contract on the plain Pico in experiment 001 advertises
`set_brightness` and claims `dimmable`.

Experiment 001 could only simulate that with an environment variable. Here it
is two physically different boards, and the host learns the difference by
asking.

---

## Results

### Part A — the binding, against a real broker ✅ 2026-08-24

Fifteen checks, all passing:

- A body that connects appears in the retained set; `describe` answers over
  MQTT with the same verbs and shapes as the USB bodies, `userOnly` included.
- A call round-trips; `blink times=99` is still a **result**, not a fault.
- Two bodies on one broker each contribute their own verbs, and the combined
  list stays sorted.
- **A killed body — no goodbye — leaves the retained set**, the survivor is
  untouched, and calling the departed one returns a readable result.
- **A host that starts later is told the truth by the broker**: retained
  presence replays for the live body and not for the dead one.

That last pair is the presence mechanism the specification recommends,
working exactly as described: a retained announcement, cleared by a Last Will
with an empty payload. No heartbeat table, no TTL sweeper.

### Part B — the Pico W ✅ 2026-08-24

- Board: `picow-7c6e37` (Pico W, pico-sdk C, no MicroPython) · broker on the
  LAN at `:1883` · SSID and PSK passed on the cmake command line.

```text
$ obp_cli --mqtt bodies
picow-7c6e37         Raspberry Pi Pico W body           2 verbs  via mqtt  caps: led

$ obp_cli --mqtt describe
Raspberry Pi Pico W body  [picow-7c6e37]  fw obp-picow-0.1.0
caps: led
  set_led(on:boolean)         Turn the body's indicator light on or off.
  blink(times, interval_ms)   Blink the indicator light.
  reboot()  !user-only        Restart the body. Disconnects it briefly.

$ obp_cli --mqtt call blink times=4 interval_ms=150
blinked 4 times
$ obp_cli --mqtt call blink times=99
ERROR: times must be between 1 and 10
```

Five consecutive `blink` calls: 0.9–1.1 s each, process start to printed
result — connect, discover, describe and call, over WiFi.

| Check | Result |
|---|---|
| Serial log shows wifi ok and `mqtt connected` | ✅ |
| `obp_cli --mqtt bodies` lists `picow-7c6e37` | ✅ |
| `describe` shows **no** `set_brightness`, `caps: led` only | ✅ |
| `blink times=5` blinks | ✅ |
| `blink times=99` returns a readable error, not a fault | ✅ |
| `userOnly` reboot hidden from agents, callable by a person | ✅ |
| Ids echoed verbatim: string, number and null (B8a) | ✅ |
| A reboot withdraws presence and returns without a host restart | ✅ |

### A body that knows it is leaving should say so

Instrumenting presence transitions through a reboot made the difference
measurable:

```text
  1.30s  reply: 'rebooting'  isError=False
  1.30s  presence: picow-7c6e37 -> ABSENT     <- the body clearing its own
 14.27s  presence: picow-7c6e37 -> ABSENT     <- the broker's Last Will, finally
 14.64s  presence: picow-7c6e37 -> PRESENT
 47.24s  after its return: blinked 3 times
```

Both mechanisms fire, thirteen seconds apart. The Last Will is the backstop for
a body that dies without warning; it cannot be fast, because the broker has to
wait out a keep-alive to know. A body that is going deliberately already knows,
and publishing the empty retained payload itself is the difference between a
host seeing a restart and a host confidently calling a board that is not there.

Worth noting how this was nearly missed: an earlier version of this check polled
`bodies()` once a second and reported "presence never withdrawn". The body was
correct and the test could not see it. Presence is an event, so the test had to
watch for the event rather than sample for it.

### What Part B actually cost: two bugs and a spec gap

Neither bug was in a message. Both were in the space around it.

**1. A 2 KB buffer starved a 4 KB heap.** The board opened TCP to the broker
and then said nothing; mosquitto logged `exceeded timeout` over and over. The
vendor's own `picow_mqtt_client` connected first try, which proved the board,
the WiFi, the broker and the toolchain were all fine. A full diff of
`lwipopts.h` against the vendor's showed **only debug flags differed** — and I
dismissed that as cosmetic. It was the answer. Turning `LWIP_DEBUG` and
`MQTT_DEBUG` on produced the diagnosis in a single line:

```text
mqtt_output_send: tcp_sndbuf: 11680 bytes, ringbuf_linear_available: 60, get 0, put 60
mqtt_output_send: Send failed with err -1 ("Out of memory error.")
```

A 60-byte CONNECT, an 11 KB send window, and no memory to build a pbuf. The
cause was mine: I had raised `MQTT_OUTPUT_RINGBUF_SIZE` to 2048 so a 1.4 KB
describe response would fit, and that buffer lives *inside* the `mqtt_client_t`
allocated from `MEM_SIZE 4000`. I made the buffer big enough for the data and
starved the allocator the same data had to pass through. `MEM_SIZE` is now
16000; a Pico W has 264 KB of RAM, so the frugality bought nothing.

**2. The id was read as a `long`.** JSON-RPC ids may be strings or numbers, and
`handle_request` parsed with `jm_get_int`, so every string id came back as `0`.
A host correlates replies by id and silently skips the ones that do not match,
so the body answered correctly, in 0.8 s, to a host that could never claim the
answer. **It failed as silence.**

The spec is what taught me this. `conformance.md` had **no requirement to echo
the id at all**, and every example in `messages.md` used a number. An
implementer reading them would do exactly what I did. Both are fixed: **B8a**
is now normative, an example uses a string id, and the suite probes string,
numeric and null ids against the fake body and the real board.

**3. `reboot` never replied.** It cleared its presence and reset from inside
the lwIP callback, so both the presence-clear and the reply were still in the
output ring buffer when the core went down. The verb worked perfectly and
reported as a timeout. It now answers, clears presence, and lets the main loop
reset once lwIP has flushed — B8 applies to `reboot` like anything else.

**An honest note on what is *not* established.** Before the id fix, the CLI —
which sends *numeric* ids — also timed out, and the id bug does not explain
that: compiling `json_min.c` on the host and feeding it the exact 54-byte
request shows numeric ids parse correctly. Something else was wrong in that
window and was cleared by the reflash. The binding has been reliable across
every run since, so this is recorded rather than chased.

### Part C — two bindings at once ⏳ (partly run 2026-08-24)

The plain Pico on USB **and** the Pico W over MQTT, in one registry, both
offered to one agent. This is the claim that transport is a binding, stated
as plainly as it can be. Pending: the plain Pico needs to be attached.

What has already run is the half nobody plans for. The Pico W exposes a USB
serial console for its own debug log, and it is **not** an OBP body — so
`--port auto` finds a device that opens cleanly, emits text, and cannot answer:

```text
$ obp_cli --mqtt --port auto bodies
[body stderr] up: body=picow-7c6e37 wifi=192.168.1.227 mqtt=connected
/dev/serial/by-id/usb-Raspberry_Pi_Pico_E6614864D37C6E37-if00: no response to body/describe within 5.0s
picow-7c6e37         Raspberry Pi Pico W body           2 verbs  via mqtt  caps: led
```

One board, two ways in, and only the one that answers is a body — which is
[H5a](../../docs/spec/conformance.md) meeting a real impostor rather than a
contrived one. An attached device is a device; a body is something that
replies.

Getting there needed a fix. `--port auto` is this experiment's headline flag
and it silently found nothing: `ports.expand()` turns `auto` into the attached
devices, experiment 002 calls it, and this CLI never did — it passed the
literal string `auto` to `resolve()`, which matched no path. The failure
printed *"auto: not present"* directly above a list of attached devices, which
is the kind of self-contradicting message that gets read past.

---

## What this tests

| Requirement | Where |
|---|---|
| Presence via retained message + Last Will | `tests/test_mqtt_binding.py` |
| H5 verbs withdrawn on presence loss | same |
| H6 no hang on a departed body | same |
| H2 deterministic ordering across bodies | same |
| Host restart re-establishes presence | same |
| Capability gating across physical boards | Part B |

## What it does not test

- **Authentication.** The broker is anonymous, deliberately: this experiment
  is about the binding. Per-body credentials and ACLs are what the
  specification's security page asks for, and belong in their own experiment.
- **MQTT over WebSocket**, though the broker exposes 9001 for it.
- **Reconnection storms**, a flaky link, or a broker restart.
