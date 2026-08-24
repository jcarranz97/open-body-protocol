# Protocol

The wire contract between the body and the daemon: MQTT topics, JSON
payloads, and the rules that keep a device which was unplugged overnight
from behaving badly when it comes back.

Every payload carries `v` (schema version) and `ts` (RFC3339, UTC). Keys are
short on purpose — the ESP32 parses these with ArduinoJson on a modest heap,
and the same structures have to survive being packed into a 247-byte BLE MTU
in v2 ([roaming](roaming.md)).

## Topics

Base prefix `tama/`. `<id>` is MAC-derived, e.g. `tama-a1b2c3`.

| Topic | Dir | Retain | QoS | Purpose |
|---|---|---|---|---|
| `tama/dev/<id>/status` | dev→srv | yes | 1 | LWT. `online` / `offline` |
| `tama/dev/<id>/hello` | dev→srv | no | 1 | Boot announce: fw version, caps |
| `tama/dev/<id>/event` | dev→srv | no | 1 | User and sensor events |
| `tama/dev/<id>/telemetry` | dev→srv | no | 0 | rssi, uptime, heap, battery |
| `tama/pet/state` | srv→dev | **yes** | 1 | Full state snapshot |
| `tama/pet/say` | srv→dev | no | 1 | An utterance + expression |
| `tama/pet/cmd` | srv→dev | no | 1 | Imperative device control |
| `tama/srv/status` | srv→dev | yes | 1 | Daemon LWT — device shows an offline badge |

Two retained topics carry the whole boot story: `tama/pet/state` means the
device renders the correct face before it has asked anything, and
`tama/srv/status` means it knows whether that face is current or a memory.

`tama/pet/*` is deliberately **not** per-device. There is one pet; bodies
are views onto it. When v2 adds a second body, both subscribe to the same
state and the daemon tracks which is *active* for routing `say`.

**Nothing in this contract is specific to hardware.** The terminal body
([TUI](tui.md)) is an ordinary MQTT client with an id like `tui-thinkpad-jc`
and a `caps` list that omits `buzzer`, `imu` and `speaker`. A second,
independent implementation is the cheapest proof that the contract is
complete: anything a body cannot do from `state` + `say` alone is a hole,
and it is cheaper to find in Python than in C.

### Access control

Per-device credentials, and a broker ACL that says what each may touch
(NFR-011). The device may publish only to `tama/dev/<its-own-id>/#` and
subscribe only to `tama/pet/#`. It must not be able to impersonate the
daemon or read another body's traffic. This costs one Mosquitto ACL file in
v1 and is the difference between a lost keychain being a toy and being a
key in v2.

## Payloads

### `hello` — device → server

```json
{
  "v": 1,
  "ts": "2026-08-23T10:04:11Z",
  "dev": "tama-a1b2c3",
  "fw": "0.3.1",
  "caps": ["display", "buttons", "buzzer", "imu"],
  "reset_reason": "power_on"
}
```

`caps` is what makes the registry useful: the daemon learns what this body
can do rather than assuming. A keychain that reports no `speaker` never gets
a `say` with `tts: true`, and neither does a terminal. Known capabilities:
`display`, `buttons`, `text_input`, `buzzer`, `speaker`, `mic`, `imu`.

### `event` — device → server

```json
{
  "v": 1,
  "id": "01J8...",
  "ts": "2026-08-23T10:05:00Z",
  "type": "button",
  "name": "feed",
  "payload": { "hold_ms": 120 }
}
```

| Field | Values |
|---|---|
| `type` | `button` · `shake` · `touch` · `idle` · `voice` · `boot` |
| `name` | `feed` · `play` · `clean` · `pet` · `menu` |

**`id` is a ULID and the daemon must dedupe on it.** MQTT QoS 1 is
at-least-once, so a redelivered `feed` is not a hypothetical — and a
duplicate that slips through is a stat change the owner did not make
(FR-013).

**`ts` is the device's clock, and the device says whether to trust it.**
Queued offline events carry a `clock_confident` flag; when it is false the
daemon falls back to arrival time (FR-042). This matters little on a
USB-powered LAN device and completely in v2, which is exactly why it is
specified in v1.

### `state` — server → device, retained

```json
{
  "v": 1,
  "ts": "2026-08-23T10:05:02Z",
  "name": "Nubbin",
  "age_days": 12,
  "stage": "child",
  "alive": true,
  "stats": {
    "hunger":   34,
    "energy":   71,
    "hygiene":  58,
    "social":   22,
    "health":   90
  },
  "mood": "lonely",
  "expression": "sad_blink",
  "streak_days": 4,
  "last_interaction": "2026-08-23T08:41:00Z"
}
```

Stats are 0..100. `hunger` is inverted — 0 is full, 100 is starving — which
is the one field everyone gets backwards; the [simulation](simulation.md)
page keeps the same convention throughout.

`stage` is `egg` · `baby` · `child` · `teen` · `adult`. `mood` is `happy` ·
`content` · `grumpy` · `sleepy` · `sick` · `excited` · `lonely`.

**Firmware renders from `expression` + `mood` only, and the server never
sends sprite data** (FR-031). The art stays in flash. This is what keeps the
payload small enough to matter in v2 and keeps a firmware update from being
required every time the pet learns a new face.

### `say` — server → device

```json
{
  "v": 1,
  "id": "01J8...",
  "ts": "2026-08-23T10:05:03Z",
  "expression": "excited",
  "animation": "bounce",
  "line": "you finally showed up. i counted 4 hours.",
  "sound": "chirp_up",
  "tts": false,
  "ttl_s": 45
}
```

**`ttl_s` is not optional politeness.** Without it, a device that was
unplugged overnight reconnects and replays a backlog of stale lines, which
reads as a malfunction rather than a personality (FR-032). A `say` whose
`ts + ttl_s` has passed is dropped on arrival, silently.

`say` is never retained, for the same reason.

### `cmd` — server → device

```json
{ "v": 1, "op": "set_brightness", "value": 40 }
{ "v": 1, "op": "set_volume", "value": 60 }
{ "v": 1, "op": "reboot" }
{ "v": 1, "op": "sync" }
{ "v": 1, "op": "ota", "url": "http://fw.dev.lan/0.3.2.bin", "sha256": "..." }
```

`sync` asks for a fresh state publish. `ota` carries a hash because the URL
is plain HTTP on the LAN and the device verifies the image itself rather
than trusting the transport (NFR-012).

## Schema versioning

`v` is a single integer per payload type, bumped only on a **breaking**
change. Adding an optional field is not breaking: firmware ignores unknown
keys, the daemon defaults missing ones. The rule that makes this safe is
that the device is always the *older* peer — it is reflashed less often than
the pod is redeployed — so the daemon must accept every `v` it has ever
emitted, while the firmware only has to understand its own.

## The packed form (write it in Phase 1)

BLE caps the MTU at 247 bytes and the `state` JSON above is ~400. The packed
binary form of `state` and `say` is ~24 bytes plus a 140-char line, which
fits in one MTU (FR-063).

v1 sends JSON over MQTT and never uses the packed codec in anger. Write it
and test it anyway, in the daemon, in Phase 1: it is an afternoon now and a
change to every layer later.

| Field | Packed |
|---|---|
| `stats` (5 × u8) | 5 B |
| `mood`, `expression`, `stage` (enums, u8) | 3 B |
| `age_days` (u16), `streak_days` (u8), flags (u8) | 4 B |
| `ts` (u32 epoch), `last_interaction` (u32 epoch) | 8 B |
| `line` (UTF-8, ≤140) | ≤140 B |

Enums being packed as `u8` is the reason `mood` and `expression` are closed
vocabularies rather than free strings — a constraint worth having anyway,
since it is also what the [brain](brain.md) validates model output against.
