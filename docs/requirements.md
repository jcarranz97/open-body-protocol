# Requirements

## 1. Introduction

### 1.1 Purpose

This document specifies **Open Body Protocol**: a physical desk pet whose state, memory
and personality live in a homelab container. It defines what the system must
do and under which constraints. Every requirement carries a stable identifier
(`FR-NNN`, `NFR-NNN`) that the architecture pages cite back.

Identifiers are allocated from one flat sequence per prefix and are **never
renumbered**. A new requirement takes the next free number and is then filed
into the topically correct section, so section numbering is not contiguous
and gaps are expected.

### 1.2 Scope

**The daemon is one container on one machine.** A laptop, a mini PC, a
Raspberry Pi or a homelab cluster are all supported hosts, and the pet is
identical on each; nothing in this specification may assume an orchestrator,
a reverse proxy or a public hostname.

**v1 is WiFi-only, home network, USB-powered.** One pet, one owner, three
faces: an ESP32-S3 desk device on the LAN, a Telegram bot, and a terminal
application. The hardware is optional — a user with only the terminal body
has the complete pet. The pet has
persistent state that survives reflashing, a deterministic simulation that
needs no LLM, an optional pluggable brain that gives it personality, and a
webhook that lets homelab events reach it. Voice is push-to-talk only, and is
the last v1 feature built.

Out of scope for v1: on-device inference, battery and portability, BLE,
cellular, WireGuard, wake words, always-on listening, a desktop GUI, and
multi-user or multi-pet operation. The BLE keychain is v2 and is designed for only to the
extent of FR-060 – FR-063.

### 1.3 Definitions

| Term | Means |
|---|---|
| **body** | Anything that renders the pet and reports events — the ESP32, the terminal, Telegram. Hardware is not implied. |
| **daemon** | The homelab container. The pet's authority. |
| **state** | The full snapshot: stats, mood, stage, age. |
| **say** | One utterance plus expression, animation and sound. |
| **event** | Something that happened to the pet, carrying a ULID and a timestamp. |
| **brain** | The pluggable component that turns a trigger into a `say`. |
| **trigger** | Why the brain was called: `idle`, `conversation`, `journal`, `homelab`. |

## 2. Overall description

The daemon owns the truth; the device is a cached view of it with inputs
attached. The simulation is a pure function of elapsed time and the event
log, so the same state can be derived independently on both sides and the
device's copy can always be overwritten without merging.

Everything a language model does is additive: the pet is fully playable with
every model switched off.

## 3. Functional requirements

### 3.1 Product

| ID | Requirement |
|---|---|
| FR-001 | The pet's state SHALL persist across device reflashes, reboots and replacements. |
| FR-002 | The pet SHALL be fully playable through Telegram alone, with no hardware present. |
| FR-003 | The pet SHALL remain animated and responsive on the device while the daemon is unreachable. |
| FR-004 | The system SHALL support exactly one pet and one owner in v1. |
| FR-005 | The pet SHALL be functional with every LLM provider disabled or unreachable. |

### 3.2 Device protocol

| ID | Requirement |
|---|---|
| FR-010 | Control traffic SHALL use MQTT with a `obp/` topic prefix, with device topics keyed by a device id. |
| FR-011 | The device SHALL register a Last Will and Testament on `obp/body/<id>/status`; the daemon SHALL do the same on `obp/srv/status`. |
| FR-012 | The device SHALL announce firmware version and capabilities on boot via `hello`. |
| FR-013 | Every device event SHALL carry a ULID, and the daemon SHALL deduplicate on it. |
| FR-014 | Every payload SHALL carry a schema version `v` and an RFC3339 UTC timestamp `ts`. |
| FR-015 | The daemon SHALL accept every schema version it has ever emitted; the device need only understand its own. |
| FR-016 | Device credentials SHALL be per-device, and broker ACLs SHALL restrict a device to its own `obp/body/<id>/#` and to `obp/#`. |

### 3.3 Simulation

| ID | Requirement |
|---|---|
| FR-020 | The simulation SHALL be deterministic and SHALL NOT invoke a language model. |
| FR-021 | Decay SHALL be computed from elapsed time, so a missed tick applies the full elapsed interval on the next one. |
| FR-022 | Stats SHALL be `hunger`, `energy`, `hygiene`, `social` and `health`, each clamped to 0..100. |
| FR-023 | On sync, server state SHALL overwrite device state without merging. |
| FR-024 | Mood SHALL be derived from stats on read and SHALL NOT be stored as authoritative. |
| FR-025 | Death SHALL require `health == 0` sustained for 6 consecutive hours, and `alive: false` SHALL be rendered distinctly from a disconnected state. |
| FR-026 | The event log SHALL be durable and SHALL NOT be compacted; checkpoints exist only to shorten replay. |

### 3.4 State and rendering

| ID | Requirement |
|---|---|
| FR-030 | The daemon SHALL publish the full state to `obp/state` as a retained message on every change. |
| FR-031 | The device SHALL render from `expression`, `animation` and `mood` ids only; the server SHALL NOT send sprite data. |
| FR-032 | A `say` SHALL carry `ttl_s`, and the device SHALL discard one received after expiry. |
| FR-033 | `say` SHALL NOT be retained. |
| FR-034 | The device SHALL accept `cmd` operations for brightness, volume, reboot, sync and OTA. |

### 3.5 Offline behaviour

| ID | Requirement |
|---|---|
| FR-040 | The device SHALL cache the last state in NVS, throttled to at most one write per 30 s. |
| FR-041 | On loss of connectivity the device SHALL enter DEGRADED mode: keep rendering, run local decay as a prediction, and show a disconnected indicator. |
| FR-042 | Events generated offline SHALL be queued with their true timestamps and a `clock_confident` flag, and flushed on reconnect. |
| FR-043 | The offline event queue SHALL be bounded (≈32 entries) and SHALL drop oldest-first when full. |

### 3.6 Triggers

| ID | Requirement |
|---|---|
| FR-050 | The simulation SHALL emit a `mood_changed` event on transition only, not per tick. |
| FR-051 | Neglect thresholds at 4 h, 12 h and 24 h since the last interaction SHALL each fire once and re-arm only after an interaction. |
| FR-052 | A daily journal entry SHALL be written once per day at a configured local time. |

### 3.7 Architecture

| ID | Requirement |
|---|---|
| FR-060 | The daemon core SHALL consume events and emit state and `say` over an internal bus; MQTT, Telegram, HTTP and audio SHALL be edge adapters. |
| FR-061 | The firmware SHALL address the network through a `Transport` interface with exactly one v1 implementation. |
| FR-062 | Devices SHALL be rows in a registry table with per-device credentials and an `active_body` pointer. |
| FR-063 | A packed binary form of `state` and `say` fitting a 247-byte MTU SHALL be defined and unit-tested in the daemon in Phase 1, even though v1 transmits JSON. |
| FR-064 | Adding a new face (dashboard, second body) SHALL require no change to the daemon core. |

### 3.8 The brain

| ID | Requirement |
|---|---|
| FR-070 | The brain SHALL be reached through one narrow interface returning a single validated JSON object. |
| FR-071 | The brain SHALL influence the simulation only through a bounded `mood_nudge` (−10..+10) and durable memories; it SHALL NOT set stats directly. |
| FR-072 | Every provider SHALL run `constrain → parse → validate → clamp enums`, falling back to a canned line on any failure. |
| FR-073 | Providers SHALL be selected per trigger by a configured route chain. |
| FR-074 | Every route chain SHALL terminate in the canned provider; the daemon SHALL refuse to start otherwise. |
| FR-075 | Spontaneous brain calls SHALL be rate limited to at most 1 per 15 minutes and ~40 per day. |
| FR-076 | Token usage and cost SHALL be normalised at the adapter boundary and logged per call. |
| FR-077 | An eval harness SHALL score any configured provider against a fixture set for schema validity, enum range, length and character. |
| FR-078 | Tools SHALL be offered to the cloud tier only; local providers SHALL receive pre-fetched context instead. |

### 3.9 Voice

| ID | Requirement |
|---|---|
| FR-080 | Audio SHALL use a dedicated WebSocket session opened on button-down and closed after playback, never MQTT. |
| FR-081 | A transcript SHALL enter the brain as an ordinary `conversation` trigger, requiring no change to the brain. |
| FR-082 | Transcription and synthesis SHALL be pluggable providers configured alongside the brain, with a local-only configuration fully supported. |
| FR-083 | Synthesis SHALL begin on the first complete sentence rather than the full response. |
| FR-084 | The device SHALL respond to button release with an immediate chirp and thinking animation. |
| FR-085 | The device SHALL support barge-in: pressing the button during playback stops it and starts a new recording. |

### 3.10 Telegram

| ID | Requirement |
|---|---|
| FR-090 | Telegram commands SHALL enter the system as the same events a physical button produces. |
| FR-091 | Proactive messages SHALL be capped at 3 per day and SHALL respect a `/quiet` window. |
| FR-092 | The bot token SHALL exist only in the daemon. |
| FR-093 | Voice exchanges SHALL be mirrored to Telegram as text, and Telegram messages SHALL be reflected on the device screen. |

### 3.11 Homelab events

| ID | Requirement |
|---|---|
| FR-100 | The daemon SHALL expose `POST /event` accepting `source`, `severity` and `summary`. |
| FR-101 | Event-to-reaction mapping SHALL be configuration, not code. |
| FR-102 | An unmapped source SHALL be logged and journaled without altering stats. |
| FR-103 | Repeated identical `(source, severity)` events SHALL collapse within a window, firing the brain at most once. |

### 3.12 Hardware

| ID | Requirement |
|---|---|
| FR-110 | The v1 board SHALL be an ESP32-S3 with ≥2 MB PSRAM, purchased in Phase 1 with the microphone and amplifier fitted. |
| FR-111 | Push-to-talk SHALL have a dedicated GPIO, separate from the action buttons. |
| FR-112 | A passive piezo buzzer SHALL be present independently of any TTS capability. |

### 3.13 Bodies and the terminal client

| ID | Requirement |
|---|---|
| FR-120 | A body SHALL be defined by the protocol it speaks, not by being hardware; the terminal client SHALL be a body under the same contract, TTLs and authority rules as the ESP32. |
| FR-121 | The terminal client SHALL register in the device registry with a distinct id and a `caps` list that omits capabilities it does not have. |
| FR-122 | The terminal client SHALL offer a solo mode that runs the daemon core in-process against a local database, requiring no broker, container or network. |
| FR-123 | Solo mode SHALL use the same core, simulation and adapters as the daemon service; the simulation SHALL NOT be reimplemented for it. |
| FR-124 | The terminal client SHALL cache the last state locally and keep rendering when the daemon is unreachable. |
| FR-125 | Events generated by the terminal client while disconnected SHALL be queued with their original ULIDs and timestamps and flushed on reconnect. |
| FR-126 | Multiple terminal clients SHALL run simultaneously, each with a distinct id; in v1 `say` is delivered to every subscribed body. |
| FR-127 | The terminal client SHALL map `expression` and `animation` ids to its own art; the server SHALL NOT send art in any medium. |
| FR-128 | The terminal client SHALL render legibly without colour and without Unicode. |
| FR-129 | The terminal client SHALL offer the interactions a hardware body offers — feed, play, clean, pet — plus a text prompt for conversation. |
| FR-130 | The terminal client SHALL be runnable without a checkout or a virtualenv, via a single `uvx` command. |
| FR-131 | Transport, state cache, event queue, ULID generation and TTL handling SHALL live in a reusable client package that any body may import; the terminal client SHALL be its reference consumer. |

### 3.14 The sense tier

| ID | Requirement |
|---|---|
| FR-140 | The system SHALL distinguish a **voice tier**, which produces the pet's utterances, from an optional **sense tier**, which produces facts about the world. A sensor SHALL NOT produce an utterance, an expression or an animation. |
| FR-141 | A sensor SHALL NOT appear in a `routes:` chain, and no body SHALL ever wait on one. Its output SHALL enter the next utterance as context. |
| FR-142 | `latency_class` SHALL admit a third value for agentic providers, with its own timeout budget distinct from `fast` and `slow`. |
| FR-143 | The daemon SHALL enforce the `line` length limit itself — validating, retrying once, then truncating on a word boundary. The limit SHALL NOT be relied upon from the output schema, which does not enforce string length. |

### 3.15 MCP

| ID | Requirement |
|---|---|
| FR-150 | The daemon SHALL be able to act as an MCP **client** and as an MCP **server**, independently; neither SHALL be a precondition of the other. |
| FR-151 | The daemon SHALL run its own MCP client rather than relying on a hosted connector, so that stdio and private in-network servers are reachable. |
| FR-152 | Pet state SHALL be exposed as a tool, not as a resource. |
| FR-153 | An inbound MCP call SHALL enter the core as an ordinary event with a ULID, indistinguishable from a button press; there SHALL be no agent-specific path through the core. |

### 3.16 Deployment

| ID | Requirement |
|---|---|
| FR-160 | The daemon SHALL run as a single container with a single writable volume, requiring no orchestrator, reverse proxy, public hostname or inbound port. |
| FR-161 | Published images SHALL support x86-64 and arm64, so a Raspberry Pi is a supported host. |
| FR-162 | No deployment SHALL require an inbound connection from the internet. Telegram SHALL be reached by outbound polling; bodies SHALL reach the daemon over the local network. |
| FR-163 | The reference compose file SHALL include a broker, so a first install needs one command and no prior infrastructure. An existing broker SHALL be usable instead, by configuration. |
| FR-164 | One image SHALL serve every deployment shape; differences SHALL be configuration only, never a separate build or a second implementation of the core. |
| FR-165 | The daemon SHALL start and run with no API keys, no Telegram token and no configuration file, falling back to canned lines and whichever bodies are present. |

## 4. Non-functional requirements

| ID | Requirement |
|---|---|
| NFR-001 | The device SHALL render a face within ~1 s of power-on, before network association. |
| NFR-002 | Brain calls SHALL time out at 8 s (local tier) and 15 s (cloud tier) and fall through. |
| NFR-003 | The first synthesised sound SHALL be heard within 1.5 s of button release under a local-only configuration. |
| NFR-004 | STT SHALL time out at 5 s and TTS at 5 s, falling back to a canned line and a confused animation. |
| NFR-005 | No user-visible path SHALL block on a language model. |
| NFR-006 | The daemon SHALL run as a single container with a single writable volume. |
| NFR-007 | A missed simulation tick SHALL never produce incorrect state, only a delayed one. |
| NFR-008 | Audio SHALL have the highest firmware task priority; dropped display frames are acceptable, dropped audio frames are not. |
| NFR-009 | NVS writes SHALL be throttled to preserve flash endurance. |
| NFR-010 | The microphone SHALL be electrically active only while the push-to-talk button is held, and this SHALL be visible on screen. |
| NFR-011 | Secrets — bot token, API keys — SHALL exist only on the daemon, never on a device. |
| NFR-012 | OTA images SHALL be verified against a SHA-256 supplied out of band before flashing. |
| NFR-013 | Audio SHALL be discarded after transcription by default; only transcripts are retained. |
| NFR-014 | The terminal client SHALL redraw only on a state change or an animation frame, at no more than 8 fps, and SHALL fall to a slow idle cadence after a period without events. |
| NFR-015 | The terminal client SHALL render a face within 1 s of launch, from cache, before any connection is established. |
| NFR-016 | Solo mode SHALL require no broker, no container and no network. |
| NFR-017 | A body in connected mode SHALL hold no credential beyond its own broker login. A machine running the core in solo mode is a daemon for the purposes of NFR-011, and SHALL read any provider credentials from the environment or a user config file, never from the repository. |
| NFR-018 | Timeouts SHALL be set per latency class — 8 s `fast`, 15 s `slow`, 60 s `agentic` — and expiry SHALL fall through the chain rather than failing the turn. |
| NFR-019 | A sensor's failure or timeout SHALL degrade only the specificity of what the pet says, never whether it reacts. |
| NFR-020 | A harness SHALL be run with ambient configuration discovery disabled, so that no hook, settings file or MCP server is loaded from a working directory the daemon did not author. |
| NFR-021 | No MCP tool exposed by the daemon SHALL perform an irreversible action, execute a command, or return provider credentials. |
| NFR-022 | The daemon SHALL run within approximately one CPU core and 256 MB of RAM, excluding any locally hosted model. |
| NFR-023 | A default installation SHALL produce a working pet from a single command, with no credentials configured. |
| NFR-024 | A host that suspends SHALL NOT corrupt or desynchronise state; on resume the daemon SHALL fold the whole elapsed interval in one step. |
| NFR-025 | The pet's entire persistent state SHALL be a single file, so that backing it up is copying it. |
