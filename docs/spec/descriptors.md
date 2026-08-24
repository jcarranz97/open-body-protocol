# Descriptors

What a body says about itself in response to `body/describe`.

## The body descriptor

```json
{
  "id": "pico-3f5022",
  "name": "Raspberry Pi Pico body",
  "fw": "obp-pico-0.1.0",
  "caps": ["led", "dimmable"]
}
```

| Field | Rules |
|---|---|
| `id` | **MUST** be stable across restarts and reflashes. **SHOULD** derive from hardware — a board serial, a MAC address. |
| `name` | Human-readable. For logs and pickers, never for dispatch. |
| `fw` | Free-form implementation version. |
| `caps` | Coarse labels: `led`, `display`, `audio_in`, `audio_out`, `motion`, `imu`, `dimmable`. Advisory. |

**`id` from hardware, not firmware.** Two independent firmwares on the same
Raspberry Pi Pico — one in C, one in MicroPython — reported the same `id`,
because both read the same board serial. A host registry keyed this way
survives reflashing and even a change of implementation language.

**`caps` are a hint, not the interface.** They let a host pick a rendering
strategy or filter a list without parsing every schema. **Verbs are the
interface**; a host MUST NOT infer that a verb exists because a capability
is present, nor refuse a verb because one is absent.

## The tool descriptor

```json
{
  "name": "set_brightness",
  "description": "Set how brightly the indicator light glows, as a percentage. Use for mood: dim when calm, bright when alert.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "level": {"type": "integer", "minimum": 0, "maximum": 100,
                "description": "0 is off, 100 is full."}
    },
    "required": ["level"]
  },
  "userOnly": false
}
```

| Field | Rules |
|---|---|
| `name` | **MUST** be unique within the body and match `^[a-z][a-z0-9_]*$`. |
| `description` | **MUST** be present and non-empty. |
| `inputSchema` | **MUST** be a JSON Schema object, even when there are no parameters (`{"type": "object", "properties": {}}`). |
| `userOnly` | Optional, default `false`. |

**The description is part of the interface, not documentation.** Where the
consumer is a language model, the description is what it reads to decide
whether this verb is the one it wants. *"Use for mood: dim when calm, bright
when alert"* does more work than the schema does, and a body that ships
`"description": "sets brightness"` has under-specified itself.

## The restricted schema subset

A body's `inputSchema` **SHOULD** use only:

- types `boolean`, `integer`, `number`, `string`
- `enum` on a string
- `minimum` / `maximum` on numbers
- `description` on any property
- `required`

**No nested objects, no arrays of objects, no `$ref`, no composition
keywords.** A host MUST accept a richer schema, but a body that stays inside
the subset can be implemented on a microcontroller with a table rather than
a serialiser.

This restriction is not timidity. Two independent embedded MCP
implementations — `xiaozhi-esp32` and Espressif's own SDK — converged on the
same subset, for the same reason: **a builder must never hand-write JSON
Schema in C.** A firmware helper takes a name, a type and a range and emits
the schema:

```c
mcp_tool_add_property(tool, property_int("level", 0, 100, "0 is off, 100 is full."));
```

Ease of implementation is a protocol concern here, because the bodies will be
built by people who are not protocol implementers.

## `userOnly`

```json
{"name": "reboot", "description": "Restart the body.", "userOnly": true}
```

Marks a verb that a human may invoke but an autonomous caller **MUST NOT**.
`wave` and `reboot` are different kinds of verb and no amount of typing says
so; the distinction becomes serious once a verb moves an arm rather than an
LED.

A host **MUST** exclude `userOnly` verbs from any set offered to an
autonomous decider, and **MAY** expose them in a human interface.

## Capability gating

A body **MUST** advertise only verbs it can actually perform, and this is
expected to vary between physically different units running identical
source.

The reference case: a plain Raspberry Pi Pico drives its LED from GPIO 25 and
can dim it, so it advertises `set_brightness`. A Pico W drives the same LED
through its wireless chip and cannot, so the same firmware advertises one
fewer verb. **The host learns this by asking; nothing is configured.**

## Ordering

A body **MAY** emit verbs in any order. A host **MUST** sort them
deterministically before offering them onward, and **MUST NOT** rely on the
body's ordering being stable.

This is normative because it has already bitten: two firmwares of the same
body disagreed on both verb order and property order, and one of them
(MicroPython, whose dictionaries do not preserve insertion order) cannot
control its own. Where the consumer is a language model, a reshuffled tool
array invalidates its prompt cache — so an unstable order turns a reflash
into a silent, recurring cost.

## Namespacing

Where a host presents verbs from several bodies at once, it **MUST**
namespace them — `body.<id>.<name>` is the recommended form — and **MUST NOT**
merge two bodies into one flat set.
