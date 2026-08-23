# TAMALAB

**TAMALAB** is an AI Tamagotchi: an ESP32-S3 desk pet whose brain, memory and
personality run as a container in a homelab, reachable from both the device
and Telegram. The device is a **body** — display, buttons, buzzer, mic,
speaker — and nothing else.

**Status: Phase 0.** This repository is documentation only. There is no
`daemon/` and no `firmware/` yet. Do not scaffold either until the
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
6. **Art lives in flash.** The server sends an `expression` and an
   `animation` id — never sprite data.
7. **The mic opens only while the push-to-talk button is held.** A firmware
   invariant, not a policy. Privacy here is structural.

## Documentation

`docs/` is [MkDocs Material](https://squidfunk.github.io/mkdocs-material/),
laid out like the sibling projects `piezario` and `printforhelp`:

```bash
pip install mkdocs-material
mkdocs serve                # read locally
mkdocs build --strict       # what CI runs; broken links fail the build
```

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
| **body** | A physical device. v1 has one (the desk unit); v2 adds the keychain. |
| **daemon** | The homelab pod. The pet's brain, memory and authority. |
| **state** | The full snapshot of §4.3 — stats, mood, stage. Server→device, retained. |
| **say** | One utterance plus an expression, animation and sound. Perishable (`ttl_s`). |
| **event** | Something that happened to the pet: a button, a shake, a voice turn, a webhook. Carries a ULID. |
| **brain** | The pluggable thing that turns context into a `say`. |
| **trigger** | Why the brain was called (`idle`, `conversation`, `journal`, `homelab`). Routing keys off this. |
