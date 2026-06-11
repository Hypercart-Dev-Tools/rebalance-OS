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
| Baseline triage complete: the next refactor candidates have been identified, prioritized, and compared against recent collector-path work. | Phase 0 spike: lock subsystem boundaries, choose the first slice (`config/auth/path`), and define the compatibility rules for the rest of the rollout. |

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

- [ ] Generate a subsystem seam map:
  observable result: one table mapping each subsystem to its entry points, contract owners, shared config surfaces, and current duplication points.
- [ ] Lock the first executable slice:
  observable result: explicit statement that Phase 1 starts with `config/auth/path`, plus the specific files touched first.
- [ ] Define compatibility rules for facades and deprecations:
  observable result: one short rule set covering when legacy commands or scripts can remain as wrappers.
- [ ] Define rollout invariants:
  observable result: one list of end-to-end behaviors that must continue to work after every phase (`refresh_index`, MCP startup, scheduled syncs, dashboard render, doctor).
- [ ] Identify the two highest-risk regressions per subsystem:
  observable result: a risk table used to decide where tests must land before edits.

### QA Checklist
<!-- phase-qa -->
- [ ] DRY: No rule, constant, or business logic duplicated across files changed in this phase
- [ ] S (Single Responsibility): Each new or changed unit has exactly one reason to change
- [ ] O (Open/Closed): New variants don't require editing existing switch/if chains or type lists
- [ ] L (Liskov): No subtype overrides a method to throw NotSupported or narrows the base contract
- [ ] I (Interface Segregation): No implementer forced to stub or no-op methods it doesn't use
- [ ] D (Dependency Inversion): High-level code depends on interfaces, not concrete classes or vendors
- [ ] Observability: new behavior at failure boundaries (external calls, state mutations, async ops) emits a loggable or measurable signal
- [ ] Seam map validated against the actual codebase — entry points listed in the table exist and are reachable
- [ ] Compatibility rules address wrapper-decay explicitly: a rule governs when temporary wrappers must be removed, not just that they may exist
- [ ] Rollout invariants are machine-checkable — at least one automated smoke test per invariant exists or is scheduled before Phase 1 begins
- [ ] Risk table includes mitigations, not just descriptions, for the two highest-risk regressions per subsystem

## Phase 1 - Config, Auth, and Path Resolution

Goal: finish consolidating operator config, auth-token paths, and repo/path resolution behind a stable runtime contract.

System state at phase completion:

- all existing refresh paths still run
- setup flows still produce usable credentials
- no collector depends on ad hoc path logic for normal runtime behavior

- [ ] Introduce one canonical token-path resolver contract everywhere it belongs:
  observable result: runtime modules and setup scripts resolve Calendar/Gmail token paths through the same helper.
- [ ] Separate repo-local operator config from user-level defaults more explicitly:
  observable result: one documented accessor boundary for `temp/rbos.config` vs `~/.config/rebalance-os/config.json`.
- [ ] Collapse duplicated auth-source precedence logic:
  observable result: GitHub, Calendar, Gmail, Sleuth, and Figma each have one clearly documented precedence chain.
- [ ] Remove path bootstrap hacks from scripts where package imports can be made stable:
  observable result: fewer `sys.path.insert(...)` and fewer script-local path assumptions for normal launches.
- [ ] Add contract tests for setup/runtime path agreement:
  observable result: tests prove that setup scripts and runtime readers point at the same resolved token locations.
- [ ] Update operator docs for the final config/auth model:
  observable result: one source of truth describing where credentials and local settings live.

### QA Checklist
<!-- phase-qa -->
- [ ] DRY: No rule, constant, or business logic duplicated across files changed in this phase
- [ ] S (Single Responsibility): Each new or changed unit has exactly one reason to change
- [ ] O (Open/Closed): New variants don't require editing existing switch/if chains or type lists
- [ ] L (Liskov): No subtype overrides a method to throw NotSupported or narrows the base contract
- [ ] I (Interface Segregation): No implementer forced to stub or no-op methods it doesn't use
- [ ] D (Dependency Inversion): High-level code depends on interfaces, not concrete classes or vendors
- [ ] Observability: new behavior at failure boundaries (external calls, state mutations, async ops) emits a loggable or measurable signal
- [ ] No behavior change in the diff — all existing auth flows resolve token paths identically before and after
- [ ] Contract tests land before module movement, not after (verified by commit ordering)
- [ ] `sys.path.insert()` count is reduced, not just relocated — measure before and after
- [ ] Auth-source precedence chains are tested, not just documented

## Phase 2 - Pulse, Dashboard, and Web Surface

Goal: consolidate the pulse/dashboard surface so rendering, refresh triggers, and HTTP behavior are not spread across loosely coupled scripts.

System state at phase completion:

- pulse HTML still renders
- pulse server still serves
- dashboard refresh still works
- no user-facing page depends on a partially migrated rendering path

- [ ] Define one rendering contract for pulse/dashboard views:
  observable result: one shared renderer or rendering boundary consumed by script and server entry points.
- [ ] Separate refresh orchestration from UI rendering:
  observable result: refresh-trigger code is isolated from HTML generation and page composition.
- [ ] Reduce duplicate data-fetch helpers across script and package modules:
  observable result: page surfaces read from shared functions instead of parallel script-only implementations.
- [ ] Normalize script bootstrapping and import behavior:
  observable result: dashboard/pulse scripts stop each carrying their own fragile import/path bootstrap logic where avoidable.
- [ ] Add end-to-end checks for the main web entry points:
  observable result: tests cover dashboard refresh, pulse server refresh, and pulse HTML generation with the live function signatures.
- [ ] Preserve current user-visible routes and controls during consolidation:
  observable result: no route or operator habit disappears without an explicit deprecation note.

### QA Checklist
<!-- phase-qa -->
- [ ] DRY: No rule, constant, or business logic duplicated across files changed in this phase
- [ ] S (Single Responsibility): Each new or changed unit has exactly one reason to change
- [ ] O (Open/Closed): New variants don't require editing existing switch/if chains or type lists
- [ ] L (Liskov): No subtype overrides a method to throw NotSupported or narrows the base contract
- [ ] I (Interface Segregation): No implementer forced to stub or no-op methods it doesn't use
- [ ] D (Dependency Inversion): High-level code depends on interfaces, not concrete classes or vendors
- [ ] Observability: new behavior at failure boundaries (external calls, state mutations, async ops) emits a loggable or measurable signal
- [ ] No user-visible route or operator control removed without a deprecation note committed in the same phase
- [ ] Refresh orchestration is testable in isolation — tests do not require a live HTTP server
- [ ] No data-fetch or aggregation logic moves into the rendering layer (rendering stays pure presentation)
- [ ] Third-party and subprocess calls flow through the shared rendering boundary, not scattered across entry-point scripts

## Phase 3 - Query, Retrieval, and Synthesis

Goal: clarify the read-side architecture so semantic query, legacy source query, `ask()`, and chat-with-data are not overlapping without clear ownership.

System state at phase completion:

- semantic query still works
- MCP retrieval tools still work
- dashboard/pulse “ask” flows still work
- no query path depends on a half-migrated abstraction

- [ ] Define the read-side contract map:
  observable result: one table separating source-scoped retrieval, unified semantic retrieval, and synthesis surfaces.
- [ ] Decide which read API is canonical for each use case:
  observable result: clear ownership for `semantic_query`, legacy note/GitHub queries, `ask()`, and `chat_with_data`.
- [ ] Remove duplicated scope-normalization and result-shaping logic where possible:
  observable result: CLI and MCP wrappers use shared helpers instead of re-deriving accepted source sets and response shapes.
- [ ] Align naming and behavior between retrieval surfaces:
  observable result: “all”, source filters, top-k behavior, and freshness semantics match across CLI and MCP where they mean the same thing.
- [ ] Add contract tests for canonical read paths:
  observable result: tests prove that the chosen canonical query surfaces accept the documented scopes and return the documented structure.
- [ ] Document what remains legacy vs preferred:
  observable result: operator-facing docs can distinguish compatibility surfaces from preferred ones.

### QA Checklist
<!-- phase-qa -->
- [ ] DRY: No rule, constant, or business logic duplicated across files changed in this phase
- [ ] S (Single Responsibility): Each new or changed unit has exactly one reason to change
- [ ] O (Open/Closed): New variants don't require editing existing switch/if chains or type lists
- [ ] L (Liskov): No subtype overrides a method to throw NotSupported or narrows the base contract
- [ ] I (Interface Segregation): No implementer forced to stub or no-op methods it doesn't use
- [ ] D (Dependency Inversion): High-level code depends on interfaces, not concrete classes or vendors
- [ ] Observability: new behavior at failure boundaries (external calls, state mutations, async ops) emits a loggable or measurable signal
- [ ] MCP retrieval tools accept the same documented scopes before and after — backward-compatible
- [ ] Scope-normalization and result-shaping logic has exactly one implementation; CLI and MCP wrappers reference it, not re-derive it
- [ ] `ask()` and `semantic_query` ownership is documented and non-overlapping — no caller depends on both for the same use case
- [ ] Legacy compatibility surfaces are marked as facades in the code (not just in docs) and tested as such

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
