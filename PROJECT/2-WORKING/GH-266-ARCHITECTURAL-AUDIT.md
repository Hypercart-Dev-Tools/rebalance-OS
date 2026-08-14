---
title: "Architectural Audit: Complexity, DRY, and System Stability"
status: "Active"
created: "2026-08-11"
updated: "2026-08-11"
owner: "agent"
goal: "Consolidate duplicate ingest logic and implement bulletproof governance rules to prevent system over-engineering."
gh_issue: 266
effort: 2
complexity: 2
risk: 2
phases: 3
---

## Status

| What was just completed | What's next |
|---|---|
| Cut new branch and created PDDA tracking doc | Execute Phase 1: extract `_parse_iso`, `_now_iso`, `_json_dumps` to `src/rebalance/lib` |

## Quad Concepts
- Repeated duplicate ingest logic → Extract into domain-specific shared libraries (`src/rebalance/lib/time_ops.py`, etc.)
- Agents creating god-modules when told to use `utils.py` → Ban `utils.py` and enforce strict domain boundaries.
- Agents hallucinating duplicate checks via `grep_search` → Ban raw `datetime`/`subprocess` imports outside `lib/` and enforce via CI `import-linter`.
- Telling agents "Extend, don't invent" creates bloated god-objects → Change mandate to "Compose, don't mutate" to encourage primitives.

## Table of contents
- Phase 1 — Quick Wins (DRY Consolidation)
- Phase 2 — Governance System Rules
- Phase 3 — Technical Debt Eradication & Primitives Application

## Phase 1 — Quick Wins (DRY Consolidation)

Extract duplicated ingest utility functions into domain-specific shared libraries. 

- [ ] Extract time-related utilities (`_parse_iso`, `_now_iso`, `_now`) into `src/rebalance/lib/time_ops.py`.
- [ ] Extract JSON-related utilities (`_json_dumps`) into `src/rebalance/lib/json_ops.py`.
- [ ] Extract Git-related utilities (`_git`) into `src/rebalance/lib/git_ops.py`.
- [ ] Extract dictionary utilities (`as_dict`) into `src/rebalance/lib/dict_ops.py`.
- [ ] Refactor all existing collectors to import from these new domain-specific `lib/` modules.
- [ ] **QA Gate**: Run `pytest tests/` to ensure no regressions in behavior.
- [ ] **QA Gate**: Run `utils/pdda/pdda.sh run` to verify structural compliance.

## Phase 2 — Governance System Rules

To prevent Agents (and human developers) from building overlapping systems in the future, enforce mechanical chokepoints across the governance documentation:

- [ ] Update `AGENTS.md` (Agent Behavior) to enforce importing `datetime`, `json`, and `subprocess` exclusively from `rebalance.lib.*`. 
- [ ] Update `PROJECT/PDDA.md` (Design Decision & Automation) to require `pylint --enable=duplicate-code` in the CI pipeline and introduce mechanical import bans for `subprocess` and `datetime` outside of `src/rebalance/lib/`.
- [ ] Update `ARCHITECTURE.md` (System Constraints) to include the "Compose, Don't Mutate" rule, forcing features to break core functions into primitives rather than adding conditional flags.
- [ ] Update `ROUTER.md` (Entry Point Rules) to introduce a strict rule: any new system overlapping >50% with an old system MUST include the deletion of the old system in the same PR.
- [ ] Implement `import-linter` or a CI script to physically fail the build on restricted imports.
- [ ] **QA Gate**: Run `utils/pdda/pdda.sh run` and verify it passes with 0 errors on governance checks.

## Phase 3 — Technical Debt Eradication & Primitives Application

Apply the newly established governance rules retroactively to prune redundant systems and fix architectural stability issues.

- [ ] **Audit Overlapping Systems:** Identify existing read-paths and query layers that violate the >50% overlap rule (e.g., investigating `semantic_query` vs `ask` vs `query_notes`).
- [ ] **Execute Deletions:** Deprecate and delete the legacy, redundant systems identified in the audit to force all traffic through a single, well-maintained pipeline.
- [ ] **Refactor God Objects (Fixing #222):** Apply the "Compose, Don't Mutate" rule to the `Database is locked` (#222) issue. Refactor the monolithic, unbounded TF-IDF rebuild transactions into smaller, composable, batched transaction primitives. 
- [ ] **QA Gate:** Run the test suite (`pytest tests/`) to ensure no downstream dependencies break from the deleted query layers.
- [ ] **QA Gate:** Complete final `utils/pdda/pdda.sh run` validation.
