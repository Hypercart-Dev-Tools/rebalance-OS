---
title: "Architectural Audit: Complexity, DRY, and System Stability"
status: "Active"
created: "2026-08-11"
updated: "2026-08-14"
owner: "agent"
goal: "Consolidate duplicate ingest logic and implement bulletproof governance rules to prevent system over-engineering."
gh_issue: 266
effort: 2
complexity: 2
risk: 3
phases: 4
---

## Status

| What was just completed | What's next |
|---|---|
| Phases 1–3 landed in PR #267 / PR #268. Post-merge review found three crashing retrieval call sites (fixed) and a Phase 2 rule that forced a 64-file rewrite (pivot recorded in Phase 4). | Execute Phase 4, then measure the result against the 0.71.0 "Daily Driver" window in RELEASES.md |

> **Reopened 2026-08-14.** This doc briefly read "Completed all 3 phases → Done". That was
> premature: `rebalance query`, `rebalance github-query` and `ask()` were all raising `KeyError`
> on their first result at the time, and ~64 files of the Phase 2 migration were uncommitted.
> Phase 4 records the pivot rather than editing Phases 1–3 to look like they always said this.

## Quad Concepts
- Repeated duplicate ingest logic → Extract into domain-specific shared libraries (`src/rebalance/lib/time_ops.py`, etc.)
- Agents creating god-modules when told to use `utils.py` → Ban `utils.py` and enforce strict domain boundaries.
- ~~Agents hallucinating duplicate checks via `grep_search` → Ban raw `datetime`/`subprocess` imports outside `lib/` and enforce via CI `import-linter`.~~ **Superseded by Phase 4** — banning the stdlib was the wrong level; see "Pivot 1" below.
- Telling agents "Extend, don't invent" creates bloated god-objects → Change mandate to "Compose, don't mutate" to encourage primitives.

## Table of contents
- Phase 1 — Quick Wins (DRY Consolidation)
- Phase 2 — Governance System Rules
- Phase 3 — Technical Debt Eradication & Primitives Application
- Phase 4 — Correct the Phase 2 Rule & Close Out (added 2026-08-14)

## Phase 1 — Quick Wins (DRY Consolidation)

Extract duplicated ingest utility functions into domain-specific shared libraries. 

- [x] Extract time-related utilities (`_parse_iso`, `_now_iso`, `_now`) into `src/rebalance/lib/time_ops.py`.
- [x] Extract JSON-related utilities (`_json_dumps`) into `src/rebalance/lib/json_ops.py`.
- [x] Extract Git-related utilities (`_git`) into `src/rebalance/lib/git_ops.py`. *(Note: `github_commit_backfill.py` intentionally kept its own `_git` as it has a different return type tuple contract)*
- [~] Extract dictionary utilities (`as_dict`) into `src/rebalance/lib/dict_ops.py`. *(Deliberately skipped: `as_dict` is implemented per-dataclass and not genuinely shared)*
- [x] Refactor all existing collectors to import from these new domain-specific `lib/` modules.
- [x] **QA Gate**: Run `pytest tests/` to ensure no regressions in behavior.
- [x] **QA Gate**: Run `utils/pdda/pdda.sh run` to verify structural compliance.

## Phase 2 — Governance System Rules

To prevent Agents (and human developers) from building overlapping systems in the future, enforce mechanical chokepoints across the governance documentation:

- [x] Update `AGENTS.md` (Agent Behavior) to enforce importing `datetime`, `json`, and `subprocess` exclusively from `rebalance.lib.*`. 
- [ ] Update `PROJECT/PDDA.md` (Design Decision & Automation) to require `pylint --enable=duplicate-code` in the CI pipeline and introduce mechanical import bans for `subprocess` and `datetime` outside of `src/rebalance/lib/`. *(Un-ticked 2026-08-14: `PROJECT/PDDA.md` contains no mention of pylint, duplicate-code, banned imports, or `rebalance.lib` — PR #267's 96 lines to that file are the unrelated release-band duplicate check. Superseded by Phase 4 regardless.)*
- [x] Update `ARCHITECTURE.md` (System Constraints) to include the "Compose, Don't Mutate" rule, forcing features to break core functions into primitives rather than adding conditional flags.
- [x] Update `ROUTER.md` (Entry Point Rules) to introduce a strict rule: any new system overlapping >50% with an old system MUST include the deletion of the old system in the same PR.
- [x] Implement `import-linter` or a CI script to physically fail the build on restricted imports.
- [x] **QA Gate**: Run `utils/pdda/pdda.sh run` and verify it passes with 0 errors on governance checks.

## Phase 3 — Technical Debt Eradication & Primitives Application

Apply the newly established governance rules retroactively to prune redundant systems and fix architectural stability issues.

- [x] **Audit Overlapping Systems:** Identify existing read-paths and query layers that violate the >50% overlap rule (e.g., investigating `semantic_query` vs `ask` vs `query_notes`).
- [x] **Execute Deletions:** Deprecate and delete the legacy, redundant systems identified in the audit to force all traffic through a single, well-maintained pipeline.
- [x] **Refactor God Objects (Fixing #222):** Apply the "Compose, Don't Mutate" rule to the `Database is locked` (#222) issue. Refactor the monolithic, unbounded TF-IDF rebuild transactions into smaller, composable, batched transaction primitives. 
- [x] **QA Gate:** Run the test suite (`pytest tests/`) to ensure no downstream dependencies break from the deleted query layers.
- [x] **QA Gate:** Complete final `utils/pdda/pdda.sh run` validation.

## Phase 4 — Correct the Phase 2 Rule & Close Out

Added 2026-08-14 after post-merge review of PR #267 / PR #268. Phases 1–3 are not being
rewritten; this phase records what changed and why, and carries GH-266 to a measurable end.

### Pivot 1 — the Phase 2 import ban was at the wrong level

**What the plan said.** Phase 2 required enforcing "importing `datetime`, `json`, and
`subprocess` **exclusively from** `rebalance.lib.*`", with a CI linter to fail the build.

**What that produced.** Correct — and that is the problem. Once
`utils/pdda/check_banned_imports.py` was made blocking and widened to all of `src/rebalance`,
~64 files that legitimately import the standard library became build-breaking. `fix_imports.py`
mass-rewrote them through a new pass-through module, `src/rebalance/lib/subprocess_ops.py`,
whose entire body re-exports nine stdlib names unchanged. Call sites now read
`import rebalance.lib.subprocess_ops as subprocess` — a name that no longer refers to the
stdlib module and is missing most of its surface. No behavior changed anywhere.

**Why it was wrong.** GH-266's actual finding was duplicated *behavior* — `_parse_iso` written
3×, `_git` 4×. `datetime` and `subprocess` are not duplicated behavior; they are the raw
materials every module legitimately needs. Banning the material instead of the duplication
satisfies the rule while leaving the problem untouched.

**Corroboration.** A cross-model consult (Codex + agy, transcripts in
`relay-system/2026-08-14/lib-shim-120346/`) independently rated this a blocker on both sides,
without either advisor knowing the approach was plan-mandated.

**The correct rule already exists.** `AGENTS.md:100` as shipped in PR #267 says operations
"must use `src/rebalance/lib/*` modules instead of **creating local helper methods** in the
collector" — i.e. do not hand-roll a helper that already exists. That is the right constraint;
only the enforcement over-reached past it.

- [ ] Revert the 64-file stdlib import rewrite; keep the genuine helper consolidation from Phase 1.
- [ ] Delete `src/rebalance/lib/subprocess_ops.py`, `fix_imports.py`, and `test_hiqs.py`.
- [ ] Narrow `check_banned_imports.py` from "no stdlib import outside `lib/`" to "no *duplicate
      helper definition* (`_parse_iso`, `_now_iso`, `_json_dumps`, `_git`) outside its owning
      `lib/` module", matching `AGENTS.md:100`. Evaluate Ruff `TID251` before keeping bespoke AST code.
- [ ] Verify the `pylint --enable=duplicate-code` CI step added in the Phase 2 work does not fail
      the build permanently — 21 near-clone `as_dict` definitions remain and pylint exits non-zero
      on any R0801. Unverified locally (pylint not installed).
- [ ] **QA Gate**: `python utils/pdda/check_banned_imports.py` exits 0 with the narrowed rule and
      no stdlib rewrite in the tree.

### Pivot 2 — three crashing retrieval call sites (fixed 2026-08-14)

Phase 3 repointed three consumers at the unified `semantic_index.query()` without updating them
for its return shape (per-source fields moved under `metadata`; `source_type` is now `"github"`
for every row, with the issue/pr distinction in `metadata["item_type"]`; `doc_type` → `doc_kind`).
All three raised on the first result: `rebalance query` (`KeyError: 'heading'`),
`rebalance github-query` (`KeyError: 'labels'`), and `ask()` / `mcp__rebalance__ask`
(`KeyError: 'repo_full_name'`). `ask()`'s vault path did not crash but silently dropped the
section anchor from every citation.

`src/rebalance/cli/semantic.py:161-178` had been consuming the same function correctly the whole
time; the fix copies that idiom rather than inventing one.

- [x] Fix all three call sites to read from `metadata`.
- [x] Add `tests/test_unified_retrieval_call_sites.py` — drives all three real render paths with a
      realistic unified row; reproduced all three failures before the fix, passes after.
- [ ] Restore the assertion weakened in `21bc1b5e`: `tests/test_github_knowledge.py` now reads
      `assertIsNotNone(results[0].get("similarity_score") or results[0].get("doc_id"))`, which
      cannot fail — `0.0` is falsy and falls through to `doc_id`. Relevance ranking is unasserted.
- [ ] Add a contract test for the unified retrieval surface; `tests/test_retrieval_contracts.py`
      lost 4 tests in PR #268 and gained none.

### Pivot 3 — documentation still advertises deleted tools

PR #268 removed the `query_notes` and `query_github_context` MCP tools. Six places still tell
callers — including AI agents — that they exist.

- [ ] Update `AGENTS.md:53,55`, `ARCHITECTURE.md:382,507,509`, `MCP.md:96,109,429`,
      `README.md:76-77`, `src/rebalance/mcp/tools/index.py:280`, `.claude/settings.local.json:62`.
- [ ] Decide whether the removal needs a one-release deprecation shim forwarding to
      `semantic_query`, since this is a breaking change to a public MCP surface.

### Known defects carried forward (not blocking this phase)

- [ ] TF-IDF batching (the GH-222 fix in PR #268) paginates `chunks` with `LIMIT/OFFSET` and no
      `ORDER BY`. SQLite guarantees no order without one, so chunks can be silently skipped and
      never indexed. Fix with keyset pagination (`WHERE id > ? ORDER BY id LIMIT ?`), which also
      removes the O(n²) offset scan and the double tokenization.
- [ ] The same change replaced an atomic rebuild with `DELETE` + per-batch commits, so a crash
      mid-rebuild leaves a permanently partial keyword index with no marker. Consider building into
      `keywords_new` and swapping.
- [ ] PR #268 carries ~25 unrelated files (3EYES inbox reports, GH-195 `RELAY.md` files,
      `.claude/settings.json`, `.pdda-quad`, and a leftover AI scratch script at
      `.gemini/antigravity/brain/**/scratch/refactor.py`). Strip before merge.
- [ ] PR #268 is based on `development` and contains all of PR #267 — merge #267 first or
      retarget #268, or one of them lands empty.

### Exit — how GH-266 ends

GH-266 has had no terminating condition: "consolidate duplication" is satisfiable indefinitely.
Two goal posts were added to `RELEASES.md` on 2026-08-14 to close that:

- **0.71.0 "Daily Driver"** (target 2026-10-15) — the payoff. One unbroken 14-day window running
  as daily driver on the 64 GB Mac Studio: peak collector RSS under the GH-217 cap
  (0.35 × RAM, ~22 GB) with no repeat of the 46.9 GB spike from GH-210/213; zero `database is
  locked` (GH-222); `rebalance doctor` OK every day; and a keep/merge/retire decision written for
  each of the 14 installed launchd jobs.
- **0.72.0 "Punch List"** (target 2026-11-15) — bounded refinement. Scope is frozen to whatever
  0.71.0's window produced; anything found after the freeze goes to `ROADMAP.md`. Skipped entirely
  if the frozen list is empty.

Sequencing note: 0.71.0 follows 0.70.0 "Green Board" deliberately. A 14-day dogfood window
measured against a red build proves nothing — GH-266's own review missed three crashing commands
precisely because the failing baseline had stopped carrying information.

- [ ] Close GH-266 only when 0.71.0's window completes unbroken — not when Phase 4's boxes are ticked.
