# Rationale

Why the protocol is shaped this way, and what was rejected. A specification
that only says *what* leaves the next person to re-litigate every decision.

## Why the body describes itself

The alternative is a catalogue of device types in the host — the model used
by Zigbee clusters, Matter device types and Home Assistant's entity classes.
It works beautifully for categories that are known in advance, and fails the
moment somebody builds a thing nobody anticipated.

That failure is the entire premise here. The bodies will be built by
strangers, and a host that must be taught what a claw is cannot be driven by
one.

So: the body carries the schema, and the host carries none of it.

## Why tool descriptors, and why MCP's shape

Surveying what already exists, every candidate falls into one of three
buckets:

| | Examples |
|---|---|
| Advertises state, has no actions | OCF, AWS Shadow, Home Assistant discovery, Zigbee2MQTT |
| Has actions, advertises nothing | LwM2M in practice, ThingsBoard RPC, Tasmota, AWS Commands |
| Has typed actions, but the schema is compiled in | ROS 2, Matter |

The single thing that does all three — runtime-published callable actions,
each with a name, a **description** and a JSON Schema — is MCP's `tools/list`.

Borrowing that shape has a specific payoff: **no translation layer**. A host
can hand a body's verbs to an MCP consumer unchanged, and translation layers
are exactly where semantics get lost.

Rejected along the way:

- **W3C WoT Thing Description.** Conceptually the right model, but its MQTT
  binding is an unfinished editor's draft, nothing in the agent ecosystem
  consumes a TD, and its `input` is a DataSchema dialect rather than JSON
  Schema — so you write two converters instead of none.
- **OPC UA.** The best introspection model in industry — named, typed
  arguments discoverable by browsing. Unusable here: its Nano and Micro
  embedded profiles, the ones for this class of hardware, do not support
  Methods at all, and the only ESP32 port needs PSRAM, 4 MB of flash and
  ~155 KB of heap.
- **Matter.** 1.48 MB of flash and 195 KB of DRAM for a light switch on an
  ESP32-C3, and no sanctioned extension point for a verb nobody standardised.
- **LwM2M.** Genuinely built for this hardware class, and its Execute
  operation takes ten positional untyped ASCII arguments with no
  machine-readable parameter description anywhere.

## Why not MCP itself, over MQTT

EMQX published exactly that binding, and it is dormant: an 8-star firmware
library untouched since December 2025, a spec repository with no licence
file, and an implementation pinned to MCP's first-ever revision. Conforming
would mean mandatory MQTT 5, `$`-prefixed topics many brokers reserve, and
broker-assigned names — to interoperate with an ecosystem of approximately
zero.

Its one excellent idea, **presence as a retained message cleared by an
empty-payload Last Will**, was taken.

## Why intents rather than motor commands

Three independent lines of evidence, all pointing the same way.

**Every shipped robot pet exposes verbs.** Petoi's serial protocol is `k` +
skill name; XGO has `action(13)`; Vector has `pop_a_wheelie()`; Reachy has
`look_at()` with joint control documented as "not recommended". Joint access
exists everywhere as a discouraged escape hatch.

**Every LLM-plus-robot project puts the model at supervisory rate.** NASA
JPL's ROSA wraps the ROS CLI as tools and is read-mostly; Robotec's RAI added
a *blocking* Nav2 tool so the model emits a goal and waits. Nobody puts a
model inside a control loop.

**A tool call costs one to three seconds.** Wheels cannot be driven at that
rate, and the world changes underneath a decision — RAI's own bug title says
it: *"Transform obtained from GetROS2TransformTool can be old."*

So the brain names an intent and the body re-validates and executes it. The
smallest illustration is in the reference body: a request for 10% brightness
becomes 1% duty cycle, because perceived brightness goes as roughly the
square root of duty. The host said what it wanted; the body decided what that
meant.

## Why the host sorts the verbs

Because two firmwares of the same body disagreed on order, and one of them
could not fix its side — MicroPython's dictionaries do not preserve insertion
order. Where the consumer is a language model, a reshuffled tool array
invalidates its prompt cache, so an unstable order turns a reflash into a
silent recurring cost. Making it the host's job is the only place it can be
fixed once.

## Why presence is abstract

MQTT's retained-message-plus-Last-Will is the best presence mechanism in the
protocol, and it does not exist on a USB cable. Specifying it as *the*
mechanism would have made the elegant case normative and left the common case
undefined. So presence is defined by its semantics, and each binding says how
it is detected.

## Why no brain side

OBP is the Open **Body** Protocol. How a decider works — which model, what it
remembers, who it is, how it is deployed — is somebody else's concern, and
several projects already do it well.

Specifying it here would have made the protocol harder to adopt for exactly
the people most likely to adopt it: someone with a working agent who wants to
give it a body. [desk-buddy](https://github.com/jcarranz97/desk-buddy) is one
answer to those questions, and deliberately a separate repository.

## Why JSON, and why not a binary encoding

A microcontroller can emit JSON with `printf` and parse the subset it needs
in about 200 lines, verified on the reference body. A binary encoding would
be smaller and would need a schema compiler, a code generator and a version
negotiation — for payloads measured in hundreds of bytes on links measured in
megabits.

Where that stops being true — a BLE link with a 247-byte MTU — the answer is
a packed encoding of the *same* messages, defined as a binding rather than as
a second protocol.
