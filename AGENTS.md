# Open Body Protocol (OBP)

**A specification**: how a body describes itself and is driven. This
repository is the protocol, its rationale, its conformance rules, and
reference bodies that prove it.

**It is not a product.** What decides — which model, what it remembers, who
it is, how it deploys — is out of scope. That lives in
[desk-buddy](https://github.com/jcarranz97/desk-buddy).

## The test for anything added here

*Does this constrain someone implementing a body?*

If yes, it belongs here. If it is about which model thinks, who owns a
persona, how something deploys, or what a robot should be like, it belongs in
desk-buddy. That split is why the two repositories exist, and it erodes
easily.

## Invariants

1. **The body carries the schema.** Never a catalogue of device types in the
   host.
2. **Intents down, results up.** The body owns kinematics, timing, limits and
   reflexes.
3. **Errors are results**, never transport failures or crashes.
4. **Transport is a binding.** A USB body must never require a broker.
5. **Presence is abstract**, with a per-binding implementation. MQTT's
   retained-message form is the nicest and does not generalise.
6. **The host sorts verbs and namespaces them.** Bodies cannot be trusted to
   order their own.
7. **`userOnly` is a guardrail, not access control.**
8. **v0 is unstable**, and changes are recorded with the reason.

## Normative language

Requirements use RFC 2119 keywords. **Every normative requirement must appear
in `docs/spec/conformance.md`**, which is the authoritative list; prose
elsewhere explains and illustrates, and must not introduce a requirement that
is not in that table.

## Experiments come before specification

`experiments/` holds runnable answers to single questions, indexed with what
each one changed. Several requirements exist because an experiment produced
them — cite the experiment when writing such a rule, and add an experiment
rather than asserting a claim that could be tested.

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
