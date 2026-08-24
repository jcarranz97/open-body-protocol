# Experiments

Small, runnable programs that answer one architectural question each. They
exist because an architecture argued on paper is a guess — these are how a
claim in `docs/` becomes a claim we have watched work.

**The rule: one question per experiment, and the README records the answer —
including when the answer was "no".** A failed experiment that changed the
design is worth more than a successful one that confirmed what we assumed.

Experiments are not the product. They may be scrappy, they may hardcode
paths, and they are never imported by `daemon/`, `client/` or `firmware/`.
What they produce is a paragraph in an architecture page.

## Index

| # | Experiment | Question it answers | Status | What it changed |
|---|---|---|---|---|
| [001](001-pico-usb-body/) | Pico USB body | Can a body describe its own abilities over a plain USB serial link, with no broker and no network — and does the same contract survive a different transport, and a different firmware language? | ✅ **yes** — confirmed on a real Pico, both firmwares (C and MicroPython) | Capability discovery comes from hardware, not config · errors belong in the result · intent-vs-implementation confirmed (gamma curve) · **daemon must sort tools deterministically** · identity belongs to the board · `EACCES` is a first-run UX problem |
| [002](002-agent-drives-body/) | An agent drives a body | Can an unmodified agent drive an OBP body with no code of ours inside it — and is MCP or a plain CLI the better join? | ✅ **yes**, both joins, with a real agent on real hardware | **`userOnly` is about who is asking** · **a verb's description carries the decision, not its name** · advice written for humans (`newgrp`) silently breaks agents · **a readable rejection lets an agent compose around a limit, not just apologise** |
| 003 | MQTT binding | Does the identical contract work over MQTT to a networked body, proving the transport is a binding and not the architecture? | 📋 planned | — |
| 004 | Two bodies, one brain | Does capability-gated tool discovery hold when a second body appears and disappears at runtime? | 📋 planned | — |
| 005 | Raw USB vs CDC | Does a body that carries audio need raw USB endpoints rather than a single CDC stream — the control/media split, spelled on a cable? | 📋 planned | — |

Status: 📋 planned · 🚧 in progress · ✅ answered · ❌ answered "no" · 🗄️ superseded

## Writing one

```text
experiments/NNN-short-name/
├── README.md      question · hypothesis · method · how to run · RESULTS
└── ...            whatever the experiment needs
```

The README is written **before** the code, with the Results section empty.
Fill it in afterwards, even — especially — when the result is inconvenient.
