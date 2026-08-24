# Implementations

What exists, what it proves, and how to add yours.

## Reference bodies

Both live in [`experiments/001-pico-usb-body`](https://github.com/jcarranz97/open-body-protocol/tree/main/experiments/001-pico-usb-body)
and answer identically over the same host client — which is the point.

| | MicroPython | pico-sdk (C) |
|---|---|---|
| Lines | ~190 | ~290, plus a 190-line JSON reader |
| Flash | runtime + 8 KB script | 75 KB total |
| Get started | drag a `.uf2`, copy one file | install a toolchain, run CMake |
| Iterate | save, replug | rebuild, reflash |
| Suits | trying it, changing verbs quickly | products, tight timing, no interpreter |

Plus a **hardware-free body** speaking the same protocol over a pipe, so the
host half can be exercised with nothing plugged in.

**Verified on a plain Raspberry Pi Pico:** both firmwares reported the same
hardware-derived `id`, both advertised five verbs including `set_brightness`
(present because the LED is on GPIO 25 — a Pico W would advertise four), and
both returned readable errors for out-of-range and unknown-enum calls.

Two requirements in the [conformance list](spec/conformance.md) exist because
of that run: deterministic ordering, and `userOnly`.

## Reference host

[desk-buddy](https://github.com/jcarranz97/desk-buddy) — a desk robot with an
agent for a brain. It is the first product built on OBP and the place where
all the questions the protocol refuses to answer get answered: which model
thinks, who owns the persona, how it deploys.

Reading it alongside the spec is the fastest way to see the split: everything
in desk-buddy is a decision OBP deliberately left open.

## Writing a body

Five things, and nothing else is required:

1. Announce presence with a stable id derived from your hardware.
2. Answer `body/describe` with honest capabilities and verbs whose schemas
   match what the hardware can do.
3. Execute `tools/call` and return a readable result, including failures.
4. Own the how — kinematics, timing, limits, reflexes.
5. Keep working when the host is gone.

Then check yourself against [conformance](spec/conformance.md).

### Choosing a transport

| Situation | Binding |
|---|---|
| Code inside the host | in-process |
| On this machine's USB, GPIO or serial | stdio / serial |
| Owns its own board and network | MQTT |
| A ROS 2 robot | MQTT, bridged with `mqtt_client` — config, not code |

### On USB: CDC or raw?

Both reference firmwares present as **USB CDC serial**, and should. CDC is a
class driver on every operating system, needs no udev rules or Zadig, and is
inspectable with `screen /dev/ttyACM0`.

Raw USB endpoints earn their complexity in exactly one case: **a body that
carries audio.** A CDC link is a single stream, so a microphone would share a
channel with control messages — the mistake EMQX documented when they pushed
WAVs through their control bus and measured ~3 s round trips. Separate
endpoints map onto the control/media split cleanly.

The rule at every layer: **control is small, framed and reliable; media gets
its own path.**

### Traps worth knowing

- The Pico SDK's submodules are **not** initialised by a plain clone, and
  `pico_enable_stdio_usb()` fails *silently* without TinyUSB. `blink` works,
  the first USB program does not. `git submodule update --init lib/tinyusb`.
- Disable stdio CR translation, or framing becomes `\r\n`.
- On MicroPython the REPL shares the USB port; replug after flashing.
- On Linux the device is `root:dialout`, and `usermod -aG dialout` does **not**
  apply to a shell that is already open. Use `sg dialout -c '<command>'` — not
  `newgrp`, which starts an *interactive* shell and therefore hangs a script
  or an agent. A host **should** translate `EACCES` on a tty into this
  advice; it is the first obstacle between a builder and a working body, and
  the error the OS gives mentions neither groups nor the fix.

## Listing yours

Open a pull request adding a row here: what it is, which level of
[conformance](spec/conformance.md) it reaches, its licence, and a link.
Bodies that do interesting things the reference ones do not — motion, audio,
several actuators, an unusual transport — are the ones most worth having,
because they are where the specification is most likely to be wrong.
