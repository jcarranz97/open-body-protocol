# Open Body Protocol (OBP)

**Open Body Protocol (OBP) connects a brain to a body.** The brain is any
AI agent — a model API, a local model, or a harness like OpenClaw, Hermes or
OpenCode. The body is any hardware someone built, from a terminal window to a
printed robot. The project is the standardised layer between them, and ships
neither.

**Status: architecture.** There is no `daemon/`, `client/`, `bodies/` or
`packs/` yet. There is a validated experiment under `experiments/`.

## The invariants

Load-bearing decisions. When a change would violate one, say so rather than
working around it.

1. **Two ports, one translator.** Everything is the body port, the brain
   port, or the small daemon between them. Code that belongs to neither
   probably belongs in a behaviour pack.
2. **The body describes itself.** Verbs with JSON Schema, discovered at run
   time. Never a catalogue of known device types in the daemon.
3. **Transport is a binding, not the architecture.** MQTT is one adapter. A
   USB body must never require a broker; an all-in-one box must never
   require a network.
4. **Intents down, results up.** The brain names what it wants; the body
   owns kinematics, timing, safety and reflexes. Never raw actuator
   commands.
5. **Errors are results.** A rejected or impossible call returns a readable
   `isError` result so a brain can explain itself. Never a hang, never a
   crash.
6. **Sort tools deterministically, key identity on hardware.** Both were
   learned from experiment 001; both are in `docs/architecture/body-contract.md`
   with the reasoning.
7. **A harness owns identity when present; otherwise the daemon does.** Never
   both. See `docs/architecture/identity.md`.
8. **Anything opinionated is a pack.** The core connects things; it does not
   decide what the thing wants. A Tamagotchi is a pack.
9. **One container, one volume, no orchestrator.** If a step requires
   Kubernetes, a reverse proxy, a public hostname or an inbound port, it is
   wrong. The floor is a Pi running `docker compose up`.
10. **The microphone opens only while push-to-talk is held.** A firmware
    invariant, not a policy.

## Experiments come before specifications

`experiments/` holds runnable answers to single questions, indexed with what
each one changed. Several rules in the architecture exist because an
experiment produced them — cite the experiment when writing such a rule, and
add a new experiment rather than asserting a claim that could be tested.

## Documentation

`docs/` is [MkDocs Material](https://squidfunk.github.io/mkdocs-material/),
laid out like the sibling projects `piezario` and `printforhelp`. Drive it
with [uv](https://docs.astral.sh/uv/) — **do not create a virtualenv or pip
install anything**:

```bash
uvx --with mkdocs-material mkdocs serve           # read locally
uvx --with mkdocs-material mkdocs build --strict  # what CI runs; warnings fail it
```

The version is deliberately unpinned. Material 9.x already constrains
`mkdocs<2`, so the announced MkDocs 2.0 plugin breakage cannot reach this
repo while the major version stays at 9 — if Material ever ships a 10, pin
it here before finding out the hard way.

- `docs/brief.md` is the **original seed document, kept verbatim**. Treat it
  as a historical record: do not edit it to reflect later decisions. When the
  architecture diverges from it, the architecture pages win and should say so
  explicitly.
- `docs/requirements.md` allocates stable `FR-NNN` / `NFR-NNN` identifiers
  from one flat sequence per prefix. **Never renumber.** A new requirement
  takes the next free number and is filed into the topically right section,
  so section numbering is not contiguous.
- Architecture pages cite requirements by identifier rather than restating
  them.
- Mermaid diagrams are rendered by `docs/javascripts/mermaid-init.js`, not by
  Material's built-in integration — see the comment in `mkdocs.yml` before
  changing that.

Markdown is wrapped at 80 columns (`.markdownlint.json`; tables and code
blocks are exempt).

## Vocabulary

Use these words consistently — the schema, the topics and the docs all lean
on them.

| Term | Means |
|---|---|
| **body** | Anything that renders the pet and reports events: the desk unit, the terminal, Telegram. v2 adds the keychain. Not a synonym for hardware. |
| **daemon** | The container that owns the core. The pet's brain, memory and authority, wherever it runs. |
| **state** | The full snapshot of §4.3 — stats, mood, stage. Server→device, retained. |
| **say** | One utterance plus an expression, animation and sound. Perishable (`ttl_s`). |
| **event** | Something that happened to the pet: a button, a shake, a voice turn, a webhook. Carries a ULID. |
| **brain** | The pluggable thing that turns context into a `say`. |
| **trigger** | Why the brain was called (`idle`, `conversation`, `journal`, `homelab`). Routing keys off this. |
