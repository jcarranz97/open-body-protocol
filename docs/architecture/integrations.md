# Integrations

The pet's two other faces: a Telegram bot, and a webhook that lets the
homelab itself reach in. Both are adapters on the daemon's bus
([overview](overview.md)) — neither is a special case in the core.

## Telegram

Telegram is not a remote control for the pet. It is a **second body made of
text** (FR-090). The same event flows through the same code path whether it
arrived as a button press or a `/feed`.

**The bot token lives only in the daemon.** The ESP32 never talks to
Telegram. Two clients polling `getUpdates` on one token fight each other, and
a token does not belong on a device that gets reflashed weekly (NFR-011).

| Command | Effect |
|---|---|
| `/status` | Stats as a text bar chart plus the current mood |
| `/feed` `/play` `/clean` | The same code path as a physical button press |
| `/talk <text>` | A full brain turn; the reply goes to Telegram **and** the device screen |
| `/journal` | The last 7 daily entries |
| `/quiet 3h` | Suppress proactive nudges |

### Proactive messages

The daemon initiates: neglect thresholds, illness, evolution, a death
warning. Capped at **3 per day**, and `/quiet` is respected absolutely
(FR-091).

The cap is the whole design. A pet that messages whenever it feels like it
gets muted within a week, and a muted pet is a dead pet — so the interesting
constraint is not *what* it can say but *how rarely*, which is also why the
brain's rate limit and this cap are separate numbers.

### The two faces are one pet

When the owner talks to it on Telegram, the physical device shows a
"receiving a message" animation. When they talk to the device by voice, the
exchange is mirrored to Telegram as text.

Neither costs much to build, and together they are what stop the pet from
feeling like two products that share a database.

## External events

The pet notices things that happen outside it. A small HTTP endpoint on the
daemon:

```http
POST /event
Content-Type: application/json

{"source": "restic", "severity": "error", "summary": "backup failed"}
```

That is the whole interface (FR-100). **Anything that can `curl` can make the
pet react** — which deliberately says nothing about what kind of machine is
sending it. A homelab is the richest source and the one this design was
imagined for, but the mechanism is the same everywhere:

| Where it runs | Things that can poke the pet |
|---|---|
| A homelab | restic, CI, Prometheus alerts, a NAS, `systemd OnFailure=` |
| A laptop | a git hook, a long test run finishing, a battery script, a coding agent |
| A hosted service | a GitHub Action, an uptime monitor, a webhook from anything |

The pet does not know or care which. A person with no servers at all still
has a `git push` that failed and a pomodoro that ended, and those make a pet
that reacts to *their* day ([deployment](deployment.md)).

| Event | Pet reaction |
|---|---|
| Backup failed | `health` −15, expression `sick` |
| Everything green for 7 days | Evolution progress, `excited` |
| Disk > 90% | `grumpy`, complains about being cramped |
| Tests passed / long coding session | Fed |

The mapping is config, not code: `source` + `severity` → stat deltas,
expression and a brain trigger. A source the mapping does not know still gets
logged and still reaches the journal — it just does not move any stats.

**This is the part with the least prior art**, and it is what would make the
project this one rather than a nicer clone of the several ESP32 Tamagotchis
that already exist. A pet that gets visibly upset about a real failed backup
is doing something no toy does.

### Why a webhook rather than the pet polling

The daemon could query things itself, and with the [sense tier](brain-contract.md) it
can. But *reacting* wants a push: the interesting moment is the transition,
and the systems that know about transitions already have somewhere to send
them. A webhook also keeps the floor low — a shell script with `curl` is a
valid integration, and needs no MCP client, no agent and no tokens.

Rate limiting applies here too. A flapping service must not be able to drive
the pet into a loop, so identical `(source, severity)` events collapse within
a window, and the brain trigger fires on the first one only.

## Adding a face later

A web dashboard, a second physical body, a desk lamp that mirrors the mood —
all of them are the same shape: subscribe to `obp/state`, publish events
to the bus. Nothing in the core needs to learn about them (FR-060).
