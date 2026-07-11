---
gh_issue: 124
source: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/124
title: Revisit auto-promotion of projects to watched status
status: Proposed (1-INBOX — not yet active)
created: 2026-07-10
doc_type: feedback
related:
  - PROJECT/4-MISC/DECOUPLE-OBSIDIAN-AS-SOT.md
  - PROJECT/3-COMPLETED/CLIENT-AUTO-DISCOVERY.md
  - PROJECT/3-COMPLETED/WATCHLIST-COVERAGE-GUARD.md
  - PROJECT/2-WORKING/REPO-HEALTH-AXES.md
---

# GH-124 — Revisit auto-promotion of projects to watched status

## Problem

Most users will not remember to manually register new repos into Rebalance. A new repo should
become an active project automatically once the owner/operator has pushed 2-3 commits to it — no
manual "promote" step required. Today the only write path into `project_registry` is the onboarding
`/welcome` flow's one-time human-gated "Review & promote" step (`confirm_projects()`,
`write_semantics="confirmation_gated"` per `src/rebalance/ingest/lifecycle.py:110-120`). Anything
discovered after onboarding sits in the "watched" bucket indefinitely.

**Exception:** forks/stars alone are not activity and must not trigger promotion — only actual
commits pushed by the operator (fork included) count toward the threshold.

## What already exists

- `src/rebalance/ingest/project_inference.py` — `infer_project_registry()` already writes
  `machine_owned` rows into `project_registry` (never clobbers curated rows), but is CLI-only,
  unscheduled, not MCP-exposed, and triggers on "any activity or ≥2 calendar events," not a commit
  count or operator-identity match.
- `PROJECT/4-MISC/DECOUPLE-OBSIDIAN-AS-SOT.md` (2026-05-31, still "In Review") — the prior attempt
  at this same problem ("every repo you push to is visible by default"); never closed.
- `PROJECT/3-COMPLETED/CLIENT-AUTO-DISCOVERY.md` (#100) — adjacent (client labeling on already-
  confirmed projects), not repo→project promotion.
- `PROJECT/3-COMPLETED/WATCHLIST-COVERAGE-GUARD.md` (#82) — the inverse alarm (silent removal from
  watched); no equivalent for silent non-entry into confirmed.
- `PROJECT/2-WORKING/REPO-HEALTH-AXES.md` — open, unresolved question on watched-vs-registry
  filtering.

## Proposed direction (undesigned — for triage)

- Trigger: operator (`github_login` match) pushes N commits (2-3) to a watched repo.
- Action: extend the existing `machine_owned` write path rather than requiring `confirm_projects()`.
- Exclude forks/stars with no operator commits.
- Surface non-silently (pulse/dashboard line), not a fully silent background write.
- Open: default on/off, interaction with `github_ignored_repos`, whether this rides `refresh_index()`
  or stays a separate pass.

Full discussion lives on the issue: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/124
