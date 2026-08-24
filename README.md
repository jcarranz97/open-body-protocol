# Open Body Protocol (OBP)

**A standard way to give an agent a body.**

A body — a microcontroller, a robot, a terminal window — announces itself,
**describes its own verbs with JSON Schema**, and executes them. A host
discovers those verbs at run time and offers them to whatever is deciding.
Nothing in the host is taught what a claw is.

```jsonc
// host → body
{"jsonrpc":"2.0","id":1,"method":"body/describe"}

// body → host: identity, capabilities and verbs, in one round trip
{"jsonrpc":"2.0","id":1,"result":{"v":0,
  "body":{"id":"pico-3f5022","fw":"0.1.0","caps":["led","dimmable"]},
  "tools":[{"name":"set_brightness",
            "description":"Set how brightly the indicator light glows.",
            "inputSchema":{"type":"object",
              "properties":{"level":{"type":"integer","minimum":0,"maximum":100}},
              "required":["level"]}}]}}

// host → body
{"jsonrpc":"2.0","id":2,"method":"tools/call",
 "params":{"name":"set_brightness","arguments":{"level":40}}}

// body → host
{"jsonrpc":"2.0","id":2,"result":{
  "content":[{"type":"text","text":"brightness 40%"}],"isError":false}}
```

## Scope

OBP specifies how a body is **described and driven**. It says nothing about
what decides — which model, what it remembers, who it is, how it deploys.
That is deliberate, and it is what makes the protocol adoptable by someone
who already has an agent.

If you want the other half, [desk-buddy](https://github.com/jcarranz97/desk-buddy)
is a product built on OBP and answers all of it.

## Principles

- **The body carries the schema.** A catalogue of device types in the host
  fails the first time someone builds something nobody anticipated.
- **Intents down, results up.** A tool call takes seconds; a motor needs
  milliseconds. The body owns kinematics, limits and reflexes.
- **Errors are results**, so a decider can explain itself instead of hanging.
- **Transport is a binding** — in-process, stdio, serial, MQTT. A body on a
  USB cable must never need a broker.
- **Capabilities come from hardware.** The same firmware on a different board
  advertises a different verb list.

## Status

**v0, unstable.** Published so implementations can find its edges. Two
requirements — deterministic verb ordering and `userOnly` — exist because
running code found problems the design had not.

Two conforming bodies exist today, in C and MicroPython, verified on a real
Raspberry Pi Pico: [`experiments/001-pico-usb-body`](experiments/001-pico-usb-body/).

## Documentation

```bash
uvx --with mkdocs-material mkdocs serve    # http://127.0.0.1:8000
```

| | |
|---|---|
| [Specification](docs/spec/overview.md) | Roles, messages, descriptors, results, presence, bindings, versioning, security |
| [Conformance](docs/spec/conformance.md) | What an implementation must do, and how to test it |
| [Rationale](docs/rationale.md) | Why it is shaped this way, and what was rejected |
| [Implementations](docs/implementations.md) | Working bodies, and how to write one |
| [Prior art](docs/prior-art.md) | Who else is doing this, with licences |

## License

[MIT](LICENSE).
