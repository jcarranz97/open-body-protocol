# OBP

**OBP connects a brain to a body.**

The brain is an AI agent — Claude, a local Qwen or Gemma, OpenClaw, Hermes,
OpenCode. The body is whatever hardware someone built: a terminal window, a
screen and a speaker, a 3D-printed crab with servos, a commercial robot that
adopts the contract.

Neither is ours. The standardised way to marry them is.

```text
  any brain              obp                any body
 ───────────      ───────────────      ─────────────────
  Claude       ◄─►  identity        ◄─►  terminal
  local model       memory               ESP32 / Pico
  OpenClaw          translation          servos, wheels, claws
  Hermes            presence             a commercial robot
```

A body **describes its own abilities** — *"I can `move(direction,
distance_cm)` and `set_brightness(level: 0–100)"*, with JSON Schema — and the
daemon turns that into verbs the brain can call. Nobody teaches the daemon
what wheels are.

> **Status: architecture, with the first claim tested.** There is no
> `daemon/` yet. There *is* a working
> [experiment](experiments/001-pico-usb-body/): a Raspberry Pi Pico
> describing itself to a host that had never met it, over a bare USB cable,
> in two firmware languages.

## The idea in one table

| | Plugs in | Must do |
|---|---|---|
| [Body port](docs/architecture/body-contract.md) | anything physical or rendered | announce itself, describe its verbs, accept intents, report honestly |
| [Brain port](docs/architecture/brain-contract.md) | any model or agent harness | take context, return a decision |
| The daemon | — | hold identity and memory, translate, stay out of the way |

## Topology is a binding, not an architecture

| Where things run | Binding |
|---|---|
| All in one box — Jetson, mini PC, Pi, actuators on USB | stdio subprocess, no broker |
| One box, split processes | unix socket / localhost |
| Brain on a PC, body over Wi-Fi | MQTT |
| No hardware at all | in-process |

A robot with the model inside its own chassis and the network unplugged is a
config file, not a fork.

## Documentation

[MkDocs Material](https://squidfunk.github.io/mkdocs-material/), run through
[uv](https://docs.astral.sh/uv/) — no virtualenv to create or remember:

```bash
uvx --with mkdocs-material mkdocs serve    # http://127.0.0.1:8000
```

| Document | What it covers |
|---|---|
| [Overview](docs/architecture/overview.md) | The shape, in one page |
| [Body contract](docs/architecture/body-contract.md) | The specification — read this to build a body |
| [Brain contract](docs/architecture/brain-contract.md) | Plugging in a model or a harness |
| [Identity & memory](docs/architecture/identity.md) | Who owns the character, and when |
| [Behaviour packs](docs/architecture/behaviour-packs.md) | Optional behaviour, including a Tamagotchi |
| [Deployment](docs/architecture/deployment.md) | One container, on whatever machine you have |
| [Experiments](experiments/) | What has been tried, and what it changed |
| [Prior art](docs/prior-art.md) | Who else is doing this, with licences |

## Planned layout

Nothing below exists yet.

```text
daemon/      Python + SQLite. Registry, presence, translation, packs.
client/      The body half — transports, descriptors, presence.
bodies/      Reference bodies: terminal, ESP32, Pico.
packs/       Behaviour packs, including the Tamagotchi one.
experiments/ Runnable answers to single questions.
docs/        These documents.
```

## License

[MIT](LICENSE).
