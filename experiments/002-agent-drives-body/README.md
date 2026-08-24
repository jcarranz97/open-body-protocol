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
python3 tests/test_useronly.py     # userOnly is about who is asking
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

### Part B — CLI against the Pico ✅ 2026-08-24

Plain Raspberry Pi Pico, pico-sdk firmware, `/dev/ttyACM0`, Ubuntu.

```text
$ obp_cli.py --port /dev/ttyACM0 bodies
pico-3f5022   Raspberry Pi Pico body (pico-sdk)   4 verbs   caps: led, dimmable

$ obp_cli.py --port /dev/ttyACM0 call blink times=5
blinked 5 times
$ obp_cli.py --port /dev/ttyACM0 call set_brightness level=10
brightness 10%
$ obp_cli.py --port /dev/ttyACM0 call move direction=forward distance_cm=15
acknowledged move forward 15cm (simulated: no drivetrain attached)
$ obp_cli.py --port /dev/ttyACM0 call move direction=sideways
ERROR: unknown direction: sideways          # exit 1
```

`describe` prints the MCP name each verb would get, which turned out to be
the most useful thing in the output — it makes the naming rules concrete
before an agent is anywhere near them.

**Four verbs, not five.** `reboot` is `userOnly`, so it is excluded from the
count and from anything an agent sees.

### Part D — the MCP server against the real Pico ✅ 2026-08-24

Not Claude Code yet: a scripted MCP client, speaking the same protocol an
agent would, against the physical board.

```text
handshake: 2025-06-18 | listChanged: True
tools: pico-3f5022__blink, pico-3f5022__move,
       pico-3f5022__set_brightness, pico-3f5022__set_led

  level=5    isError=False   brightness 5%
  level=90   isError=False   brightness 90%
  level=250  isError=True    level must be 0..100
  blink:                     blinked 3 times
```

Sorted, namespaced, `reboot` withheld, and the board's own error wording
reaching the caller unchanged through two protocol layers.

### A bug this experiment found 🐛

Calling `reboot` from the CLI failed with *"no body currently offers
'pico-3f5022__reboot'"*.

The registry had been dropping `userOnly` verbs at registration, so they were
not merely unoffered — they were unroutable. **A person could not reboot
their own board.**

That is a misreading of the requirement. H4 says a host must withhold
`userOnly` verbs *from autonomous callers*; the spec's own descriptor page
says a host **MAY** expose them in a human interface. `userOnly` is about
**who is asking**, not about what exists.

Fixed: every verb is routable, `tools()` (the MCP surface) excludes
`userOnly`, and `call()` takes `autonomous=` — an agent passes `True`, the
CLI passes `False`. `tests/test_useronly.py` pins the distinction.

Worth noting how it surfaced: not from reading the spec, but from a human
trying to use the tool for its obvious purpose.

### Part C — Claude Code via the CLI ⏳

_Not yet run. The question is behavioural, not mechanical: does an agent read
the schemas, choose a sensible verb, respect the ranges, and recover from a
rejection._

### Part D — Claude Code via MCP ⏳

_The transport is proven above; what remains is whether Claude Code
negotiates a revision the server offers, and whether unplugging the body
withdraws its tools mid-session._

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
