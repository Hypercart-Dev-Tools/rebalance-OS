---
title: Collector Path and Portability Audit
status: in-progress
doc_type: audit-project-plan
owner: Noel Saw
last_updated: 2026-06-10
surfaces:
  - mcp
  - cli
  - scheduler
  - web
  - obsidian
---

| Most recently completed phase | What's next |
|---|---|
| Phase 0 spike complete (2026-06-10): source-manifest built, single-writer map drawn, and the two load-bearing decisions locked — `all` = raw sources only (figma stays opt-in); semantic projection is **stage-owned**. Spike confirms the target model, no blockers. | Phase 1: model raw-sources vs derived/projection/export explicitly; retire `included_in_all` in favor of explicit raw-source membership + a named default-refresh recipe (`all` + `code` + `semantic` + `sync`); keep scope-name back-compat; propagate the taxonomy + `all` definition into `ARCHITECTURE.md`. |

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Audit Scope](#audit-scope)
3. [Current Findings](#current-findings)
4. [Target Refactor Model](#target-refactor-model)
5. [Phase 0 - Technical Spike](#phase-0---technical-spike)
6. [Phase 1 - Split Raw Sources from Derived Jobs](#phase-1---split-raw-sources-from-derived-jobs)
7. [Phase 2 - Consolidate User-Facing Write Paths](#phase-2---consolidate-user-facing-write-paths)
8. [Phase 3 - Unify Semantic Projection Ownership](#phase-3---unify-semantic-projection-ownership)
9. [Phase 4 - Portability Contract Cleanup](#phase-4---portability-contract-cleanup)
10. [Phase 5 - Tests, Observability, and Rollout](#phase-5---tests-observability-and-rollout)
11. [Open Decisions and Risks](#open-decisions-and-risks)
12. [Definition of Done](#definition-of-done)

Decision lock-ins for this plan:

- "One collector per data source" applies to raw incoming sources, not to exports, projections, or local utility scans.
- User-facing write surfaces should go through one orchestrator or one source-owned helper, not directly to leaf ingest functions.
- Derived work such as semantic projection, sync export, and dashboard write-back should be explicit stages with named ownership.
- Obsidian should be treated as an optional context/output surface unless a specific workflow explicitly requires it.

## Executive Summary

The repo already has the beginnings of the right model: `src/rebalance/ingest/index_ops.py` is the intended write-side spine, and `refresh_index()` is the closest thing to a real single entry point.

The current problems are structural, not cosmetic:

- The collector registry mixes raw external sources with derived local scans and post-ingest/export jobs.
- Several MCP and CLI write surfaces still bypass the collector/orchestrator layer and call source-specific ingest functions directly.
- Semantic projection ownership is inconsistent across sources.
- Portability is improved at the DB/secrets layer, but runtime config, auth fallback paths, repo-root assumptions, and Obsidian write-back still create hidden coupling.

Refactor implication:

- Do not start by moving random call sites.
- First lock the contracts for source taxonomy, `all` semantics, and semantic ownership.
- Then consolidate the write paths behind those contracts.

## Audit Scope

This audit covered:

- Collector registration and orchestration in `src/rebalance/ingest/index_ops.py`
- MCP write surfaces in `src/rebalance/mcp/tools/`
- CLI write surfaces in `src/rebalance/cli/`
- Scheduler entry points in `scripts/*sync.sh`
- Semantic projection ownership in `src/rebalance/ingest/semantic_index.py`
- Portability and runtime-path assumptions in `src/rebalance/paths.py`, `src/rebalance/ingest/config.py`, and related runtime modules

This audit did not include:

- Full test-suite coverage analysis by source
- Runtime performance measurements beyond what the code shape already implies
- End-to-end live tool execution against external services

## Current Findings

> Code-verified 2026-06-10 against the live tree — taxonomy, `all` expansion, both write-path tables, semantic ownership, and the portability hotspots all confirmed with file:line evidence. Refinements surfaced by that pass are inlined below.

### 1. Collector taxonomy is mixed

Current registered scopes:

| Scope | Current class | Should count as a raw incoming source? | Notes |
|---|---|---|---|
| `vault` | raw source | Yes | vault ingest + embeddings + semantic backfill/embed |
| `github` | raw source | Yes | activity scan + artifact sync + embeddings + semantic backfill/embed |
| `calendar` | raw source | Yes | structured sync |
| `sleuth` | raw source | Yes | structured sync |
| `email` | raw source | Yes | sync + semantic backfill only |
| `figma` | raw source | Yes | opt-in, registry-provider semantic path |
| `code` | derived local scan | No | source-tree semantic collector |
| `semantic` | projection stage | No | cross-source semantic maintenance |
| `sync` | export stage | No | pulse snapshot export |
| `focus5` | derived local scan | No | local repo ranking cache |
| `ask_self` | derived local scan | No | device-local ask_self index inventory |

Audit conclusion:

- The registry is useful, but it currently groups unlike things under one abstraction.
- Raw source collectors, derived scans, projection stages, and export stages should not all be peers.

### 2. `all` is ambiguous

`all` currently expands through the set of collectors marked `included_in_all=True`, not through a pure "all raw sources" concept.

Verified current expansion (`_all_scope_names()`, `index_ops.py:114-116`): `all` = `vault, github, calendar, sleuth, email, code, semantic, sync`. Two consequences fall out of that:

- It **includes** derived/projection/export scopes (`code`, `semantic`, `sync`).
- It **excludes** `figma` — a *raw* source that is `included_in_all=False` because it requires a PAT plus a file-key allowlist (opt-in).

Audit conclusion:

- The codebase needs one explicit meaning for `all`.
- Recommended target: `all` means all raw incoming sources; projection/export stages are attached intentionally, not because they happen to be peers in the registry.
- **Caution — redefining `all` as "all raw sources" is not just a drop.** It would simultaneously remove `code`/`semantic`/`sync` from `all` **and pull `figma` in**. Because `figma` is opt-in for a reason (PAT + allowlist), Phase 0 must explicitly decide whether `figma` stays intentionally opt-in/attached rather than being silently swept into `all`.

### 3. User-facing write paths are duplicated

Already aligned to the orchestrator:

| Surface | Entry point | Current path |
|---|---|---|
| MCP | `refresh_index` | collector registry |
| CLI | `rebalance refresh` | `refresh_index(scope=["all"])` |
| Scheduler | `daily_sync.sh` | `refresh_index(scope=["all"])` |
| Scheduler | `vault_sync.sh` | `refresh_index(scope=["vault"])` |
| Scheduler | `github_sync.sh` | `refresh_index(scope=["github"])` |
| Web | `scripts/dashboard.py` background refresh | `refresh_index(scope=["github"])` |
| Web | `scripts/pulse_server.py` Figma add flow | `refresh_index(scope=["figma"])` |

Known bypasses:

| Surface | Entry point | Direct write path today |
|---|---|---|
| MCP | `sleuth_sync_reminders` | `sync_sleuth_reminders(...)` |
| MCP | `ingest_gmail_messages` | `ingest_email_messages(...)` + `backfill_semantic_documents(...)` |
| CLI | `rebalance github-scan` | `scan_github()` + `upsert_github_activity()` |
| CLI | `rebalance github-sync-artifacts` | `sync_github_repo()` |
| CLI | `rebalance github-embed` | `embed_github_documents()` |
| CLI | `rebalance calendar-sync` | `sync_calendar()` |
| CLI | `rebalance sleuth-sync` | `sync_sleuth_reminders()` |
| CLI | `rebalance ingest notes` | `ingest_vault()` |
| CLI | `rebalance ingest embed` | `embed_chunks()` |
| CLI | `rebalance semantic-backfill` | `backfill_semantic_documents()` |
| CLI | `rebalance semantic-embed` | `embed_pending()` |
| CLI | dashboard/weekly note re-ingest flows | `ingest_vault()` + `embed_chunks()` |

Audit conclusion:

- The repo does not yet satisfy "each user-facing module should resolve to a single collector path."
- The MCP and scheduler story is better than the CLI story, but all surfaces need the same write contract.

Export/publish surfaces outside the orchestrator (not an ingest bypass, but worth tracking):

- MCP `publish_pulse` ([src/rebalance/mcp/tools/index.py](src/rebalance/mcp/tools/index.py)) exports the pulse directly, outside `refresh_index`. It is export-class (sibling to the `sync` stage), so it belongs in the export picture (Phase 2) rather than the ingest bypass list above.

### 4. Semantic ownership is inconsistent

Current semantic behaviors differ by source:

- `vault`: source collector runs embed + semantic backfill + semantic embed
- `github`: source collector runs GitHub embeddings + semantic backfill + semantic embed
- `email`: source collector only backfills semantic documents — it does **not** embed them. Email is embedded only by the standalone `semantic` scope (which processes `['vault','github','email']` and rides in `all`). **Consequence:** a targeted `refresh_index(["email"])` leaves email semantically unsearchable until `semantic` runs separately — the concrete user-visible failure mode of the split-brain.
- `figma`: source collector uses the registry-provider semantic path
- `semantic_index.py`: still owns a legacy hardcoded ladder for `vault`, `github`, `email`, `code`

Audit conclusion:

- Semantic projection is split-brain today.
- The refactor must choose one ownership model and apply it consistently.

### 5. Portability is improved but incomplete

What is in good shape:

- DB path resolution is centralized.
- Secret-file resolution is centralized.
- Doctor already checks DB split, vault path, token reachability, and scheduler health.
- Scheduler scripts use the shared DB resolver.

Portability hotspots still in the critical path:

| Hotspot | Why it matters |
|---|---|
| repo-local `temp/rbos.config` remains a primary config store | config ownership is split between repo-local and user-local |
| Calendar/Gmail auth fallbacks still use fixed `Path.home()` token paths | auth storage is not behind one shared resolver |
| repo-root assumptions such as `parents[3]` and `sys.path.insert(...)` | runtime behavior still assumes checkout shape |
| sibling checkout assumption in `sleuth_grouping.py` | behavior depends on a local repo layout outside the collector contract |
| dashboard note write-back after full refresh | Obsidian is still part of the write-side control plane |

Audit conclusion:

- Portability work is not separate from this refactor; it will materially affect design choices.

## Target Refactor Model

Target split:

1. Raw source collectors:
   - `vault`
   - `github`
   - `calendar`
   - `sleuth`
   - `email`
   - `figma`

2. Derived/projection/export jobs:
   - `semantic`
   - `sync`
   - `dashboard`
   - `code`
   - `focus5`
   - `ask_self`

3. User-facing write wrappers:
   - MCP, CLI, schedulers, and web helpers call one orchestrator or one source-owned helper
   - leaf ingest functions stop being directly user-facing

4. One portability contract:
   - one DB resolver
   - one secret-file resolver
   - one auth/token resolver
   - one operator/workspace config resolver

## Phase 0 - Technical Spike

Goal: Lock the three decisions that determine the rest of the refactor before any write-path movement starts.

- [x] Generate a temporary source-manifest view directly from the collector registry — see [Phase 0 Results](#phase-0-results-locked-2026-06-10) below.
- [x] Define the meaning of `all` — **Decision A locked** below. (Statement also lands in `ARCHITECTURE.md` during Phase 1, which owns the taxonomy doc update; deferred here to avoid colliding with in-flight `ARCHITECTURE.md` edits.)
- [x] Decide semantic ownership — **Decision B locked** below (stage-owned).
- [x] Identify non-negotiable contract owners — single-writer list drafted below.
- [x] Pause if the spike contradicts the current target model — no contradiction; spike **confirms** the target model. One nuance resolved (figma stays opt-in; `code`/`semantic`/`sync` become named stages in the default recipe).

### Phase 0 Results (locked 2026-06-10)

Spike outcome: **the target model holds — no blockers.** The manifest confirms every classification. The one structural surprise: the semantic tables have **six writers** today (each raw source + `code` + the standalone `semantic` scope) — resolved by Decision B.

#### Source manifest (code-verified)

| Scope | Kind | in `all` today | Config / secrets | Tables written | Semantic |
|---|---|---|---|---|---|
| vault | raw_source | yes | `vault_path` | `vault_files`, `chunks` | backfill + embed |
| github | raw_source | yes | `github_token` (PAT / gh-cli) | `github_activity`, `github_commits/items/comments`, `github_repo_meta/branches/labels/milestones/releases/check_runs/links`, `github_pushed_repos`, `github_documents` | backfill + embed |
| calendar | raw_source | yes | Google OAuth | `calendar_events` | none |
| sleuth | raw_source | yes | `SLEUTH_WEB_API_*` | `sleuth_reminders`, `sleuth_sync_meta` | none |
| email | raw_source | yes | Gmail OAuth (MCP push-mode skips) | `email_messages` | backfill only |
| figma | raw_source | **no (opt-in)** | `figma_token` + `figma_file_keys` allowlist | `figma_comments` | backfill + embed (registry path) |
| code | derived_scan | yes | none (local FS) | `semantic_documents` (FTS only) | backfill only |
| semantic | projection | yes | none (local DB) | `semantic_documents`, `semantic_embeddings` | backfill + embed |
| sync | export | yes | `pulse_target_path` | none (git export) | none |
| focus5 | derived_scan | no (opt-in) | `repo_scan_roots`, `focus5_ranking_mode`, … | `focus5_repo_signals`, `focus5_roster` | none |
| ask_self | derived_scan | no (opt-in) | `repo_scan_roots` | `ask_self_indexes` | none |

#### Single-writer contract (drafted)

- **Raw source tables — one source owner each:** `vault_files`/`chunks` → vault; all `github_*` → github; `calendar_events` → calendar; `sleuth_reminders`/`sleuth_sync_meta` → sleuth; `email_messages` → email; `figma_comments` → figma.
- **`semantic_documents` / `semantic_embeddings` — sole owner = the `semantic` stage** (post-Decision B). Today six scopes write them; this collapses to one writer.
- **Sync export (pulse snapshots / git)** → the `sync` export stage.
- **Dashboard note (vault write-back)** → the `dashboard` stage (currently embedded in the full-refresh path).
- **Local derived scans** → focus5 owns `focus5_*`; ask_self owns `ask_self_indexes`.
- **Auth log** (`temp/logs/auth_activity.jsonl`) → the `auth_log` writer.

#### Decision A — meaning of `all` (LOCKED)

`all` = **raw incoming sources only**: `vault, github, calendar, sleuth, email`. Chosen as the most maintainable long-run end-state (the 80–90% destination), per owner direction.

- `figma`, `focus5`, `ask_self` stay **opt-in** (figma needs a PAT + file-key allowlist; the local scans are explicit). figma is **not** swept into `all`.
- Retire the `included_in_all` flag in favor of (a) explicit raw-source membership and (b) a **named default-refresh recipe**: `rebalance refresh` / `daily_sync` = `all` (raw sources) **+ named follow-on stages `code`, `semantic`, `sync`**. This preserves today's full-refresh behavior exactly while separating raw sources from derived/projection/export stages.
- Back-compat: existing scope names continue to work (carried as a Phase 1 lock-in).

#### Decision B — semantic ownership (LOCKED)

**Stage-owned.** The `semantic` projection stage is the **single writer** of `semantic_documents` and `semantic_embeddings`. Raw-source refreshes (and `code`) stop calling `backfill_semantic_documents` / `embed_pending` directly — they write only their own raw tables; the `semantic` stage reads those and owns all projection + embedding.

- Fixes the email-never-embedded gap (the stage always embeds every source).
- Collapses the six-writer overlap on the semantic tables to one writer (clean contract).
- Trade-off: semantic results are staged just after source ingest rather than inline; in the default recipe the stage runs immediately after the raw sources, so end-to-end freshness for a full refresh is unchanged.

## Phase 1 - Split Raw Sources from Derived Jobs

Goal: Make the registry reflect the actual architecture rather than treating all jobs as peer "collectors."

- [ ] Introduce an explicit source/job classification in the orchestrator layer:
  observable result: registered entries can distinguish raw sources from derived scans, projections, and exports without relying on comments or `included_in_all`.
- [ ] Remove `semantic`, `sync`, `dashboard`, `code`, `focus5`, and `ask_self` from the mental model of "data sources":
  observable result: docs and registry metadata stop describing them as equivalent to GitHub, vault, or calendar.
- [ ] Make `all` expand through raw-source membership instead of generic collector inclusion:
  observable result: the raw-source set is explicit and testable.
- [ ] Document the new taxonomy in `ARCHITECTURE.md`:
  observable result: the Signal Sources section and "Adding a New Source" guidance reflect the new boundary.
- [ ] Keep backward compatibility for existing scope names where possible:
  observable result: callers using legacy scope names continue to work or fail with explicit migration guidance.

## Phase 2 - Consolidate User-Facing Write Paths

Goal: Stop exposing leaf ingest functions as parallel user-facing write APIs.

- [ ] Route MCP Sleuth write operations through the source-owned path:
  observable result: the MCP Sleuth sync tool uses one `sleuth` orchestrator/helper path rather than calling `sync_sleuth_reminders(...)` directly.
- [ ] Route MCP Gmail push-ingest through the `email` source contract:
  observable result: agent-pushed Gmail payloads enter one `email` write path that also owns any follow-on projection work.
- [ ] Rework CLI GitHub write commands as thin wrappers over one GitHub-owned path:
  observable result: `github-scan`, `github-sync-artifacts`, and `github-embed` stop being separate leaf-entry write surfaces.
- [ ] Rework CLI vault write commands as thin wrappers over one vault-owned path:
  observable result: `ingest notes`, `ingest embed`, and note re-ingest flows converge on one vault contract.
- [ ] Rework CLI calendar and Sleuth sync commands as thin wrappers over their source-owned paths:
  observable result: the CLI does not call `sync_calendar()` or `sync_sleuth_reminders()` directly.
- [ ] Make re-ingest after generated note writes reuse the same vault path:
  observable result: dashboard and weekly-note write-back flows call the same vault refresh helper rather than duplicating `ingest_vault()` + `embed_chunks()`.

## Phase 3 - Unify Semantic Projection Ownership

Goal: Replace the current mixed semantic behavior with one explicit contract.

- [ ] Decide whether semantic projection is synchronous with source ingest or staged after source ingest:
  observable result: each source has a documented rule for when its documents become searchable.
- [ ] Remove the hardcoded semantic source ladder where possible:
  observable result: semantic-capable sources expose one provider/contract instead of requiring special-case branches in `semantic_index.py`.
- [ ] Normalize source behavior for `vault`, `github`, `email`, and `figma`:
  observable result: all semantic-capable sources follow the same projection lifecycle.
- [ ] Define how non-semantic structured sources fit the model:
  observable result: `calendar` and `sleuth` are explicitly documented as structured-only or upgraded intentionally with a semantic provider.
- [ ] Make semantic-only maintenance a clearly separate operational stage if retained:
  observable result: `semantic` is documented as a projection job, not a source.

## Phase 4 - Portability Contract Cleanup

Goal: Remove the environment and filesystem coupling that would make the refactor brittle or non-reusable.

- [ ] Inventory every config setting by storage class:
  observable result: one table naming which settings live in repo-local config, user-level config, keyring, filesystem secrets, and environment variables.
- [ ] Decide whether operator config is repo-local, user-local, or workspace-scoped:
  observable result: one explicit contract for `temp/rbos.config` versus user-level config.
- [ ] Move auth/token fallback paths behind one resolver:
  observable result: Calendar and Gmail no longer hardcode their fallback token file locations internally.
- [ ] Reduce repo-root runtime assumptions:
  observable result: critical runtime paths no longer depend on `parents[3]` or ad-hoc `sys.path.insert(...)` where a stable resolver could be used.
- [ ] Remove sibling-checkout assumptions from product behavior:
  observable result: Sleuth grouping/mapping resolution uses a documented resolver or optional config, not a fixed neighboring checkout layout.
- [ ] Reclassify Obsidian write-back as optional output where appropriate:
  observable result: dashboard note generation and similar flows are clearly outputs, not hidden required control-plane side effects.

## Phase 5 - Tests, Observability, and Rollout

Goal: Land the refactor without silently breaking refresh behavior or data freshness.

- [ ] Add or update smoke tests for each raw source write path:
  observable result: each source has at least one happy-path ingest test through the source-owned entry point.
- [ ] Add failure-path tests for auth/config errors:
  observable result: each source surfaces missing credential/config errors as structured failures, not implicit no-ops.
- [ ] Add unchanged/no-op tests for incremental runs:
  observable result: repeated refreshes prove that unchanged inputs do not drift counts or duplicate writes.
- [ ] Add contract tests for `all` expansion:
  observable result: one test proves which scopes are included in `all` and why.
- [ ] Add observability around stage timing and ownership:
  observable result: logs and/or status outputs distinguish source ingest from semantic projection and export work.
- [ ] Update docs and runbooks at rollout time:
  observable result: `ARCHITECTURE.md`, relevant project docs, and any scheduler guidance match the new write-path model.

## Open Decisions and Risks

- Semantic ownership risk:
  if source-owned and stage-owned projection remain mixed, the refactor will keep producing surprising freshness differences by source.
- Backward-compatibility risk:
  several CLI commands are effectively operator habits; the thin-wrapper strategy should preserve command names where possible.
- Obsidian coupling risk:
  if Obsidian stays in the write-side control plane by default, the repo will keep carrying hidden assumptions about vault availability.
- Portability risk:
  if repo-local config and hardcoded token paths remain untouched, the code may look cleaner after refactor while still being difficult to move or package.
- Scope creep risk:
  do not mix this refactor with unrelated product-surface changes; keep the work on collector taxonomy, write-path ownership, and portability contracts.

## Definition of Done

- [ ] Every raw incoming source has exactly one source-owned write path.
- [ ] User-facing write surfaces no longer call leaf ingest functions directly.
- [ ] `all` has one explicit, tested meaning.
- [ ] Semantic projection ownership is explicit and consistent across semantic-capable sources.
- [ ] Raw sources, derived scans, projection jobs, and export jobs are modeled separately in code and docs.
- [ ] Runtime config and auth-path assumptions are documented and reduced behind resolvers.
- [ ] Obsidian write-back is treated as an intentional output surface, not a hidden default control-plane dependency.
- [ ] Tests and observability cover the new contracts well enough to ship the refactor without blind spots.
