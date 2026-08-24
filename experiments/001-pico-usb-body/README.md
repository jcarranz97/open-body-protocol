# Experiment 001 — Pico USB body

**Goal:** prove that a body can describe its own abilities over a plain USB
cable — no broker, no network, no configuration on the host — and that the
*same* contract works over a completely different transport.

If this holds, "any brain, any body" is just a matter of bindings, and the
all-in-one deployments (a Jetson or mini PC with the model, the daemon and
the actuators on one box) work. If it fails, the architecture is secretly
MQTT-shaped and needs rethinking.

**Time needed:** ~10 minutes with a Pico. ~1 minute without one.

---

## Part A — no hardware

Proves the host half works and that the transport is interchangeable:
`fake_body.py` speaks the identical protocol over a pipe instead of a cable.
This part passes as of 2026-08-24.

```bash
cd ~/repos/tamalab/experiments/001-pico-usb-body

python3 host/cli.py --fake describe
python3 host/cli.py --fake call set_led --arg on=true
python3 host/cli.py --fake call move --arg direction=forward --arg distance_cm=25
python3 host/cli.py --fake call move --arg direction=sideways     # should fail cleanly
python3 host/cli.py --fake call set_brightness --arg level=40
TAMABODY_DIMMABLE=0 python3 host/cli.py --fake describe            # a W-shaped body: the dim verb is gone
```

## Part B — the Pico

### Requirements

- A Raspberry Pi Pico (any model — Pico, Pico W, Pico 2, Pico 2 W)
- A USB cable
**Nothing else is needed.** The onboard LED does the work: it is switched,
blinked, and — on a plain Pico — dimmed with PWM. A dimmable LED exercises
the same thing a servo would (a continuous actuator with a range, so the
schema carries `minimum`/`maximum` rather than a boolean), which is what
matters to the contract.

A hobby servo is supported if one is to hand, but the experiment answers its
question without one.

### Step 1 — flash MicroPython (Option A only)

Skip this entirely when using the pico-sdk firmware in Step 2. Only needed if
the board doesn't already have MicroPython on it.

1. Download the `.uf2` for the board from
   [micropython.org/download](https://micropython.org/download/) (pick the
   exact model — Pico and Pico 2 are different files).
2. Hold **BOOTSEL**, plug the Pico in, release. A drive called `RPI-RP2`
   appears.
3. Drag the `.uf2` onto it. The board reboots on its own.

### Step 2 — pick a firmware and flash it

Two implementations of the same contract; either is fine. See
[`firmware/README.md`](firmware/README.md) for the comparison.

**Option A — MicroPython** (nothing to build)

Copy `firmware/micropython/main.py` to the board **as `main.py`**:

```bash
uv run --with mpremote mpremote connect /dev/ttyACM0 fs cp firmware/micropython/main.py :main.py
```

or in [Thonny](https://thonny.org/): open the file, *File → Save as… →
Raspberry Pi Pico*, name it `main.py`.

**Optional:** with a servo to hand, set `SERVO_PIN` near the top of the file
to its GPIO number. Leave it as `None` otherwise.

**Option B — pico-sdk (C)**

```bash
cd firmware/pico-sdk
export PICO_SDK_PATH=~/repos/pico-sdk
cmake -B build -DPICO_BOARD=pico       # or pico_w / pico2 / pico2_w
cmake --build build -j4
# -> build/tamalab_body.uf2
```

Flash it: hold **BOOTSEL**, plug the Pico in, and copy the `.uf2` onto the
mass-storage device it presents. On Ubuntu it auto-mounts:

```bash
# confirm where it landed
findmnt -no TARGET -S LABEL=RPI-RP2        # usually /media/$USER/RPI-RP2

cp build/tamalab_body.uf2 /media/$USER/RPI-RP2/
sync
```

The board reboots into the firmware as soon as the copy completes, and the
drive disappears on its own — that is expected, not an unmount error.

If it did not auto-mount:

```bash
lsblk -o NAME,LABEL,SIZE | grep -i RPI-RP2
sudo mkdir -p /mnt/pico && sudo mount /dev/sdX1 /mnt/pico
sudo cp build/tamalab_body.uf2 /mnt/pico/ && sync
```

(`picotool load -x build/tamalab_body.uf2` would avoid the BOOTSEL button
entirely, but the copy the SDK downloads is built without USB support unless
`libusb-1.0-0-dev` was installed before configuring.)

**Optional:** with a servo to hand, uncomment `#define SERVO_PIN 15` in
`main.c` and rebuild.

If the build cannot find `pico/stdio_usb.h`, the SDK's TinyUSB submodule is
not initialized — see the trap noted in `firmware/README.md`:

```bash
git -C $PICO_SDK_PATH submodule update --init lib/tinyusb
```

The JSON reader used by the C firmware has host-side tests that need no
board and no SDK:

```bash
cd firmware/pico-sdk
cc -std=c11 -Wall -Wextra -Werror -o /tmp/t test/test_json_min.c json_min.c && /tmp/t
```

### Step 3 — get the body running

**MicroPython:** unplug and replug so `main.py` runs instead of the REPL.
This matters — if the REPL holds the port, `describe` will time out.

**pico-sdk:** the board runs the firmware as soon as it reboots after
flashing; nothing else to do.

### Step 4 — run it

```bash
uv run --with pyserial python3 host/cli.py --port /dev/ttyACM0 describe
uv run --with pyserial python3 host/cli.py --port /dev/ttyACM0 call set_led --arg on=true
uv run --with pyserial python3 host/cli.py --port /dev/ttyACM0 call blink --arg times=5
uv run --with pyserial python3 host/cli.py --port /dev/ttyACM0 call move --arg direction=forward
uv run --with pyserial python3 host/cli.py --port /dev/ttyACM0 call move --arg direction=sideways

# a continuous actuator, on a bare board (plain Pico only -- see below)
uv run --with pyserial python3 host/cli.py --port /dev/ttyACM0 call set_brightness --arg level=10
uv run --with pyserial python3 host/cli.py --port /dev/ttyACM0 call set_brightness --arg level=100
```

To identify the port: `ls /dev/ttyACM*`, or list once with the Pico unplugged
and again with it plugged in, and take the new entry.

### Troubleshooting

**`PermissionError: [Errno 13] ... /dev/ttyACM0`** — the device is
`root:dialout`, and the user is not in that group:

```bash
sudo usermod -aG dialout $USER
```

**This does not take effect in a shell that is already open.** Supplementary
groups are fixed at login, so the running shell — and everything it spawns,
including `uv run` — keeps the old set. Either log out and back in, or apply
it to the current shell:

```bash
newgrp dialout                  # affects this shell onward
sg dialout -c '<command>'       # or apply it to one command
```

Check with `id -nG` (the running process) against `id -nG $USER` (the user
database). If `dialout` appears in the second and not the first, that is
exactly this problem.

**`describe` times out** — on MicroPython, the REPL is holding the port;
unplug and replug so `main.py` runs. On the pico-sdk firmware, confirm the
`.uf2` actually copied (the drive should have vanished by itself).

**Port opens then goes quiet** — `ModemManager` probes new ACM devices and
can hold the port for a few seconds after plug-in. `sudo systemctl stop
ModemManager` will confirm whether that is the cause.

---

## Results

### Run 1 — pico-sdk (C) firmware, real hardware, 2026-08-24 ✅

**Setup**

- Firmware: ☑ pico-sdk (C)  ☐ MicroPython
- Board: plain Raspberry Pi Pico (non-W — `caps` confirms it)
- Servo attached: no
- `set_brightness` advertised: **yes**, as expected on a non-W board
- Port: `/dev/ttyACM0` · OS: Ubuntu

**`describe` output**

```text
Raspberry Pi Pico body (pico-sdk)  [pico-3f5022]  fw pico-sdk-0.1.0
caps: led, dimmable
tools: 5
  - set_led(on)
  - blink(times, interval_ms)
  - set_brightness(level)
  - move(direction, distance_cm)
  - reboot(-)  !user-only
```

**Observations**

| # | Check | Result |
|---|---|---|
| 1 | `describe` returns within the 5 s timeout | ✅ |
| 2 | `body.id` looks like `pico-xxxxxx` | ✅ `pico-3f5022` |
| 3 | `set_led on=true` → `light on` | ✅ wire · ✅ LED lit |
| 4 | `blink times=5` → `blinked 5 times` | ✅ wire · ✅ visible blinks |
| 5 | `move direction=forward` → `acknowledged move forward 10cm (simulated: no drivetrain attached)` | ✅ |
| 6 | `move direction=sideways` → `ERROR: unknown direction: sideways` | ✅ |
| 7 | Tool count matches the hardware | ✅ 5 tools, `dimmable` in caps |
| 8 | `set_brightness level=10` → `brightness 10%` | ✅ wire · ✅ LED responded |
| 9 | `set_brightness level=100` → `brightness 100%` | ✅ wire · ✅ LED responded |
| 10 | `set_brightness level=150` → `ERROR: level must be 0..100` | ✅ |
| 11 | Servo | n/a |
| 12 | Both firmwares answer identically | ⬜ MicroPython not yet run |

**Confirmed end to end**, protocol and hardware, by the author running every
command listed in Part B against a physical board.

**The gamma curve behaves as designed.** Observed: 10% barely on, 50%
noticeably brighter, 100% fully lit — a perceptually even ramp. `duty =
pct² × 65535 / 10000` turns a request for 10% into 1% duty, and since
perceived brightness goes roughly as the square root of duty, that reads as
about a tenth. A linear duty would have made 10% look like a third and 50%
like two thirds; the numbers would have lied to the brain.

Small as it is, this is the clearest demonstration in the experiment of the
rule the architecture rests on: **the brain names an intent, the body decides
what that means in hardware.** Neither side needs to know the other's
reasoning, and the same `set_brightness(50)` would mean something entirely
different to a body with a servo-driven shutter.

**Problems encountered**

`PermissionError: [Errno 13] ... /dev/ttyACM0`. `sudo usermod -aG dialout
$USER` succeeded, but the running shell kept its login-time group set, so the
immediate retry failed identically and looked as though the fix had not
worked. `id -nG` (process) versus `id -nG $USER` (user database) showed
`dialout` present in one and absent from the other; `sg dialout -c '...'`
then worked first time.

Worth noting beyond this experiment: **the first obstacle between a maker and
a working body was a Unix group**, and the error message never mentions
groups.

**Subjective notes**

_Round-trip feel and how the dimming looked: to add._

### Run 2 — MicroPython firmware, same board, 2026-08-24 ✅

All Part B commands run against the MicroPython firmware on the same Pico,
with the same host client. Every check that passed in Run 1 passed again.

```text
Raspberry Pi Pico body  [pico-3f5022]  fw pico-0.1.0
caps: led, dimmable
tools: 5
  - set_led(on)
  - blink(interval_ms, times)
  - move(direction, distance_cm)
  - set_brightness(level)
  - reboot(-)  !user-only
```

**Row 12: the contract is language-independent.** Same five tools, same
schemas, same semantics, two implementations that share no code.

Three things the diff against Run 1 shows:

1. **Identity is a property of the board, not the firmware.** Both report
   `pico-3f5022` — the C build reads `pico_get_unique_board_id()`, MicroPython
   reads `machine.unique_id()`, and they agree because it is the same flash
   chip. A device registry keyed on this survives a firmware change, and even
   a language change.
2. **The capability heuristic agreed with the compile-time fact.** C decides
   `dimmable` from `CYW43_WL_GPIO_LED_PIN` being undefined; MicroPython
   decides it from `" W" not in os.uname().machine`. Both said `led,
   dimmable`. The runtime guess held here, but it is still a guess, and a
   board whose `machine` string is worded unexpectedly would disagree.
3. **Tool order and property order differ between the two.** C emits
   `blink(times, interval_ms)` and places `set_brightness` before `move`;
   MicroPython emits `blink(interval_ms, times)` and places `set_brightness`
   last. MicroPython dictionaries do not preserve insertion order, so the
   firmware cannot control this even if it wanted to.

That third point is the finding, and it is not cosmetic.

### What this changed in the architecture

1. **Hypotheses 1, 2 and 4 confirmed on hardware.** A body described itself
   over a bare USB cable; a host that had never met it called its tools; the
   same contract ran unchanged over a pipe and a cable; `reboot` arrived
   flagged `userOnly`.
2. **Hypothesis 3 confirmed, and by hardware rather than a flag.** `caps:
   led, dimmable` and the 5-tool list follow from `CYW43_WL_GPIO_LED_PIN`
   being undefined on a non-W board. The same source on a Pico W advertises
   4. Capability discovery is a property of the build meeting the board.
3. **Errors belong in the result, not the transport.** `level=150` and
   `direction=sideways` both returned readable `isError` results, which is
   what lets a brain explain itself instead of hanging. Promote to a contract
   requirement.
4. **`EACCES` is a first-run experience problem, not a user error.** The host
   client should translate a permission failure on a tty into the `dialout`
   advice rather than a stack trace.
5. **The daemon must sort a body's tools deterministically** before handing
   them to a brain, and must not rely on the order the body sent them. Run 2
   proved two firmwares of the *same body* disagree on ordering, and
   MicroPython cannot fix its side. This matters beyond tidiness: MCP's
   2026-07-28 revision recommends stable tool ordering precisely because a
   reshuffled tool array busts the model's prompt cache — on a desk agent
   that otherwise runs warm all day, a reflash would silently start costing
   full-price prompts.
6. **Identity belongs to the board.** Keying the device registry on the
   hardware unique id survives reflashing and even switching language, which
   is what makes "the pet survives a firmware change" true rather than
   hopeful.

## The contract under test (v0)

Newline-delimited JSON-RPC 2.0, both directions.

```jsonc
// host -> body
{"jsonrpc":"2.0","id":1,"method":"body/describe"}
// body -> host
{"jsonrpc":"2.0","id":1,"result":{
  "body":{"id":"pico-1a2b3c","name":"Raspberry Pi Pico body","fw":"pico-0.1.0",
          "caps":["led"]},
  "tools":[{"name":"set_led","description":"Turn the body's indicator light on or off.",
            "inputSchema":{"type":"object",
                           "properties":{"on":{"type":"boolean"}},"required":["on"]}}]}}

// host -> body
{"jsonrpc":"2.0","id":2,"method":"tools/call",
 "params":{"name":"blink","arguments":{"times":3}}}
// body -> host
{"jsonrpc":"2.0","id":2,"result":{"content":[{"type":"text","text":"blinked 3 times"}],
                                  "isError":false}}

// body -> host, unsolicited, on boot
{"jsonrpc":"2.0","method":"notifications/body/online","params":{"id":"pico-1a2b3c","fw":"pico-0.1.0"}}
```

Three deliberate decisions, each with a reason:

| Decision | Why |
|---|---|
| Tool descriptors and results are **MCP-shaped** (`name`/`description`/`inputSchema`, `content[]`/`isError`) | Re-exposing a body as an MCP server becomes a relabelling, not a translation ([mcp](../../docs/architecture/mcp.md)) |
| **`body/describe` in one round trip**, not `initialize` + `tools/list` | Round trips cost on a serial link, and MCP's 2026-07-28 revision retired that handshake anyway |
| **`userOnly: true`** on privileged verbs | Borrowed from xiaozhi's `AddUserOnlyTool`. `reboot` is a different kind of verb from `wave`, and JSON Schema cannot say so |

## Method

Two implementations of the same body, so the transport claim is testable
rather than asserted:

```text
firmware/micropython/main.py   MicroPython on the Pico, over USB CDC serial
firmware/pico-sdk/             the same body in C, same wire protocol
host/fake_body.py              the same body with no hardware, over a pipe
host/tamabody/                 the host client: transports, contract, discovery
host/cli.py                    drives any of them
```

## What this experiment deliberately does not test

- **MQTT.** That is [003](../README.md) — and the point of doing it *after*
  this one is that the contract will already have been proven without a
  broker.
- **An LLM.** [002](../README.md) re-exposes these descriptors as an MCP
  server so an unmodified agent can drive the body. Keeping the brain out of
  001 means a failure here is unambiguously a protocol failure.
- **Async intents.** Every call here is synchronous. Real motion needs
  `accepted → running → done` with a cancel, which is the one genuinely good
  idea ROS actions have. That is a v1 contract question, not a v0 one.
- **Presence beyond process liveness.** Over a pipe or a cable, "the body is
  alive" is "the process/port is open". MQTT's retained-message + Last Will
  trick is strictly better and does not generalise here — which is exactly
  why presence has to be an abstraction with per-binding implementations.
