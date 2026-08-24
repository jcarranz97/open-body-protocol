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

**Attachment is not presence.** A host that reports what it attached at
startup, rather than what is reachable now, will confidently list a body that
has been unplugged for an hour. A failed operation is therefore a presence
signal in its own right: a host **MUST** treat an error talking to a body as
loss of presence, not merely as a failed call.

The reference host learned this the hard way. A Raspberry Pi Pico
re-enumerated from `/dev/ttyACM0` to `/dev/ttyACM1` mid-session; every write
then failed, and the host's status verb went on reporting the body as
attached with all four verbs available.

## Announced, not polled

A body **SHOULD** announce itself on connect
(`notifications/body/online`), and a host **SHOULD** treat that as sufficient
to begin `body/describe`.

A host **MUST NOT** rely on the announcement alone. A body on a cable may
have been running for hours before the host started, and will never send
another. Every binding therefore also supports discovery by asking — opening
the port and calling `body/describe`, or reading the retained set.

## Device paths are not identities

On Linux a USB serial device is `/dev/ttyACM0` until something re-enumerates
it and it becomes `/dev/ttyACM1`. A host holding the old path writes into a
node that no longer exists.

A host **SHOULD** therefore address a serial body by something stable — on
Linux, the `/dev/serial/by-id/` symlink, which is keyed on the USB serial
number — and **SHOULD** re-resolve it when reattaching. For boards whose OBP
`id` derives from the same hardware serial, the two identities coincide, and
`pico-3f5022` is findable without configuration.

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
