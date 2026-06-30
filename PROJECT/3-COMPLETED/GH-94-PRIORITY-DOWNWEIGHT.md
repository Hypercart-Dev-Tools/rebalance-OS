---
gh_issue: 94
source: "https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/94"
title: "Wire priority_tier into 'what to do next' ranking as a soft down-weight"
status: "Completed (shipped 2026-06-30)"
created: 2026-06-30
updated: 2026-06-30
doc_type: feedback
---

# GH-94 — priority_tier soft down-weight in "what to do next"

Per-project `priority_tier` was stored + settable (`set_project_priority_rule`) and
overlaid by `apply_project_priorities`, but only reached the vault note / dashboard —
**not** the "what to do next" ranking. So marking a low-cadence repo (e.g. git-pulse,
weekly devops) `priority_tier: 5` changed nothing in the headline. Wired it in as a
**soft down-weight** (still visible, just lower) — no new table/config surface.

## Outcome (2026-06-30)

In `src/rebalance/ingest/next_actions.py`:
- `_DEPRIORITIZE_TIER = 4` + `_is_low_priority()` — one shared predicate (tier ≥ 4 = low).
- `_signal_views()` (renamed from `_client_views`) now also returns a
  `priority_by_project` map built from `apply_project_priorities(get_projects(db))`,
  so operator-local priority **rules** are honored, keyed by project name + repos.
- `build_rank_prompt`: low-priority `[OWN]` lines get a `[priority:low]` tag + a
  `PRIORITY DOWN-WEIGHT` calibration lever (only when ≥1 low item present).
- Deterministic fallback: operator candidates **stable-sorted** so low-priority sinks
  to the bottom of the operator arm — the down-weight holds when synthesis is skipped/fails.

Reuses the existing priority-rule config; Focus 5 board + `NOISE_REPOS` untouched (out of scope).

## Verification

4 tests in `tests/test_priority_downweight.py` (threshold, prompt tag low-only, inert
without metadata, stable demotion). Full suite **1230 green**; `rebalance doctor` clean;
live smoke: `_signal_views` resolves 20 priority-keyed projects, `rank_next_actions` runs clean.

## How to use

Set a project low-cadence, e.g.:
`set_project_priority_rule(name="git-pulse", priority_tier=5)` (via the priority-rule
config/CLI) → its items get `[priority:low]` and sink in the ranking, without being muted.
