# Prior Art

Who else is building pieces of the Open Body Protocol (OBP) problem, and
under which licences.

Nothing found does exactly *ESP32 pet + self-hosted brain + Telegram +
homelab events*, but every individual piece exists and is worth reading
before writing code. The gap is narrow enough to be worth being honest about:
what makes this project its own is the [external
events](https://github.com/jcarranz97/desk-buddy/blob/main/docs/https://github.com/jcarranz97/desk-buddy/blob/main/docs/architecture/integrations.md), not the Tamagotchi.

## Closest in spirit

- **[`jsprpalm/claudigotchi`](https://github.com/jsprpalm/claudigotchi)** — a
  desk Tamagotchi fed by Claude Code usage. ESP32-C6 + LCD + piezo, a plugin
  hooks session events, and a Mac daemon holds a USB serial link and pushes
  JSON to the device. **The same daemon-owns-state pattern**; swap serial for
  MQTT and it is this architecture.
- **[`MaliosDark/Sablina-Tamagotchi-ESP32`](https://github.com/MaliosDark/Sablina-Tamagotchi-ESP32)**
  — ESP32-S3 pet with Telegram control, BLE peer interaction, evolving
  personality traits and an offline thought engine. The Telegram half of this
  idea, already built.
- **Pixel-Pets (M5Stack)** — a local virtual-pet ecosystem with an LLM
  variant, Whisper, ESP-NOW peer devices, offline-first.

## Voice and AI-companion stacks worth stealing from

- **[`78/xiaozhi-esp32`](https://github.com/78/xiaozhi-esp32)** — by far the
  most mature. 170+ board variants across C3/S3/P4, WebSocket *and* MQTT+UDP
  transports, Opus streaming, and MCP built in so the backend can discover
  and call tools on the device. Its companion server is Docker-deployable
  with swappable LLM providers — a plausible shortcut, and the source of the
  control/audio transport split used here ([voice](https://github.com/jcarranz97/desk-buddy/blob/main/docs/architecture/voice.md)).
- **`akdeb/OpenToys`** (formerly ElatoAI) — ESP32-S3 realtime AI toys.
- **`StarmoonAI/Starmoon`** — empathic AI companion hardware and software.
- **ESP-SparkBot** (Espressif) — official open-source S3 conversation robot.

## Pure Tamagotchi references — art, sprites, game loop

- `nthnn/tomo` — handheld emotion pet, Piskel facial animations.
- `CyberXcyborg/ESP32-TamaPetchi` — full stat / day-night / minigame loop
  with a WebSocket API.
- `derdacavga/Esp32-Tamagotchi` — ESP32-C3 + ST7789, modular sprite pipeline.

## Agent-driven pets — the closest prior art of all

This is the crowded part, and it was not obvious until we went looking. If
you read only two things here, read the first two.

- **[`alvinunreal/openpets`](https://github.com/alvinunreal/openpets)** —
  MIT, active. A local-first pet platform whose virtual-pet plugin tracks
  **hunger, affection and energy**, and whose agent layer lets Claude Code,
  OpenCode, Cursor and other MCP clients drive the pet's reactions through an
  MCP server. Substantially the same idea as
  [MCP § inbound](guides/using-obp-with-mcp.md),
  already built. Read it before writing `obp-mcp`.
- **`geeks-accelerator/animal-house-ai-tamagotchi`** — MIT, tiny, and sharply
  framed: *"Tamagotchi for AI agents"*, delivered purely as an MCP server
  with no HTTP at all. **The pet is the tool surface and the agent is the
  caretaker** — the exact inverse of this design, where the pet has its own
  brain and merely accepts visitors. Worth reading to be sure which way round
  you want it.
- **Claude Code Channels** — a first-party extension point where *a channel
  is an MCP server* pushing external events into a running session, with
  Telegram and Discord plugins shipped and a documented build-your-own path.
  An "OBP channel" is a legitimate design rather than a hack.
- **[`petdex`](https://github.com/crafter-station/petdex)** — not a pet
  project but a **sprite format**: `pet.json` plus a spritesheet of 192×208
  cells over nine named states, with a public gallery and a generator. Nous
  Research's Hermes ships an MIT Python decoder and terminal renderer for it
  (`agent/pet/render.py`), directly reusable for the
  [terminal body](https://github.com/jcarranz97/desk-buddy/blob/main/docs/architecture/terminal-body.md). Its nine states do not map cleanly
  onto this project's expression vocabulary, so adopting it is a deliberate
  choice, not a drop-in.

!!! note "Hermes 'pets' are not pets"
    Nous Research's `hermes-agent` has a documented pets feature, and it is
    **cosmetic sprite mascots only** — *"no effect on prompt caching, tokens,
    or the agent's behavior"*. No stats, no persistence, no tick, no tools,
    and no route on its HTTP API. What Hermes usefully offers this project is
    an **OpenAI-compatible API server**, not a pet
    ([brain](https://github.com/jcarranz97/desk-buddy/blob/main/docs/architecture/brain.md)).

## Embodied companions

- **`anthropics/claude-desktop-buddy`** — a first-party ESP32-S3 desk
  companion on ~$30 hardware, where you approve or deny the agent's actions
  with **physical buttons over BLE**, the interaction staying local. The
  nearest thing to an official version of this form factor.
- **`elliotboney/shelldon`** — MIT. *"A tiny AI creature that lives on an
  E-Ink screen, chats with a remote LLM brain."* Almost unknown, and it is
  precisely this project's thin-device / remote-brain split.
- **Espressif's own MCP client and server examples for ESP32** — relevant if
  the body should one day be a tool an agent calls, rather than a thing that
  calls tools.

## Software-only, for personality inspiration

- `Ido-Levi/claude-code-tamagotchi`, `vincent-k2026/codachi` — pets living in
  a terminal statusline, reacting to tool events. A good source of ideas for
  *what the pet should have opinions about*, and the closest prior art to
  the [terminal body](https://github.com/jcarranz97/desk-buddy/blob/main/docs/architecture/terminal-body.md): a pet that lives where the work
  happens is a different feeling from one that lives on a desk, and the
  terminal ones tend to be tied to a single tool's lifecycle. This pet is
  not — it is the same creature the ESP32 and Telegram see, and it outlives
  whatever is running in the next pane.

## Licensing, before you copy anything

This repository is MIT. Two traps found while researching the above:

- ⚠️ **`MaliosDark/Sablina-Tamagotchi-ESP32` is GPL-2.0** — contagious. It is
  listed here because it is worth reading, not because it is worth copying.
- ⚠️ **Several agent↔Telegram bridges carry no licence at all**, which means
  no permission to reuse, however useful they look. Treat an unlicensed
  repository as a read-only reference.

Where a project is named above without a licence note, check before
vendoring, not after.
