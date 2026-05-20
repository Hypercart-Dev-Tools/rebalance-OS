---
title: Rebalance-OS Codebase Refactor
status: in-progress
updated: 2026-05-20
branch: claude/refactor-codebase-tl4PQ
phases_done: 1, 2, 3, 4
phases_pending: 6, 5, 7, 9, 10
phases_skipped: 8
---

# Rebalance-OS Codebase Refactor

## Table of Contents

- [Baseline & acceptance bar](#baseline--acceptance-bar)
- [Phase 3a — Raw-SQL eviction + schema decomposition](#phase-3a--raw-sql-eviction--schema-decomposition)
- [Phase 3b — schema_version + migrations](#phase-3b--schema_version--migrations)
- [Phase 6 — MCP server registry + Pydantic response models](#phase-6--mcp-server-registry--pydantic-response-models)
- [Phase 5 — CLI decomposition](#phase-5--cli-decomposition)
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

- **285 passed.**
- **1 pre-existing failure** (also fails on `main`, not introduced by this refactor):
  `tests/test_github_knowledge.py::test_sync_persists_github_artifacts_and_documents`
  — `prs_synced 0 != 1`. Real bug, out of refactor scope; triage separately.
- **1 pre-existing collection error**: `tests/test_pulse_sleuth_scope.py` — `pulse.py`
  imports `requests`, which is **not** a declared dependency in `pyproject.toml`.
  Undeclared-dependency bug → folded into Phase 10.

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

> Primary external-facing API — agents (Claude, Codex, Gemini) hit this surface
> directly. Unblocks clean tool additions without merge conflicts. Do before CLI
> decomposition.

- [ ] Split the 826-line `create_server()` god-function (`src/rebalance/mcp_server.py`,
      25 inline `@mcp.tool()` defs) into an `mcp/` package with a tool registry.
- [ ] Add typed Pydantic response models.
- [ ] Wire new response models to all existing MCP tools.
- [ ] **Reconsider `response_version`.** A version field on every response is
      speculative churn unless there is a concrete breaking-change roadmap. Typed models
      alone deliver ~90% of the value. Add the field only if a real consumer needs it.

---

## Phase 5 — CLI decomposition

- [ ] Split `cli.py` (~2,626 lines) into a `cli/` package — one subcommand group per
      file (`refresh.py`, `github.py`, `calendar.py`, `semantic.py`, `raw.py`, etc.)
- [ ] Shrink the 186-line `refresh_cmd` by delegating to `refresh_index()`

---

## Phase 7 — Config + secrets consolidation

- [ ] Route all credential reads through `config.py`
- [ ] Add `rebalance config doctor` command

---

## Phase 9 — Scripts + experimental triage

- [ ] Deduplicate `scripts/dashboard.py` ↔ `scripts/pulse_web.py` *(fetch guards in
      `dashboard.py` already fixed — remaining: shared fetch module)*
- [ ] Promote `git-pulse` to first-class module. It is **actively maintained** (renamed
      from the old `git-history` spike, functional: hourly launchd collector, health
      checks, recap generation) — this is a promotion, not a rescue.
- [ ] **Inventory experimental spikes before deleting anything.** Produce the list
      first, confirm each is dead, *then* delete. Known dead-spike candidate so far:
      `temp/bash_script_rag_spike.py` (note: `temp/` is gitignored, so the actual
      delete surface may be thin).

---

## Phase 10 — Docs + manifest + lockfile reconcile

- [ ] Reconcile `manifest.json` against installed package versions
- [ ] Add / pin lockfile
- [ ] Declare `requests` in `pyproject.toml` (or remove the import from `pulse.py`) —
      see Baseline. This currently breaks `test_pulse_sleuth_scope.py` collection.
- [ ] Fix `tests/test_github_knowledge.py::test_sync_persists_github_artifacts_and_documents`
      — `prs_synced 0 != 1`. Pre-existing on `main`, independent of this refactor;
      triage whether the bug is in PR sync logic or a stale fixture.
- [ ] Audit and update docs for accuracy post-refactor

---

## Phase 8 — Scheduler template consolidation *(skippable)*

> Only worth doing if adding a new scheduler. Don't schedule proactively.

- [ ] Collapse 6 plist templates + 10 install scripts into one generator

---

## Deferred micro-cleanups (P1/P2 tail)

> Moved out of Phase 3 — unrelated to DB work. Each is a small standalone commit; do
> anytime, blocks nothing.

- [ ] Sweep `print`/`echo` calls → `logger` *(deferred from Phase 1)*
- [ ] Consolidate `_parse_iso` / `_truncate` time helpers *(deferred from Phase 2)*
