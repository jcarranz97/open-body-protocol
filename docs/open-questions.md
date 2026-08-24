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

## Whether selecting a body belongs in the specification at all

A person driving several bodies wants one of them in focus — *"I am operating
the arm"* — so an unqualified instruction means that body. [Experiment
004](https://github.com/jcarranz97/open-body-protocol/tree/main/experiments/004-many-bodies)
implements this and deliberately does **not** add a requirement for it.

It is host-side by the test this specification already applies: it constrains
nobody implementing a body. A drone does not need to know it has been
deselected, any more than it needs to know a verb was marked `userOnly`. Making
it protocol would mean every body implementing a concept only the host uses.

What the experiment settled, and what a host doing this should probably be held
to, is that **selection must not filter the tool list**:

- MCP's 2026-07-28 revision (SEP-2567) requires that `tools/list` not depend on
  per-connection or prior-tool-call state.
- Tool definitions sit at the front of a model's cache prefix, so replacing
  them discards the system prompt and the whole conversation with them.
- A filtered list makes the motivating case impossible: with the arm selected,
  "turn on the lights in room1" must still work.

Whether those become `H` requirements is the open part. Arguments against:
`H2` and `H3` already forbid the mechanism a filtering host would need, so a
new rule may be redundant; and a specification that starts describing host
convenience features grows without limit. Arguments for: two hosts that
disagree about what an unqualified verb means are not interchangeable, and
`connecting-agents.md` already says *"two hosts must expose the same body
identically, or an agent configuration stops being portable."*

Three sub-questions the experiment answered by choosing, none of which is
obviously right:

- **A failed selection clears** (IMAP: *"no mailbox is selected"*) rather than
  leaving the previous one live (POSIX `chdir`). For physical bodies the IMAP
  behaviour looks clearly safer, but it means a typo silently costs you your
  focus.
- **A verb the selected body lacks is refused, naming the bodies that have
  it** — never auto-retargeted. Defensible alternative: auto-redirect when
  exactly one other body qualifies and the verb is read-only, which is what the
  disambiguation literature suggests and what a smoother assistant would do.
- **Selection is process-scoped** (`$OBP_BODY`, like `adb`'s
  `$ANDROID_SERIAL`), not stored in a shared file — `kubectl`'s
  `current-context` is one global pointer shared by every terminal. The
  stricter design is request-scoped, as in NFSv4's current filehandle, which is
  unset at the start of every request; that is what a multi-user host would
  need and this one does not have.
