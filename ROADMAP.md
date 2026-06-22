---
title: Project Roadmap Ledger
status: Active
created: 2026-06-21
updated: 2026-06-21
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
| **Front-door / portability / auth unification — Phases 1–6 shipped (2026-06-21).** Runtime contract closure, CI-enforced contract tests, canonical doc truthfulness, install-path clarity, and Google consumption-path trade-offs all landed against one canonical plan (1080 tests green; CI unblocked). | **Operator-only:** run `rebalance config migrate-secrets` on the ~2 remaining Macs (Phase 1 item 6); otherwise the deferred multi-operator / fleet scope, revived on trigger. |

## Ledger

### In progress

- `Unified front-door, portability & auth hardening` — Phases 1–6 complete; only the operator-only per-machine `migrate-secrets` (~2 Macs) + deferred fleet/multi-operator scope remain. → [PROJECT/2-WORKING/FRONT-DOOR-PORTABILITY-AUTH-UNIFICATION.md](PROJECT/2-WORKING/FRONT-DOOR-PORTABILITY-AUTH-UNIFICATION.md)

### Completed

_None yet._

### Attempted

_None yet._

### Deferred

_None yet._

---

## Entry format

Use one flat bullet per item:

- `Project / track name` — one-line status summary. → `[linked project doc](PROJECT/...)`
