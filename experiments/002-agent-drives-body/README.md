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
python3 tests/test_departure.py    # a body that leaves is a result, not a fault
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

**No configuration at all.** Claude Code can already run shell commands.

**Pre-flight, or the experiment measures the wrong thing.** Check that the
session can open the port before starting:

```bash
python3 host/obp_cli.py --port /dev/ttyACM0 bodies
```

If that fails with a permission error the CLI now prints what to do. The
short version: `sg dialout -c '<command>'` for a script or an agent — **not**
`newgrp`, which opens an interactive shell and hangs a non-interactive
caller. Better still, log out and back in so neither is needed, because
otherwise every command in the session has to be wrapped.

Then, in a session started from this directory:

> *There is a robot attached. Run `python3 host/obp_cli.py --port
> /dev/ttyACM0 describe` to see what it can do, then make it acknowledge me.*

What to watch for: does it read the schemas and pick a sensible verb, and
does it respect the declared ranges.

### C2 — force a rejection

The first prompt does not exercise recovery, because an agent that reads
`describe` first never sends a bad value. Ask for something the schema
forbids:

> *Blink it twenty times so I can see it from across the room.*

`blink` declares `times: 1..10`. What to watch: does it notice the limit
before calling, or send `20`, read the error and adapt — and does it say
something sensible to you either way.

## Part D — Claude Code, through MCP

**First, the permission trap again — it bites harder here.** Claude Code
spawns the server as a child of its own session, so the server inherits
whatever groups that session has. If `id` does not list `dialout`, the port
fails inside a process you cannot see, and `/mcp` reports only
`Failed to reconnect to obp: CONNECTION_CLOSED`.

The clean fix is to log out and back in. Failing that, register the server
wrapped:

```bash
cd ~/repos/open-body-protocol/experiments/002-agent-drives-body

# after logging out and back in:
claude mcp add obp -- python3 "$PWD/host/obp_mcp.py" --log /tmp/obp-mcp.log

# or, in a session that still lacks the group:
claude mcp add obp -- sg dialout -c "python3 $PWD/host/obp_mcp.py --log /tmp/obp-mcp.log"
```

**Note there is no `--port`.** The default is `auto`: every USB serial device
present is attached, and re-attached on each `obp__status`, so a board that
re-enumerates or arrives later is picked up without touching the config.

Earlier revisions of this file said `--port /dev/ttyACM0`, which pinned the
server to a node the board eventually left — the exact mistake H5b exists to
prevent, sitting in the setup instructions of the experiment that produced
H5b. Naming a device node in a config file is the thing to avoid; `--port
3f5022` (a serial fragment) or a `/dev/serial/by-id/...` path both work if
something more specific is wanted.

The server no longer dies when a body is unreachable — it starts anyway and
offers `obp__status`, so an agent can ask what is wrong and read the answer
out to you.

Then in a session:

> *What can the body do? Set it to about a third brightness.*

The `--log` file records every MCP message in both directions, which is how
this experiment finds out **which MCP dialect Claude Code actually speaks** —
the server accepts several and echoes back whichever revision the client
asks for.

Remove it afterwards with `claude mcp remove obp`.

## Part E — OpenCode, through MCP

The same server, a different agent. **OpenCode has no `mcp add` command** —
MCP servers are declared in a config file, and one that lives in the working
directory applies to that project.

`opencode.json` is committed alongside this experiment, so from here it is
already configured:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "obp": {
      "type": "local",
      "command": ["python3", "host/obp_mcp.py", "--log", "/tmp/obp-mcp.log"],
      "enabled": true,
      "cwd": "."
    }
  }
}
```

**Start OpenCode from this directory**, or the relative path will not
resolve. OpenCode finds the config by scanning the project, but runs the
command against *its own working directory* — so from the repository root
the same config fails:

```text
$ cd ~/repos/open-body-protocol && opencode mcp list
●  ✗ obp failed
│      MCP error -32000: Connection closed

$ cd experiments/002-agent-drives-body && opencode mcp list
●  ✓ obp connected
```

Verify before starting a session:

```bash
opencode mcp list
```

```text
┌  MCP Servers
│
●  ✓ obp  connected
│      python3 host/obp_mcp.py --log /tmp/obp-mcp.log
│
└  1 server(s)
```

**If `id` does not list `dialout`**, the server will connect but attach no
body — `obp__status` will be its only verb. Either log out and back in, or
change the command array to the wrapped form:

```json
"command": ["sg", "dialout", "-c", "python3 host/obp_mcp.py --log /tmp/obp-mcp.log"]
```

Both forms are verified: the plain one offers `obp__status` alone from a
session without the group, and the wrapped one offers all five tools.

Then run `opencode` and use the same prompts as Part D:

> *Blink the robot twice.*
> *Put the LED to 25%.*
> *Blink it twenty times.*
> *Reboot the robot.*

### What to compare against Claude Code

| | Watch for |
|---|---|
| Revision | `/tmp/obp-mcp.log` — Claude Code negotiated `2025-11-25`; does OpenCode differ? |
| Discovery | Does it call `tools/list` once, or re-list per turn? |
| `tools/list_changed` | Unplug mid-session: does OpenCode act on the notification the way Claude Code did? |
| Naming | Do the `body__verb` names read as well in its UI? |
| `userOnly` | Does asking to reboot produce a clean refusal? |

The log is shared, so the two agents' conversations sit side by side in
`/tmp/obp-mcp.log` and can be compared directly.

### Part E results ⏳

```text

```

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

### Part C — Claude Code via the CLI ✅ 2026-08-24

Claude Code, no MCP, no OBP-specific context beyond the repository's own
`AGENTS.md`. Prompt as written in this README.

| Check | Result |
|---|---|
| Ran `describe` unprompted, or needed telling | told, by the prompt |
| Chose a sensible verb for "acknowledge me" | ✅ chose `blink` over `set_led` |
| Respected the schema ranges | ✅ `times=3`, `interval_ms=250`, both inside the declared bounds |
| Recovered from a rejected call | ✅ in C2, below |

Five calls, five results, no transport errors. `reboot` appeared marked
`!user-only` and was not attempted.

**The finding: the description string carried the decision.** Two verbs could
plausibly acknowledge, and the agent had no knowledge of OBP, this repository
or the hardware. `blink`'s description reads *"Use to acknowledge something
without speaking"* — and that, not the verb name, is what separated it from
`set_led`. `set_brightness` was then used for its stated purpose too
(*"dim when calm, bright when alert"*), setting 80% so a 250 ms blink would
read across a desk.

This is direct evidence for the claim in
[descriptors](https://github.com/jcarranz97/open-body-protocol/blob/main/docs/spec/descriptors.md)
that a description is part of the interface rather than documentation.

**What the first prompt did not establish.** Nothing was rejected, because
every argument was read off the schema first. That is what C2 was added for.

Unrequested behaviour worth noting: the agent left the body in a defined
state afterwards (brightness 25%, light on) without being asked. Harmless
here; worth watching in a body with moving parts.

### C2 — recovery from a rejection ✅ 2026-08-24

Prompt: *"Blink it twenty times so I can see it from across the room."*
`blink` declares `times: 1..10`.

```text
$ ... call blink times=20 interval_ms=250
ERROR: times must be between 1 and 10          # exit 1

$ ... call set_brightness level=100
brightness 100%
$ ... call blink times=10 interval_ms=250
blinked 10 times
$ ... call blink times=10 interval_ms=250
blinked 10 times
```

**It did not clamp, and it did not give up. It decomposed.** Twenty blinks
happened, as two calls of ten, and the person got what they asked for while
the body's limit stayed intact.

Three things this establishes that the first prompt could not:

1. **A rejection arrived as a result, not a fault.** The body's own wording —
   *"times must be between 1 and 10"* — reached the caller through the CLI as
   exit 1, with no crash and no transport error. This is the observable
   consequence of the rule in
   [results](https://github.com/jcarranz97/open-body-protocol/blob/main/docs/spec/results.md).
2. **The host never second-guessed the limit.** It passed `20` down and let
   the body refuse. The limit is the body's to enforce, and the host declining
   to pre-validate is what let the body's real constraint surface intact.
3. **A readable error enables composition, not merely apology.** The
   interesting recovery is not "sorry, ten is the maximum" — it is finding an
   arrangement of legal calls that satisfies the actual request. That is only
   possible because the error said *what* the limit was.

The agent also reported sending the out-of-range value **deliberately**,
having read the schema, to exercise the case rather than avoid it.

One honest edge: 10 + 10 is not quite 20. There is a round trip between the
two calls, so the rhythm has a small hitch in the middle where a single
twenty-blink call would not. Decomposition across a protocol boundary is
close to the intent, not identical to it — worth remembering for verbs where
timing matters more than it does for a blinking LED.

### The `newgrp` bug this run found 🐛

The first command in Part C's own prompt failed with `EACCES`, and **the
advice this experiment gave was wrong for the caller it was aimed at.**

Experiment 001 and this README both said to run `newgrp dialout`. That is
correct for a person at a prompt and useless to an agent: `newgrp` replaces
the shell with a new *interactive* one and waits for input, so a caller
issuing one non-interactive command per invocation hangs or loses it. The
non-interactive equivalent is `sg dialout -c '<command>'`.

Fixed in three places:

- **The CLI now explains itself.** `SerialTransport` translates `EACCES` into
  the group that owns the device, the `usermod` line, and both `sg` and
  `newgrp` with a note on which is for scripts. It also detects the case
  where the process *is* in the group and points at ModemManager instead.
- **Both experiment READMEs** now lead with `sg` and say why.
- **`implementations.md`** carries it as a trap, with the recommendation that
  any host translate `EACCES` rather than surfacing it raw.

The general lesson is worth more than the fix: **advice written for a human
was silently wrong for an agent**, in a project whose entire purpose is
agents driving hardware.

### Part D — first attempt ❌ 2026-08-24, and the bug it found

```text
❯ /mcp
  ⎿  Failed to reconnect to obp: CONNECTION_CLOSED
```

Claude Code (v2.1.241) registered the server and could not talk to it. The
cause was the same `dialout` membership as Part C — Claude Code spawns the
server as a child of its own session, so the server inherited a group list
without `dialout` — but **three bugs of mine turned a fixable permission
problem into an unexplainable dead connection.**

| Bug | Fix |
|---|---|
| `SerialTransport` raised `SystemExit` on `EACCES`. Fine for a CLI; fatal for a server. | Raises `BodyUnavailable`, an ordinary exception a caller can handle |
| `obp_mcp.py` exited when no body attached | Starts regardless. A server that exits because a cable is unplugged looks to an agent exactly like a broken server |
| The `--log` file was never written, because the failure happened before logging began | Attach failures are recorded and reported |

**And the fix that matters most: the server now always offers `obp__status`.**
With nothing attached, an agent asking it receives:

```text
isError: true

/dev/ttyACM0:
Permission denied opening /dev/ttyACM0.
/dev/ttyACM0 is owned by group 'dialout' and this process is not in it.

  sudo usermod -aG dialout $USER      # once, permanently
  ...
  sg dialout -c '<command>'           # one command, non-interactive
```

So the failure is now something the agent can read and explain to the person
sitting there, instead of a connection that closed for no stated reason.
Calling it again retries the attach, so a fixed permission clears without
restarting the session.

With the group present, the same server attaches cleanly:

```text
tools: obp__status, pico-3f5022__blink, pico-3f5022__move,
       pico-3f5022__set_brightness, pico-3f5022__set_led
status: attached: Raspberry Pi Pico body (pico-sdk) [pico-3f5022]
        — set_led, blink, set_brightness, move
```

### Part D — with an agent ✅ 2026-08-24

Claude Code v2.1.241, registered with the `sg` wrapper. Three requests in
plain English, three correct calls, no `describe` step — MCP had already put
the schemas in context.

```text
"can you please blink the led of my robot 5 times?"
    → pico-3f5022__blink {"times": 5}

"blink it 5 times but with a 500ms interval"
    → pico-3f5022__blink {"times": 5, "interval_ms": 500}

"put the led to 25 %"
    → pico-3f5022__set_brightness {"level": 25}
```

**The dialect, from `/tmp/obp-mcp.log`:** Claude Code negotiated MCP revision
**`2025-11-25`** — handshake-based, not the stateless 2026-07-28 — and
advertised `roots.listChanged` and `elicitation` as client capabilities. The
server echoed the requested revision back, which is why the connection
worked without either side special-casing the other.

### The disconnect test 🐛 — three more bugs

Unplugging the Pico mid-session was meant to test hot-plug. It found
something worse, and the agent's own diagnosis is worth quoting:

> *`obp__status` still reports the Pico as attached with all four verbs, so
> the host thinks the body is fine while the serial write is actually
> failing.*

The board had **re-enumerated** from `/dev/ttyACM0` to `/dev/ttyACM1`. Not a
disconnection at all — the host was writing into a device node that no longer
existed.

| Bug | Fix |
|---|---|
| A dead body's failure escaped as JSON-RPC `-32603`, violating "errors are results" | `Registry.call` catches everything, detaches the body, and returns a readable `isError` result |
| `obp__status` reported attach-time inventory as if it were presence | `Registry.verify()` pings each body first and drops the ones that do not answer |
| A numbered device node was treated as an identity | Ports resolve through `/dev/serial/by-id/`, and re-resolve on every reattach |

The third fix is the one worth keeping. A Pico's by-id symlink is
`usb-Raspberry_Pi_Pico_E6611C08CB3F5022-if00`, and our firmware derives its
OBP `id` from the last bytes of that same serial — so `pico-3f5022` and the
OS-level device identity are the same fact seen from two directions:

```bash
python3 host/obp_cli.py --port 3f5022 bodies      # finds it wherever it landed
```

A stale path now explains itself rather than failing obscurely:

```text
/dev/ttyACM0: not present. Attached USB serial devices:
    /dev/serial/by-id/usb-Raspberry_Pi_Pico_E6611C08CB3F5022-if00
```

Generalised into the specification as **H5a** (an error talking to a body is
loss of presence; never report attach-time inventory as current presence) and
**H5b** (address a serial body by a stable identifier, and re-resolve on
reattach). `tests/test_departure.py` pins both.

### A fourth bug, in the documentation 🐛

The unplug test failed again, and this time the fault was in this README.
The `claude mcp add` line above said `--port /dev/ttyACM0`, so the server was
pinned to a node the board had left. `obp__status` correctly reported
`/dev/ttyACM0: not present` and listed the by-id path it should have been
using — the diagnosis worked, the configuration was wrong.

Writing H5b and then leaving an unstable device node in the setup
instructions is a good illustration of why a specification needs worked
examples that are themselves conformant.

**Fixed by removing the choice.** `--port` now defaults to `auto`, attaching
every USB serial device present and re-scanning on each `obp__status`. Nobody
has to name a port, so nobody can name the wrong one.

Worth recording from that run: **the CLI rescued the MCP path.** With the MCP
server pinned to a dead node, the agent fell back to the shell, ran
`describe`, hit the `dialout` problem, read the host's own explanation, used
`sg`, and completed the blink. The two joins are not redundant — one
diagnosed the other.

### Hot-plug ✅ 2026-08-24 — the last requirement

With the server auto-discovering, the cable was pulled mid-session and put
back. From `/tmp/obp-mcp.log`, timestamps as recorded:

```text
07:39:40  <--  call blink {"times": 2}
07:39:41  -->  "blinked 2 times"

          ... cable pulled ...

07:39:58  <--  call blink {"times": 2}
07:39:58  -->  notifications/tools/list_changed        ← host emits
07:39:58  -->  isError=true "stopped responding and has been detached"
07:39:58  <--  tools/list                              ← Claude Code re-lists
07:39:58  -->  1 tool                                  ← only obp__status left

          ... cable replaced ...

07:40:27  <--  call obp__status {}
07:40:27  -->  notifications/tools/list_changed        ← host emits
07:40:27  -->  "attached: Raspberry Pi Pico body ... set_led, blink, ..."
07:40:27  <--  tools/list                              ← re-lists again
07:40:39  <--  call blink {"times": 2}
07:40:39  -->  "blinked 2 times"
```

**Five tools → one → five, with Claude Code re-listing on both transitions.**
M6 is confirmed against a real client, not merely declared.

What the agent said, unprompted and correct: *"The body was detached and
`obp__status` now reports no bodies attached, so its verbs are gone… that
errno 5 on write usually means the USB serial device disappeared."* Then, on
"try again", it called `obp__status` — which re-attached — and blinked. It
recovered without being told how.

Three of our fixes chained to make that possible: the failure became a result
rather than a fault (H5a), presence loss withdrew the verbs (H5), and status
retried the attach (M9).

**One weakness the log exposed.** With nothing attached, status said *"No
bodies attached and no errors recorded"* — true and useless. It now reports
which USB serial devices are present and what to check, or says plainly that
none are.

### What Part D settled

- **Claude Code speaks MCP revision `2025-11-25`**, handshake-based.
- **`tools/list_changed` works** and is acted on immediately.
- **Natural language reaches the right verb with the right arguments**, with
  no `describe` step, because MCP puts the schemas in context.
- **A body can leave and return mid-session** without restarting the agent.

### Which join felt better

**Both, and not redundantly.** MCP is lower friction when it works — three
sentences of plain English, no paths, no commands, and the schemas already in
context so no `describe` step. But every failure in this experiment was
diagnosed through the CLI: when the MCP server was pinned to a dead node, the
agent fell back to the shell, ran `describe`, hit the `dialout` problem, read
the host's own error text, wrapped the command in `sg`, and finished the job.

The CLI has no configuration to be wrong, which is exactly why it survives
the configuration being wrong. A host should offer both and say so.



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
- **Recovery from a rejected call by an agent.** C2 exists to force it and
  has not been run.
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
