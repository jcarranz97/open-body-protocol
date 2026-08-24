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
| [002](002-agent-drives-body/) | An agent drives a body | Can an unmodified agent drive an OBP body with no code of ours inside it — and is MCP or a plain CLI the better join? | ✅ **yes** — two agents, two joins, real hardware, and a *local* model | **`userOnly` is about who is asking** · **a verb's description carries the decision, not its name** · advice written for humans (`newgrp`) silently breaks agents · **a readable rejection lets an agent compose around a limit, not just apologise** |
| [003](003-mqtt-binding/) | MQTT binding | Does the identical contract work over MQTT to a networked body, proving the transport is a binding and not the architecture? | ✅ **yes** — a Pico W over WiFi, ~0.9s per call | **A reply must echo the request id verbatim** (string *or* number), and the spec's own examples taught the bug · a body that knows it is leaving should clear its own presence — the broker's Last Will was 13s behind · raising one buffer starved the allocator its data had to pass through |
| [004](004-many-bodies/) | One brain, many bodies | Does routing hold when the body set is plural, changing and occasionally wrong — and can a person put one body in focus without the others becoming unreachable? | ✅ **yes** — three bodies, three bindings, Claude Code driving | **Selection must not filter the tool list** — MCP forbids it, it discards the whole prompt cache, and it breaks the case that motivates it · a failed selection clears (IMAP), it does not leave a stale one (POSIX `chdir`) · **a house's lights are one body with rooms as arguments**, and needed no protocol change · **a correct host is not enough: an agent reported a tool surface it had already refreshed**, so a repairable link is now repaired in place rather than detached |
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
