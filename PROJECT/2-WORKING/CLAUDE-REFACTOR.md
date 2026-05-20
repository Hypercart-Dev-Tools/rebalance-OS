---
title: Rebalance-OS Codebase Refactor
status: in-progress
updated: 2026-05-20
branch: claude/refactor-codebase-tl4PQ
phases_done: 1, 2, 4
phases_in_progress: 3a (3 of 5 steps done — github_knowledge.py + semantic_index.py eviction remain)
phases_pending: 3b, 6, 5, 7, 9, 10
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

> Highest leverage, lowest glamour. Foundation for phases 5 and 6 — skipping this means
> inheriting the raw-SQL sprawl in both. **Do this first.** Pure mechanical /
> behavior-preserving work; fully covered by the existing suite.

- [x] Split the ~312-line `ensure_github_schema` into per-table-group helpers
      (`activity` / `repo` / `artifact` / `knowledge`). Public `ensure_github_schema()`
      stays as the unchanged entry point. *(commit `e7eb40b`)*
- [x] Pull raw SQL out of `src/rebalance/cli.py` (`_raw_*` helpers) into typed db
      helpers (`top_active_repos`, `repo_last_active`, `repo_meta_names`). `cli.py` now
      has zero raw `sqlite3`. *(commit `e7eb40b`)*
- [x] Convert the single `db.py` into a `db/` package — `connection.py` / `schema.py` /
      `github.py`, with `db/__init__.py` re-exporting the full public API so all 40+
      importers keep working unchanged. *(commit `bd330c0`)*
- [ ] **NEXT — Step B:** Pull raw SQL out of `src/rebalance/ingest/github_knowledge.py`
      (45 statements) into `db/github.py`. Plan: ~12 `upsert_*` helpers (one per
      `github_*` table), `insert_document`, `delete_item_children`, plus the
      `purge_github_repo_data` count/delete helpers. Use named-parameter binding for
      `github_items` to kill the fragile `tuple(item_record.values())` ordering
      dependency. **Note:** this file is 1,177 lines — largest non-CLI module; SQL
      eviction is the 3a scope, broader decomposition is a separate phase.
- [ ] **Step C:** Pull raw SQL out of `src/rebalance/ingest/semantic_index.py`
      (23 statements) into a new `db/semantic.py`.

---

## Phase 3b — schema_version + migrations

> Depends on 3a. **Not mechanical** — this is a design decision and must be settled
> before any code is written.

- [ ] **Decide the migration model first.** The DB has no `schema_version` mechanism
      today; schema is created entirely by seven idempotent `ensure_*_schema`
      (`CREATE TABLE IF NOT EXISTS`) functions plus `ON CONFLICT REPLACE` upserts. That
      *is* the current de-facto migration layer. Resolve explicitly: do the `ensure_*`
      functions **stay alongside** numbered migrations, or get **replaced** by them?
      Leaving both is the failure mode. Also pick: hand-rolled runner vs. a library
      (e.g. `yoyo`).
- [ ] Add a `schema_version` table + `migrations/` directory so external tools reading
      `rebalance.db` don't break silently on column changes.

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
