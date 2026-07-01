---
title: Collector Path and Portability Audit
status: "Active — reopened 2026-06-30 for 4 remaining Definition-of-Done gaps. Phases 0-5 of the original refactor are COMPLETE (2026-06-10) and preserved below as provenance; only Phase 6 is active work."
doc_type: audit-project-plan
owner: Noel Saw
created: 2026-06-10
updated: 2026-06-30
goal: >
  Close the 4 remaining Definition-of-Done gaps from the original collector-path/portability
  refactor, surfaced by a Codex review (GH-62, closed 2026-06-30): (1) not every raw source has
  exactly one source-owned write path, (4) semantic-maintenance CLI commands (`--source all`)
  drift from the live semantic-stage source coverage, (6) some setup scripts still hardcode
  auth/token paths outside the shared resolvers, (8) test/observability blind spots — e.g. the
  mocked-signature test that let a real `dashboard.py` runtime break through undetected (that
  specific break, GH-62 finding #1, is already fixed; the blind-spot gap itself is not).
related:
  - PROJECT/2-WORKING/FRONT-DOOR-PORTABILITY-AUTH-UNIFICATION.md
gh_issue_context: "https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/62 (closed — reopened here as the tracking doc for its remaining findings)"
surfaces:
  - mcp
  - cli
  - scheduler
  - web
  - obsidian
effort: 2
complexity: 3
risk: 2
phases: 6
roadmap_exempt: false
---

## Status

| What was just completed | What's next |
|---|---|
| **Reopened 2026-06-30.** Moved back from `PROJECT/4-MISC/` after a Codex review (GH-62) confirmed the audit's Definition of Done was never fully closed — 4 of 8 items are still `not yet`/`partial`. GH-62's own "High" finding (a runtime-breaking stale param in `scripts/dashboard.py`) was independently verified fixed in current code, so it is **not** part of the reopened scope; GH-62 was closed with that verification and a pointer here for the rest. | **Phase 6 — Close remaining DoD gaps** (below): single-write-path-per-source, semantic-CLI `all` normalization, hardcoded OAuth setup paths, test/observability blind spots. |

Active sequencing for the earlier, now-complete follow-up lived in [FRONT-DOOR-PORTABILITY-AUTH-UNIFICATION.md](FRONT-DOOR-PORTABILITY-AUTH-UNIFICATION.md). This doc stays the source context for the original audit, decisions, and shipped collector refactor (Phases 0-5), plus the new Phase 6 closing its remaining gaps.

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
11. [Phase 6 - Close Remaining DoD Gaps](#phase-6---close-remaining-dod-gaps) _(active)_
12. [Open Decisions and Risks](#open-decisions-and-risks)
13. [Definition of Done](#definition-of-done)

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

**COMPLETE 2026-06-10** — commits `8f1c447` (Phase 1a), `f731dbd` (Phase 1b), `ff9a8ae` (docs). Contract tests for taxonomy, raw-source membership, and `all`-expansion are GREEN; full suite passes.

- [x] Introduce an explicit source/job classification in the orchestrator layer — added a `kind` field (`raw_source` / `derived_scan` / `projection` / `export`) to `Collector`, validated at registration.
- [x] Remove `semantic`, `sync`, `dashboard`, `code`, `focus5`, and `ask_self` from the mental model of "data sources" — tagged by `kind`; they no longer ride in `all`; taxonomy recorded in `AGENTS.md`.
- [x] Make `all` expand through raw-source membership instead of generic collector inclusion — `_all_scope_names()` = raw sources only; new `_default_refresh_scopes()` = raw + code/semantic/sync is the no-scope default recipe.
- [x] Document the new taxonomy — recorded in `AGENTS.md` (Code & Architecture). **`ARCHITECTURE.md` deferred:** it is regenerated by ask-self ingest, so not a durable home yet — move there once its segmentation-of-concerns rework lands.
- [x] Keep backward compatibility for existing scope names — all scope names unchanged; `scope=None`/default → full recipe (also fixed a latent `None → ["all"]` quirk that skipped vault); only the bare `all` *token* changed, documented.

## Phase 2 - Consolidate User-Facing Write Paths

Goal: Stop exposing leaf ingest functions as parallel user-facing write APIs.

**COMPLETE 2026-06-10** — commits `65abdee` (sleuth), `6e8b5c6` (calendar), `a488511` (github×3), `f5c8a29` (vault), `50765e9` (gmail + semantic-maintenance + contract enforced). **Reframe:** a Phase-2 analysis workflow (adversarial verify per site) found `refresh_index(scope=[source])` is **not** behavior-preserving for any surface (different return envelope, runs migrations, hardcodes/drops flags) — so Phase 2 became **helper-extraction**: one source-owned helper per source, called by the CLI, the MCP tool, and the `_refresh_<source>` collector alike. `test_user_surfaces_do_not_import_leaf_ingest_functions` is now enforced (no xfail).

- [x] Route MCP Sleuth write operations through the source-owned path — `sleuth_reminders.sync_sleuth`; CLI + MCP + `_refresh_sleuth` all use it (removed an ingest→cli back-import).
- [x] Route MCP Gmail push-ingest through the `email` source contract — `gmail.push_email_messages` (upsert + email-scoped backfill; backfill stays inline until Phase 3).
- [x] Rework CLI GitHub write commands as thin wrappers — `scan_and_store_github_activity`, `sync_github_artifacts` (streaming callbacks + fail-fast), `refresh_github_embeddings`.
- [x] Rework CLI vault write commands as thin wrappers — `note_ingester.ingest_notes_command` + `embedder.embed_vault_chunks` (`ingest notes`, `ingest embed`).
- [x] Rework CLI calendar + Sleuth sync commands — `calendar.refresh_calendar_source` + the sleuth helper above.
- [x] Make re-ingest after generated note writes reuse the same vault path — the calendar weekly-note + dashboard `--reingest-note` flows now call `ingest_notes_command` + `embed_vault_chunks` (the previously-uncatalogued `dashboard-render` bypass folded in).
- [x] *(Maintenance, per owner decision)* `semantic-backfill` / `semantic-embed` → thin facades `project_semantic_documents` / `embed_semantic_pending` (keep the contract test strict rather than scoping it).

## Phase 3 - Unify Semantic Projection Ownership

Goal: Replace the current mixed semantic behavior with one explicit contract.

**COMPLETE 2026-06-10** — `semantic` is the single writer of `semantic_documents`/`semantic_embeddings`. All 7 inline `backfill_semantic_documents` and 5 `embed_pending` calls stripped from source `_refresh_*` functions. `_refresh_semantic_only` expanded to all sources via registry-derived `_all_semantic_sources()`. `test_semantic_projection_is_single_writer` flipped from xfail → GREEN. Codex findings addressed: freshness for targeted refreshes (scripts chain `semantic`; MCP push returns `semantic_pending: True`), `_ALL_SEMANTIC_SOURCES` replaced by registry-derived function, ARCHITECTURE.md updated.

- [x] Decide whether semantic projection is synchronous with source ingest or staged after source ingest:
  **staged** — source `_refresh_*` functions write raw tables only; the `semantic` stage owns all projection and embedding.
- [x] Remove the hardcoded semantic source ladder where possible:
  `_all_semantic_sources()` is registry-derived: ladder sources (`vault`, `github`, `email`, `code`) are hardcoded only because they use the if-ladder path in `backfill_semantic_documents`; sources with a `semantic_docs` provider (e.g., `figma`) are auto-included from the registry.
- [x] Normalize source behavior for `vault`, `github`, `email`, and `figma`:
  all semantic-capable sources follow the same lifecycle — raw tables written by source stage; projection/embedding by the `semantic` stage.
- [x] Define how non-semantic structured sources fit the model:
  `calendar` and `sleuth` are documented as structured-only sources; no semantic provider.
- [x] Make semantic-only maintenance a clearly separate operational stage if retained:
  `semantic` is a `projection` kind collector in the registry; documented in AGENTS.md and ARCHITECTURE.md.

## Phase 4 - Portability Contract Cleanup

Goal: Remove the environment and filesystem coupling that would make the refactor brittle or non-reusable.

**COMPLETE 2026-06-10** — Walk-up resolver (`resolve_project_root` in `paths.py`) replaces all `parents[N]` hacks across `cli/_core.py`, `ingest/token_meta.py`, `ingest/auth_log.py`, `ingest/semantic_index.py`, `chat.py`. Auth token paths centralized via `resolve_oauth_token_path("calendar"/"gmail")` in `calendar.py` and `gmail.py`. Sleuth `_find_client_mapping_path()` is config-first (`get_sleuth_client_mapping_path()`) with heuristic fallback. `refresh_index` docstring documents `update_dashboard_note` as optional output. Operator config decision recorded below. All 35 affected tests GREEN.

- [x] Inventory every config setting by storage class:
  see config inventory table below.
- [x] Decide whether operator config is repo-local, user-local, or workspace-scoped:
  **repo-local** — `temp/rbos.config` (gitignored) is the operator config store for machine/checkout-specific settings; `~/.config/rebalance-os/config.json` (`USER_CONFIG_DIR` via `paths.py`) holds cross-repo/user defaults. `get_sleuth_client_mapping_path` / `set_sleuth_client_mapping_path` added to `config.py` as the first config-backed key following this contract.
- [x] Move auth/token fallback paths behind one resolver:
  `resolve_oauth_token_path(service)` in `paths.py` computes `USER_CONFIG_DIR / f"google-{service}-oauth"`; `calendar.py` and `gmail.py` now call it instead of hardcoding `Path.home() / ".config" / "rebalance-os" / ...`.
- [x] Reduce repo-root runtime assumptions:
  `resolve_project_root(Path(__file__))` (walk-up, no `parents[N]`) used in all critical runtime paths; lazy import pattern used in `token_meta.py`, `auth_log.py`, `semantic_index.py` to avoid circular imports.
- [x] Remove sibling-checkout assumptions from product behavior:
  `sleuth_grouping._find_client_mapping_path()` checks `rbos.config["sleuth_client_mapping_path"]` first; falls back to the heuristic sibling-checkout path using `resolve_project_root` (not raw `parents[3]`).
- [x] Reclassify Obsidian write-back as optional output where appropriate:
  `refresh_index` docstring documents `update_dashboard_note` as a documented optional side-output; callers without a vault set it to `False`.

### Config inventory (2026-06-10)

| Setting | Storage class | Accessor | Notes |
|---|---|---|---|
| `vault_path` | repo-local `temp/rbos.config` | `config.get_vault_path()` | set via `rebalance config set-vault-path` |
| `github_token` | keyring (file fallback in `temp/secrets/`) | `config.get_github_token()` | set via `setup_github_token` MCP / CLI |
| `sleuth_client_mapping_path` | repo-local `temp/rbos.config` | `config.get_sleuth_client_mapping_path()` | optional; heuristic fallback if absent |
| `sleuth_web_api_*` | keyring (env fallback) | `config.get_sleuth_*()` | set via `rebalance config sleuth-*` |
| `figma_token` | keyring | `config.get_figma_token()` | optional source |
| `figma_file_keys` | repo-local `temp/rbos.config` | `config.get_figma_file_keys()` | allowlist; opt-in |
| `ask_self_path` | repo-local `temp/rbos.config` | `config.get_ask_self_path()` | path to ask-self install |
| Google Calendar OAuth token | user-local `~/.config/rebalance-os/google-calendar-oauth` | `resolve_oauth_token_path("calendar")` | pickle file; launchd fallback |
| Google Gmail OAuth token | user-local `~/.config/rebalance-os/google-gmail-oauth` | `resolve_oauth_token_path("gmail")` | pickle file; launchd fallback |
| `REBALANCE_DB_PATH` | environment variable | `paths.resolve_database_path()` | overrides default DB location |
| `REBALANCE_AUTH_LOG_DIR` | environment variable | checked in `auth_log._log_dir()` | test/sandbox override for log writes |

## Phase 5 - Tests, Observability, and Rollout

Goal: Land the refactor without silently breaking refresh behavior or data freshness.

**COMPLETE 2026-06-10** — `tests/test_phase5_collector_smoke.py` (13 tests GREEN) covers smoke, auth-failure, and idempotency for all 5 raw sources. `ARCHITECTURE.md` updated. 700 total tests pass.

- [x] Add or update smoke tests for each raw source write path:
  `CollectorSmokeTests` — dry-run test per source through `_refresh_*` entry point (vault, calendar, sleuth, email + MCP-skip variant).
- [x] Add failure-path tests for auth/config errors:
  `CollectorAuthConfigFailureTests` — all 5 sources: vault missing path, github missing token, calendar API exception, sleuth API exception, email GmailAuthError inline. All verify structured error envelopes, not uncaught exceptions.
- [x] Add unchanged/no-op tests for incremental runs:
  `CollectorIdempotencyTests` — vault: real SQLite, second run reports 0 new/updated files; calendar: same events across two calls produce stable result keys and counts; github: dry-run plan is identical across calls.
- [x] Add contract tests for `all` expansion:
  Already GREEN from Phase 1 — `test_collector_contracts.py` + `test_collector_registry.py` enforce the raw-source-only `all` expansion and follow-on stage recipe; no xfail markers remain.
- [x] Add observability around stage timing and ownership:
  `elapsed_seconds` present in all collector results; `scope` key enforced by existing contract tests; stage ownership explicit via `kind` field on `Collector` dataclass. Surfacing `kind` in the `refresh_index` result envelope deferred — not a blocker for rollout.
- [x] Update docs and runbooks at rollout time:
  `ARCHITECTURE.md`: Calendar credential row updated to reference `resolve_oauth_token_path`; `paths.py` entry documents `resolve_project_root` and `resolve_oauth_token_path`. Scheduler script descriptions were corrected in Phase 3 (lines 358-359).

## Phase 6 - Close Remaining DoD Gaps

Goal: close the 4 Definition-of-Done items still `not yet`/`partial` (below), surfaced by the GH-62
Codex review. Reopened 2026-06-30; not yet started.

- [ ] **DoD #1 — single write path per raw source.** Audit which raw sources still expose more than
  one user-facing write path (per the "known bypasses" pattern from Phase 2) and collapse each to
  one source-owned helper.
- [ ] **DoD #4 — semantic-CLI `all` normalization.** `rebalance semantic-backfill --source all` /
  `semantic-embed --source all` still normalize to the legacy `["vault", "github"]` triad
  (`src/rebalance/cli/semantic.py`), while the live `semantic` stage covers
  `_all_semantic_sources()` = `['vault', 'github', 'email', 'code', 'figma']`. Make the CLI's `all`
  match the stage's `all`.
- [ ] **DoD #6 — hardcoded OAuth setup paths.** `scripts/setup_gmail_oauth.py` and
  `scripts/setup_calendar_oauth.py` still hardcode token paths instead of calling
  `resolve_oauth_token_path(service)` (already used by the runtime `calendar.py`/`gmail.py` paths
  per Phase 4). Route the setup scripts through the same resolver.
- [ ] **DoD #8 — test/observability blind spots.** The GH-62 root cause for its own finding #1: a
  test asserted a stale, mocked call signature instead of exercising the real one
  (`tests/test_dashboard_terminal_theme.py`), so a genuine runtime break shipped undetected. Audit
  other mocked-signature tests on write-path call sites for the same blind spot; add at least one
  test that exercises `refresh_index()`'s real signature from a caller surface, not a mock.

**QA gate:** each of the 4 items above has a corresponding test (or an existing test upgraded from
mock-signature to real-signature); `pytest tests/` green; `rebalance doctor` clean; the Definition of
Done section below updated to `[x]`/`complete` for every item this phase closes.

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
  Status: not yet. Source-owned wrappers exist, but some raw sources still expose multiple user-facing write paths rather than one single path.
- [x] User-facing write surfaces no longer call leaf ingest functions directly.
  Status: complete. `tests/test_collector_contracts.py::test_user_surfaces_do_not_import_leaf_ingest_functions` is GREEN.
- [x] `all` has one explicit, tested meaning.
  Status: complete. `all` = raw sources only; the default no-scope recipe adds named follow-on stages. Contract tests are GREEN.
- [ ] Semantic projection ownership is explicit and consistent across semantic-capable sources.
  Status: not yet. The `semantic` stage is the single writer on the collector path, but maintenance CLI semantics still drift from the live stage coverage (`--source all` does not match the full semantic stage source set).
- [x] Raw sources, derived scans, projection jobs, and export jobs are modeled separately in code and docs.
  Status: complete. `Collector.kind` is enforced in code and reflected in `ARCHITECTURE.md`.
- [ ] Runtime config and auth-path assumptions are documented and reduced behind resolvers.
  Status: partial. Core runtime paths now use resolvers, but setup scripts and some script bootstraps still hardcode or inject path behavior.
- [x] Obsidian write-back is treated as an intentional output surface, not a hidden default control-plane dependency.
  Status: complete. `refresh_index` documents `update_dashboard_note` as an optional side-output rather than a core contract.
- [ ] Tests and observability cover the new contracts well enough to ship the refactor without blind spots.
  Status: not yet. Contract and smoke coverage improved materially, but blind spots remain; for example, a stale dashboard refresh call still passed tests because the signature was mocked rather than exercised live.
