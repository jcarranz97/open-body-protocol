# Presence

Whether a body exists right now, and therefore whether its verbs do.

## The rule

**A host MUST offer only the verbs of bodies that are currently present.**
When presence is lost, the verbs are withdrawn rather than left to fail on
call.

Where the consumer is a language model, this is the difference between a
model that quietly stops trying to wave and a model that keeps calling a
verb into a void and reasoning about the errors.

## Presence is per binding

**There is no single mechanism, and pretending otherwise would leak one
binding's assumptions into the protocol.** Presence is defined by its
semantics; each [binding](bindings.md) states how it is detected.

| Binding | Present when | Lost when |
|---|---|---|
| in-process | the object exists | it is dropped |
| stdio subprocess | the process is running | it exits or its pipe closes |
| serial / USB | the port is open and answers | unplugged, or `ping` unanswered |
| MQTT | a retained message sits on its presence topic | Last Will clears that retained message |

A binding **MUST** define detection for both directions. A binding that
cannot detect loss **MUST** specify a `ping` interval, and the host **MUST**
treat unanswered pings as loss.

## Announced, not polled

A body **SHOULD** announce itself on connect
(`notifications/body/online`), and a host **SHOULD** treat that as sufficient
to begin `body/describe`.

A host **MUST NOT** rely on the announcement alone. A body on a cable may
have been running for hours before the host started, and will never send
another. Every binding therefore also supports discovery by asking — opening
the port and calling `body/describe`, or reading the retained set.

## Flapping

A host **SHOULD** debounce: a body that disappears and returns within a short
window is the same body, and withdrawing and re-adding its verbs on every
blip is worse than briefly stale ones.

Identity makes this safe. Because `id` derives from hardware, a host can tell
*the same body reconnected* from *a different body appeared* without
guessing.

## Several bodies

Bodies are independent. One leaving **MUST NOT** disturb another's verbs, and
a host **MUST** support several present at once — a terminal, a device on
USB, and a device on the network, all in the same registry with verbs from
all three offered together.

## On restart

After a host restarts it **MUST** re-establish presence from scratch: re-read
retained messages, re-open ports, re-spawn subprocesses, and call
`body/describe` again. It **MUST NOT** assume a cached description is still
accurate — the body may have been reflashed while the host was away, and its
verbs may have changed.
