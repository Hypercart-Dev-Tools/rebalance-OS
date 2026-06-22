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
| **Unified planning pass complete (2026-06-21).** The overlapping front-door onboarding, collector portability, and auth-storage follow-up work was consolidated into one canonical active project doc. | **Phase 1 - Runtime contract closure.** Finish the remaining collector/auth contract edges before further doc and onboarding cleanup. |

## Ledger

### In progress

- `Unified front-door, portability, and auth hardening` — canonical follow-up plan for the remaining runtime-contract, verification, onboarding, and documentation-surface work that had been split across three overlapping docs. → [PROJECT/2-WORKING/FRONT-DOOR-PORTABILITY-AUTH-UNIFICATION.md](PROJECT/2-WORKING/FRONT-DOOR-PORTABILITY-AUTH-UNIFICATION.md)

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
