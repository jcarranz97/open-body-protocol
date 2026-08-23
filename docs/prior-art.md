# Prior Art

Nothing found does exactly *ESP32 pet + self-hosted brain + Telegram +
homelab events*, but every individual piece exists and is worth reading
before writing code. The gap is narrow enough to be worth being honest about:
what makes this project its own is the [homelab
senses](architecture/integrations.md#homelab-events), not the Tamagotchi.

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
  control/audio transport split used here ([voice](architecture/voice.md)).
- **`akdeb/OpenToys`** (formerly ElatoAI) — ESP32-S3 realtime AI toys.
- **`StarmoonAI/Starmoon`** — empathic AI companion hardware and software.
- **ESP-SparkBot** (Espressif) — official open-source S3 conversation robot.

## Pure Tamagotchi references — art, sprites, game loop

- `nthnn/tomo` — handheld emotion pet, Piskel facial animations.
- `CyberXcyborg/ESP32-TamaPetchi` — full stat / day-night / minigame loop
  with a WebSocket API.
- `derdacavga/Esp32-Tamagotchi` — ESP32-C3 + ST7789, modular sprite pipeline.

## Software-only, for personality inspiration

- `Ido-Levi/claude-code-tamagotchi`, `vincent-k2026/codachi` — pets living in
  a terminal statusline, reacting to tool events. A good source of ideas for
  *what the pet should have opinions about*.
