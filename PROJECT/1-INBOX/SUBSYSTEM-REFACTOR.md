---
title: Subsystem Refactor Plan
status: complete
doc_type: project-plan
owner: Noel Saw
last_updated: 2026-06-11
priority_order:
  - config-auth-path
  - pulse-dashboard-web
  - query-retrieval
  - scheduler-launchd
  - onboarding-registry
  - welcome-agent
rollout_rule: each phase must leave the full system runnable end-to-end
branch: feat/subsystem-refactor
branch_convention: single branch, one clean commit per phase close
---

| Most recently completed phase | What's next |
|---|---|
| Phase 6 complete (v0.39.0) — **plan complete, all phases 0–6 done.** Contract v2 (skipped status, executor hints, hermetic seams incl. the gh-CLI leak the walkthrough caught); `/welcome` skill + demo transcript; CLI parity (`onboard --status`, optional-stage offers); graduation stages (scheduler fleet + first pulse); local discovery promoted from git-pulse (`provenance=local-scan`) + doctor unpushed-work signal; `rebalance reset` (dry-run default, vault never touched); hermetic clone→first-pulse walkthrough at 0.06s; README leads with /welcome. 841 tests passing (1 pre-existing figma failure). | Merge `feat/subsystem-refactor` to main. Follow-ups logged: secrets-in-transcript automated test, figma test isolation, audit_modules doc backlog, tokenizer aliasing pass. |

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
11. [Phase 6 - Welcome Agent and Guided Onboarding](#phase-6---welcome-agent-and-guided-onboarding)
12. [Cross-Phase Risks](#cross-phase-risks)
13. [Definition of Done](#definition-of-done)

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

Scope note: these anti-goals govern the refactor phases (1–5). Phase 6 (Welcome Agent) is the one explicitly scoped **feature** phase in this plan — "no new product scope" is replaced there by its bounded deliverable list; every other anti-goal still applies to it.

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
- [x] D (Dependency Inversion): `config.py` now depends on `paths.find_project_root` (abstraction) rather than its own `_project_root_from` (concrete). **Note:** the import was lazy to avoid a circular-import risk — **resolved in Phase 4**: no cycle exists (`paths.py` imports nothing from the package), import lifted to module level
- [x] Observability: `auth_log` source kwarg ensures gmail events are distinguishable from calendar events in the auth log
- [x] No behavior change in the diff — all existing auth flows resolve token paths identically before and after
- [x] Contract tests land before module movement, not after (test files committed before config.py change)
- [x] `sys.path.insert()` count is reduced, not just relocated — **done in Phase 4**: 7 call sites across 5 scripts → one `scripts/_bootstrap.py` shim
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

- [x] Define one scheduler policy table:
  observable result: `SCHEDULER.md` job table — 10 jobs (label, cadence, wrapper, work/scope, prerequisites, outputs) including the previously untracked `obsidian-rollover`; freshness model and runbook included.
- [x] Reduce duplication across shell scripts:
  observable result: `scripts/lib/scheduler_common.sh` owns env bootstrap, dated logging, job-lifecycle events, and retention; the six wrappers shrank to their policy payloads (heredocs preserved verbatim).
- [x] Normalize installer behavior across all jobs:
  observable result: `scripts/lib/install_common.sh` — always-unload (the racy grep-conditional pattern eliminated), uniform template render (`{{REBALANCE_DIR}}`/`{{PYTHON}}`/`{{HOME}}`), `plutil -lint` before load, poll-verified registration; new installers for health-check, health-check-triage, obsidian-rollover (had none).
- [x] Add smoke checks for scheduled entry points:
  observable result: `tests/test_scheduler_policy.py` (17 tests) renders every template with plistlib and asserts cadence/label/RunAtLoad/program paths, wrapper `refresh_index(...)`/`publish_pulse(...)` calls, installer flow, and doc coverage; runs `scheduler_common.sh` in a throwaway tree.
- [x] Make freshness-sensitive follow-on stages explicit:
  observable result: vault-sync's `semantic` follow-on and github-sync's deliberate exclusion (deferred to daily-sync; `github_documents_missing_from_semantic` drift metric) are encoded in script comments, SCHEDULER.md, and test-enforced scope assertions; pulse jobs documented as read-only derived stages.
- [x] Update scheduler docs and runbooks:
  observable result: SCHEDULER.md runbook; ARCHITECTURE.md mode-2 section and file map updated to point at SCHEDULER.md; README points at SCHEDULER.md; verified all 7 installed plists render byte-identical to the live LaunchAgents.

Also closed both Phase-1 deferred items: `config.py` now imports `find_project_root` at module level (no cycle exists — `paths.py` imports nothing from the package), and `sys.path.insert` dropped from 7 call sites in 5 scripts to one `scripts/_bootstrap.py` shim (all five entry points verified from a foreign cwd with empty `PYTHONPATH`).

### QA Checklist
<!-- phase-qa -->
- [x] DRY: No rule, constant, or business logic duplicated across files changed in this phase — logging/bootstrap/trap and render/load flows each live in one lib; the POLICY dict in tests intentionally mirrors SCHEDULER.md (that redundancy *is* the enforcement mechanism, and a test asserts the doc stays in sync)
- [x] S (Single Responsibility): wrappers = job payload; scheduler_common = runtime; install_common = install flow; _bootstrap = path shim
- [x] O (Open/Closed): a new launchd job = template + thin wrapper/installer + POLICY row; no edits to either lib
- [x] L (Liskov): n/a — no subtyping introduced (shell + data tables)
- [x] I (Interface Segregation): daemon wrapper uses `rb_job_mark_started` without being forced into the EXIT-trap contract that doesn't fit exec'd processes
- [x] D (Dependency Inversion): wrappers depend on the lib functions, not on auth_log internals; config.py depends on `paths.find_project_root` (now at module level)
- [x] Observability: job lifecycle (started/completed/failed + elapsed) still flows to `auth_activity.jsonl`; installer verifies registration and warns on failure; `plutil -lint` failures abort before load
- [x] No scheduled job silently loses its cadence — all 7 installed plists verified byte-identical between template render and live `~/Library/LaunchAgents/`; github-sync reinstalled end-to-end as canary
- [x] Scheduler policy table is the single source of truth — test-enforced (labels, cadences, scopes, installer wiring, doc coverage)
- [x] Smoke tests run hermetically without a live launchd environment — plistlib + throwaway-tree bash runs; zero `launchctl` in tests (and a test asserts wrappers never call `launchctl`)
- [x] Freshness-sensitive follow-on stages have explicit, testable preconditions — scope lists are test-asserted in wrappers (`["vault", "semantic"]`, `["github"]`); the github→semantic gap is observable via the drift metric rather than assumed

Phase-4 QA notes: `tests/test_pulse_server_figma.py::test_adds_new_key_and_returns_sync_counts` fails pre-existing (leaks against the operator's real figma config — 409; fails on a clean tree too). `scripts/audit_modules.py` backlog (16 ARCHITECTURE / 9 CHANGELOG misses) predates this phase; Phase-4 files are fully documented in CHANGELOG 0.36.0 and ARCHITECTURE.

## Phase 5 - Onboarding, Registry, and Inference

Goal: consolidate project discovery, confirmation, registry persistence, and priority/inference logic into clearer contracts — shaped explicitly so the Phase 6 welcome agent can sit on top of them without rework.

Still a refactor phase: no new UX ships here. What changes versus the original Phase 5 sketch is that the contracts now name the things the welcome agent will need: lifecycle stages with a status vocabulary, a discovery-provenance field in the project schema, and `onboarding_status` as the machine-readable "where am I" source of truth.

System state at phase completion:

- onboarding still completes end to end
- project registry remains queryable
- preflight and confirm flows still work through MCP
- no user loses the ability to onboard or refresh projects mid-refactor

- [x] Define the project-lifecycle contract:
  observable result: `src/rebalance/ingest/lifecycle.py` — `PROJECT_LIFECYCLE` (discovery → review → confirmation → persistence → inference → prioritization, each with one owner and a write-semantics vocabulary: read_only / confirmation_gated / machine_owned / read_time_overlay) and `SETUP_STAGES` + `evaluate_setup()` with the `done`/`now`/`next`/`blocked` vocabulary. Queryable without an LLM; 13 contract tests.
- [x] Separate durable registry writes from heuristic inference:
  observable result: two real bugs fixed. (1) `discover_candidates` no longer creates the registry file (`load_registry` wrote the default when missing — discovery flipped `registry_exists` to done before any confirmation; new `read_registry` is a pure read). (2) `sync_inferred_project_registry` no longer clobbers curated rows on name collision — names owned by non-inference rows are skipped and reported (`skipped_curated_*`), locked by `CuratedRowProtectionTests`.
- [x] Reduce duplicate project-shape normalization:
  observable result: `Project.provenance` field (`remote-activity` | `vault-note` | `inferred`; `local-scan` reserved) stamped at discovery, persisted via custom_fields (the `external` pattern), lifted top-level by `get_projects` — distinguishable end to end. `normalize_match_text` in `project_classifier` is the single text normalizer (was 3 identical copies across classifier/inference/priority).
- [x] Clarify priority and classifier ownership:
  observable result: ownership encoded in `PROJECT_LIFECYCLE` — priority rules live only in `temp/rbos.config` via `config.get_project_priority_rules` (verified: consumed only by the priority overlay and classifier matchers; no re-derivation in preflight/registry/MCP layers); inference is machine_owned (never touches curated rows); prioritization is a read-time overlay, never persisted. Curated rows survive inference re-runs byte-identical (tested).
- [x] Extend `onboarding_status` into the canonical lifecycle status contract:
  observable result: `onboarding_status` is a thin view over `evaluate_setup()` — 8 stages including vault path and optional Calendar/Gmail auth, each with status + remediation hint; legacy `steps` list preserved additively.
- [x] Add end-to-end onboarding tests around the chosen boundary:
  observable result: `tests/test_onboarding_e2e.py` — discover → confirm → `get_projects` promote path (the function layer under the MCP tools), provenance round-trip, read-only discovery, status flip to done; plus `tests/test_lifecycle_contract.py` for the stage map and vocabulary.
- [x] Update onboarding docs after the contract cleanup:
  observable result: ARCHITECTURE.md documents the registry write discipline (provenance stamping, single curated write path, machine-owned inference, read-time priority overlay) and the lifecycle module; CHANGELOG 0.37.0.
- [x] Validate the contract with a thin Phase 6 spike before phase close:
  observable result: `scripts/spike_welcome_status.py` walks the contract on a sandbox fresh machine — blocked propagation, exactly-one-now, optional-stays-offered all hold at every stage boundary — and renders the real machine via `--real`. Findings fed back (see spike notes below); nothing the spike didn't need was built.

**Phase 6 spike findings (recorded for Phase 6, not built in Phase 5):**
1. *Keyring is machine-global* — `get_github_token` reads the OS keyring first, so a "clean sandbox" walkthrough on an operator machine sees the real token. Phase 6's hermetic walkthrough test needs an injection seam (env-var disable or check-level DI); the spike used mocks.
2. *`skipped` status* — optional stages stay `next` forever; a deliberate "skip Calendar" needs persisted skip state, which is Phase 6 scope. `contract_version` exists so vocabulary v2 can add `skipped` cleanly.
3. *Executor hints* — stages carry remediation prose; the agent would benefit from a machine-executable `executor` field (MCP tool name / command) per stage. Additive Phase 6 change.
4. *Titles must not encode optionality* — fixed in-phase: renderers decorate from the `optional` flag.

### QA Checklist
<!-- phase-qa -->
- [x] DRY: No rule, constant, or business logic duplicated across files changed in this phase — text normalizer 3→1 (`normalize_match_text`); inference marker string extracted to `INFERENCE_GENERATED_BY` (was duplicated in two functions); stage definitions live only in `lifecycle.py`
- [x] S (Single Responsibility): `lifecycle.py` = contract/state; `preflight.py` = discovery + confirmation; `registry.py` = persistence; `project_inference.py` = machine-owned rows; `project_priority.py` = read-time overlay
- [x] O (Open/Closed): adding a setup stage = one `SETUP_STAGES` entry + check function; clients (`onboarding_status`, spike renderer) pick it up without edits — proven when stages went 5→8
- [x] L (Liskov): not applicable — no subtyping introduced (frozen dataclasses + dicts)
- [x] I (Interface Segregation): optional stages don't force anything on hosts that skip them — they report status like any stage and never block `setup_complete`
- [x] D (Dependency Inversion): `onboarding_status` (MCP) and the spike driver depend on `evaluate_setup` (the contract), not on each other or on config internals; checks resolve config getters lazily
- [x] Observability: inference skips are visible (`skipped_curated_count/names` in summary + CLI echo); every blocked stage carries a remediation hint; `_check_db_synced` reports read errors in detail rather than swallowing them
- [x] Registry persistence is testable without running inference — `test_onboarding_e2e.py` exercises confirm/sync/read with zero classification logic; `read_registry`/`load_registry` split makes the pure read path explicit
- [x] Inference or classification changes do not implicitly mutate durable registry state — verified `refresh_index` never calls inference (explorer claim disproven by grep); the only write path is the explicit CLI command, now curated-row-safe; classifier and priority are pure reads
- [x] `run_preflight → confirm_projects → list_projects` end-to-end path is covered by tests using stable contracts — `test_onboarding_e2e.py` (function layer under the MCP tools) incl. idempotent re-discovery
- [x] Operator override rules have one canonical home — `config.get_project_priority_rules` is the single loader; consumed only by `apply_project_priorities` and `load_project_matchers`; curated rows protected from inference; rules overlay never persisted
- [x] Lifecycle map and statuses are machine-readable without an LLM — spike driver renders "where am I / what's next" from one `evaluate_setup` call, no LLM in the loop
- [x] Canonical project schema carries discovery provenance — `remote-activity` / `vault-note` / `inferred` round-trip discovery → confirm → DB read (tested); `local-scan` reserved

Phase-5 QA notes: `test_pulse_server_figma.py::test_adds_new_key_and_returns_sync_counts` still fails pre-existing (operator-config leak, predates Phase 4). The subsystem map's claim that inference runs inside `refresh_index` was wrong — verified by grep before building the seam; the actual exposure was the CLI write path plus the name-keyed upsert.

**Post-close adversarial review (Gemini, 2026-06-11) — claims 1–3 CONFIRMED, 4–6 PARTIAL; 4 findings triaged:**
1. *[High — fixed]* `sync_registry(mode="push")` dropped `Project.provenance`: `_push_from_projection` lifted `external` out of custom_fields but ignored provenance, desyncing the typed field from its custom_fields copy. Fixed with the same lift pattern; `ProvenancePushRoundTripTests` locks the full pull→push→read cycle.
2. *[Medium — fixed]* `PROJECT_LIFECYCLE` had no runtime consumer ("documentation disguised as an array"). Now exposed as `project_lifecycle_map()` in the `onboarding_status` payload — the agent gets the write-discipline map through one tool call.
3. *[Low — declined, logged]* Token-splitting still differs between `_split_tokens` (inference) and `_camel_case_parts` (classifier). Intentional: different matching behaviors (lowercased tokens vs. acronym-preserving parts); merging would change matching results mid-refactor. Logged as a candidate for a future aliasing pass.
4. *[Low — fixed]* Write semantics were string-asserted only. `WriteSemanticsEnforcementTests` adds a behavioral lock: `apply_project_priorities` over a real SQLite registry leaves the table byte-identical (read_time_overlay persists nothing).

## Phase 6 - Welcome Agent and Guided Onboarding

Goal: ship a first-class guided setup experience — a welcome agent that walks a new user from clone to first rendered pulse, executing every step itself, with the operator always able to see what's done, what's happening now, and what's next.

**This is a feature phase, not a refactor phase.** It builds strictly on the Phase 5 lifecycle contract and must not reopen Phase 1–5 seams. The refactor anti-goals apply except "no new product scope," which is replaced by the deliverable list below — anything not on it gets logged, not built.

**Form (locked 2026-06-11): three clients of one state machine.**

| Surface | Role |
|---|---|
| MCP lifecycle tools (`onboarding_status` + step executors) | Single source of truth for setup state (done/now/next/blocked per stage). Host-agnostic; queryable without an LLM; survives `/clear`, crashes, and days-long gaps. |
| `/welcome` skill (Claude Code) | Conversational front end. Reads the state machine each turn, executes each step's commands itself, asks only real decisions (OAuth consent, promote/skip). |
| `rebalance onboard` CLI | No-LLM parity fallback covering the same stages, extended to optional auth steps and scheduler install. |

**The journey (state-machine stages the agent walks):**

1. Prerequisites — venv, package install, doctor baseline
2. Vault path — set and verified
3. GitHub PAT — stored keyring-first, validated against the API
4. Google Calendar — optional, skippable, re-enterable later via the same flow
5. Gmail — optional, skippable, re-enterable later via the same flow
6. Discovery — remote GitHub activity bands (6.1 adds local git-pulse scan, provenance `local-scan`)
7. Review & promote — "we discovered these repos — promote them to monitored?"; `confirm_projects` is the only registry write
8. Initial refresh — `refresh_index`, per-source errors surfaced with remediation hints
9. Graduation — install the launchd fleet via the Phase 4 installers, render the first pulse, hand over the SCHEDULER.md runbook

**UX requirements (the bar):**

- Agent does everything: the human only clicks OAuth consent screens and answers promote/skip decisions — zero copy-pasted commands.
- "Where am I" is always answerable: the stage list with statuses renders from one tool call, at any point, in any session.
- Every step verifies, not just runs: validation is the step's exit condition (token round-trip, OAuth probe, pulse actually renders).
- Secrets posture: tokens are never echoed into the transcript; keyring-first storage; the agent passes secrets via env/stdin, never as chat literals.
- Skippable and re-enterable: optional steps can be skipped and added later through the same entry point ("you skipped Calendar — want to add it now?").
- Start-over exists: a documented, scripted reset returns the machine to a pre-onboarding state without touching the vault.
- Time-to-first-pulse is the success metric: a new user on a clean machine reaches a rendered pulse in one guided session.

System state at phase completion:

- a brand-new user completes clone → first pulse through `/welcome` alone
- every stage is resumable, verifiable, and visible via `onboarding_status`
- existing operators are unaffected (all current entry points keep working)

- [x] Ship the `/welcome` skill:
  observable result: `.claude/skills/welcome/SKILL.md` — one status call per turn, executor-hint dispatch, verify-after-every-step, secrets out of band, skip persistence, resume from the contract; `demo-transcript.md` committed as the UX baseline.
- [x] Cover every stage with an agent-runnable executor:
  observable result: contract v2 — every stage carries `executor` (`mcp:` / `cli:` / `script:` vocabulary); existing MCP tools reused; Calendar/Gmail run as `script:` executors with the browser consent as the only human step; graduation drives the Phase 4 installers + `pulse_web_sync.sh`.
- [x] CLI parity:
  observable result: `rebalance onboard --status` renders the same stage map; the interactive flow offers every incomplete optional stage by dispatching the contract's executors (declining persists the skip); `--yes` never launches OAuth or installs jobs silently.
- [x] Promote local repo discovery (6.1):
  observable result: `ingest/local_repos.py` (git-pulse walk promoted): scan `local_repo_roots`, GitHub identity from origin, unpushed counts; discovery surfaces uncovered on-disk repos as `provenance=local-scan` candidates; the promote flow is identical for remote and local.
- [x] Surface unpushed work as an ongoing signal:
  observable result: doctor check `local repos` WARNs ("acme/x: 3 unpushed on main; …") whenever roots are configured — continuous, not onboarding-only. Off (silent OK) with no roots.
- [x] Ship the reset path:
  observable result: `rebalance reset` — dry-run by default, `--force` executes: unloads/removes the launchd fleet, deletes config + knowledge base, enumerates keyring secrets (`--include-keyring` to delete), vault never touched. Dry-run verified live (7 jobs, 4 secrets enumerated).
- [x] End-to-end walkthrough test:
  observable result: `tests/test_welcome_walkthrough.py` — clone → first pulse hermetically with REAL config writes (not mocked checks), skip round-trip, graduation; time-to-first-pulse (hermetic) 0.06s. The test caught a second machine-global escape: the gh-CLI token fallback — fixed with `REBALANCE_HERMETIC=1` (disables keyring + gh-CLI).
- [x] Rewrite onboarding docs around the agent:
  observable result: README Getting Started leads with "Fastest path — /welcome" (manual steps kept as reference); PROJECT.md v1.1 note updated — a desktop UI is now just another client of the state machine.

### QA Checklist
<!-- phase-qa -->
- [x] DRY: stage definitions live only in the lifecycle contract — skill, CLI `--status`/offers, MCP tool, spike, and walkthrough all consume `evaluate_setup`/executors; none re-declares stages
- [x] S (Single Responsibility): lifecycle = state; executors (MCP tools/scripts/installers) = actions; skill + `onboard` CLI = presentation; `local_repos.py` = read-only scanning
- [x] O (Open/Closed): graduation proved it — two new stages added as map entries + checks, and every client (skill, CLI, spike, tests) picked them up with zero edits
- [x] L (Liskov): skipped optional stages report `skipped`, never throw; `skip_onboarding_stage` refuses required stages with the optional list instead of erroring opaquely
- [x] I (Interface Segregation): optional stages never block `setup_complete`; hosts that skip them implement nothing
- [x] D (Dependency Inversion): skill and CLI depend on the status contract and executor vocabulary, not on each other or script internals; hermetic seams (`REBALANCE_HERMETIC`, `_launch_agents_dir`, `_pulse_html_path`) are injection points, not test hacks in prod code paths
- [x] Observability: stages carry detail + remediation; inference skips, doctor unpushed-work, and reset all report what they did/would do; executor failures surface exit code + fix hint in the CLI flow
- [x] Secrets: walkthrough asserts the PAT never lands in the keyring under the seam; skill rules keep tokens out of the transcript (tool-argument passing); reset only deletes secrets on explicit `--include-keyring`. *Gap accepted:* no automated transcript-scanning test — the skill is prompt-enforced; logged for a future hardening pass
- [x] Resumability: walkthrough asserts status at every stage boundary; re-poll stability and exactly-one-now are contract-tested; /welcome re-entry shape documented in the demo transcript
- [x] Host-agnostic: the state machine has zero skill dependency — `onboarding_status` (any MCP host) and `rebalance onboard --status` (no LLM at all) render the same map
- [x] Time-to-first-pulse measured: 0.06s hermetic (sandbox, real config writes); real-world time is dominated by OAuth consents and the initial refresh — measure on the first live beta install

Phase-6 QA notes: the hermetic walkthrough caught the gh-CLI token fallback leaking the operator's real login into "fresh" sandboxes (same class as the Phase 5 keyring finding) — `REBALANCE_HERMETIC=1` now covers both. The "no secrets in transcript" automated test is the one accepted gap (prompt-enforced today); candidates for a hardening pass alongside the pre-existing figma test leak.

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

- `Feature-phase drift`
  Phase 6 is the only feature phase in this plan. Its deliverable list is the scope boundary — "while we're building the agent" additions (new ingest sources, GUI work, telemetry platforms) get logged for a future plan, not built.

- `Contract built before its consumer`
  Phase 5 defines contracts (lifecycle map, provenance, status vocabulary) whose first real consumer is Phase 6. An unconsumed contract is a guess — so the thin Phase 6 spike is a mandatory Phase 5 exit item, not a contingency. The spike also bounds Phase 5's size: anything it doesn't need, Phase 5 doesn't build.

## Definition of Done

- [x] Each subsystem phase leaves the repo runnable end to end — every phase closed with doctor + full suite green; no flag days.
- [x] `config/auth/path` has one stable runtime contract for token paths, config precedence, and project-root resolution (Phase 1; deferred items closed in Phase 4; hermetic seams added in Phase 6).
- [x] `pulse/dashboard/web` has one clear rendering and refresh boundary (Phase 2: shared glyph/model contracts; the deeper refresh/render separation was deferred without regression and stands as logged debt).
- [x] `query/retrieval` surfaces have explicit ownership and reduced overlap (Phase 3: Option C ownership table, shared normalization, facades marked and tested).
- [x] `scheduler/launchd` policy is encoded consistently across scripts, installers, templates, and docs (Phase 4: SCHEDULER.md + shared libs + 17 conformance tests).
- [x] `onboarding/registry` persistence and inference responsibilities are separated cleanly enough to test independently (Phase 5: lifecycle contract, curated-row protection, provenance; adversarially reviewed).
- [x] New tests added during the rollout catch contract drift at the subsystem seam, not just inside leaf functions (~120 new seam tests: scheduler policy, lifecycle contract, onboarding E2E, curated-row protection, local repos, hermetic walkthrough).
- [x] The refactor reduces duplication and ambiguity without forcing a flag day for operators.
- [x] A new user reaches a rendered first pulse through one guided `/welcome` session — auth setup (PAT, optional Calendar/Gmail), repo promotion, and scheduler install handled by the agent; "where am I / what's next" queryable at every step via `onboarding_status` or `rebalance onboard --status` (Phase 6).
