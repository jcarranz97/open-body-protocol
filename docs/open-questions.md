# Open Questions

Decisions that shape the product rather than the code. Most are answerable in
Phase 0 with no hardware at all, and answering them late is what turns a
design into a rewrite.

## 1. Mortality: permanent or revivable?

This changes the emotional contract more than any other decision here.
Permanent death makes every day of neglect matter and makes the streak real;
it also means one bad week ends the project. A `revive` command that costs
the streak keeps the stakes visible without making the pet disposable.

The architecture assumes **revivable**, because it is the reversible choice —
permanent death can be switched on later, and a pet that died under the wrong
rules cannot be brought back.

**Decide in Phase 0.** It is one line in the simulation and a paragraph in
`character.md`.

## 2. Does the pet initiate on Telegram, or only respond?

Recommended: **yes, capped**. A pet that only answers is a command line with
a face. But an uncapped one gets muted within a week, and a muted pet is a
dead pet — hence 3 messages a day and an absolute `/quiet` (FR-091).

**Decide in Phase 0**, since it decides whether Phase 0 is fun.

## 3. One personality forever, or does it drift?

Drift is the more interesting answer and the more expensive one: it needs a
personality vector that the simulation persists, that `character.md` reads,
and that the eval harness can hold constant while comparing providers.

A cheap middle path: keep the personality fixed and let **memory** do the
drifting. The pet that remembers being ignored for a fortnight already reads
as changed, without a second state machine.

**Decide in Phase 0** — it determines whether the memory table needs a weight
column and whether `character.md` is a static file.

## 4. Colour screen or 1-bit?

1-bit is more charming and far less work; colour buys expressiveness that the
art has to earn ([hardware](architecture/hardware.md)).

**Can wait until Phase 1.** It changes the display and the sprite pipeline,
neither of which the protocol knows about.

## 5. Does the pet know it is an AI?

`character.md` should be explicit either way — this is the question that most
often gets answered accidentally, by a model improvising when the prompt is
silent, and then answered differently the next time.

**Decide in Phase 0.** It costs a sentence and prevents an inconsistency the
owner will definitely notice.

## 6. What is it called?

TAMALAB is a working codename. The docs avoid baking it into the protocol —
topics are `tama/`, which is short enough to live with, and no payload field
carries the product name.

**Can wait indefinitely**, provided nothing but the topic prefix ever
depends on it.
