# Experiment 002 — an agent drives a body

**Goal:** find out whether an unmodified agent can drive an OBP body with no
code of ours running inside it — and which of the two joins, MCP or the CLI,
is actually pleasant to use.

Experiment 001 proved a body can describe itself. This one asks whether that
description is enough for something that has never heard of OBP to pick up a
verb and use it.

**Time needed:** ~5 minutes without hardware, ~15 with the Pico.

---

## Part A — no hardware, no agent

Two test suites that need nothing plugged in and nothing installed.

```bash
cd ~/repos/open-body-protocol/experiments/002-agent-drives-body

python3 tests/test_naming.py       # MCP-safe tool names (M1–M3)
python3 tests/test_mcp_server.py   # the whole MCP mapping, over a pipe
```

The second one speaks MCP to the server exactly as an agent would, and
checks the handshake, the naming grammar, deterministic ordering, `userOnly`
exclusion, schema pass-through, and that a rejected call arrives as a result
rather than a fault. Both pass as of 2026-08-24.

## Part B — the CLI

```bash
python3 host/obp_cli.py --fake bodies
python3 host/obp_cli.py --fake describe
python3 host/obp_cli.py --fake call set_brightness level=40
```

With the Pico attached (flashed from experiment 001):

```bash
python3 host/obp_cli.py --port /dev/ttyACM0 bodies
python3 host/obp_cli.py --port /dev/ttyACM0 describe
python3 host/obp_cli.py --port /dev/ttyACM0 call blink times=5
python3 host/obp_cli.py --port /dev/ttyACM0 call set_brightness level=10
```

If that fails with `EACCES`, the shell has not picked up the `dialout` group
— see experiment 001's troubleshooting, or run `newgrp dialout` first.

## Part C — Claude Code, through the CLI

**No configuration at all.** Claude Code can already run shell commands, so
in a session started from this directory:

> *There is a robot attached. Run `python3 host/obp_cli.py --port
> /dev/ttyACM0 describe` to see what it can do, then make it acknowledge me.*

What to watch for: does it read the schemas and pick a sensible verb, does it
respect the ranges, and does it recover when a call is rejected.

## Part D — Claude Code, through MCP

```bash
cd ~/repos/open-body-protocol/experiments/002-agent-drives-body
claude mcp add obp -- python3 "$PWD/host/obp_mcp.py" --port /dev/ttyACM0 --log /tmp/obp-mcp.log
```

Then in a session:

> *What can the body do? Set it to about a third brightness.*

The `--log` file records every MCP message in both directions, which is how
this experiment finds out **which MCP dialect Claude Code actually speaks** —
the server accepts several and echoes back whichever revision the client
asks for.

Remove it afterwards with `claude mcp remove obp`.

---

## Results

Filled in after each run. Raw output is more useful than a summary.

### Part A — automated ✅ 2026-08-24

`test_naming.py` — 11 checks pass, including truncation of a 60-character
body id down to a legal 64-character name with the verb intact and a hash
appended, and two bodies sharing a long prefix staying distinct.

`test_mcp_server.py` — 17 checks pass: handshake, revision echo and
fallback, 4 tools offered (`reboot` correctly withheld as `userOnly`), all
names legal and namespaced, stable ordering across two calls, schemas passed
through, `level=150` returning `isError` with the body's own wording, an
unknown tool returning a result rather than a fault, `-32601` for an
unimplemented method, and `ping`.

### Part B — CLI against the Pico ⏳

- Port: `______`  · Firmware: ⬜ pico-sdk ⬜ MicroPython

```text

```

### Part C — Claude Code via the CLI ⏳

| Check | Result |
|---|---|
| Ran `describe` unprompted, or needed telling | ⬜ |
| Chose a sensible verb for "acknowledge me" | ⬜ |
| Respected the schema ranges | ⬜ |
| Recovered from a rejected call | ⬜ |

Transcript, or the interesting parts:

```text

```

### Part D — Claude Code via MCP ⏳

| Check | Result |
|---|---|
| `claude mcp add` succeeded | ⬜ |
| Tools appeared with body-namespaced names | ⬜ |
| Called a verb correctly from the schema | ⬜ |
| Errors read as errors, not crashes | ⬜ |
| Unplugging the body withdrew the tools mid-session | ⬜ |

Which revision did Claude Code negotiate? (from `/tmp/obp-mcp.log`)

```text

```

### Which join felt better

The point of running both. CLI or MCP — which needed less explaining, which
made better verb choices, and which would you keep?

```text

```

---

## What this tests

| Requirement | Where |
|---|---|
| M1–M3 tool naming | `tests/test_naming.py` |
| M4 `userOnly` withheld | `tests/test_mcp_server.py` |
| M5 schemas and results pass through | `tests/test_mcp_server.py` |
| M6 `tools.listChanged` declared | `tests/test_mcp_server.py` |
| M7 departed body → `isError` | `tests/test_mcp_server.py` |
| H2 deterministic ordering | both suites |
| H4, H5, H6 host behaviour | `host/obp/registry.py` |

## What it does not test

- **Hot-plug.** The server emits `notifications/tools/list_changed` on a
  presence change, but nothing here removes a body mid-session. Part D's
  last row is the manual version; a proper test needs a body that can be
  unplugged on cue.
- **Several bodies at once.** The registry supports it and nothing exercises
  it. Two Picos, or a Pico and the fake body, would.
- **Any agent other than Claude Code.** OpenCode and Cursor speak MCP and
  should work unchanged; unverified is unverified.
- **Long actions.** No verb here takes long enough to need the lifecycle, so
  the block-versus-detach question is untested.

## Notes on the implementation

The MCP server is hand-written rather than built on an SDK. Two reasons: the
experiment is partly *about* the mapping, so the mapping should be readable
rather than buried in a library; and it keeps the whole thing dependency-free
apart from `pyserial`, which matters when the claim is that a maker can run
it.

It logs every inbound method, including ones it does not implement, so an
agent speaking an unexpected dialect shows up as data rather than as a
mystery.
