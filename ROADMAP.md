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
| **Focus 5 Float — Phases 0–4 complete (feature-complete).** Read-only `GET /focus-5.json` + frozen contract (90 tests); `Focus5Float` SwiftPM package (harvested design system, `Codable` models); menu-bar agent + non-activating floating `NSPanel`; **live data** via `Focus5Client` (same `summarize_focus5()` as the web; poll/refresh/mode/offline/tap-to-open, E2E-verified); and **collapsible card UI** (Tree health / PR / activity, in-panel ranking toggle, ⚠ stale badge, off-roster footer). | **Phase 5 — Packaging:** `make-app.sh` (bundle id, `LSUIElement`, icon, ad-hoc sign, install to /Applications), launch-at-login, settings, README. _Prior track:_ front-door v0.41.1 — run `rebalance config migrate-secrets` on the ~2 remaining Macs, then a `development` → `main` PR. |

## Ledger

### In progress

- `Focus 5 Float (floating macOS card stack)` — native menu-bar app that renders the web Focus 5 roster as a vertical, collapsible card stack; reuses the `macOS/TextReplacementStudio` SwiftUI scaffolding. **Phases 0–4 complete (feature-complete):** read-only `GET /focus-5.json` + frozen contract (90 tests), `Focus5Float` SwiftPM package (harvested design system + `Codable` models), menu-bar agent + non-activating floating `NSPanel`, live data via `Focus5Client` (same `summarize_focus5()` as the web; poll/refresh/mode/offline/tap-to-open, E2E-verified), and collapsible card UI (Tree health / PR / activity, in-panel ranking toggle, ⚠ stale badge, off-roster footer). Phase 5 (packaging/install) ahead. → [PROJECT/2-WORKING/P2-MACOS-FOCUS5-FLOAT.md](PROJECT/2-WORKING/P2-MACOS-FOCUS5-FLOAT.md)

### Completed

- `Focus 5 active repos bug remediation` — root-cause trace + remediation implemented and tested (transient Dirty Five mode, scan-root CLI setters). → [PROJECT/2-WORKING/FOCUS-5-RANKING-BUG-AND-REMEDIATION.md](PROJECT/2-WORKING/FOCUS-5-RANKING-BUG-AND-REMEDIATION.md)
- `Team Calendar as a Signal (HiQS)` — Phase 2 v0.5 built on `development`, data-layer DoD proven, pending live validation and merge/tag. → [PROJECT/2-WORKING/SIGNAL-GENERATION/P2-TEAM-CALENDAR-SIGNAL.md](PROJECT/2-WORKING/SIGNAL-GENERATION/P2-TEAM-CALENDAR-SIGNAL.md)
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
