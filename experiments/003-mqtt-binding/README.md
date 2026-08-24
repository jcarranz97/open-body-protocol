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

### Part B — the Pico W ⏳

- Board: `______` · broker at `______` · SSID `______`

```text

```

| Check | Result |
|---|---|
| Serial log shows wifi ok and `mqtt connected` | ⬜ |
| Three flashes on connect | ⬜ |
| `obp_cli --mqtt bodies` lists `picow-xxxxxx` | ⬜ |
| `describe` shows **no** `set_brightness`, `caps: led` only | ⬜ |
| `blink times=5` blinks five times | ⬜ |
| `blink times=99` returns a readable error | ⬜ |
| Powering the Pico off withdraws its verbs within the keep-alive | ⬜ |
| Powering it back on brings them back with no host restart | ⬜ |

### Part C — two bindings at once ⏳

The plain Pico on USB **and** the Pico W over MQTT, in one registry, both
offered to one agent. This is the claim that transport is a binding, stated
as plainly as it can be.

```text

```

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
