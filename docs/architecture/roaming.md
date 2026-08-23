# Roaming — the keychain (v2, deferred)

!!! danger "Deferred"
    None of this is built in v1. It is documented now for one reason: five
    v1 decisions keep the door open, and they are cheap now and expensive
    later ([overview](overview.md) → *The five v1 decisions*). Read this
    page for those; build the desk pet first.

The device leaves the house. It is now *mostly disconnected*. Design for
that rather than fighting it.

## The core trick: the simulation is a pure function of time

Decay depends only on `elapsed_seconds` and the event log
([simulation](simulation.md)). So the device and the server can compute **the
same state independently**, with no chatter.

- The server is authoritative. The device runs the identical decay function
  as a *prediction*.
- On sync, server state overwrites device state, silently. **No merge
  logic.**
- The device's only real contribution is its **event log** — timestamped,
  ULID'd, queued in NVS while offline, replayed on reconnect. The server
  re-runs the simulation from the last checkpoint with those events folded in
  at their true timestamps.
- This is why events carry `id` and `ts`. The whole roaming design hangs off
  those two fields.

An unplugged keychain still gets hungry, still gets sad, and reconciles
perfectly when it next sees the internet. No split brain.

## Connectivity ladder

| Option | Effort | Power | Verdict |
|---|---|---|---|
| Multi-SSID list + phone hotspot | trivial | ok | Fine for a desk unit |
| MQTT over WSS :443 to a rendezvous broker | low | ok | Best if the device has WiFi |
| **BLE tether to the phone** | medium | **best** | **Best for a keychain** |
| WireGuard on the ESP32 | medium | poor | Only if you refuse a broker |
| CAT-M / NB-IoT cellular | high | good | Only if the phone can't be a dependency |

### Multi-SSID + hotspot

Store 4–5 known networks in NVS; scan on wake, connect to the strongest
known one, sync, sleep. A provisioning SoftAP with a captive portal adds
networks in the field.

Beware public captive portals — the ESP32 will associate and believe it has
internet. Probe with a HEAD request to a known URL before trusting the link.

### MQTT over WebSocket Secure on port 443 — recommended

Do **not** expose port 8883 from the homelab.

```text
keychain ──WSS:443──┐
                    ├──▶ rendezvous broker ◀──WSS:443── pet-daemon (homelab)
desk unit  ──MQTT───┘        (VPS or managed)
```

Both the device and the homelab daemon connect **outbound**. No port
forwarding, no dynamic DNS, nothing inbound at home.

Why 443 specifically: captive portals, corporate WiFi and some mobile
carriers block or mangle everything else. 8883 fails in exactly the places a
keychain lives.

Rendezvous options: a small VPS running Mosquitto with a WSS listener behind
Caddy; a Cloudflare Tunnel to the homelab broker (MQTT-over-WebSocket is
HTTP-shaped, so this works and exposes nothing at home); or a managed broker
free tier, where a third party sees the traffic — the payloads are trivial,
so probably fine.

The homelab daemon stays the brain either way. The broker is a dumb relay.

### WireGuard on the ESP32

Real and it works (`trombik/esp_wireguard` for ESP-IDF,
`ciniml/WireGuard-ESP32-Arduino` for Arduino). Caveats before committing:

- **Both peers need synced time**, and the library does not sync it — SNTP
  must succeed before the tunnel can come up.
- Handshake and crypto cost is real on a battery budget, and it re-handshakes
  every ~2 minutes while up.
- WiFi interface only; the sample sketches ship with no reconnect logic.
- UDP-based, so it dies behind the same restrictive networks that kill 8883.

Fine for a device that lives on trusted networks. Poor for a keychain.

### Cellular (CAT-M / NB-IoT)

The genuine keychain answer, at a cost. Reference board: **LilyGO
T-SIM7080G-S3** — ESP32-S3 (16 MB flash, 8 MB PSRAM) plus a SIM7080G
supporting CAT-M and NB-IoT, with PSM at ~3.2 µA, GNSS, and an 18650 holder
with solar input.

- The SIM7080G speaks **MQTT natively over AT commands** (MQTTS via
  `AT+SMSSL`), so the ESP32 needs no MQTT stack at all — a real size win.
- TX bursts hit ~500 mA. Power the modem from the LiPo directly, not through
  the 3.3 V LDO, with a fat bulk cap.
- The SIM must be inserted before the modem powers on, and its carrier must
  actually have CAT-M/NB-IoT enabled. This is the number one failure.
- An 18650 is not keychain-sized. A real keychain means a custom PCB, a
  400–600 mAh LiPo, and accepting a ~1×/hour sync cadence.

A pet syncing 24 tiny messages a day is a near-perfect fit for an IoT data
plan.

### BLE tether to the phone — the Apple Watch model

Architecturally the *right* answer. The device has no WiFi and no SIM; it
speaks BLE GATT to the phone, and the phone relays to the broker.

**Why it wins**

- **Power.** A BLE connection at a 1–2 s interval averages ~1–3 mA; WiFi +
  MQTT is ~80–120 mA. That is the difference between a day and a month on the
  same cell. Not a marginal gain — the whole ballgame.
- **Security.** No WiFi PSK, no broker credentials, no TLS certs on a losable
  object. The phone holds every secret. A found keychain is a plastic toy.
- **A free game mechanic.** BLE RSSI gives presence for nothing: phone in
  range means the owner is nearby and the pet is content; out of range for
  hours means lonely. **The pet notices when you come home.** That is the
  single most "alive" feature available and it costs one line of firmware.
- **Free clock sync.** The phone writes the time on every connect. No SNTP,
  no RTC drift problem.

**Where the Apple Watch analogy is unfair.** The Watch works because Apple
ships first-party software with privileged, essentially unlimited background
execution. A third-party BLE app gets a rationed version of that. Usable —
just do not expect a persistent, always-live link.

**iOS reality.** Two things are needed: `UIBackgroundModes` =
`bluetooth-central`, and Core Bluetooth **State Preservation and
Restoration** via `CBCentralManagerOptionRestoreIdentifierKey`. iOS then
relaunches the app *into the background* on peripheral discovery, connection,
or a notification on a subscribed characteristic. That last one is the hook:
**the pet notifies, the phone wakes, the relay runs.** Caveats, all real:

- Background scanning ignores `allowDuplicates` and **requires an explicit
  service UUID** — the peripheral must advertise the custom service UUID in
  its advertisement data, not only in the GATT table.
- A force-quit from the app switcher defeats state restoration permanently
  until the app is opened again; so does a phone reboot.
- If Bluetooth is off or permission is revoked, background relaunch stops
  silently and a terminated app cannot learn this.
- Wake-ups are throttled — on the order of 1–2 per hour for
  background-to-background discovery. For a pet syncing a few hundred bytes,
  completely fine.
- iOS aggressively caches GATT service definitions. Change the layout during
  development and you will lose an evening to it; unpair and reboot.
- Sideloading with a free developer account means re-signing every 7 days; a
  paid account gives a year.

**Android reality.** Much easier. A foreground service with a persistent
notification holds the link indefinitely; request battery-optimisation
exemption and it works. Tasker or a Termux script can do the relay with no
app at all.

**The no-app option: Web Bluetooth.** Chrome on Android supports it; a small
PWA can connect and POST to the daemon with no app store involved. iOS Safari
does not, though the Bluefy browser does. It runs only in the foreground, so
this is "sync when I glance at it" rather than a background tether — good
enough for a first prototype, and a great way to validate the GATT design
before writing anything native.

## GATT design

Custom 128-bit service. The device is the *peripheral*, the phone the
*central*.

| Characteristic | Props | Payload |
|---|---|---|
| `state_in` | write | Authoritative state from the server |
| `event_out` | notify | Queued device events, one per notification |
| `say_in` | write | Utterance + expression |
| `time_in` | write | Unix epoch, ms |
| `meta` | read | fw version, battery, queue depth |

- Negotiate the MTU up to 247 bytes. The state JSON is ~400 and will not fit:
  **use the packed binary form for BLE and keep JSON for MQTT**, with the
  daemon translating ([protocol](protocol.md) → *The packed form*). Packed
  state is ~24 bytes; only `line` needs real text, and 140 chars fits in one
  MTU.
- The `event_out` notification is what wakes the iOS app. Keep the pet
  notifying on any user interaction, even with an empty payload.
- Use **NimBLE**, not Bluedroid — roughly 100 KB less flash and far less RAM.

## Recommended: BLE primary, WiFi at home

Do not choose. Provision the keychain with home WiFi only, and:

- **Out of the house:** BLE to the phone. Trickle sync, presence, tiny
  payloads.
- **At home or on the charger:** WiFi + MQTT directly. Full-fidelity sync,
  OTA updates, log upload, big payloads.

OTA over BLE is miserable; OTA over WiFi while docked is trivial. This split
gives both and lets cellular be skipped entirely.

**Build order:** Web Bluetooth PWA first (an afternoon, validates the GATT
contract), then an Android foreground service or an iOS app with state
restoration once the protocol has stopped changing.

## Power budget

Always-on WiFi + MQTT keepalive is ~80–120 mA; on a 500 mAh cell that is a
few hours. So: deep sleep, and wake on three triggers only.

| Trigger | Action |
|---|---|
| Button press / shake (ext0/ext1 wake) | Wake, render, queue event, sync if due |
| Timer, every 15–30 min | Connect, flush queue, pull state, sleep |
| Low battery | Stop syncing, render a "tired" face, sleep 4 h |

A sync cycle is roughly wake (0.2 s) → WiFi assoc (2–4 s) → TLS + MQTT
(1–2 s) → exchange (0.5 s) → sleep. Call it 6 s at ~120 mA ≈ 0.2 mAh per
sync. At two syncs an hour that is ~10 mAh/day of radio — days to weeks of
runtime, dominated by the display, not the network.

Keep the display in the deepest partial-refresh mode available; consider
e-paper for a keychain, where a static face costs nothing between wakes.

## Security for a losable object

Assume the keychain will be left in a taxi.

- **Per-device credentials.** A unique MQTT user/password or, better, an mTLS
  client certificate. Never the same secret as the desk unit.
- **Broker ACLs.** The device may publish only to `tama/dev/<its-own-id>/#`
  and subscribe only to `tama/pet/#`.
- **Revocation.** One command in the daemon kills a device's cert and
  rotates. Test it before you need it.
- **Do not put the main WiFi PSK on it.** A separate IoT SSID, or
  hotspot-only, so a found keychain is not a house key.
- Journal and memory stay server-side. The device caches state, not secrets
  or history.

## Time

Deep sleep preserves the RTC, but it drifts. SNTP on every successful sync,
store `last_sync_ts` and `rtc_offset` in RTC memory, and mark queued events
with `clock_confident` so the server knows whether to trust the device's
timestamp or fall back to arrival time. On the BLE path this becomes moot —
the phone writes the time on every connect.

## End state: two bodies, one pet

- **Desk unit** — USB-powered, always connected, bigger screen, mic and
  speaker. The pet's "home".
- **Keychain** — deep-sleeping, offline-first, e-paper or small OLED, syncs
  opportunistically.

Both subscribe to `tama/pet/state`. The daemon tracks which body is *active*
(most recent event wins) and routes `say` there, so the pet feels like it
**moved** rather than being duplicated. A `tama/pet/presence` topic would let
the desk unit show an empty room while the owner is out.
