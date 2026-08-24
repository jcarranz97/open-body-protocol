# Firmware — two paths to the same contract

The body contract is a wire protocol, not a language. Both firmwares here
answer identically; the host client cannot tell them apart, which is the
whole point — **the builder chooses the toolchain, not the architecture.**

| | [`micropython/`](micropython/) | [`pico-sdk/`](pico-sdk/) |
|---|---|---|
| Language | Python | C |
| Getting started | Drag a `.uf2`, copy one file | Install a toolchain, run CMake |
| Iterate | Save the file, replug | Rebuild, reflash |
| Flash used | ~600 KB runtime + 8 KB script | 74 KB total |
| Line count | 190 | 290 + a 190-line JSON reader |
| Good for | Trying the idea, changing verbs quickly | Products, tight timing, no interpreter |

Both are ~200 lines of *contract* and a handful of hardware calls. That ratio
is the thing to notice: the protocol is small enough that reimplementing it
in a new language is an afternoon, which is what "any body" has to mean in
practice.

## USB CDC, and why not raw USB

Both firmwares present the Pico as a **USB CDC serial device** — the host
opens `/dev/ttyACM0` and reads lines. The pico-sdk could instead expose a
raw vendor-specific USB interface through TinyUSB, so it is worth saying why
it does not.

**CDC wins for v0**, on three counts that all point the same way:

- **No driver, no permissions dance.** CDC is a class driver on Linux, macOS
  and Windows. A raw interface needs udev rules on Linux and WinUSB/Zadig on
  Windows — a support burden paid by every builder to benefit none of them
  yet.
- **It is debuggable by a human.** `screen /dev/ttyACM0 115200` shows the
  conversation. A bulk endpoint needs a tool written specially to look at it.
- **It is the same shape as every other binding.** Lines of JSON in, lines of
  JSON out — identical to the pipe binding and to what an MQTT payload
  carries. One mental model.

**Raw USB earns its complexity exactly once: when a body carries audio.** A
CDC link is a single stream, so a microphone would have to be multiplexed
into the same channel as control messages — and that is precisely the mistake
[the EMQX series](../../../docs/prior-art.md) documented when they pushed WAVs
through their control bus and measured ~3 s round trips. Separate USB
endpoints map cleanly onto the control-plane/media-plane split the
architecture already commits to, the same way MQTT-for-control and
UDP-for-audio does on a networked body.

So the rule is the same at every layer: **control is small, framed and
reliable; media gets its own path.** Raw USB is how that rule is spelled on a
cable, and it is [experiment 005](../../README.md) rather than a v0 decision.

## A trap worth knowing

The Pico SDK's submodules are **not** initialized by a plain `git clone`, and
`pico_enable_stdio_usb()` fails *silently* when TinyUSB is missing — the
build simply cannot find `pico/stdio_usb.h`. `blink` works fine, so the
toolchain looks healthy right up until the first USB program:

```bash
git -C /path/to/pico-sdk submodule update --init lib/tinyusb
```

Only that one submodule is needed here; btstack, lwip, cyw43-driver and
mbedtls can stay uninitialized unless a board needs wireless.
