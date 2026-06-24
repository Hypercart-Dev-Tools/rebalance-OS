---
title: Project Roadmap Ledger
status: Active
created: 2026-06-21
updated: 2026-06-22
branch: main
supersedes: []
synthesizes: []
goal: >
  Canonical pointer/ledger index for this repo's work. Track projects in progress, completed,
  attempted, and deferred here, and keep execution detail in the linked PROJECT/** docs.
---

<!-- PDDA ROADMAP CONTRACT — this file is a POINTER/LEDGER, not a plan body.
     Allowed: projects in progress / completed / attempted / deferred + links to PROJECT/** docs.
     NOT allowed: phase checklists, build steps, deep execution notes — put those in the project doc.
     Carve-out: a SHORT exception note is OK only when omitting it would hide an operationally critical fact.
     Enforced by utils/pdda-check-roadmap.sh (deterministic) + utils/pdda-doc-ready.sh ROADMAP rubric (LLM). -->

# Project Roadmap

> **Pointer/ledger only — not a plan body.** Execution detail lives in the linked `PROJECT/**` docs.

## Status

| What was just completed | What's next |
|---|---|
| **Focus 5 Float — Phase 0 (spike & data contract) complete.** Read-only `GET /focus-5.json` shipped (no scan, no roster write — verified), data contract + field classification frozen in `CONTRACT.md`, and the non-activating floating-panel interaction spike written and typechecking. 90 focus5 tests green. | **Operator:** run [`FloatPanelSpike.swift`](PROJECT/2-WORKING/P2-MACOS-FOCUS5-FLOAT.md) over a fullscreen app to confirm interaction, then Phase 1 (scaffold & reuse harvest). _Prior track:_ front-door v0.41.1 — run `rebalance config migrate-secrets` on the ~2 remaining Macs, then a `development` → `main` PR. |

## Ledger

### In progress

- `Focus 5 Float (floating macOS card stack)` — native menu-bar app that renders the web Focus 5 roster as a vertical, collapsible card stack; reuses the `macOS/TextReplacementStudio` SwiftUI scaffolding. **Phase 0 complete:** read-only `GET /focus-5.json` shipped, data contract frozen, interaction spike written (operator run pending); Phases 1–5 (scaffold → floating shell → card UI → live data → packaging) ahead. → [PROJECT/2-WORKING/P2-MACOS-FOCUS5-FLOAT.md](PROJECT/2-WORKING/P2-MACOS-FOCUS5-FLOAT.md)

### Completed

- `Unified front-door, portability & auth hardening` — Phases 1–6 complete, merged to `development` (v0.41.1, PR #78). Operator-only per-machine `migrate-secrets` (~2 Macs) + deferred fleet/multi-operator scope remain; `development` → `main` PR pending. → [PROJECT/2-WORKING/FRONT-DOOR-PORTABILITY-AUTH-UNIFICATION.md](PROJECT/2-WORKING/FRONT-DOOR-PORTABILITY-AUTH-UNIFICATION.md)
- `AI-agent front door (ROUTER.md)` — added the canonical startup-order entry point (ROUTER → AGENTS → ARCHITECTURE → ROADMAP → PROJECT docs; run `rebalance doctor` / `pytest tests/` / `utils/pdda-run.sh` before claiming wins), completing the PDDA front-door layer alongside the installed `utils/pdda-*.sh` suite. → [ROUTER.md](ROUTER.md)

### Attempted

_None yet._

### Deferred

_None yet._

---

## Entry format

Use one flat bullet per item:

- `Project / track name` — one-line status summary. → `[linked project doc](PROJECT/...)`
