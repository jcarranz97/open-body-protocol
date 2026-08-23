# TAMALAB

**TAMALAB** is a physical desk pet — an ESP32 with a face — whose brain,
memory and personality live in a container in a homelab. The device is a
*body*, not a computer: it renders a face, reads buttons and a microphone,
and caches the last known state so it keeps being charming when the network
is not. Everything that decides *who the pet is* runs on the server, and is
reachable from both the device and Telegram.

Three ideas hold it together:

- **The daemon owns the truth.** The ESP32 holds a cached copy only. Reflash
  it, unplug it, replace it — the pet is unaffected.
- **The simulation is deterministic and LLM-free.** Hunger and mood decay are
  a pure function of elapsed time and the event log. The pet works with the
  brain unplugged; the LLM adds personality, never state.
- **The brain is a config value.** Local (Qwen via Ollama), cloud (Claude, or
  anything OpenAI-compatible), or none at all — behind one narrow interface,
  with a canned-line table as the permanent last fallback.

> **Status: Phase 0 — design only.** This repository currently contains
> documentation and no code. The architecture is being written first,
> deliberately: see [`docs/`](docs/).

## Documentation

The docs are [MkDocs Material](https://squidfunk.github.io/mkdocs-material/).
To read them locally:

```bash
python -m venv .venv && source .venv/bin/activate
pip install mkdocs-material
mkdocs serve          # http://127.0.0.1:8000
```

`mkdocs build --strict` is what CI runs on every pull request; pushes to
`main` deploy to GitHub Pages via `.github/workflows/deploy-docs.yml`.

| Document | What it covers |
|---|---|
| [Home](docs/index.md) | What the pet is and how the pieces fit |
| [Roadmap](docs/roadmap.md) | Five phases, each independently playable |
| [Requirements](docs/requirements.md) | Numbered `FR`/`NFR` requirements the architecture cites |
| [Open Questions](docs/open-questions.md) | Decisions to make before Phase 0 |
| [Architecture](docs/architecture/overview.md) | Protocol, simulation, brain, voice, firmware, hardware |
| [Original Brief](docs/brief.md) | The seed document, kept verbatim |

## Planned layout

Nothing below exists yet. It is here so the docs can refer to it.

```text
daemon/      Python + SQLite. Owns state, runs the sim tick, hosts the brain,
             the Telegram bot and the homelab webhook.
firmware/    ESP32-S3. Display, buttons, buzzer, I2S mic + speaker.
docs/        These documents.
```

## License

[MIT](LICENSE). The design documents and, when they exist, the daemon and
firmware are free to use, fork and adapt.
