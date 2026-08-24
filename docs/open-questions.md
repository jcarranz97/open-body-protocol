# Open questions

Things the specification deliberately does not answer yet. They are recorded
here rather than settled quietly, because a normative rule is expensive to
withdraw once implementers have built against it — and because a question that
looks obvious from one implementation often is not from another.

An entry here is an invitation to argue. If you have hit one of these in a real
body, that experience is worth more than the reasoning below it.

## Two bodies claiming the same id

`B2` requires an id stable across restarts and reflashes, and recommends
deriving it from hardware. It says nothing about what a host should do when two
bodies present the same id at once.

This is not hypothetical: hardware-derived ids do not collide, but a
hand-assigned one, a cloned firmware image, or a body reachable over two
bindings at the same time all produce it. **The host cannot distinguish those
cases** — identical firmware yields identical descriptors, so one body reached
twice and two boards flashed alike look exactly the same from the outside.

The reference host in
[experiment 004](https://github.com/jcarranz97/open-body-protocol/tree/main/experiments/004-many-bodies) refuses the newcomer and keeps the
incumbent, with a diagnostic naming both transports. The reasoning: if it is
one body, a second route adds nothing; if it is two boards, merging them means
every command reaches an arbitrary one of the pair, which for anything with
motors is the worst available outcome. Before that it silently replaced the
incumbent and leaked its connection, which is the one clearly wrong answer.

Defensible alternatives, none of them ruled out:

- **Prefer the newer.** A body that just announced itself is more likely to be
  the live one; the incumbent may be a stale entry nobody has swept.
- **Disambiguate by transport**, addressing them as `id@usb` and `id@mqtt`.
  Honest about there being two routes, at the cost of making a body's name
  depend on how you reached it — which `B2` exists to avoid.
- **Say nothing at all**, and leave it entirely to hosts. Different deployments
  may genuinely want different answers.

What is not in doubt is that a collision must be *visible*. A host that quietly
picks one is a host whose commands land somewhere the operator did not choose.

## Whether a body may be reached over two bindings at once

Related but distinct. Nothing forbids a body speaking OBP over USB and MQTT
simultaneously, and there are good reasons to want it — a local fallback when
the network is down, or a wired console for debugging a wireless robot.

The specification currently neither blesses nor forbids it, and the identity
question above is what makes it awkward: the second route arrives at a host
looking exactly like a duplicate. A resolution probably needs a way for a body
to say "this is another route to me", which is a message the protocol does not
have.

## How long a host should wait before declaring a body gone

[Presence](spec/presence.md) says attachment is not presence, and the MQTT
binding clears a retained announcement with a Last Will. But the broker only
notices a dead client after a keep-alive, so there is a window — measured at
**13 seconds** on the Pico W in experiment 003 — where a host believes a body
is present and every call to it will fail.

A body that leaves deliberately can and should clear its own presence first,
which closes the window to nothing. The open part is what a host should do
about the involuntary case: whether the specification should recommend a
timeout, require hosts to treat a failed call as evidence of absence, or leave
it to each binding.
