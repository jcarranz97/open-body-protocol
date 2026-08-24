# Conformance

The authoritative list of normative requirements. Prose elsewhere explains
them; this page is what an implementation is measured against.

## Levels

| Level | Means |
|---|---|
| **Core** | Everything below marked *core*. A body at this level works with any host. |
| **Actions** | Core, plus the long-action lifecycle ([results](results.md)). |
| **Events** | Core, plus unsolicited `notifications/body/event`. |

Core is small on purpose: a body with one LED should be a weekend, and every
requirement here is one somebody would otherwise get wrong.

## A conforming body

### Identity and description — core

| | Requirement |
|---|---|
| B1 | **MUST** answer `body/describe` with `v`, a body descriptor and a tool array. |
| B2 | **MUST** report an `id` stable across restarts and reflashes; **SHOULD** derive it from hardware. |
| B3 | **MUST** give every verb a unique `name`, a non-empty `description`, and an `inputSchema` object. |
| B4 | **MUST** advertise only verbs it can actually perform on the hardware it is running on. |
| B4a | **MUST NOT** report success for an action it did not perform. A verb standing in for absent hardware **MUST** either be left out of the descriptor or return `isError: true`. Explaining the simulation in the result text is not sufficient: a host reads `isError`, so a "success" that means nothing happened is a body lying about the world, and no care taken in the brain can detect it. |
| B5 | **SHOULD** restrict schemas to the [documented subset](descriptors.md#the-restricted-schema-subset). |
| B6 | **MUST** mark verbs unsafe for autonomous use as `userOnly`. |
| B7 | **MUST** answer `body/describe` at any time, including mid-action. |

### Invocation — core

| | Requirement |
|---|---|
| B8 | **MUST** reply to every `tools/call`. |
| B8a | **MUST** echo the request's `id` verbatim, whether it is a string or a number. A reply carrying any other `id` is unmatchable, and is worse than no reply: the body looks silent while it is in fact answering. |
| B9 | **MUST** validate arguments against its own schema and physical limits, and **MUST NOT** trust the host. |
| B10 | **MUST** return `isError: true` with readable text for a rejected or impossible call. |
| B11 | **MUST NOT** crash, hang or close the connection on malformed input. |
| B12 | **MUST** answer an unknown method with JSON-RPC `-32601`. |
| B13 | **MUST** own execution: kinematics, timing, limits and reflexes. |
| B14 | **MUST NOT** accept raw actuator commands as a substitute for verbs. |

### Liveness — core

| | Requirement |
|---|---|
| B15 | **MUST** answer `ping` promptly. |
| B16 | **SHOULD** send `notifications/body/online` when it can speak. |
| B17 | **SHOULD** keep functioning — reflexes, local behaviour — with no host present. |

### Actions — level *actions*

| | Requirement |
|---|---|
| B18 | **MUST** mark long verbs `"async": true`. |
| B19 | **MUST** reply immediately with `accepted` and a `call_id`. |
| B20 | **MUST** emit a terminal `done`, `failed` or `cancelled` for every accepted action. |
| B21 | **MUST** support `tools/cancel`, even if cancelling means stopping where it is. |

## A conforming host

| | Requirement |
|---|---|
| H1 | **MUST** discover verbs by calling `body/describe`, never from a built-in catalogue of device types. |
| H2 | **MUST** sort verbs deterministically before offering them onward. |
| H3 | **MUST** namespace verbs when several bodies are present. |
| H4 | **MUST** withhold `userOnly` verbs from autonomous callers. |
| H4a | **MUST NOT** make a `userOnly` verb unreachable altogether; a human interface **MAY** invoke it. |
| H5 | **MUST** withdraw a body's verbs when presence is lost. |
| H5a | **MUST** treat an error talking to a body as loss of presence, and **MUST NOT** report attach-time inventory as current presence. |
| H5b | **SHOULD** address a serial body by a stable identifier rather than a numbered device node, and re-resolve it when reattaching. |
| H6 | **MUST** synthesise an `isError` result — never hang — for a call to a body that has gone. |
| H7 | **MUST** apply a timeout to every call and surface expiry as a result. |
| H8 | **MUST** re-read `body/describe` after a reconnect, and **MUST NOT** reuse a cached description. |
| H9 | **MUST** support every `v` it has ever supported. |
| H10 | **SHOULD** validate arguments before sending. |
| H11 | **SHOULD** treat all body-supplied text as untrusted data ([security](security.md)). |
| H12 | **MUST NOT** require a capability label to be present before using a verb. |

## A host exposing bodies over MCP

Optional — a host need not speak MCP at all. One that does **MUST** follow
these, so that an agent's configuration is portable between hosts
([guide](../guides/connecting-agents.md)).

| | Requirement |
|---|---|
| M1 | **MUST** name tools `<sanitised-body-id>__<verb>`, replacing characters outside `[a-zA-Z0-9_-]` with `_`. |
| M2 | **MUST** keep names within 64 characters by truncating the body id — never the verb — and appending `_` plus six hex characters of the SHA-256 of the full `<id>__<verb>`. |
| M3 | **MUST** produce the same tool name for the same body and verb on every host and every run. |
| M4 | **MUST NOT** expose `userOnly` verbs. |
| M5 | **MUST** pass `inputSchema`, `content` and `isError` through unchanged. |
| M6 | **MUST** declare `tools.listChanged` and emit `notifications/tools/list_changed` when a body arrives or leaves. |
| M7 | **MUST** return an `isError` tool result — never a protocol error, never a hang — when a body vanishes mid-call. |
| M8 | **MUST** document whether `async` verbs block or detach. |
| M9 | **MUST** remain available when no body is attached, and **SHOULD** offer a way for the caller to learn why. A server that exits because a body is unreachable is indistinguishable, to an agent, from a broken server. |

## Testing a body

The reference host ships a conformance runner. With no hardware:

```bash
obp-conformance --fake
```

Against a real device:

```bash
obp-conformance --port /dev/ttyACM0
```

It exercises each requirement above that can be checked from outside —
describe round trip, schema validity, unique names, `userOnly` presence,
out-of-range rejection, malformed input survival, unknown method handling,
`ping`, and ordering stability across two describes.

Four requirements cannot be tested from outside and are left to review:

- **B4** — whether advertised verbs match the hardware.
- **B13** — whether the body really owns its limits.
- **B17** — behaviour with no host.
- **H11** — how a host handles hostile text.

A body that passes core is usable by any host. A body that passes core *and*
has been read by someone for B4 and B13 is one you would let move.
