# Versioning

## The `v` field

Every `body/describe` result carries an integer `v`, the OBP version the
body speaks. This document specifies **v0**.

```json
{"v": 0, "body": {...}, "tools": [...]}
```

A body **MUST** include it. A host **MUST** read it and **MUST NOT** assume a
version it has not seen.

## What bumps it

Only a **breaking** change: removing a field, changing a field's meaning,
changing a message's semantics, or altering the result shape.

Adding an **optional** field is not breaking. Bodies ignore unknown keys;
hosts default missing ones. Most of the protocol's expected growth —
`async`, richer content types, new capability labels — arrives this way.

## The older-peer rule

**The body is always assumed to be the older peer.** A host is redeployed
weekly; a body is reflashed when someone has a cable and a reason.

Therefore:

- A **host MUST** support every version it has ever supported. Dropping
  support for an old `v` breaks devices in the field that nobody is going to
  update.
- A **body** need only understand its own version.
- When a host meets a `v` it does not know, it **MUST** refuse the body with
  a logged, human-readable reason rather than guessing.

## Version 0 is unstable

v0 will change. It is published so that implementations can find its edges,
and [experiments](../implementations.md) have already changed it twice —
deterministic ordering and `userOnly` both came from running code rather than
from design.

Stability is not promised before v1. What *is* promised is that changes are
recorded here, with the reason.

## Extensions

An implementation **MAY** add fields prefixed `x_`. A host **MUST** ignore
unknown `x_` fields, and **MUST NOT** require them.

Anything genuinely useful should stop being an extension: propose it, and if
it is adopted it gets a real name.
