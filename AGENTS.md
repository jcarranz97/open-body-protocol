# TAMALAB

**TAMALAB** is an AI Tamagotchi whose brain, memory and personality run as a
single container — on a laptop, a mini PC, a Raspberry Pi, or a homelab
cluster; the deployment is the owner's choice and the pet is identical in
each. It has three **bodies** — an ESP32-S3 desk unit, a
terminal application, and a Telegram bot — and none of them is primary. The
hardware is optional.

**Status: Phase 0.** This repository is documentation only. There is no
`daemon/`, no `client/`, no `tui/` and no `firmware/` yet. Do not scaffold either until the
architecture documents they implement are settled; the whole point of the
phase order in `docs/roadmap.md` is that Phase 0 is playable on Telegram
alone and costs nothing.

## The invariants

These are the load-bearing decisions. Everything else is negotiable; when a
change would violate one of these, say so rather than working around it.

1. **The daemon owns the truth.** The ESP32 caches the last `state` in NVS so
   it can keep animating through a pod restart. It never computes
   authoritative state, never persists history, and never holds a secret
   worth stealing.
2. **The simulation is a pure function of elapsed time and the event log**
   (`docs/architecture/simulation.md`). No LLM appears anywhere in it. This
   is what makes the offline device and the server agree without merge logic
   — and what makes the v2 keychain possible at all.
3. **The device must never wait on the brain.** Every LLM path ends in a
   timeout and a canned line. `CannedBrain` is the zeroth provider and the
   permanent fallback, not a stub to be deleted later.
4. **The brain is provider-agnostic.** The pet asks for one small JSON object
   (`docs/architecture/brain.md` §Structured output). Which model produces it
   is a line in `providers.yaml`. Never let a vendor's SDK types leak past
   the adapter boundary.
5. **Transport is abstracted on both sides.** Firmware talks to a `Transport`
   interface, the daemon consumes *events* and emits *state*/*say* over an
   internal bus with MQTT as an edge adapter. v1 has one implementation each.
   v2 adds BLE as an addition, not a rewrite.
6. **Art lives in the body.** The server sends an `expression` and an
   `animation` id — never sprite data, and never ASCII either. The firmware
   keeps sprites in flash; the terminal keeps frames in the client package.
7. **A body is defined by the protocol it speaks, not by being hardware.**
   The terminal client is a body under the same contract, not a debug tool
   or a mock. Anything it cannot do from `state` + `say` alone is a hole in
   the protocol — fix the protocol, never special-case the daemon.
8. **Solo mode imports the core; it does not reimplement it.** `tui --solo`
   runs the same simulation code in-process. Two implementations of decay
   would be two pets.
9. **One container, one volume, no orchestrator.** A homelab is a deployment
   option, never an assumption: if a design step would require Kubernetes, a
   reverse proxy, a public hostname or an inbound port, it is wrong. The
   floor is a Raspberry Pi running `docker compose up`.
10. **The mic opens only while the push-to-talk button is held.** A firmware
   invariant, not a policy. Privacy here is structural.

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
