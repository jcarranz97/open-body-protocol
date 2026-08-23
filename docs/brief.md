# TAMALAB — an AI Tamagotchi backed by your homelab

> Working codename. Rename freely.
> A physical desk pet (ESP32) whose brain, memory and personality live in a
> container in your homelab, reachable from both the device and Telegram.

---

## 1. Goals and non-goals

**Goals**

- A physical object with a face that reacts in real time, with buttons/sensors.
- The pet has **persistent state and memory** that survives reflashing the device.
- The same pet is reachable from Telegram (your existing bot) and from the device.
- Personality comes from an LLM, but **which** LLM is a config value — local
  (Qwen via Ollama), cloud (Claude, or anything OpenAI-compatible), or none.
- The *simulation* (hunger, mood decay) is deterministic and runs without any
  LLM at all, so the pet works with the brain unplugged.
- The pet can react to homelab events (backup failed, CI red, uptime milestones).
- It must still be charming when the network or the server is down.

### Scope lock

> **v1 is WiFi-only, home network, USB-powered.**
> The device lives on the LAN and talks MQTT to the daemon directly. No VPN,
> no rendezvous broker, no cellular, no BLE, no battery. If it leaves the
> house it simply goes into DEGRADED mode (§9) until it comes back.
>
> **v2 is the BLE keychain** (§11b-E). Everything in §11b is deliberately
> deferred — read it now only for the handful of v1 decisions in §11a that
> keep that door open.

**Explicit non-goals for v1**

- On-device LLM inference. The ESP32 is a terminal, not a brain.
- Battery / portability / roaming. USB-powered on a desk, full stop.
- BLE, cellular, WireGuard, or any off-LAN transport.
- **Wake words / always-on listening.** Voice is push-to-talk only (§6b).
- Multi-user / multi-pet. One pet, one owner — though eventually two *bodies*.

> **Note:** voice (§6b) is a v1 feature but the *last* one built. It forces the
> board choice up front — buy the ESP32-S3 with PSRAM in Phase 1 even though
> nothing uses the mic until Phase 5. Voice is also inherently WiFi-only, so
> the v2 keychain will be a silent body.

---

## 2. Architecture

```
              ┌──────────────────────────────┐
              │      ESP32-S3 (the body)     │
              │  display · buttons · buzzer  │
              │  I2S mic + speaker · IMU     │
              │  local cache: last state     │
              └───────┬──────────────┬───────┘
                      │              │
         MQTT/TLS ────┘              └──── WSS: audio session
         (control, state,                  (PCM in / PCM out,
          events, say)                      push-to-talk only)
                             │
    ┌────────────────────────▼─────────────────────────────┐
    │              pet-daemon  (homelab pod)               │
    │                                                      │
    │  ┌───────────┐   ┌────────────┐   ┌───────────────┐  │
    │  │ sim tick  │   │   state    │   │  memory /     │  │
    │  │ (cron 1m) │──▶│  SQLite    │◀──│  journal      │  │
    │  └───────────┘   └─────┬──────┘   └───────────────┘  │
    │                        │                             │
    │                 ┌──────▼───────┐   ┌──── canned lines │
    │                 │  brain       │──▶├──── local LLM    │
    │                 │  (pluggable) │   │     (Qwen, etc)  │
    │                 └──────┬───────┘   └──── cloud LLM    │
    │                        │                 (Claude…)    │
    │                        │                             │
    │        ┌───────────────┼────────────────┐            │
    │        ▼               ▼                ▼            │
    │  MQTT publish    Telegram bot     webhook in         │
    │  (to device)     (your existing)  (homelab events)   │
    └──────────────────────────────────────────────────────┘
```

**The single most important rule:** the daemon owns the truth. The ESP32 holds
only a cached copy so it can keep animating when the pod restarts.

### Why MQTT

- Retained messages → device gets the current state instantly on boot.
- Last Will and Testament → "the body went offline" for free.
- Pub/sub → adding a web dashboard or a second device later costs nothing.
- Tiny client footprint on the ESP32.

Use Mosquitto or the broker you already have. WebSocket is the better choice
only if you later stream audio (see §9).

---

## 3. MQTT topic schema

Base prefix: `tama/`

| Topic | Dir | Retain | QoS | Purpose |
|---|---|---|---|---|
| `tama/dev/<id>/status` | dev→srv | yes | 1 | LWT. `online` / `offline` |
| `tama/dev/<id>/hello` | dev→srv | no | 1 | Boot announce: fw version, caps |
| `tama/dev/<id>/event` | dev→srv | no | 1 | User/sensor events |
| `tama/dev/<id>/telemetry` | dev→srv | no | 0 | rssi, uptime, heap, battery |
| `tama/pet/state` | srv→dev | **yes** | 1 | Full state snapshot |
| `tama/pet/say` | srv→dev | no | 1 | An utterance + expression |
| `tama/pet/cmd` | srv→dev | no | 1 | Imperative device control |
| `tama/srv/status` | srv→dev | yes | 1 | Daemon LWT — device shows "offline" badge |

`<id>` = MAC-derived, e.g. `tama-a1b2c3`.

---

## 4. JSON contracts

Every payload carries `v` (schema version) and `ts` (RFC3339 UTC).
Keep keys short — the ESP32 parses these with ArduinoJson on a modest heap.

### 4.1 `hello` (device → server)

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

### 4.2 `event` (device → server)

```json
{
  "v": 1,
  "id": "01J8...",          // ULID, for idempotency
  "ts": "2026-08-23T10:05:00Z",
  "type": "button",         // button | shake | touch | idle | voice | boot
  "name": "feed",           // feed | play | clean | pet | menu
  "payload": { "hold_ms": 120 }
}
```

The daemon must dedupe on `id` — MQTT QoS 1 is at-least-once.

### 4.3 `state` (server → device, retained)

```json
{
  "v": 1,
  "ts": "2026-08-23T10:05:02Z",
  "name": "Nubbin",
  "age_days": 12,
  "stage": "child",             // egg | baby | child | teen | adult
  "alive": true,
  "stats": {
    "hunger":   34,             // 0 = full, 100 = starving
    "energy":   71,
    "hygiene":  58,
    "social":   22,
    "health":   90
  },
  "mood": "lonely",             // happy | content | grumpy | sleepy | sick | excited | lonely
  "expression": "sad_blink",    // maps to a sprite/animation id in firmware
  "streak_days": 4,
  "last_interaction": "2026-08-23T08:41:00Z"
}
```

Firmware renders from `expression` + `mood` only. Never let the server send
sprite data — keep the art in flash.

### 4.4 `say` (server → device)

```json
{
  "v": 1,
  "id": "01J8...",
  "ts": "2026-08-23T10:05:03Z",
  "expression": "excited",
  "animation": "bounce",
  "line": "you finally showed up. i counted 4 hours.",
  "sound": "chirp_up",          // null | chirp_up | chirp_down | alarm | purr
  "tts": false,
  "ttl_s": 45                   // drop if received late (offline queue)
}
```

`ttl_s` matters: without it, a device that was unplugged overnight replays a
backlog of stale lines the moment it reconnects.

### 4.5 `cmd` (server → device)

```json
{ "v": 1, "op": "set_brightness", "value": 40 }
{ "v": 1, "op": "reboot" }
{ "v": 1, "op": "sync" }          // request a fresh state publish
{ "v": 1, "op": "ota", "url": "http://homelab.lan/fw/0.3.2.bin", "sha256": "..." }
```

---

## 5. The simulation (no LLM involved)

A cron tick every 60s in the daemon. All values clamp to 0..100.

| Stat | Change per hour | Notes |
|---|---|---|
| hunger | +4 | ×0.5 while asleep |
| energy | −3 awake, +12 asleep | sleeps 23:00–07:00 local |
| hygiene | −2 | +5 per `clean` event |
| social | −6 | resets to 0 on any interaction |
| health | −5/h if hunger>85 or hygiene<10 | +2/h otherwise |

Mood is derived, not stored as truth:

```
health < 30                      → sick
energy < 20                      → sleepy
hunger > 70                      → grumpy
social > 70                      → lonely
all stats "good" + recent play   → excited
else                             → content
```

Death: `health == 0` for 6 consecutive hours. Make it recoverable (a `revive`
command that costs the streak) unless you want genuine 1997-era stakes.

---

## 6. The brain (provider-agnostic LLM layer)

> **Design rule:** the pet must never know which model is thinking for it.
> The brain is a swappable component behind a narrow interface, and the
> canned-line table is always available as the zeroth provider.

### 6.0 The abstraction

You already have the abstraction — it's §6.3. The pet doesn't need "an LLM",
it needs *one small JSON object*. That's a narrow enough contract that any
model from Qwen 2.5 3B upward can satisfy it. Build to that, not to a vendor.

```python
@dataclass
class Capabilities:
    structured: str      # none | json_mode | json_schema | grammar | native_strict
    tools: bool
    context_tokens: int
    latency_class: str   # fast | slow
    cost_class: str      # free | cheap | paid
    privacy: str         # local | cloud

class Brain(Protocol):
    name: str
    caps: Capabilities
    def respond(self, ctx: PetContext) -> PetResponse: ...
```

Three implementations cover essentially the whole world:

| Implementation | Covers |
|---|---|
| `CannedBrain` | Static line table. No network. **Always the final fallback.** |
| `OpenAICompatBrain` | Ollama, llama.cpp server, vLLM, LM Studio, LocalAI, plus OpenAI, Groq, Together, DeepSeek, Mistral, OpenRouter — anything speaking `/v1/chat/completions` |
| `AnthropicBrain` | Native Messages API, for guaranteed-schema Structured Outputs, prompt caching, and MCP tools |

**Why two cloud paths rather than one.** Anthropic does publish an
OpenAI-compatible endpoint — point the OpenAI SDK at `https://api.anthropic.com/v1/`
and change the model name. But Anthropic explicitly frames it as a way to test
and compare model capabilities rather than a long-term production solution, and
the important limitation for us is that the `strict` parameter for function
calling is ignored, so tool-use JSON is not guaranteed to match your schema;
for guaranteed conformance you need the native API's Structured Outputs. Other
gaps: no prompt caching, no audio input, system messages hoisted and
concatenated (Anthropic takes a single initial system message), and temperature
capped at 1.0.

So: use `OpenAICompatBrain` for local models and for cheap cloud tiers, and
`AnthropicBrain` when you want the guarantees. One extra class, ~80 lines.

### 6.0.1 Reliable JSON from small models

This is the real engineering problem, not the HTTP plumbing. A 7B model *will*
emit prose, markdown fences, and trailing commas if you merely ask nicely. Use
constrained decoding, which every serious runtime now supports:

| Runtime | Mechanism |
|---|---|
| Ollama | `format` = your JSON Schema |
| llama.cpp server | GBNF grammar |
| vLLM | guided decoding (xgrammar / outlines) |
| Claude native | Structured Outputs |
| Anything else | ask for JSON, then repair-and-retry once, then fall back |

Pipeline for every provider, no exceptions:
`constrain → parse → validate against schema → clamp enums → on any failure,
CannedBrain`. The device must never hang on the brain.

### 6.0.2 Routing

Different jobs deserve different models. Route by trigger, not by preference:

| Trigger | Tier | Why |
|---|---|---|
| Idle chatter, mood transitions | **local** (Qwen 3 8B) | Free, private, unlimited, quality barely matters for 12 words |
| Owner conversation (Telegram/voice) | **cloud** | This is the moment the pet earns its existence |
| Daily journal, memory writes | **cloud** | Long-lived artefacts; worth the tokens |
| Homelab event reactions | **local** | Templated and frequent |
| Anything, when the primary fails | **canned** | Never blocks |

Config, not code:

```yaml
providers:
  local:
    kind: openai_compat
    base_url: http://ollama.homelab.lan:11434/v1
    model: qwen3:8b
    caps: { structured: json_schema, tools: false, privacy: local, cost_class: free }
  cloud:
    kind: anthropic
    model: claude-sonnet-4-5
    caps: { structured: native_strict, tools: true, privacy: cloud, cost_class: paid }

routes:
  idle:         [local, canned]
  conversation: [cloud, local, canned]
  journal:      [cloud, canned]
  homelab:      [local, canned]
```

Swapping to a different local model, or going 100% local for privacy, or
100% cloud when your GPU is busy, is then a YAML edit and a restart.

### 6.0.3 Portability details that actually bite

- **System prompts.** Keep `character.md` vendor-neutral. Give each provider a
  small adapter that handles its quirks (Anthropic wants a single leading
  system message; some local chat templates want the persona in the first user
  turn to be respected at all).
- **Tools.** Normalise tool definitions to plain JSON Schema and translate per
  provider. Small local models are bad at tool use — **don't give them tools.**
  Instead pre-fetch the context they need (state, top memories, recent journal)
  and hand it over in the prompt. Reserve real tool calling for the cloud tier.
- **Token accounting.** Providers report usage differently. Normalise to
  `{in, out, cost_eur}` at the adapter boundary so your budget guard (§6.1)
  works regardless of who answered.
- **Latency.** A pet tolerates 2–5 s far better than a chatbot does — just show
  a thinking animation. But a 14B model on CPU can take 30 s. Set a hard
  timeout per tier (local 8 s, cloud 15 s) and fall through on expiry.

### 6.0.4 The eval harness — build this in Phase 3

The thing that makes provider-swapping *safe* rather than a vibe check:

- 30 golden `(state, trigger)` fixtures in a YAML file.
- Run all of them against any configured provider.
- Score mechanically: valid JSON? enums in range? `line` under 140 chars? no
  emoji if forbidden? stayed in character (a cloud model can judge this).
- `make eval provider=local` prints a table.

Now "can Qwen 3 8B run my pet?" is a question with an answer, and you can
adopt a new model the week it ships without regressions.

### 6.1 Budget discipline

Do **not** call the brain on every tick. Call it on:

- an inbound `voice` or Telegram text message (always),
- a mood *transition* (content → grumpy), not every tick in that mood,
- a neglect threshold crossing (4h, 12h, 24h),
- one daily journal entry at 21:00,
- a homelab webhook event.

Rate limit: max 1 spontaneous call per 15 min, max ~40/day. Everything else
uses a canned line table keyed by `(mood, expression)`.

### 6.2 System prompt layout

```
character.md          ← stable personality, voice, hard rules
+ memory (top 20)     ← facts learned about the owner
+ recent journal (3)  ← last few days, one line each
+ current state JSON  ← from §4.3
+ trigger description ← "neglected 12h" / "owner said: ..."
```

### 6.3 Structured output

Ask for JSON only, no prose, no fences:

```json
{
  "line": "max 140 chars, in character, lowercase, no emoji",
  "expression": "one of: idle|happy|sad|angry|sleepy|sick|excited|confused",
  "animation": "one of: none|bounce|shake|wobble|spin",
  "sound": "one of: none|chirp_up|chirp_down|alarm|purr",
  "remember": null,
  "mood_nudge": 0
}
```

`remember` lets the pet write a durable fact about you; `mood_nudge` (−10..+10)
lets it tweak its own social stat so the personality has *some* feedback into
the simulation. Validate strictly and fall back to a canned line on parse
failure — the device must never hang waiting for the brain.

### 6.4 Tools (cloud tier only)

Expose the pet's world as tools, defined once as plain JSON Schema and
translated per provider:

- `get_pet_state()` → §4.3
- `recall(query)` / `remember(fact, weight)`
- `set_expression(expr, animation)` — lets it emote mid-turn
- `send_telegram(text)`
- `get_homelab_status()` — uptime, last backup, disk usage
- `read_journal(days)`

This is what turns it from a chatbot with a sprite into something that feels
continuous.

Implement these as an **MCP server** rather than as inline function definitions.
MCP is the closest thing to a neutral standard here — the Claude Agent SDK
consumes it directly, and the same server can be exposed to other runtimes or
called directly by your own code for providers that don't support tools. It
also means the `xiaozhi` firmware path in §12, which already speaks MCP, could
later talk to the same server.

For the local tier: no tools. Pre-fetch state, top memories and recent journal
into the prompt and let the small model just write a line.

---

## 6b. Voice: push-to-talk

### Why push-to-talk is the right call

Holding a button is not a compromise — it deletes most of the hard problems:

- **No wake word engine.** No false triggers, no per-user tuning.
- **No VAD.** Button down is the start marker, button up is the end marker.
  Perfect endpointing, for free.
- **No acoustic echo cancellation.** The pet never listens while it speaks, so
  you don't need AEC hardware or the S3 audio front-end.
- **No always-on mic.** Privacy is structural, not a promise. This matters for
  an object that sits on your desk all day.
- **Far lower power and far cheaper silicon.**

Wake words can come in v3 if you ever want them. Don't start there.

### Transport: MQTT is wrong for audio

Keep MQTT for control (state, events, say) and add a **second transport for the
audio session only**. This is exactly the split `xiaozhi-esp32` makes — control
over MQTT, audio over a separate channel — and it's why §11a told you to put a
`Transport` interface in the firmware.

```
button DOWN  → open WSS to wss://pet.homelab.lan/audio
             → send {"type":"start","fmt":"pcm16","sr":16000}
             → stream binary frames (20 ms = 640 bytes) while held
button UP    → send {"type":"end"}
             ← {"type":"stt","text":"..."}          (show on screen)
             ← {"type":"say","line":"...","expression":"happy"}
             ← binary PCM frames → I2S out
             ← {"type":"done"}
             → close
```

Use WebSocket over TLS on the same port as everything else. A dedicated
long-lived WS is unnecessary — open it on button-down, close it after playback.
Connection setup is ~200 ms on the LAN and happens while you're still talking.

**Codec: raw PCM 16 kHz mono 16-bit for v1.** That's 32 KB/s — nothing on a
LAN. Opus would be ~20× smaller but costs ESP32 CPU and a lot of integration
work. Add it only if you later stream over the internet.

**Buffering:** 8 MB PSRAM holds minutes of audio. Stream while recording rather
than buffering-then-sending; it hides the upload entirely behind your speech.

### Server pipeline

Voice adds exactly one stage on each side of the existing brain. The brain from
§6 does not change at all — a transcript is just another `conversation`
trigger.

```
PCM in → Transcriber → text → Brain (§6) → text → Synthesiser → PCM out
```

Both new stages get the same pluggable treatment as the brain:

```python
class Transcriber(Protocol):
    def transcribe(self, pcm: bytes, sr: int) -> str: ...

class Synthesiser(Protocol):
    def stream(self, text: str) -> Iterator[bytes]: ...   # PCM chunks
```

| Stage | Local option | Cloud option |
|---|---|---|
| STT | `faster-whisper` (small/base), Vosk for lowest latency | Deepgram, Groq whisper-turbo |
| TTS | Piper (CPU, fast), Kokoro (better) | ElevenLabs |

Put them in the same `providers.yaml` as the brain, with the same fallback
chains. Local-only is a completely viable config: Whisper small + Qwen + Piper
all run on one modest homelab box.

**A note on voice choice:** for a pet, a slightly strange, small, pitch-shifted
voice is *better* than a photorealistic one. Piper with the pitch pushed up is
more charming than ElevenLabs' best, and free. Spend the effort on the
character, not the fidelity.

### Latency budget

Target: **first sound within 1.5 s of button release.**

| Stage | Budget |
|---|---|
| Upload tail (streamed during speech) | ~0 |
| STT | 300–800 ms |
| LLM first sentence | 400–1500 ms |
| TTS first chunk | 200–500 ms |

Three tricks that matter more than any of those numbers:

1. **Stream TTS on the first sentence.** Don't wait for the full LLM response.
   Split on the first `.` / `?` / `!` and start synthesising immediately.
2. **React instantly on the device.** The moment the button lifts, play a
   thinking chirp and switch to a "hmm" animation. Perceived latency collapses
   even though nothing got faster.
3. **A pet is allowed to be slow.** A chatbot pausing for 2 s feels broken; a
   creature tilting its head for 2 s feels like it's thinking. This is a real
   advantage of the form factor — use it.

Hard timeouts: STT 5 s, brain 8 s local / 15 s cloud, TTS 5 s. On any expiry,
fall back to a canned line and a confused animation. It must never just hang.

### Device state machine (extends §9)

```
IDLE ──button down──▶ LISTENING ──button up──▶ THINKING ──▶ SPEAKING ──▶ IDLE
  ▲                       │                        │            │
  └───── timeout/err ◀─────┴────────────────────────┴──button────┘
                                                      (barge-in: cancel)
```

- **LISTENING** — obvious visual (ear/waveform), mic LED on. Hard cap 15 s.
- **THINKING** — chirp + animation immediately, never a blank screen.
- **SPEAKING** — mouth animation synced to output amplitude. Cheap, very effective.
- **Barge-in** — pressing the button during SPEAKING stops playback and starts
  a new recording. Small feature, enormous usability difference.

Never open the mic outside LISTENING. Never buffer audio in IDLE. Make that a
firmware invariant, not a policy.

### Privacy

- Mic is electrically active only while the button is held. Show it on screen.
- Server keeps **transcripts, not audio**, by default. Discard PCM after STT.
- Add a `voice_log` toggle if you want recordings for debugging, off by default.
- If STT/TTS run locally, no audio ever leaves the house — a genuine advantage
  over every commercial smart speaker, and worth building for.

### Extra protocol additions

| Topic | Dir | Purpose |
|---|---|---|
| `tama/dev/<id>/event` type `voice` | dev→srv | Transcript, for the journal and Telegram mirror |
| `tama/pet/cmd` op `set_volume` | srv→dev | Volume control from Telegram |

Mirror every voice exchange to Telegram as text. You get a free conversation
log, and the pet feels like one continuous being across both faces.

---

## 7. Telegram integration

Keep the bot token **only** in the daemon. The ESP32 never talks to Telegram.
(Two clients polling `getUpdates` on one token fight each other, and the token
does not belong on a device you reflash weekly.)

Commands:

| Command | Effect |
|---|---|
| `/status` | Render stats as a text bar chart + current mood |
| `/feed` `/play` `/clean` | Same code path as a physical button press |
| `/talk <text>` | Full LLM turn; reply goes to Telegram *and* the device screen |
| `/journal` | Last 7 daily entries |
| `/quiet 3h` | Suppress proactive nudges |

Proactive nudges from the daemon: neglect thresholds, illness, evolution,
death warning. Cap at 3/day and respect `/quiet`.

Nice touch: when you talk to it on Telegram, the physical device shows a
"receiving a message" animation. The two faces of the same pet.

---

## 8. Homelab event hooks

A small HTTP endpoint on the daemon: `POST /event` with
`{"source":"restic","severity":"error","summary":"backup failed"}`.

Mapping ideas:

| Event | Pet reaction |
|---|---|
| Backup failed | health −15, expression `sick` |
| All services green 7 days | evolution progress, `excited` |
| Disk > 90% | `grumpy`, complains about being cramped |
| Long Claude Code session | fed (this is the joke `claudigotchi` makes) |

This is the part with no real prior art in a Telegram+homelab shape, and it's
what would make the project yours.

---

## 9. Firmware design (ESP32)

### Tasks (FreeRTOS)

| Task | Prio | Job |
|---|---|---|
| `net` | 2 | WiFi + MQTT keepalive, reconnect backoff |
| `ui` | 3 | 30 fps render loop, sprite animation |
| `input` | 3 | Debounced buttons, PTT edge detect, IMU shake |
| `audio` | 4 | I2S in/out DMA, WS audio session (highest prio — underruns are audible) |
| `sim` | 1 | Local mood decay for offline mode only |

`audio` gets the highest priority because a dropped display frame is invisible
and a dropped audio frame is a click. Give it its own core on the S3 if you can.

### State machine

```
BOOT → WIFI_CONNECT → MQTT_CONNECT → SYNCED
                            │
                            └── (lost) → DEGRADED
```

**DEGRADED mode is a feature.** On disconnect, keep the last state from NVS,
keep animating, run a slow local decay, show a small "disconnected" glyph.
Queue user events (ring buffer, ~32 entries) and flush them on reconnect —
that's why events carry ULIDs.

### Persistence

Store the last `state` JSON in NVS on every change (throttled to once/30s to
save flash wear). Boot renders from that before the network is even up.

---

## 10. Bill of materials

### v1 — WiFi, USB-powered, screen + push-to-talk voice (~€35)

Buy this in Phase 1 even though the mic sits unused until Phase 5. Retrofitting
the board later means redoing the enclosure and the pinout.

- **ESP32-S3 with ≥2 MB PSRAM** — non-negotiable once audio is in scope
  (N16R8 boards are the common choice)
- SSD1306 128×64 OLED (I²C) for chunky 1-bit faces, **or**
  ST7789 1.47" IPS for colour
- **INMP441** I²S MEMS microphone (or ICS-43434) — 16 kHz mono is plenty
- **MAX98357A** I²S amp + small 4 Ω or 8 Ω speaker
- Dedicated **push-to-talk button** on its own GPIO, plus 3 action buttons
- Passive piezo buzzer on LEDC — still worth it for chirps, independent of TTS
- USB-C power (2 A supply; the amp draws real current on peaks)

Pin budget note: I²S mic (3 pins) + I²S out (3 pins) + I²C display (2) +
4 buttons = 12 GPIOs. Comfortable on an S3, tight on a C3.

### v1 alternative — buy the body

Waveshare ESP32-C6-Touch-LCD-1.47 or an M5Stack unit. Both are used by
existing projects in this space, so enclosures and drivers already exist.

---

## 11. v1 build plan (WiFi only)

Five phases. Each one is independently playable — don't start the next until
the current one is boring.

### Phase 0 — daemon only, no hardware

- [ ] Container: Python (or Go/TS) + SQLite, one pod in the homelab
- [ ] State schema from §4.3, `pets` and `events` tables
- [ ] Decay tick from §5 on a 60 s loop
- [ ] Wire up your existing Telegram bot: `/status /feed /play /clean`
- [ ] Canned line table keyed by `(mood, expression)` — **no LLM yet**

**Exit criterion:** play it on Telegram alone for a week. If it isn't fun in a
chat window, a screen will not save it. This is the phase most likely to kill
the project, which is exactly why it goes first and costs €0.

### Phase 1 — dumb body

- [ ] Mosquitto on the LAN, one user for the daemon, one per device
- [ ] Daemon publishes retained `tama/pet/state` on every change
- [ ] ESP32: WiFi + MQTT + LWT, subscribe to state, render a face
- [ ] Buttons → `tama/dev/<id>/event` with ULID + timestamp
- [ ] NVS cache + DEGRADED mode (§9) — unplug the daemon and confirm the pet
      keeps animating

**Exit criterion:** pressing a physical button changes what `/status` says in
Telegram, and killing the pod doesn't kill the pet.

### Phase 2 — the pet speaks

- [ ] `tama/pet/say` with `ttl_s` honoured on the device
- [ ] Sprite/animation table in flash, driven by `expression` + `animation`
- [ ] Buzzer via LEDC — chirps do more for perceived life than any sprite
- [ ] Still canned lines only

**Exit criterion:** it feels alive across a room. Tune timing here, not later.

### Phase 3 — Claude in the loop

- [ ] `Brain` interface + `CannedBrain` first, then one real provider
- [ ] `character.md`, structured JSON output (§6.3), strict validation
- [ ] Fallback chain on any parse failure — the device must never wait on the
      brain
- [ ] `providers.yaml` + routing table (§6.0.2) — even with one provider in it
- [ ] Eval harness (§6.0.4): 30 golden fixtures, `make eval provider=…`
- [ ] Trigger rules + rate limit (§6.1). Log every call with normalised cost
- [ ] `remember()` / memory table, daily journal at 21:00

**Exit criterion:** a week of use under ~40 LLM calls/day, and you're surprised
by something it said.

### Phase 4 — homelab senses

- [ ] `POST /event` webhook, mappings from §8
- [ ] MCP tools so Claude can query real infra state
- [ ] OTA over WiFi (trivial while it's a desk device — do it now, it makes
      every later phase faster)

**Exit criterion:** the pet got visibly upset about something real.

### Phase 5 — push-to-talk voice (§6b)

The mic and amp have been sitting on the board since Phase 1. Now use them.

- [ ] I2S mic capture at 16 kHz mono, gated strictly on the PTT button
- [ ] WSS audio endpoint on the daemon; stream PCM while the button is held
- [ ] `Transcriber` provider (start with local `faster-whisper` small)
- [ ] Route the transcript into the existing `conversation` brain trigger —
      **no changes to §6 at all**
- [ ] `Synthesiser` provider (Piper), streamed back as PCM, I2S out
- [ ] Sentence-level TTS streaming + instant thinking chirp
- [ ] LISTENING / THINKING / SPEAKING states with barge-in
- [ ] Mirror every exchange to Telegram as text

**Exit criterion:** under 1.5 s from button release to first sound, and you
find yourself talking to it without thinking about it.

### Then, and only then → v2

Battery, BLE, keychain enclosure. §11b.

---

## 11a. v1 decisions that keep the BLE door open

Five things to get right now so v2 is an addition, not a rewrite. All of them
are nearly free in v1 and expensive to retrofit.

**1. Abstract the transport in firmware.**
Define a `Transport` interface with `connect()`, `send(topic, payload)`,
`onMessage(cb)`, `isConnected()`. v1 has one implementation, `MqttTransport`.
v2 adds `BleTransport` and nothing above that line changes. This is the single
highest-leverage decision in the document.

**2. Keep the daemon transport-agnostic.**
The daemon's core should consume *events* and emit *state/say*, with MQTT as an
adapter at the edge — not woven through the logic. In v2 the BLE relay becomes
a second adapter publishing to the same internal bus.

**3. Design payloads as if MTU were 247 bytes.**
BLE will cap you there; your §4.3 state JSON is ~400. Define the packed binary
form of `state` and `say` **now** (~24 bytes + a 140-char line), even if v1
sends JSON over MQTT. Write the JSON↔packed codec in the daemon in Phase 1 and
test it. Retrofitting this later means touching every layer.

**4. Never let firmware assume it is always connected.**
DEGRADED mode is in Phase 1 for a reason. In v1 it's a nicety; in v2 it's the
normal state of the world. Build the offline event queue (ULID + `ts` +
`clock_confident` flag) in Phase 1 even though a LAN device rarely needs it.

**5. Don't hardcode one device.**
Topics already carry `<id>`. Make the daemon's device registry a table from
day one, with per-device credentials and an `active_body` pointer. Adding the
keychain in v2 should be an INSERT, not a refactor.

One thing you can safely *not* worry about in v1: power. Deep sleep, wake
sources, and duty cycling touch only the firmware's main loop and can be added
later without disturbing the protocol.

---

## 11b. Roaming: the keychain form factor — **v2, deferred**

The device leaves the house. It is now *mostly disconnected*. Design for that
rather than fighting it.

### The core trick: the simulation is a pure function of time

Decay in §5 depends only on `elapsed_seconds` and the event log. So the device
and the server can compute **the same state independently** with no chatter.

- Server is authoritative. Device runs the identical decay function as a
  *prediction*.
- On sync, server state overwrites device state, silently. No merge logic.
- The device's only real contribution is its **event log** — timestamped,
  ULID'd, queued in NVS while offline, replayed on reconnect. The server
  re-runs the simulation from the last checkpoint with those events folded in
  at their true timestamps.
- This is why events carry `id` and `ts` (§4.2). The whole roaming design
  hangs off those two fields.

Result: an unplugged keychain still gets hungry, still gets sad, and reconciles
perfectly when it next sees the internet. No split brain.

### Connectivity ladder

| Option | Effort | Power | Verdict |
|---|---|---|---|
| Multi-SSID list + phone hotspot | trivial | ok | Fine for a desk unit |
| MQTT over WSS :443 to a rendezvous broker | low | ok | Best if the device has WiFi |
| **BLE tether to the phone** | medium | **best** | **Best for a keychain — see E** |
| WireGuard on the ESP32 | medium | poor | Only if you refuse a broker |
| CAT-M / NB-IoT cellular | high | good | Only if the phone can't be a dependency |

#### A. Multi-SSID + hotspot

Store 4–5 known networks in NVS (home, office, gym, your phone's hotspot).
Scan on wake, connect to the strongest known one, sync, sleep. Add a
provisioning AP (SoftAP + captive portal) for adding networks in the field.

Beware public WiFi captive portals — the ESP32 will associate and think it has
internet. Probe with a HEAD request to a known URL before trusting the link.

#### B. MQTT over WebSocket Secure on port 443 ← recommended

Do **not** expose port 8883 from your homelab. Instead:

```
keychain ──WSS:443──┐
                     ├──▶ rendezvous broker ◀──WSS:443── pet-daemon (homelab)
desk unit  ──MQTT────┘        (VPS or managed)
```

Both the device and your homelab daemon connect **outbound**. No port
forwarding, no dynamic DNS, nothing inbound at home.

Why 443 specifically: captive portals, corporate WiFi, and some mobile
carriers block or mangle everything else. 8883 fails in exactly the places a
keychain lives.

Options for the rendezvous point:

- A €4/mo VPS running Mosquitto with a WSS listener behind Caddy (free TLS).
- Cloudflare Tunnel to your homelab Mosquitto — works because MQTT-over-
  WebSocket is HTTP-shaped. Nothing exposed at home at all.
- A managed broker (HiveMQ Cloud / EMQX Cloud) free tier. Simplest, but a
  third party sees your pet's traffic — payloads are trivial, so probably fine.

The homelab daemon stays the brain either way. The broker is a dumb relay.

#### C. WireGuard on the ESP32

Real and it works — `trombik/esp_wireguard` (ESP-IDF) and
`ciniml/WireGuard-ESP32-Arduino` (Arduino), same lineage as the ESPHome and
Tasmota WireGuard components. Caveats before you commit:

- **Both peers must have synced time.** The library does not sync it — you must
  SNTP first, which means the tunnel can't come up until the clock is right.
- Handshake + crypto cost is real on a battery budget, and it re-handshakes
  every ~2 min while up.
- WiFi interface only; the sample sketches ship with no reconnect logic.
- UDP-based, so it dies behind the same restrictive networks that kill 8883.

Fine for a device that lives on trusted networks. Poor for a keychain.

#### D. Cellular (CAT-M / NB-IoT)

The genuine keychain answer, at a cost. Reference board: **LilyGO
T-SIM7080G-S3** — ESP32-S3 (16MB flash, 8MB PSRAM) plus a SIM7080G supporting
CAT-M and NB-IoT globally, with PSM at ~3.2 µA and sleep at ~0.6 mA, plus GNSS
and an 18650 holder with solar input.

Practical notes:

- The SIM7080G speaks **MQTT natively over AT commands** (and MQTTS via
  `AT+SMSSL`), so the ESP32 doesn't need an MQTT stack at all — it just feeds
  the modem strings. Nice size win.
- TX bursts hit ~500 mA. Power the modem straight from the LiPo, not through
  the 3.3 V LDO, with a fat bulk cap.
- The SIM must be inserted before the modem powers on, and it must be a SIM
  whose carrier actually has CAT-M/NB-IoT enabled — this is the #1 failure.
- An 18650 is not keychain-sized. A real keychain build means a custom PCB with
  a 400–600 mAh LiPo and accepting a ~1×/hour sync cadence.

A pet syncing 24 tiny messages a day is a near-perfect fit for an IoT data plan.

#### E. BLE tether to the phone (the Apple Watch model)

This is architecturally the *right* answer for a keychain. The device has no
WiFi and no SIM; it speaks BLE GATT to your phone, and the phone relays to the
broker over its own internet connection.

**Why it wins**

- **Power.** A BLE connection at a 1–2 s interval averages ~1–3 mA. WiFi +
  MQTT is ~80–120 mA. That is the difference between a day and a month on the
  same cell. It's not a marginal gain, it's the whole ballgame.
- **Security.** No WiFi PSK, no broker credentials, no TLS certs on a losable
  object. The phone holds all the secrets. A found keychain is a plastic toy.
- **Free game mechanic.** BLE RSSI gives you presence for nothing: phone in
  range = owner nearby = pet content; out of range for hours = lonely. The
  pet notices when you come home. That is the single most "alive" feature
  available and it costs one line of firmware.
- **Free clock sync.** The phone writes the time on every connect. No SNTP, no
  RTC drift problem (§ Time above becomes moot on this path).

**Why the Apple Watch analogy is slightly unfair**

The Watch works because Apple ships first-party software with privileged,
essentially unlimited background execution. A third-party BLE app gets a
strictly rationed version of that. It's usable — just don't expect a
persistent, always-live link.

**iOS reality**

Two things are needed: `UIBackgroundModes` = `bluetooth-central` in
Info.plist, and Core Bluetooth **State Preservation and Restoration** via
`CBCentralManagerOptionRestoreIdentifierKey`. With those, iOS preserves your
central manager's state and relaunches the app *into the background* when a
relevant BLE event arrives — specifically peripheral discovery, peripheral
connection, and notifications/indications on a characteristic the app has
subscribed to. That last one is the hook: **the pet notifies, the phone wakes,
the relay runs.**

Caveats, all real:

- Background scanning ignores `allowDuplicates` and **requires an explicit
  service UUID** — the peripheral must advertise your custom service UUID in
  its advertisement data, not just in the GATT table. Easy to get wrong.
- If the user force-quits the app from the app switcher, state restoration
  will not bring it back. A phone reboot also kills it permanently until the
  app is opened once. (CoreLocation / iBeacon monitoring is the usual escape
  hatch, at a privacy and complexity cost.)
- If Bluetooth is turned off or permission revoked, background relaunch stops
  silently and the app has no way to learn this while terminated.
- Background wake-ups are throttled; Apple's own guidance for background-to-
  background BLE discovery is on the order of 1–2 wake-ups per hour. For a
  Tamagotchi syncing a few hundred bytes, that is *completely fine*.
- iOS aggressively caches GATT service definitions. If you change your service
  layout during development, unpair and reboot the phone or you will lose an
  evening.
- Distribution: sideloading with a free Apple developer account requires
  re-signing every 7 days. A paid account ($99/yr) gives a year. Budget for it.

**Android reality**

Much easier. A foreground service with a persistent notification holds the BLE
link indefinitely; request exemption from battery optimisation and it just
works. If you don't want to write an app at all, Tasker or a Termux script can
do the relay.

**The no-app option: Web Bluetooth**

Chrome on Android supports Web Bluetooth; a small PWA can connect to the pet
and POST to your daemon with zero app-store involvement. iOS Safari does not
support it, but the Bluefy browser does. Limitation: it only runs while the
page is in the foreground, so this is a "sync when I glance at it" model
rather than a background tether. Good enough for a first prototype, and a
great way to validate the GATT design before writing anything native.

**GATT design**

Custom 128-bit service. Device is the *peripheral*, phone is the *central*.

| Characteristic | Props | Payload |
|---|---|---|
| `state_in` | write | Authoritative state from server |
| `event_out` | notify | Queued device events, one per notification |
| `say_in` | write | Utterance + expression |
| `time_in` | write | Unix epoch, ms |
| `meta` | read | fw version, battery, queue depth |

Practical notes:

- Negotiate MTU up to 247 bytes. The §4.3 state JSON is ~400 bytes and will
  not fit. **Use a packed binary struct or CBOR for BLE, keep JSON for MQTT** —
  the daemon translates. Packed state is ~24 bytes; only `line` needs real
  text, and 140 chars fits in one MTU.
- The `event_out` notification is what wakes the iOS app. Keep the pet
  notifying on any user interaction, even if the payload is empty.
- Use **NimBLE**, not Bluedroid — roughly 100 KB less flash and far less RAM.

**Recommended: BLE primary, WiFi at home**

Don't choose. Provision the keychain with home WiFi only, and:

- **Out of the house:** BLE to phone. Trickle sync, presence, tiny payloads.
- **At home / on the charger:** WiFi + MQTT directly. Full-fidelity sync, OTA
  firmware updates, log upload, big payloads.

OTA over BLE is miserable; OTA over WiFi while docked is trivial. This split
gives you the best of both and lets you skip cellular entirely.

**Suggested build order:** Web Bluetooth PWA first (an afternoon, validates the
GATT contract), then an Android foreground service or an iOS app with state
restoration once the protocol has stopped changing.

### Power budget for a keychain

Always-on WiFi + MQTT keepalive is ~80–120 mA. On a 500 mAh cell that's a few
hours. So: deep sleep, and wake on three triggers only.

| Trigger | Action |
|---|---|
| Button press / shake (ext0/ext1 wake) | Wake, render, queue event, sync if due |
| Timer, every 15–30 min | Connect, flush queue, pull state, sleep |
| Low battery | Stop syncing, render a "tired" face, sleep 4h |

A sync cycle is roughly: wake (0.2s) → WiFi assoc (2–4s) → TLS + MQTT (1–2s) →
exchange (0.5s) → sleep. Call it 6s at ~120 mA ≈ 0.2 mAh per sync. At 2 syncs
an hour that's ~10 mAh/day of radio — days to weeks of runtime, dominated by
the display, not the network.

Keep the display in the deepest partial-refresh mode you can; consider a small
e-paper panel for a keychain, where a static face costs nothing between wakes.

### Security for a losable object

Assume the keychain will be left in a taxi.

- **Per-device credentials.** Unique MQTT username/password or, better, an
  mTLS client cert. Never the same secret as the desk unit.
- **Broker ACLs.** The device may publish only to `tama/dev/<its-own-id>/#`
  and subscribe only to `tama/pet/#`. It must not be able to impersonate the
  daemon or read anything else.
- **Revocation.** One command in the daemon that kills a device's cert/user and
  rotates. Test it before you need it.
- **Don't put your main WiFi PSK on it.** Give it a separate IoT SSID, or
  hotspot-only, so a found keychain isn't a house key.
- Journal and memory stay server-side. The device caches state, not secrets or
  history.

### Time

Deep sleep preserves the RTC, but it drifts. SNTP on every successful sync,
store `last_sync_ts` and `rtc_offset` in RTC memory, and mark queued events
with a `clock_confident` flag so the server knows whether to trust the device's
timestamp or fall back to arrival time.

### Suggested end state: two bodies, one pet

- **Desk unit** — USB-powered, always connected, bigger screen, mic/speaker,
  the "home" of the pet.
- **Keychain** — deep-sleeping, offline-first, e-paper or small OLED, syncs
  opportunistically.

Both subscribe to `tama/pet/state`. The daemon tracks which body is "active"
(most recent event wins) and routes `say` messages there, so the pet feels like
it *moved* with you rather than being duplicated. Add a `tama/pet/presence`
topic if you want the desk unit to show an empty room while you're out.

---

## 12. Prior art

Nothing found does exactly *ESP32 pet + self-hosted Claude daemon + Telegram*,
but every individual piece exists and is worth reading before writing code.

**Closest in spirit**

- **`jsprpalm/claudigotchi`** — a desk Tamagotchi fed by Claude Code usage.
  ESP32-C6 + LCD + piezo, a Claude Code plugin hooks session events, a Mac
  daemon holds a USB serial link and pushes JSON to the device. Same
  daemon-owns-state pattern; swap serial for MQTT and it's your architecture.
  <https://github.com/jsprpalm/claudigotchi>
- **`MaliosDark/Sablina-Tamagotchi-ESP32`** — ESP32-S3 pet with Telegram
  control, BLE peer interaction, evolving personality traits, and an offline
  LLM-ish thought engine. The Telegram half of your idea, already built.
  <https://github.com/MaliosDark/Sablina-Tamagotchi-ESP32>
- **Pixel-Pets (M5Stack)** — a local virtual-pet ecosystem with an LLM variant
  ("Muffin"), Whisper, ESP-NOW peer devices, offline-first.

**Voice / AI-companion stacks worth stealing from**

- **`78/xiaozhi-esp32`** — by far the most mature. 170+ board variants across
  C3/S3/P4, WebSocket *and* MQTT+UDP transports, Opus streaming, and MCP built
  in so the backend can discover and call tools on the device. Its companion
  server (`xiaozhi-esp32-server`) is Docker-deployable and has swappable LLM
  providers — a plausible shortcut for Phase 4.
  <https://github.com/78/xiaozhi-esp32>
- **`akdeb/OpenToys`** (formerly ElatoAI) — ESP32-S3 realtime AI toys.
- **`StarmoonAI/Starmoon`** — empathic AI companion hardware + software.
- **ESP-SparkBot** (Espressif) — official open-source S3 conversation robot.

**Pure Tamagotchi references (art, sprites, game loop)**

- `nthnn/tomo` — handheld emotion pet, Piskel facial animations.
- `CyberXcyborg/ESP32-TamaPetchi` — full stat/day-night/minigame loop, WS API.
- `derdacavga/Esp32-Tamagotchi` — ESP32-C3 + ST7789, modular sprite pipeline.

**Software-only, for personality inspiration**

- `Ido-Levi/claude-code-tamagotchi`, `vincent-k2026/codachi` — pets living in
  the Claude Code statusline, reacting to tool events. Good source of ideas
  for *what* the pet should have opinions about.

---

## 13. Open questions to decide before Phase 0

1. Mortality: permanent death, or revivable? Changes the emotional contract.
2. Does the pet initiate on Telegram, or only respond? (Recommend: yes, capped.)
3. One personality forever, or does it drift based on how you treat it?
4. Colour screen or 1-bit? 1-bit is more charming and far less work.
5. Does the pet know it's an AI? `character.md` should be explicit either way.

Questions 1–3 and 5 are answerable in Phase 0 with no hardware at all. Question
4 can wait until Phase 1.
