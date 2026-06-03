---
title: Rebalance-OS Codebase Refactor
status: in-progress
updated: 2026-06-03
branch: claude/refactor-codebase-tl4PQ
phases_done: 1, 2, 3, 4, 5, 6, 7, 10 (partial)
phases_pending: issue-39, 9, 10 (remaining)
execution_order: Phase 9 → Issue #39 (multi-device sync) → Phase 10 (remaining)
phases_skipped: 8
---

# Rebalance-OS Codebase Refactor

| ✅ Most recently completed | ▶️ What's next |
|---|---|
| **Phase 5 — complete** *(2026-06-03)*: CLI decomposition done — `cli.py` (2,899 lines) split into a 15-module `cli/` package with a 156-line root; `refresh_cmd` shrunk. (Earlier in Phase 5: unified auth/deauth log + `rebalance doctor` as the single observability hub + diagnostic `print()` sweep.) Every step behavior-preserving; 443 passed. | **Phase 9** — full git-pulse migration (collect.sh/recap/launchd; dedup against `pulse_health`) + shared fetch module + experimental-spike inventory. Then **Issue #39** (multi-device sync) and **Phase 10** (manifest/lockfile/docs). |

## Table of Contents

- [Baseline & acceptance bar](#baseline--acceptance-bar)
- [Phase 3a — Raw-SQL eviction + schema decomposition](#phase-3a--raw-sql-eviction--schema-decomposition)
- [Phase 3b — schema_version + migrations](#phase-3b--schema_version--migrations)
- [Phase 6 — MCP server registry + Pydantic response models](#phase-6--mcp-server-registry--pydantic-response-models)
- [Phase 5 — CLI decomposition + logging/observability cleanup](#phase-5--cli-decomposition--loggingobservability-cleanup)
- [Phase 7 — Config + secrets consolidation](#phase-7--config--secrets-consolidation)
- [Phase 9 — Scripts + experimental triage](#phase-9--scripts--experimental-triage)
- [Phase 10 — Docs + manifest + lockfile reconcile](#phase-10--docs--manifest--lockfile-reconcile)
- [Phase 8 — Scheduler template consolidation *(skippable)*](#phase-8--scheduler-template-consolidation-skippable)
- [Deferred micro-cleanups (P1/P2 tail)](#deferred-micro-cleanups-p1p2-tail)

---

## Baseline & acceptance bar

Captured 2026-05-19 on `claude/refactor-codebase-tl4PQ` (`.venv/bin/python -m pytest -q
--continue-on-collection-errors`). Every phase is behavior-preserving: it must leave
this exactly as-is — no *new* failures.

- **285 passed** at capture. Now **364 passed** — Phase 3b added 4 migration tests,
  Phase 6 (MCP decomposition) added none but all existing tests continue to pass.
- ~~**1 pre-existing failure**: `test_github_knowledge::test_sync_persists_…` —
  `prs_synced 0 != 1`.~~ **Resolved** — it was a time-fragile fixture (a hardcoded
  April-2026 PR date drifted past the 30-day cutoff), not a product bug. The fixture
  date is now computed relative to now.
- **1 pre-existing collection error** *(still open)*: `tests/test_pulse_sleuth_scope.py`
  — `pulse.py` imports `requests`, which is **not** a declared dependency in
  `pyproject.toml`. Undeclared-dependency bug → Phase 10.

Acceptance for every phase: run the full suite, diff against this baseline, and confirm
no row moved except intentionally.

---

## Phase 3a — Raw-SQL eviction + schema decomposition

> ✅ **Done.** `cli.py`, `github_knowledge.py`, and `semantic_index.py` all hold
> zero raw SQL; persistence lives entirely in the `db/` package. Highest leverage,
> lowest glamour — the foundation for phases 5 and 6. Behavior-preserving throughout;
> full suite held at baseline across all four steps.

- [x] Split the ~312-line `ensure_github_schema` into per-table-group helpers
      (`activity` / `repo` / `artifact` / `knowledge`). Public `ensure_github_schema()`
      stays as the unchanged entry point. *(commit `e7eb40b`)*
- [x] Pull raw SQL out of `src/rebalance/cli.py` (`_raw_*` helpers) into typed db
      helpers (`top_active_repos`, `repo_last_active`, `repo_meta_names`). `cli.py` now
      has zero raw `sqlite3`. *(commit `e7eb40b`)*
- [x] Convert the single `db.py` into a `db/` package — `connection.py` / `schema.py` /
      `github.py`, with `db/__init__.py` re-exporting the full public API so all 40+
      importers keep working unchanged. *(commit `bd330c0`)*
- [x] **Step B:** Pull raw SQL out of `src/rebalance/ingest/github_knowledge.py`
      (47 statements) into `db/github.py` — 10 `upsert_*` helpers, `insert_github_document`,
      `delete_item_children`, `search_github_documents`, the embed helpers, and the
      `purge_github_repo_data` count/delete helpers. `github_items` uses named-parameter
      binding, killing the fragile `tuple(item_record.values())` dependency.
      `github_knowledge.py` now has zero raw SQL. *(commit `49c6266`)*
- [x] **Step C:** Pull raw SQL out of `src/rebalance/ingest/semantic_index.py`
      (23 statements) into a new `db/semantic.py` (19 helpers). `semantic_index.py`
      now has zero raw SQL; the duplicate `delete_semantic_rows_for_docs` was
      removed from `db/github.py` in favour of the canonical `db/semantic.py`
      helper. *(commit `c9bea2d`)*

---

## Phase 3b — schema_version + migrations

> ✅ **Done** *(commit `c02f88d`)*.

**Decided model** (documented in `db/migrations/README.md`):

- **Version 1 is the baseline** — everything the `ensure_*_schema` functions create.
- The `ensure_*_schema` functions **stay** (not replaced by numbered migrations), so
  all 40+ call sites are untouched. `schema.py` is frozen at the baseline; every
  change from v2 onward is a forward-only `NNNN_*.sql` file in `db/migrations/`.
- **Hand-rolled runner** — no new dependency; `rebalance.db` is a single local cache.

- [x] Migration model decided and documented (see above).
- [x] Added `schema_version` table, `db/migrate.py` runner (`run_migrations`,
      `current_schema_version`, `discover_migrations`), `db/migrations/` with README,
      and wheel `package-data` for the `.sql` files. `run_migrations` runs at the
      start of every non-dry-run `refresh_index()`. 4 tests in `test_db_migrations.py`.

---

## Phase 6 — MCP server registry + Pydantic response models

> ✅ **Done** *(commit `e9a12a4`)*.

- [x] Split the 857-line `create_server()` god-function into `src/rebalance/mcp/` package:
      `server.py` (thin orchestrator) + `tools/` with 7 modules by domain
      (`projects`, `onboarding`, `retrieval`, `calendar`, `index`, `hygiene`, `sleuth`).
      `mcp_server.py` kept as a 5-line shim — `.vscode/mcp.json` untouched.
- [x] Pydantic response models — **deferred by design.** Typed models deliver ~90% of
      the value; `response_version` field is speculative churn without a concrete
      breaking-change roadmap. Revisit only when a real consumer requires it.
- [x] 364 tests pass (all existing tests hold; no new failures).

---

## Phase 5 — CLI decomposition + logging/observability cleanup

> **Expanded scope (2026-06-02):** Phase 5 now also covers **unifying logging and
> improving observability**. Diagnostics are currently spread across `doctor.py`
> (credential presence), `diagnose.py` (live repo probes), `repair.py` (FSM
> circuit-breaker keywords), the stderr `logging` handler in `__init__.py`, and
> several JSONL files under `temp/logs/`. Collectors break or get de-authorized
> with no single place to see *which* one, *when*, or *why*. The CLI decomposition
> is the natural moment to wire per-collector auth/error logging cleanly instead of
> cramming it into the 2,626-line god-function.

**CLI decomposition** ✅ *(complete 2026-06-03 — `cli.py` was 2,899 lines → a
15-module `cli/` package with a 156-line root)*

- [x] Split `cli.py` into a `cli/` package — one subcommand group per file.
      `cli.py` → `cli/` package (behavior-identical `git mv`, `_PROJECT_ROOT` fixed
      to `parents[3]`); `cli/_core.py` holds the shared `app`/`ingest_app`/`config_app`
      + `_PROJECT_ROOT` (domain modules import from `_core`, no circular dep).
      Extracted: `raw`, `semantic`, `config_cmds` (19), `calendar` (6 cmds + 9
      helpers + 2 constants; test patch targets retargeted to `rebalance.cli.calendar.*`),
      `github` (6 + `_resolve_github_repos`), `query` (query/search/ask),
      `ingest_cmds` (5), `serve`, `sleuth` (`_load_sleuth_env` re-exported for
      `index_ops`; dead `SLEUTH_ENV_PATH` dropped), `dashboard` (dashboard-render),
      `onboard`, `profile_sync`, `refresh`. `__init__.py` is now a ~156-line package
      root: the no-arg callback, `dashboard`/`doctor`/`version`, `_launch_dashboard`,
      and the registration imports. **Every step verified behavior-preserving** —
      the full 28 top-level cmds + config(19)/ingest(5) groups are byte-identical to
      pre-refactor; 443 passed throughout. Entry point `rebalance.cli:app` unchanged.
- [x] Shrink the 186-line `refresh_cmd` *(2026-06-03)*. Its orchestration already
      delegated to `refresh_index` (step 1); the remaining length was the
      web/pulse.html + publish pipeline with 3× duplicated timing/try-except/record
      boilerplate, now factored into a `_timed_step(name, fn)` helper in
      `cli/refresh.py`. Behavior-preserving.

**Logging + observability**

- [x] Unified auth-event log — `ingest/auth_log.py` now covers **all** collectors
      (calendar / github / gmail), not just calendar. Single JSONL at
      `temp/logs/auth_activity.jsonl` with a `source` field, a generic `log_event()`,
      a `FAILURE_EVENTS` set, and `latest_failure_by_source()` for readers. GitHub
      (token validate/invalid, live 401 deauth) and Gmail (ADC missing, insufficient
      scope) now emit events. Web dashboard (`web.py`) gained a Source column.
      *(2026-06-02)*
- [x] **Wire `doctor.py` to read from the unified auth log** — `_check_auth_failures()`
      surfaces the last auth failure per integration via
      `auth_log.latest_event_by_source()` (event + timestamp + device + a per-source
      remediation hint). A source whose *most recent* event is a failure is flagged
      WARN; a later success means it recovered (not flagged). Wired into both
      `run_doctor()` (→ `rebalance doctor`) and `rebalance config doctor` (new "Auth
      activity" section). Added `latest_event_by_source()` to `auth_log.py`.
      **Live-verified:** immediately caught a real GitHub `auth_failed` (401) and a
      Gmail `scope_insufficient` already in the log. *(2026-06-02)*
- [x] **`rebalance doctor` is now the single observability entry point** —
      `_diagnostics_index()` appends a map of every diagnostics surface (auth-log
      JSONL + `/auth-log` dashboard, git-pulse collector health command, `diagnose_repo`
      MCP probes, the health-reporter log) so one command points at all of them.
      *(2026-06-02)*
- [x] **Direct git-pulse collector health in doctor** *(2026-06-02)* — a *broken*
      collector now shows in `rebalance doctor` next to a de-authorized one.
      Targeted-promoted the health-read path into a first-class module
      `src/rebalance/ingest/pulse_health.py` (`CollectorHealth`, `classify()`,
      `read_collector_health()`, `resolve_sync_repo_dir()`), so doctor reads the
      structured per-device `devices/*.yaml` directly — no `experimental/` import,
      no CLI-text parsing. Sync dir resolves via rebalance's own `pulse_target_path`
      (git-pulse `config.sh` fallback). `doctor._check_pulse_collectors()` emits one
      check per device (ALIVE → OK; STALE/ALERT/DEGRADED/NO-PUSHES → WARN with age +
      failure counts). **Live-verified:** flagged a real ALERT (a device ~1.3d stale).
      `classify()` thresholds mirror the experimental script exactly.
      *Remaining for Phase 9:* migrate the rest of git-pulse (collect.sh, recap,
      launchd) and refactor `experimental/git-pulse/health-check.py` +
      `scripts/health_issue_reporter.py:run_pulse_checks()` to import from this
      module (kills the duplicate logic + the fragile `line[38:56]` CLI parse).
- [x] Sweep diagnostic `print()` in library code → the `rebalance` logger
      *(2026-06-02)*. Audited every `print()` in `src/rebalance`: the genuine
      diagnostic ones were just 5 — `querier.py` ×4 ("…context unavailable", was
      stderr) and `mcp/server.py` ×1 ("Created empty database") → now
      `logger.warning`/`logger.info`. The rest are correct as-is: `cli.py`/
      `profile_sync.py` (user-facing CLI / rich `Console` output), `paths.py`
      (`--migrate` JSON), `preflight.py` (questionary UI), `calendar_config.py`
      (✓ confirmation). **"Where do logs go?" now has a single documented
      answer** in `src/rebalance/__init__.py`: (1) diagnostics → the `rebalance`
      logger (stderr, level-gated; MCP never prints to stdout); (2) durable
      structured records → JSONL under `temp/logs/`; (3) user-facing → `typer.echo`/
      rich `Console`. Run-summary JSONL and the stderr logger are intentionally
      *not* merged — they serve different purposes (durable audit vs transient
      diagnostic); the convention names which to use when.

---

## Phase 7 — Config + secrets consolidation ✅

- [x] Route all credential reads through `config.py`:
      - `get_gemini_api_key()` moved from `note_builder.py` → `config.py`; `os` import removed from note_builder
      - `get_anthropic_api_key()` added to `config.py`; `repair.py` now calls it instead of `os.environ.get`
      - `get_sleuth_credentials()` added to `config.py` (raises `FileNotFoundError`/`ValueError`);
        `cli._load_sleuth_env()` reduced to a thin wrapper converting errors to `typer.BadParameter`;
        `mcp/tools/sleuth.py` now calls `config.get_sleuth_credentials()` directly — bad `mcp → cli` import direction eliminated
      - Calendar OAuth and Gmail ADC left as-is (complex auth flows, not simple key lookups)
      - Keyring deferred to Issue #39 Phase 0 (multi-device sync prerequisite)
- [x] Add `rebalance config doctor` command — shows live status of all credential sources:
      config file, GitHub token (live validation + login + scopes), vault path, DB path,
      ANTHROPIC_API_KEY, GEMINI_API_KEY, Sleuth env file, Google Calendar env file.
- [x] 382 tests pass.

---

## Phase 9 — Scripts + experimental triage

- [x] Deduplicate helper functions between `scripts/dashboard.py` ↔ `scripts/pulse_web.py`
      — `_truncate` and `_parse_iso` now imported from `dashboard.py`; no local copies
      in `pulse_web.py`. *(done in simplification audit Phase 1, 2026-06-01)*
- [ ] Shared fetch module — `pulse_web.py` still imports data-fetch functions directly
      from `scripts/dashboard.py` via `sys.path` injection; extract to a proper
      `src/rebalance/` module so both TUI and web share one import path
- [ ] Promote `git-pulse` to first-class module. It is **actively maintained** (renamed
      from the old `git-history` spike, functional: hourly launchd collector, health
      checks, recap generation) — this is a promotion, not a rescue.
      - [x] **Health-read path already promoted** *(2026-06-02, see Phase 5)* —
            `src/rebalance/ingest/pulse_health.py` owns the canonical
            `classify()` + device-YAML read; `doctor` consumes it. Resolved a live
            config split: rebalance `pulse_target_path`
            (`…/rebalance-OS/git-pulse-sync`) vs. git-pulse `config.sh`
            (`~/git-pulse-sync`) — pulse_health prefers `pulse_target_path`.
      - [ ] Remaining: migrate `collect.sh`, `recap.py`, `pulse_common.py`, launchd
            jobs; repoint `experimental/git-pulse/health-check.py` and
            `health_issue_reporter.py` at `pulse_health` to delete the duplicates.
- [ ] **Inventory experimental spikes before deleting anything.** Produce the list
      first, confirm each is dead, *then* delete. Known dead-spike candidate so far:
      `temp/bash_script_rag_spike.py` (note: `temp/` is gitignored, so the actual
      delete surface may be thin).

---

## Phase 10 — Docs + manifest + lockfile reconcile

- [ ] Reconcile `manifest.json` against installed package versions
- [ ] Add / pin lockfile
- [x] Remove undeclared `requests` dependency from `pulse.py` — replaced `requests.get()`
      with `urllib.request` (stdlib, consistent with `repair.py` and `note_builder.py`).
      `test_pulse_sleuth_scope.py` now collects and passes. Suite: 382 tests. *(2026-06-01)*
- [x] Fix `tests/test_github_knowledge.py::test_sync_persists_github_artifacts_and_documents`
      — `prs_synced 0 != 1`. **Done** — it was a stale (time-fragile) fixture, not a
      PR-sync bug; the PR-summary date is now computed relative to now.
- [ ] Audit and update docs for accuracy post-refactor

---

## Phase 8 — Scheduler template consolidation *(skippable)*

> Only worth doing if adding a new scheduler. Don't schedule proactively.

- [ ] Collapse 6 plist templates + 10 install scripts into one generator

---

## Deferred micro-cleanups (P1/P2 tail)

> Moved out of Phase 3 — unrelated to DB work. Each is a small standalone commit; do
> anytime, blocks nothing.

- [x] Sweep `print`/`echo` calls → `logger` *(done 2026-06-02 — see Phase 5
      logging/observability; the 5 genuine diagnostic prints converted, convention
      documented in `__init__.py`)*
- [x] Consolidate `_parse_iso` / `_truncate` time helpers *(done — simplification audit Phase 1 F4, 2026-06-01)*
