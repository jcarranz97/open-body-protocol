# TAMALAB

**TAMALAB** is a desk pet whose brain, memory and personality live in a
container — **one container and one volume, on whatever machine you have**: a
laptop, a mini PC, a Raspberry Pi, or a homelab if you run one. What you look
at is a **body**, and there are three, none of them primary:

| Body | What it is |
|---|---|
| **Device** | An ESP32-S3 with a screen, buttons, a buzzer and push-to-talk voice |
| **Terminal** | A Python + [Rich](https://rich.readthedocs.io/) TUI, for a pet in a pane next to your work |
| **Telegram** | The same pet, as text, on your phone |

**The hardware is optional, and so is the infrastructure.** A pet with no
ESP32 is not a lesser pet, just one with fewer bodies — and the smallest
install is not a container at all:

```bash
uvx tamalab tui --solo     # a whole pet: no container, no broker, no keys
docker compose up -d       # the normal install: daemon + broker, one volume
```

See [deployment](docs/architecture/deployment.md) for what a host actually
needs (spoiler: one core, 256 MB, no inbound ports).

Four ideas hold it together:

- **The daemon owns the truth.** The ESP32 holds a cached copy only. Reflash
  it, unplug it, replace it — the pet is unaffected.
- **The simulation is deterministic and LLM-free.** Hunger and mood decay are
  a pure function of elapsed time and the event log. The pet works with the
  brain unplugged; the LLM adds personality, never state.
- **The brain is a config value.** Local (Qwen via Ollama), cloud (Claude, or
  anything OpenAI-compatible), or none at all — behind one narrow interface,
  with a canned-line table as the permanent last fallback.
- **Bodies are clients of one protocol.** Same events, same ULIDs, same
  TTLs, whether the face is drawn in flash or in characters. A fourth body —
  a web dashboard, an e-ink frame — needs no change in the daemon.

> **Status: Phase 0 — design only.** This repository currently contains
> documentation and no code. The architecture is being written first,
> deliberately: see [`docs/`](docs/).

## Documentation

The docs are [MkDocs Material](https://squidfunk.github.io/mkdocs-material/),
run through [uv](https://docs.astral.sh/uv/). There is no virtualenv to
create, activate or remember:

```bash
uvx --with mkdocs-material mkdocs serve    # http://127.0.0.1:8000
```

`uvx` resolves the toolchain into a cached throwaway environment — a couple
of hundred milliseconds after the first run — and nothing is installed into
your Python or into this repo. If you would rather have `mkdocs` on your
`PATH` permanently:

```bash
uv tool install mkdocs --with mkdocs-material
```

`mkdocs build --strict` is what CI runs on every pull request; pushes to
`main` deploy to GitHub Pages via `.github/workflows/deploy-docs.yml`, which
uses the same `uvx` invocation.

| Document | What it covers |
|---|---|
| [Home](docs/index.md) | What the pet is and how the pieces fit |
| [Roadmap](docs/roadmap.md) | Five phases, each independently playable |
| [Requirements](docs/requirements.md) | Numbered `FR`/`NFR` requirements the architecture cites |
| [Open Questions](docs/open-questions.md) | Decisions to make before Phase 0 |
| [Architecture](docs/architecture/overview.md) | Protocol, simulation, brain, voice, firmware, hardware |
| [Terminal body](docs/architecture/tui.md) | The no-hardware path, and the contract any new body implements |
| [Original Brief](docs/brief.md) | The seed document, kept verbatim |

## Planned layout

Nothing below exists yet. It is here so the docs can refer to it.

```text
daemon/      Python + SQLite. Owns state, runs the sim tick, hosts the brain,
             the Telegram bot and the event webhook.
client/      The body half — transport, state cache, event queue, TTLs.
             Importable by any body; the TUI is its reference consumer.
tui/         The terminal body. Rich, plus a small raw-mode key reader.
firmware/    ESP32-S3. Display, buttons, buzzer, I2S mic + speaker.
docs/        These documents.
```

## License

[MIT](LICENSE). The design documents and, when they exist, the daemon and
firmware are free to use, fork and adapt.
