# Hardware

What to buy, and the one decision that cannot be deferred.

!!! warning "Buy the S3 with PSRAM in Phase 1"
    Nothing uses the microphone until Phase 5. Buy the board that can do
    voice anyway (FR-110): retrofitting it later means redoing the enclosure
    and the pinout, and the price difference is a few euros.

## v1 — WiFi, USB-powered, screen and push-to-talk voice (~€35)

- **ESP32-S3 with ≥2 MB PSRAM** — non-negotiable once audio is in scope
  (N16R8 boards are the common choice, and 8 MB is plenty)
- **SSD1306 128×64 OLED (I²C)** for chunky 1-bit faces, **or**
  **ST7789 1.47" IPS** for colour
- **INMP441** I²S MEMS microphone (or ICS-43434) — 16 kHz mono is plenty
- **MAX98357A** I²S amp plus a small 4 Ω or 8 Ω speaker
- A **dedicated push-to-talk button on its own GPIO**, plus 3 action buttons
- A passive **piezo buzzer** on LEDC — still worth having for chirps,
  independent of TTS
- **USB-C power, 2 A supply** — the amp draws real current on peaks

### Pin budget

| Function | Pins |
|---|---|
| I²S mic | 3 |
| I²S out | 3 |
| I²C display | 2 |
| Buttons (3 action + PTT) | 4 |
| **Total** | **12** |

Comfortable on an S3, tight on a C3 — which is the other half of the argument
for the S3, alongside PSRAM and the second core for the audio task
([firmware](firmware.md)).

## 1-bit or colour

The [open question](../open-questions.md) that can wait until Phase 1, but
the bias is toward **1-bit**: it is more charming, the sprite work is a
fraction of the effort, and a monochrome OLED at 128×64 is legible across a
room in a way a 1.47" colour panel is not.

Colour buys expressiveness the art has to earn. If the sprites are not
already good in black and white, colour will not save them.

## Buying the body instead

Waveshare **ESP32-C6-Touch-LCD-1.47** or an **M5Stack** unit. Both are used
by existing projects in this space, so enclosures and drivers already exist.

The trade is real: a ready-made body gets Phase 1 and 2 done in a weekend,
and then Phase 5 needs a mic and a speaker that the enclosure has no room
for. Good choice for validating whether the *game* is fun; poor choice as the
final object if voice is wanted.

## The piezo earns its place

Independently of TTS. Chirps do more for perceived life per line of code than
any sprite work — a rising chirp on being fed, a flat one on being ignored —
and they work in Phase 2, long before there is a voice pipeline
([voice](voice.md)).

## What v1 deliberately does not buy

- **A battery.** USB-powered on a desk, full stop. Power management is the
  one thing safely deferred to v2 — it touches only the firmware's main loop
  and no protocol.
- **A SIM or BLE-only board.** Both are v2 questions
  ([roaming](roaming.md)).
- **An e-paper panel.** Right for a keychain that shows a static face between
  wakes; wrong for a desk pet that should blink.
