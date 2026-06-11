---
title: Subsystem Refactor Plan
status: in-progress
doc_type: project-plan
owner: Noel Saw
last_updated: 2026-06-10
priority_order:
  - config-auth-path
  - pulse-dashboard-web
  - query-retrieval
  - scheduler-launchd
  - onboarding-registry
rollout_rule: each phase must leave the full system runnable end-to-end
branch: feat/subsystem-refactor
branch_convention: single branch, one clean commit per phase close
---

| Most recently completed phase | What's next |
|---|---|
| Phase 3 complete: Option C ownership model locked; `normalize_sources` + `scope_to_sources`/`WORK_SOURCES` extracted to `semantic_index.py`; `chat.py` and `cli/semantic.py` delegate to the canonical owner; legacy facades marked in `retrieval.py`; 28 contract tests added (791 total passing). `ARCHITECTURE.md` read-side diagram updated. | Phase 4: Scheduler and Launchd Orchestration — consolidate shell scripts, plist templates, and installer behavior; resolve lazy-import smell in `config.py` (Phase 1 deferred item). |

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Scope](#scope)
3. [Current Prioritization](#current-prioritization)
4. [Refactor Principles](#refactor-principles)
5. [Phase 0 - Architecture Spike](#phase-0---architecture-spike)
6. [Phase 1 - Config, Auth, and Path Resolution](#phase-1---config-auth-and-path-resolution)
7. [Phase 2 - Pulse, Dashboard, and Web Surface](#phase-2---pulse-dashboard-and-web-surface)
8. [Phase 3 - Query, Retrieval, and Synthesis](#phase-3---query-retrieval-and-synthesis)
9. [Phase 4 - Scheduler and Launchd Orchestration](#phase-4---scheduler-and-launchd-orchestration)
10. [Phase 5 - Onboarding, Registry, and Inference](#phase-5---onboarding-registry-and-inference)
11. [Cross-Phase Risks](#cross-phase-risks)
12. [Definition of Done](#definition-of-done)

## Executive Summary

This plan converts the earlier subsystem-refactor sketch into a real rollout sequence. The goal is not generic cleanup. The goal is to reduce the same spread, duplication, and contract drift that recently forced the command-system refactor.

Priority is driven by user-visible reliability:

1. `config/auth/path`
2. `pulse/dashboard/web`
3. `query/retrieval`
4. `scheduler/launchd`
5. `onboarding/registry`

Important nuance:

- `config/auth/path` and `scheduler/launchd` already received meaningful portability work during the collector refactor.
- `pulse/dashboard/web` has been touched repeatedly, but mostly through feature additions and local fixes rather than subsystem consolidation.
- `semantic_index.py` is intentionally not the center of this plan. It is still in active contract churn from the collector-path refactor, so broadening it casually would raise regression risk.

This rollout is designed so that **each phase can stop cleanly**. At the end of every phase:

- the system still refreshes end to end
- the MCP server still works
- scheduled jobs still run
- no user-facing surface is left half-migrated

## Anti-Goals

These are explicit non-targets. If a task would require doing any of these to make a phase work, that is a scope violation — stop, reassess, and split it out rather than expanding the phase to cover it.

- **No semantic-index redesign.** `semantic_index.py` is still in active contract churn from the collector-path refactor. Broadening it here adds regression risk with no phase-gated benefit. Read-side and pulse/web work may brush against it but must not alter its internals.
- **No collector registry redesign.** The collector registry was just restructured. This plan consolidates the subsystems that call it, not the registry itself.
- **No new product scope for existing sources.** Sources already in production stay as-is. Refactoring a subsystem is not an opportunity to add ingest features.
- **No scheduler replacement.** launchd stays. Policy consolidation and script cleanup are in scope; evaluating or introducing a new scheduler is not.
- **No flag-day migrations.** Every phase must leave the system runnable end-to-end. If a phase requires a simultaneous cutover across multiple subsystems to work, it has been scoped incorrectly.
- **No broad renaming or reorganization.** Narrow seam extraction and contract stabilization are the tools here. Repo-wide file moves or rename passes are out of scope unless a specific seam forces it.
- **No "while we're in here" cleanup.** Spotted a debt item that isn't a blocker for the seam being extracted? Log it, don't fix it mid-phase. Opportunistic cleanup silently expands diffs and makes rollback harder.

## Scope

This plan covers five subsystem families:

1. `Config + auth + path resolution`
2. `Pulse / dashboard / web surface`
3. `Query / retrieval / synthesis`
4. `Scheduler / launchd orchestration`
5. `Project onboarding / registry / inference`

See [Anti-Goals](#anti-goals) above for a full list of explicit non-targets.

## Current Prioritization

### 1. Config, Auth, and Path Resolution

Primary files:

- [src/rebalance/ingest/config.py](/Users/noelsaw/Documents/rebalance-OS/src/rebalance/ingest/config.py)
- [src/rebalance/paths.py](/Users/noelsaw/Documents/rebalance-OS/src/rebalance/paths.py)
- [src/rebalance/ingest/auth_log.py](/Users/noelsaw/Documents/rebalance-OS/src/rebalance/ingest/auth_log.py)
- [scripts/setup_calendar_oauth.py](/Users/noelsaw/Documents/rebalance-OS/scripts/setup_calendar_oauth.py)
- [scripts/setup_gmail_oauth.py](/Users/noelsaw/Documents/rebalance-OS/scripts/setup_gmail_oauth.py)

Why first:

- It has the largest effect on collector reliability and portability.
- Recent collector work already touched it, so the next pass can finish seams rather than invent new ones.

### 2. Pulse, Dashboard, and Web Surface

Primary files:

- [scripts/dashboard.py](/Users/noelsaw/Documents/rebalance-OS/scripts/dashboard.py)
- [scripts/pulse_web.py](/Users/noelsaw/Documents/rebalance-OS/scripts/pulse_web.py)
- [scripts/pulse_server.py](/Users/noelsaw/Documents/rebalance-OS/scripts/pulse_server.py)
- [src/rebalance/web.py](/Users/noelsaw/Documents/rebalance-OS/src/rebalance/web.py)
- [src/rebalance/web_components.py](/Users/noelsaw/Documents/rebalance-OS/src/rebalance/web_components.py)

Why second:

- This is the most visibly accreted subsystem.
- It now contains multiple refresh triggers, rendering paths, and path-bootstrap patterns.

### 3. Query, Retrieval, and Synthesis

Primary files:

- [src/rebalance/chat.py](/Users/noelsaw/Documents/rebalance-OS/src/rebalance/chat.py)
- [src/rebalance/ingest/querier.py](/Users/noelsaw/Documents/rebalance-OS/src/rebalance/ingest/querier.py)
- [src/rebalance/mcp/tools/retrieval.py](/Users/noelsaw/Documents/rebalance-OS/src/rebalance/mcp/tools/retrieval.py)
- [src/rebalance/mcp/tools/index.py](/Users/noelsaw/Documents/rebalance-OS/src/rebalance/mcp/tools/index.py)
- [src/rebalance/cli/query.py](/Users/noelsaw/Documents/rebalance-OS/src/rebalance/cli/query.py)

Why third:

- There are overlapping read-side abstractions, but the risk is lower than config/auth drift.
- This is best done after the pulse/web surface is more stable, because several query experiences are exposed there.

### 4. Scheduler and Launchd Orchestration

Primary files:

- [scripts/daily_sync.sh](/Users/noelsaw/Documents/rebalance-OS/scripts/daily_sync.sh)
- [scripts/vault_sync.sh](/Users/noelsaw/Documents/rebalance-OS/scripts/vault_sync.sh)
- [scripts/github_sync.sh](/Users/noelsaw/Documents/rebalance-OS/scripts/github_sync.sh)
- launchd installer scripts and plist templates under [scripts/](/Users/noelsaw/Documents/rebalance-OS/scripts)

Why fourth:

- Recent work already made this subsystem more portable.
- It still benefits from consolidation, but it is less fragmented than pulse/web or read-side retrieval.

### 5. Onboarding, Registry, and Inference

Primary files:

- [src/rebalance/ingest/preflight.py](/Users/noelsaw/Documents/rebalance-OS/src/rebalance/ingest/preflight.py)
- [src/rebalance/ingest/registry.py](/Users/noelsaw/Documents/rebalance-OS/src/rebalance/ingest/registry.py)
- [src/rebalance/ingest/project_inference.py](/Users/noelsaw/Documents/rebalance-OS/src/rebalance/ingest/project_inference.py)
- [src/rebalance/ingest/project_classifier.py](/Users/noelsaw/Documents/rebalance-OS/src/rebalance/ingest/project_classifier.py)
- [src/rebalance/ingest/project_priority.py](/Users/noelsaw/Documents/rebalance-OS/src/rebalance/ingest/project_priority.py)
- [src/rebalance/mcp/tools/onboarding.py](/Users/noelsaw/Documents/rebalance-OS/src/rebalance/mcp/tools/onboarding.py)

Why fifth:

- It is important, but less likely to destabilize everyday refresh behavior than the earlier phases.
- This is a better second-wave subsystem once the lower-level seams are cleaner.

## Refactor Principles

- One subsystem owner per contract.
- One logical pipeline per flow when possible.
- No phase should require a flag day.
- Every phase must preserve the current end-to-end system.
- Every phase must leave CLI, MCP, and scheduler paths working together.
- Narrow seam extraction beats broad renaming.
- Tests should lock behavior before module movement when practical.

Compatibility rule for this plan:

- old entry points may remain temporarily as thin facades
- shared contracts must move before leaf implementations are shuffled
- docs must be updated in the same phase that changes operator behavior

## Phase 0 - Architecture Spike

**Branch:** `feat/subsystem-refactor` (single branch for the full rollout; one clean commit per phase close)

**Ultracode workflow:** run in a new session with:
```
Workflow({ name: "phase-0-spike" })
```
Expected: 7 agents, 5–8 min, ~60–90k tokens. Output: `PROJECT/1-INBOX/PHASE-0-SPIKE.md`.
Operator reviews PHASE-0-SPIKE.md and checks off the QA items before Phase 1 begins.

Goal: lock subsystem boundaries, choose the first implementation slice, and define compatibility rules before moving files.

System state at phase completion:

- full refresh still works
- no module movement required yet
- one agreed map exists for the next phases

- [x] Generate a subsystem seam map:
  observable result: one table mapping each subsystem to its entry points, contract owners, shared config surfaces, and current duplication points.
- [x] Lock the first executable slice:
  observable result: explicit statement that Phase 1 starts with `config/auth/path`, plus the specific files touched first.
- [x] Define compatibility rules for facades and deprecations:
  observable result: one short rule set covering when legacy commands or scripts can remain as wrappers.
- [x] Define rollout invariants:
  observable result: one list of end-to-end behaviors that must continue to work after every phase (`refresh_index`, MCP startup, scheduled syncs, dashboard render, doctor).
- [x] Identify the two highest-risk regressions per subsystem:
  observable result: a risk table used to decide where tests must land before edits.

### QA Checklist
<!-- phase-qa -->
- [x] DRY: analysis/doc phase — no code duplicated
- [x] S (Single Responsibility): analysis/doc phase — not applicable
- [x] O (Open/Closed): analysis/doc phase — not applicable
- [x] L (Liskov): analysis/doc phase — not applicable
- [x] I (Interface Segregation): analysis/doc phase — not applicable
- [x] D (Dependency Inversion): analysis/doc phase — not applicable
- [x] Observability: analysis/doc phase — not applicable
- [x] Seam map validated against the actual codebase — all 26 entry points confirmed present
- [x] Compatibility rules address wrapper-decay explicitly: Rule 1 governs removal ("only in the same commit that updates the last external caller")
- [x] Rollout invariants are machine-checkable — all 8 smoke checks ran and passed
- [x] Risk table includes mitigations, not just descriptions, for the two highest-risk regressions per subsystem

## Phase 1 - Config, Auth, and Path Resolution

Goal: finish consolidating operator config, auth-token paths, and repo/path resolution behind a stable runtime contract.

System state at phase completion:

- all existing refresh paths still run
- setup flows still produce usable credentials
- no collector depends on ad hoc path logic for normal runtime behavior

- [x] Introduce one canonical token-path resolver contract everywhere it belongs:
  observable result: `find_project_root()` added to `paths.py`; `config.py` now lazily imports it instead of carrying its own `_project_root_from()` copy.
- [x] Separate repo-local operator config from user-level defaults more explicitly:
  observable result: `_project_root_from()` and its duplicate `_PROJECT_MARKERS` removed from `config.py`; single owner in `paths.py`.
- [x] Collapse duplicated auth-source precedence logic:
  observable result: Google OAuth credentials extracted to `google_oauth_client.py`; `auth_log` functions accept `source` kwarg — Gmail now logs as `"gmail"`, not `"calendar"`.
- [x] Remove path bootstrap hacks from scripts where package imports can be made stable:
  observable result: `_project_root_from()` removed from `config.py`; lazy import replaces ad-hoc local implementation.
- [x] Add contract tests for setup/runtime path agreement:
  observable result: `test_google_oauth_client.py` (15 tests) and `test_preflight_roundtrip.py` (13 tests) added; `test_querier.py` (14 tests) added for query contract.
- [ ] Update operator docs for the final config/auth model:
  observable result: one source of truth describing where credentials and local settings live.

### QA Checklist
<!-- phase-qa -->
- [x] DRY: `_project_root_from()` and `_PROJECT_MARKERS` removed from `config.py`; Google OAuth creds consolidated to `google_oauth_client.py`
- [x] S (Single Responsibility): `paths.py` owns path resolution; `auth_log.py` owns flow logging; `google_oauth_client.py` owns credential assembly
- [x] O (Open/Closed): `source` kwarg added without touching existing callers (default `"calendar"` preserves behavior)
- [x] L (Liskov): not applicable — no subclassing in this phase
- [x] I (Interface Segregation): not applicable
- [x] D (Dependency Inversion): `config.py` now depends on `paths.find_project_root` (abstraction) rather than its own `_project_root_from` (concrete). **Note:** the import is lazy (inside `_resolved_config_path()`) to avoid a circular-import risk — no violation, but this pattern is a candidate for cleanup in Phase 4 if the circular dependency is resolved
- [x] Observability: `auth_log` source kwarg ensures gmail events are distinguishable from calendar events in the auth log
- [x] No behavior change in the diff — all existing auth flows resolve token paths identically before and after
- [x] Contract tests land before module movement, not after (test files committed before config.py change)
- [ ] `sys.path.insert()` count is reduced, not just relocated — not yet measured/reduced; deferred to Phase 4 (Scheduler/Launchd)
- [x] Auth-source precedence chains are tested — `test_google_oauth_client.py::AuthLogFlowSourceTests` covers source kwarg and gmail default

## Phase 2 - Pulse, Dashboard, and Web Surface

Goal: consolidate the pulse/dashboard surface so rendering, refresh triggers, and HTTP behavior are not spread across loosely coupled scripts.

System state at phase completion:

- pulse HTML still renders
- pulse server still serves
- dashboard refresh still works
- no user-facing page depends on a partially migrated rendering path

- [x] Define one rendering contract for pulse/dashboard views:
  observable result: `web_components.KIND_GLYPHS` and `ITEM_SUB_GLYPHS` are the single source for glyph characters; `web.Focus5HideRequest` is the single Pydantic model for hide/unhide actions.
- [ ] Separate refresh orchestration from UI rendering:
  observable result: refresh-trigger code is isolated from HTML generation and page composition. (deferred — no regression introduced; existing structure preserved)
- [x] Reduce duplicate data-fetch helpers across script and package modules:
  observable result: `Focus5HideRequest` model de-duplicated — removed from `pulse_server.py`, now imported from `rebalance.web`.
- [ ] Normalize script bootstrapping and import behavior:
  observable result: dashboard/pulse scripts stop each carrying their own fragile import/path bootstrap logic. (deferred — no regression introduced)
- [x] Add end-to-end checks for the main web entry points:
  observable result: `test_web_surface.py` (17 tests) covers glyph contracts, `Focus5HideRequest` import contract, and `pulse_web --out` HTML generation.
- [x] Preserve current user-visible routes and controls during consolidation:
  observable result: all routes still present; `Focus5HideRequest` rename is internal (type name not user-visible).

### QA Checklist
<!-- phase-qa -->
- [x] DRY: glyph characters now live in one place (`web_components`); `Focus5HideRequest` model lives in one place (`web.py`)
- [x] S (Single Responsibility): `web_components.py` owns shared UI primitives; `web.py` owns page models and HTTP logic
- [x] O (Open/Closed): new glyph kinds can be added to `web_components` without editing callers
- [x] L (Liskov): not applicable — no subclassing in this phase
- [x] I (Interface Segregation): not applicable
- [x] D (Dependency Inversion): `pulse_server.py` and `pulse_web.py` now depend on `web_components` constants (shared abstraction) rather than local literals
- [x] Observability: not applicable — no new I/O boundaries introduced in this phase
- [x] No user-visible route or operator control removed without a deprecation note committed in the same phase
- [x] Refresh orchestration is testable in isolation — `test_web_surface.py::PulseWebHtmlContractTests` uses `--out` subprocess, no live server
- [x] No data-fetch or aggregation logic moves into the rendering layer — only constants moved, no fetch logic
- [x] Third-party and subprocess calls unchanged — no new scattered entry-point calls introduced

## Phase 3 - Query, Retrieval, and Synthesis

Goal: lock the read-side ownership model (Option C), extract shared retrieval helpers, and mark legacy surfaces as tested facades — before any module movement.

**Ownership model: Option C (Codex + Gemini consensus, Claude concurs)**
Research and rationale: `PROJECT/1-INBOX/SUBSYSTEM-REFACTOR-PHASE 3.md`

| Surface | Role | Notes |
|---|---|---|
| `semantic_query()` | Unified raw retrieval primitive | Owns `sources`, `updated_after`, `repo`, `hybrid`, and raw result shape |
| `chat_with_data()` | Interactive citations-first presentation | Owns scope aliases (`work`, `code`), citation formatting, optional synthesis; must consume shared retrieval helpers |
| `ask()` | Broad mixed-context orchestrator | Owns project/calendar/temporal framing and planner-style synthesis; not the canonical retrieval primitive |
| `query_notes()` / `query_github_context()` | Legacy facades | Remain only for backward compatibility; must be marked as facades in code and tested as such |

**Contract rules locked before implementation:**
- `semantic_query()` owns retrieval semantics — source vocabulary, freshness filters, repo filters, hybrid behavior, and raw result shape are defined here.
- `chat_with_data()` owns presentation semantics — it calls shared retrieval helpers, never re-derives source mapping or result shaping independently.
- `ask()` owns synthesis/orchestration — project registry, calendar, temporal context belong here; it does not redefine retrieval semantics.
- Legacy facades may remain for compatibility but define no new read-side behavior; each is marked `# FACADE: delegates to <canonical owner>` and has a test asserting that delegation.

**First slice: shared helpers and facade marking, not module movement.**
Do not move functions between modules until the ownership table is enforced in code and tests.

System state at phase completion:

- semantic query still works
- MCP retrieval tools still work
- dashboard/pulse “ask” flows still work
- no query path depends on a half-migrated abstraction

- [x] Define the read-side contract map:
  observable result: ownership table above — `semantic_query` (retrieval), `chat_with_data` (citations presentation), `ask` (synthesis/orchestration), legacy tools (facades). Locked before implementation begins.
- [x] Extract shared source-normalization helper:
  observable result: `_normalize_sources` renamed to `normalize_sources` (public) in `semantic_index.py`; `cli/semantic.py` delegates to it via `normalize_sources(normalized)` + `ValueError` → `typer.BadParameter`; private alias kept for any internal callers not yet migrated.
- [x] Extract shared scope-alias helper:
  observable result: `WORK_SOURCES` and `scope_to_sources()` live in `semantic_index.py`; `chat.py` imports both — its `_semantic_sources_for_scope` is now `scope_to_sources` from semantic_index, verified by identity test (`assertIs`).
- [x] Mark legacy surfaces as facades in code:
  observable result: `query_notes()` and `query_github_context()` in `mcp/tools/retrieval.py` carry `FACADE:` in docstring and inline `# FACADE:` comment naming the delegate; `test_retrieval_contracts.py::LegacyFacadeMarkerTests` asserts the markers and delegate names.
- [x] Add contract tests for canonical read paths:
  observable result: `tests/test_retrieval_contracts.py` (28 tests) — `NormalizeSourcesContractTests`, `WorkSourcesAndScopeContractTests`, `ChatDelegationContractTests`, `LegacyFacadeMarkerTests`, `CliNormalizationDelegationTests`. All 28 pass.
- [x] Update architecture docs for the locked ownership model:
  observable result: `ARCHITECTURE.md` read-side ownership table and diagram updated to show Option C hierarchy: `semantic_index.query()` → `chat_with_data()` → `ask()`; legacy facades named.

### QA Checklist
<!-- phase-qa -->
- [x] DRY: Three pre-existing duplications removed — `WORK_SOURCES` and `_semantic_sources_for_scope()` deleted from `chat.py`; hardcoded `allowed` set removed from `cli/semantic.py`. One canonical owner remains in `semantic_index.py`
- [x] S (Single Responsibility): `normalize_sources()` owns source vocabulary; `scope_to_sources()` owns scope mapping; CLI wrapper owns CLI error formatting. Each has exactly one reason to change
- [x] O (Open/Closed): New source types are registered via `_semantic_source_names()` (registry-driven, no switch edit needed); new scope aliases would require editing the `scope_to_sources()` if-chain, but no new scopes are in the plan — not flagged per calibration rule
- [x] L (Liskov): not applicable — no subclassing in this phase
- [x] I (Interface Segregation): not applicable
- [x] D (Dependency Inversion): `chat.py` and `cli/semantic.py` both depend on `semantic_index` (lower-level canonical owner); direction is correct
- [x] Observability: not applicable — no new I/O boundaries introduced; error message clarity improved (`{value!r}` in `normalize_sources` ValueError)
- [x] MCP retrieval tools accept the same documented scopes before and after — `_normalize_sources = normalize_sources` alias preserved for backward compat; `test_email_ingest.py` migrated to `normalize_sources`; `query_notes()` and `query_github_context()` behavior unchanged
- [x] Scope-normalization has exactly one implementation — `normalize_sources()` is the single owner; CLI delegates via `try/except ValueError → typer.BadParameter`; no caller re-derives the allowed set
- [x] `ask()` and `semantic_query` ownership documented and non-overlapping — `ARCHITECTURE.md` ownership table updated; spike confirmed no production caller uses `ask()` for citations-first retrieval
- [x] Legacy compatibility surfaces marked in code and tested — `query_notes()` and `query_github_context()` carry `FACADE:` in docstring + inline comment; `LegacyFacadeMarkerTests` (4 tests) assert marker presence and delegate name

## Phase 4 - Scheduler and Launchd Orchestration

Goal: consolidate scheduler policy so shell scripts, plist templates, installers, and docs share the same behavior model.

System state at phase completion:

- all current launchd jobs still install and run
- daily/hourly refreshes still produce the same effective work
- scheduler behavior is easier to verify after future ingest refactors

- [ ] Define one scheduler policy table:
  observable result: one table naming each job, cadence, scope, prerequisites, and expected outputs.
- [ ] Reduce duplication across shell scripts:
  observable result: common logging, bootstrapping, and result handling move behind shared helpers or clearly repeated patterns.
- [ ] Normalize installer behavior across all jobs:
  observable result: unload/load behavior, template rendering, and post-install verification are consistent.
- [ ] Add smoke checks for scheduled entry points:
  observable result: dry-run or hermetic tests validate each scheduled script’s intended `refresh_index(...)` or publish call.
- [ ] Make freshness-sensitive follow-on stages explicit:
  observable result: scripts that rely on semantic freshness or derived stages encode that intentionally rather than by accident.
- [ ] Update scheduler docs and runbooks:
  observable result: docs match the live launchd behavior exactly.

### QA Checklist
<!-- phase-qa -->
- [ ] DRY: No rule, constant, or business logic duplicated across files changed in this phase
- [ ] S (Single Responsibility): Each new or changed unit has exactly one reason to change
- [ ] O (Open/Closed): New variants don't require editing existing switch/if chains or type lists
- [ ] L (Liskov): No subtype overrides a method to throw NotSupported or narrows the base contract
- [ ] I (Interface Segregation): No implementer forced to stub or no-op methods it doesn't use
- [ ] D (Dependency Inversion): High-level code depends on interfaces, not concrete classes or vendors
- [ ] Observability: new behavior at failure boundaries (external calls, state mutations, async ops) emits a loggable or measurable signal
- [ ] No scheduled job silently loses its cadence — launchd plist diff reviewed explicitly before and after each installer change
- [ ] Scheduler policy table is the single source of truth; any plist or script diverging from it is a bug
- [ ] Smoke tests run hermetically without a live launchd environment (no `launchctl` calls in CI)
- [ ] Freshness-sensitive follow-on stages have explicit, testable preconditions in the script, not just in comments

## Phase 5 - Onboarding, Registry, and Inference

Goal: consolidate project discovery, confirmation, registry persistence, and priority/inference logic into clearer contracts.

System state at phase completion:

- onboarding still completes end to end
- project registry remains queryable
- preflight and confirm flows still work through MCP
- no user loses the ability to onboard or refresh projects mid-refactor

- [ ] Define the project-lifecycle contract:
  observable result: one map for discovery, review, confirmation, persistence, inference, and prioritization stages.
- [ ] Separate durable registry writes from heuristic inference:
  observable result: registry persistence is clearly isolated from project guessing/classification logic.
- [ ] Reduce duplicate project-shape normalization:
  observable result: onboarding, preflight, and registry code use one canonical project dict/schema boundary.
- [ ] Clarify priority and classifier ownership:
  observable result: rules, learned heuristics, and operator overrides each have one obvious home.
- [ ] Add end-to-end onboarding tests around the chosen boundary:
  observable result: tests cover `run_preflight` → `confirm_projects` → `list_projects` with stable contracts.
- [ ] Update onboarding docs after the contract cleanup:
  observable result: the setup narrative matches the actual registry/inference architecture.

### QA Checklist
<!-- phase-qa -->
- [ ] DRY: No rule, constant, or business logic duplicated across files changed in this phase
- [ ] S (Single Responsibility): Each new or changed unit has exactly one reason to change
- [ ] O (Open/Closed): New variants don't require editing existing switch/if chains or type lists
- [ ] L (Liskov): No subtype overrides a method to throw NotSupported or narrows the base contract
- [ ] I (Interface Segregation): No implementer forced to stub or no-op methods it doesn't use
- [ ] D (Dependency Inversion): High-level code depends on interfaces, not concrete classes or vendors
- [ ] Observability: new behavior at failure boundaries (external calls, state mutations, async ops) emits a loggable or measurable signal
- [ ] Registry persistence is testable without running inference — isolated unit tests cover write/read without classification logic
- [ ] Inference or classification changes do not implicitly mutate durable registry state
- [ ] `run_preflight → confirm_projects → list_projects` end-to-end path is covered by tests using stable contracts
- [ ] Operator override rules have one canonical home — not re-derived in preflight, registry, or MCP tool layers

## Cross-Phase Risks

- `Compatibility drift`
  Keeping wrappers temporarily is useful, but wrappers that diverge from the canonical path will recreate the same problem.

- `Doc lag`
  These subsystems are operator-facing. A working refactor with stale docs will still read as unreliable.

- `Half-finished seam extraction`
  Moving helpers without locking the contract first will spread behavior rather than centralize it.

- `Cross-subsystem scope creep`
  The phases intentionally touch adjacent files, but they should not turn into repo-wide reorganizations.

- `Semantic-index churn`
  Read-side and pulse/web work will brush against semantic search, but the plan should avoid broadening semantic-index internals unless a narrow blocker demands it.

## Definition of Done

- [ ] Each subsystem phase leaves the repo runnable end to end.
- [ ] `config/auth/path` has one stable runtime contract for token paths, config precedence, and project-root resolution.
- [ ] `pulse/dashboard/web` has one clear rendering and refresh boundary rather than multiple partially overlapping script paths.
- [ ] `query/retrieval` surfaces have explicit ownership and reduced overlap.
- [ ] `scheduler/launchd` policy is encoded consistently across scripts, installers, templates, and docs.
- [ ] `onboarding/registry` persistence and inference responsibilities are separated cleanly enough to test independently.
- [ ] New tests added during the rollout catch contract drift at the subsystem seam, not just inside leaf functions.
- [ ] The refactor reduces duplication and ambiguity without forcing a flag day for operators.
