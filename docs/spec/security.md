# Security considerations

OBP connects an autonomous decider to something that moves. The
considerations follow from that, and several are unusual enough to be worth
stating plainly.

## The body is a credential boundary

A body **MUST NOT** hold secrets beyond what its own connection needs. No API
keys, no bot tokens, no user data. A body is a thing that can be lost,
borrowed, reflashed or bought second-hand.

Where a binding supports authentication, credentials **MUST** be per body, so
one can be revoked without touching the others.

## The host must not trust the body

A body's `description` text reaches a language model. A malicious or
compromised body can therefore attempt **prompt injection** through its own
tool descriptions, its result text, or its event payloads.

A host **SHOULD** treat all body-supplied text as untrusted data:

- present descriptions and results as data, clearly delimited, never as
  instructions;
- bound their length;
- refuse control characters and escape sequences.

This is a real path, not a theoretical one: connecting a body means adding a
stranger's text to a model's context.

## The body must not trust the host

A body **MUST** validate every argument against its own schema and its own
physical limits. A host may be buggy, may be driven by a confused model, or
may not be the host the body's owner intended.

Physical limits are the body's to enforce, always. **A body that relies on
the host to stay within its servo range has no safety at all**, since the
host cannot know the linkage jammed.

## `userOnly` is not access control

Marking a verb `userOnly` keeps it out of an autonomous caller's tool set.
It does not authenticate anyone, and it does not stop a host that ignores
the flag. It is a guardrail against a model doing something surprising, not
a defence against an attacker who already speaks to the body.

Genuinely dangerous verbs need a physical interlock — a button held, a
key turned — and that interlock belongs to the body.

## Rate and repetition

A body **SHOULD** rate-limit destructive or wearing verbs, and **SHOULD** be
idempotent where physics allows. A looping caller is a normal failure mode
for an autonomous system, and the body is the only party that knows a servo
is overheating.

## The privileged escape hatch

Any verb capable of running a command, writing arbitrary storage, or
reflashing the body **MUST** be `userOnly`, and **SHOULD** simply not exist.
A body is not a shell, and reaching a body must not thereby reach the host it
is plugged into.

## Bindings carry their own risks

- **stdio / serial** — no authentication at all. Physical access is
  authorisation. On Linux this also means group membership on the device
  node.
- **MQTT** — credentials and ACLs per body; a body may publish only to its
  own topics and subscribe only to what it is sent, so it cannot impersonate
  the host or read another body's traffic.
- **in-process** — the body is code in the host, and is as trusted as the
  host.

## What OBP does not do

No confidentiality, integrity or authentication of its own. It is carried
over whatever the binding provides — TLS, a USB cable, a function call. A
deployment that needs those **MUST** obtain them from the binding.
