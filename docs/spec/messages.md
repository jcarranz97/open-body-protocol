# Messages

Five messages. Every one is a JSON-RPC 2.0 object; requests carry an `id`,
notifications do not.

An `id` **MAY** be a string or a number, and a reply **MUST** echo the
request's verbatim, preserving its type ([B8a](conformance.md)). It is the only
thing tying an answer to the question that asked it, and a host skips replies it
cannot match — so a body that rewrites, renumbers or coerces the `id` does not
fail loudly. It appears to say nothing at all while answering perfectly. Do not
parse it as an integer; treat it as an opaque token to be handed back.

| Message | Direction | Kind |
|---|---|---|
| `notifications/body/online` | body → host | notification |
| `notifications/body/offline` | body → host | notification |
| `notifications/body/event` | body → host | notification |
| `body/describe` | host → body | request |
| `tools/call` | host → body | request |
| `ping` | host → body | request |

## `notifications/body/online`

Sent by a body as soon as it can speak. Carries enough to be recognised
before a full description is fetched.

```json
{"jsonrpc": "2.0", "method": "notifications/body/online",
 "params": {"id": "pico-3f5022", "fw": "obp-pico-0.1.0"}}
```

A host **MUST NOT** require this message: a body attached to a cable may have
been running long before the host started, so a host **MUST** also be able to
discover a body by asking ([presence](presence.md)).

## `notifications/body/offline`

Best-effort, for a body that knows it is going.

```json
{"jsonrpc": "2.0", "method": "notifications/body/offline",
 "params": {"id": "pico-3f5022", "reason": "reboot"}}
```

A host **MUST NOT** depend on it. Most departures are power loss.

## `body/describe`

```json
{"jsonrpc": "2.0", "id": 1, "method": "body/describe"}
```

```json
{"jsonrpc": "2.0", "id": 1, "result": {
  "v": 0,
  "body": {"id": "pico-3f5022", "name": "Raspberry Pi Pico body",
           "fw": "obp-pico-0.1.0", "caps": ["led", "dimmable"]},
  "tools": [ /* descriptors */ ]
}}
```

**Identity, capabilities and verbs arrive together, in one round trip.** This
is deliberate and differs from MCP, which separates `initialize` from
`tools/list`. On a serial link every round trip costs, a body's description
is small, and MCP's own 2026-07-28 revision retired that handshake.

A host **MAY** call `body/describe` again at any time, and **MUST** re-read it
after a body reconnects. A body **MUST** answer it at any point, including
while an action is running.

## `tools/call`

```json
{"jsonrpc": "2.0", "id": "01J8XRQ2F7", "method": "tools/call",
 "params": {"name": "set_brightness", "arguments": {"level": 40}}}
```

- `name` **MUST** be a verb the body advertised.
- `arguments` **MUST** validate against that verb's `inputSchema`. A host
  **SHOULD** validate before sending; a body **MUST** validate on receipt and
  **MUST NOT** trust the host.
- A body **MUST** reply, with a [result](results.md), for every call.

Calls are independent. A body **MAY** execute several concurrently, and
**MUST** either serialise or reject a call it cannot run alongside another —
never silently interleave conflicting motion.

## `ping`

```json
{"jsonrpc": "2.0", "id": 3, "method": "ping"}
```

```json
{"jsonrpc": "2.0", "id": 3, "result": {}}
```

Liveness for bindings that cannot tell on their own. A body **MUST** answer
promptly and **MUST NOT** treat it as activity for any idle logic.

## `notifications/body/event`

Something the body noticed, unprompted: a button, a sensor threshold, a
completed motion.

```json
{"jsonrpc": "2.0", "method": "notifications/body/event",
 "params": {"id": "01J8XR...", "ts": "2026-08-24T09:14:02Z",
            "type": "button", "name": "top", "payload": {"hold_ms": 120}}}
```

- `id` **SHOULD** be a ULID or UUID, so a host can deduplicate across a
  reconnect.
- `ts` is the body's clock. Where a body's clock is unreliable it **SHOULD**
  say so with `"clock_confident": false`, and a host **SHOULD** then prefer
  arrival time.

Events are the body's only way to speak first. A host **MUST** tolerate
events for verbs and types it does not recognise.

## Unknown methods

A body **MUST** answer an unrecognised method with a JSON-RPC error:

```json
{"jsonrpc": "2.0", "id": 4,
 "error": {"code": -32601, "message": "method not found: tools/list"}}
```

**A protocol error means "I do not implement that message."** It is not how a
verb reports failure — see [results](results.md).
