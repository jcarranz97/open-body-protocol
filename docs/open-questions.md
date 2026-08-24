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

## How an event reaches a brain that is not looking

Experiment 005 gets a button press from the body to the *host*. What it does
not solve is the last hop: from the host to a brain that is not currently
paying attention. Two deployment shapes need different answers, and the
protocol should stay out of both.

**The body is attached to someone's session.** A person is already using
Claude Code or OpenCode for their own work and adds a robot as an MCP server.
They are present and driving; the body is an actuator. Polling is *legitimate*
here — "wait until I press the button" is a reasonable thing to ask an agent
that is sitting there anyway, and `obp__wait_for_event` is the right tool
rather than a workaround.

**The body owns a session.** The robot has its own computer running a
long-lived agent, and input comes *from* the robot — a button, a spoken
sentence. Nobody is typing. Polling is wrong here: something must be awake on
the robot's behalf, and the event has to arrive as a turn. This is the shape a
Telegram bot has, and the reason it works is that a process is always listening
and injects the message.

**The body is identical in both.** Same firmware, same events on the wire.
What differs is entirely host-side, which is the argument that this belongs in
a reference host — desk-buddy — rather than in the specification.

Research into the transport half is unambiguous: **MQTT 5 persistent sessions
already solve the offline-consumer problem**, and OBP's MQTT binding is one
CONNECT flag away from it. `Clean Start = 0`, a `Session Expiry Interval`
covering the worst expected outage, QoS 1, and — the part everyone gets wrong —
a *stable client id*, since the session is keyed on it and a randomised id on
each boot silently discards the whole mechanism. Retained messages answer "what
is true now"; the persistent session answers "what happened while I was away",
and a body wants both. Message Expiry Interval matters too: a brain that
reconnects after six hours should not act on a six-hour-old button press.

The open part is not the transport. It is what turns a queued event into a turn
in an agent's context, and whether OBP should say anything at all about it.

### What the mechanisms actually are

Research settled the host-side options, and they are worth writing down because
the constraints are not obvious.

**Claude Code Channels is an MCP server**, and a small one: declare
`capabilities.experimental['claude/channel']` as an empty object, emit
`notifications/claude/channel` with a `content` string and a `meta` map, and
connect over stdio. The event reaches the model as a tag whose `source` is the
server name and whose attributes come from `meta`. Registration needs both an
`.mcp.json` entry and the server named at launch.

Its limits matter more than its interface. It is a research preview whose flag
syntax may change; it delivers **only into a live session** and cannot wake a
dead one; and it is **fire-and-forget** — if the session did not load the
server as a channel, events are dropped silently with no error to the sender.
So a channel is a good doorbell and a bad system of record, which is the
argument for the persistent-session backlog underneath it.

It also confirms the constraint from the other direction: Claude Code will not
register a channel server that negotiates the 2026-07-28 revision, *because
that revision cannot carry channel messages*. Channels depend on precisely the
server-initiated notifications that revision removed.

**A server can push, but not usefully.** The claim "an MCP server cannot speak
first" is slightly too strong: over a client-opened `subscriptions/listen`
stream a server may push four notification types — tools/prompts/resources list
changes and resource-subscription updates. None carries an application payload,
so a robot event arrives as a doorbell with a URI and nothing else.

**Blocking works over stdio and not over HTTP.** A tool call that blocks for
30–300s is fine on a stdio server, which has no per-request timer. The same
tool over HTTP hits a 60-second first-byte timer. This is what makes
`obp__wait_for_event` viable in the attached-body case, and it is a property of
the transport rather than of the design.

The deeper objection to blocking is unchanged and is not about timeouts: it
only works while the model is *already* calling the tool, which means the agent
had to decide to wait. That leaves "an agent that is not currently looking"
exactly where it was.

**The pattern behind all of it.** Surveying agent frameworks, the ability to
deliver an unsolicited event exists wherever a run is *not turn-shaped* —
persistent bidirectional socket, actor mailbox, or durable server-side ingress.
Everything shaped like `run() → result` answers no in the same way: the agent
interrupts itself, the run ends, and the caller re-invokes with a resume token.

The striking part is that every framework that has this solved got it through
its **voice** branch, not its text branch — same vendor, same SDK, opposite
answer. Barge-in and event-signalling are the same problem, and only voice
forced anyone to solve it. Which is the argument that a microphone is not a
harder version of a button but the case that reveals what a button lets you
get away with.

## Whether a body with a microphone needs anything new

A button is a bad model for sensing, because it hides two questions. A
microphone asks both: what can a small machine actually compute, and what does
the wire carry?

**Raw audio does not belong in this protocol, and that is not a close call.**
Seven voice systems were surveyed and none that had a choice text-encodes audio
into a control message. Three shapes are used instead: a separate transport
(xiaozhi's MQTT for control and UDP for Opus, whose documentation says plainly
that *"control is separated from data so audio has low latency"*), a separate
frame type on one connection (xiaozhi's WebSocket mode), or length-prefixed
binary sitting outside the parsed object (Wyoming writes its JSON line, then
raw bytes the parser skips by byte count — never base64).

The forces all point the same way. Base64 inflates by a third before framing —
OpenAI's WebSocket audio path costs about 1 Mbps against 32–56 kbps for the
same speech as WebRTC Opus. Audio arrives every 20–60 ms forever, so any
control message queued behind it is delivered late. And on a microcontroller,
base64-encoding and JSON-parsing every frame competes with the codec for the
same core.

Notably, where control *does* bootstrap media, it carries a reference rather
than the thing: xiaozhi hands the UDP encryption key over MQTT in its hello,
and pushes downlink speech as an `audio_url` the device fetches for itself.

**An utterance, however, is already an event, and OBP already has that
message.** Four systems in production treat a spoken phrase as a discrete
notification with a text payload — xiaozhi emits `{"type":"listen","state":
"detect","text":"<wake word>"}`, Wyoming has `detection` and `transcript`,
Hermes publishes `hermes/asr/textCaptured`, ESPHome exposes the transcript to
the device itself. `notifications/body/event` with `type: "speech"` is the same
shape, and needs no change.

**What a body can put in that payload depends on what kind of machine it is,**
and this is a hardware ceiling rather than a design choice. Free-form speech to
text needs hundreds of megabytes — whisper tiny about 273 MB, Vosk small about
300 MB — so a transcript never comes from a microcontroller. An ESP32-S3 with
PSRAM and roughly 6 MB of flash manages a wake word and a closed vocabulary of
a few hundred commands; a C3 or C5 with WakeNet9s manages a wake word alone; a
Pi-class body transcribes. Picovoice draws the same line commercially: Rhino
emits an intent on a Cortex-M, while transcription starts at a Raspberry Pi 3.

A Pico is a button, not an ear, and the reason is compute rather than memory —
the model and its arena come to about 48 KB against 264 KB available, but an
M0+ with no FPU and no SIMD saturates on two keywords at 4 kHz.

That variety is a good argument for the existing design rather than a problem
for it: a body advertises only what it can do, so a `caps` entry and the verbs
it offers already say whether a transcript is on the table. Where a body can do
both, a transcript should be the primary payload and an intent an optional
refinement beside it — a closed vocabulary drops from 91.5% to 78.25% accuracy
under white noise, and a transcript is what keeps open-ended reasoning
available to the brain.

**Barge-in restates a rule this project already has.** When someone interrupts,
the body must abort locally and immediately, then report *how much it actually
rendered* — OpenAI's realtime API requires the client to send the number of
milliseconds truly played, because the server produced audio faster than
realtime and its own model of the world is wrong. Only the body knows what it
did. That is [the same principle](../experiments/005-body-speaks-first/) as a
body owning the report of its own actuation, arrived at from the opposite
direction, and the analogue for a limb is the pose actually reached.

So the open question is narrower than it looked. Nothing about an utterance
needs new protocol. What OBP has no vocabulary for is a **media lane**: a way
for a body to say "I have a stream, here is where to get it", negotiated by the
control channel and carried somewhere else entirely.

### How the working systems actually do it

Surveying the harnesses that already bridge a chat app to an agent — Hermes,
OpenCode, Goose — settles the shape, and corrects the question.

**The message list is the database.** All three persist an inbound message to
SQLite *first*, then rebuild the turn's context by re-reading the table. Goose
re-reads the whole conversation on every turn; OpenCode re-reads the message
list each loop iteration; Hermes replays transcript rows and keeps only a warm
agent shell, not the state. None of them holds the conversation in process
memory as the source of truth.

So "how do we wake a sleeping session?" is the wrong question. Between turns
there is no process state to wake — there are rows. An event does not need to
interrupt anything; it needs to be *durably written where the next turn will
read it*. A long-lived process then exists to notice and start that turn, which
is a much weaker requirement than injecting into a live context.

That is the same shape as the event log and the MQTT persistent session in
[experiment 005](../experiments/005-body-speaks-first/), arrived at
independently by three harnesses that had to make it work.

**What happens to a message that arrives mid-turn is the real design axis, and
nobody agrees.** Claude Code Channels queues and delivers grouped on the next
turn. OpenCode queues, never rejects, never aborts. Goose *rejects* outright —
"session already has active run". Hermes makes it configurable between
interrupt, queue and steer, defaulting to interrupt.

This matters here because a robot's events are exactly the mid-turn case: a
button gets pressed while the agent is doing something else. Four production
systems chose four different answers, which is a strong hint that OBP should
carry the event and let the host decide, rather than legislate.

**And the seam is visible in the naming.** ACP has standardised starting a turn
— `session/new`, `session/prompt`, `session/update`,
`session/request_permission` — but *not* interrupting or amending one in
flight. Goose had to invent `_goose/unstable/session/steer`; the vendor prefix
and the `unstable` are the tell. Hermes invented a different one. Interrupting
a running turn is the next unstandardised frontier, and it is precisely what a
body that speaks unprompted needs most.

**One constraint recurs everywhere and is worth knowing before designing:**
Telegram long-polling allows a single consumer per bot token. That one fact is
what forces the "one session owns the bot" shape in Claude Code's plugin, in
Goose's gateway and in most community bridges. Webhooks appear only where a
hosted relay or a suspendable cloud machine already exists — which is the same
NAT story the transport research told.

### Where OBP sits, given what is already standardising

One finding from the survey is worth stating on its own, because it bears on
scope rather than on any particular feature.

**Something is already standardising the brain side.** ACP — `session/new`,
`session/prompt`, `session/update`, `session/request_permission`, over JSON-RPC
— has 39 agents in its registry, including Claude, Codex, Gemini CLI, Cursor,
Copilot, Goose and OpenCode. Goose *is* an ACP server. That is the "connect any
brain" half of this project's ambition, being built by other people, and
converging.

It suggests a cleaner division than the one we had been assuming. ACP is how
you talk to any brain; OBP is how you talk to any body. They are complementary
halves rather than competitors, and the useful consequence is that **OBP should
stay narrow**. Every brain-side feature this protocol grows is one that
duplicates work already happening elsewhere, on a surface OBP does not control.

The inbound half is the part nobody has standardised. MCP has no primitive for
a server to push an unsolicited turn — Anthropic filled that gap with a
proprietary `experimental` capability rather than an MCP feature, and a channel
event ends up **on the same prompt queue as human input**, tagged as meta and
attributed to the channel. So a body's press does not interrupt a model; it
arrives the way a person typing would. That is the same "durably write it where
the next turn reads it" shape as everything else in this section, applied one
layer further in.
