---
title: Apple Reminders Unified Integration Plan
doc_type: project-plan
status: active
owner: Noel Saw
created: 2026-06-25
updated: 2026-06-27
goal: "Deliver a safe, read-only Apple Reminders source for rebalance with deterministic extraction of reminders, tags, sections, and parent-child structure, then expose it through existing index/query surfaces."
priority: P2
related:
  - PROJECT/4-MISC/APPLE-REMINDERS-REFERENCE.md
  - PROJECT/4-MISC/APPLE-REMINDERS-REFERENCE-02.md
  - PROJECT/4-MISC/APPLE-REMINDERS.md
  - src/rebalance/ingest/index_ops.py
  - ARCHITECTURE.md
---

## Status

| What was just completed | What's next |
|---|---|
| **Phases 0–3 core complete (2026-06-27).** P0/P1 (`e81cb5e`): FDA access, deterministic store discovery, WAL-safe snapshot, dynamic REMCD mapper, read-only extraction (9010) operator-verified vs the UI. P2 (`891e210`): `apple_reminders` collector (opt-in, macOS+FDA) + table/storage (`ensure/upsert/sync`, reconcile-don't-delete, indexes) + status wiring; verified live via `refresh_index` (8147 scoped to `Reminders`, idempotent, 0 errors). **P3:** `list_apple_reminders` read accessor — safe-by-default (active-only; live read = 14, not 8147), pure-`sqlite3` (no private framework), filters for due/completed/list/retired; 26 tests pass. | **Decision: product surface.** Phase 3 *core* (query accessor) done; the optional product-surface wiring (daily context / pulse panel) + its UX copy are deferred pending where you want reminders to show. Also still open: Phase 4 hardening; deferred perf wins (active-store snapshot, mtime-skip); notes/sections decode. |

## Table of Contents

- [Scope](#scope)
- [Source Synthesis](#source-synthesis)
- [Target Architecture](#target-architecture)
- [Data Contract (Normalized)](#data-contract-normalized)
- [Verified Discovery (Phase 0 and 1 findings)](#verified-discovery-phase-0-and-1-findings)
- [Phase 0 - Access + Schema Spike](#phase-0---access--schema-spike)
- [Phase 1 - Read-only Extractor + Snapshot Pipeline](#phase-1---read-only-extractor--snapshot-pipeline)
- [Phase 2 - Collector Registration + Storage](#phase-2---collector-registration--storage)
- [Phase 3 - Query Surface + Product Integration](#phase-3---query-surface--product-integration)
- [Phase 4 - Hardening + Upgrade Safety](#phase-4---hardening--upgrade-safety)
- [Explicit Non-Goals](#explicit-non-goals)
- [Risks and Mitigations](#risks-and-mitigations)

## Scope

Build one canonical, read-only Apple Reminders ingestion path for rebalance:

1. Discover live Reminders SQLite store on macOS.
2. Create a safe local snapshot (`.sqlite`, `-wal`, `-shm`) before query.
3. Extract and normalize reminders, sections, tags, and sub-reminder relationships.
4. Register the source through the collector registry in `index_ops.py`.
5. Expose source freshness/coverage via existing status/query surfaces.

## Source Synthesis

What the three source docs establish together:

- `APPLE-REMINDERS-REFERENCE.md`: Core Data schema reality, dynamic table/column mapping expectations, and WAL safety constraints.
- `APPLE-REMINDERS-REFERENCE-02.md`: the practical sync model details (token-map mechanics, section/membership internals) and the key rule to avoid direct live-store writes.
- `APPLE-REMINDERS.md`: repo-native phased delivery shape, TCC/FDA blocker history, and integration boundaries with `index_ops.py`.

Unified decision:

- Default path is **read-only SQLite ingest** from a snapshot.
- EventKit stays optional and secondary for verification only; it is not the collector primary path.
- No mutation of Apple's live DB under any phase.

## Target Architecture

Single pipeline:

1. Path discovery: resolve active `Data-*.sqlite` in known Reminders roots.
2. Snapshot: copy `.sqlite` + `-wal` + `-shm` to `temp/apple-reminders/`.
3. Introspection: inspect schema and resolve table/column mapping dynamically.
4. Extraction: build normalized records.
5. Upsert: write into rebalance-managed table for source `apple_reminders`.
6. Registry integration: expose via collector in `src/rebalance/ingest/index_ops.py`.

## Data Contract (Normalized)

Minimum required fields:

- `reminder_id`
- `title`
- `notes`
- `is_completed`
- `due_at`
- `completed_at`
- `list_name`
- `section_name`
- `tags_json`
- `parent_reminder_id`
- `sort_hint`
- `created_at`
- `updated_at`
- `raw_payload_json` (small stability escape hatch for schema drift)

## Verified Discovery (Phase 0 and 1 findings)

> Captured from the live spike on **2026-06-25** (macOS 15.7.5, build 24G624, Darwin 24.6.0 arm64;
> sqlite 3.43.2; Python 3.13). This is the durable record — the run-time evidence in
> `temp/apple-reminders/` (schema dump, redacted sample, spike report) is **gitignored and ephemeral**.
> Implementation lives in `src/rebalance/ingest/apple_reminders.py`; tests in `tests/test_apple_reminders.py`.

### Access (TCC / Full Disk Access)

- Store directory: `~/Library/Group Containers/group.com.apple.reminders/Container_v1/Stores`.
- FDA must be granted to the **host application that owns the process tree**, not the CLI. In this
  environment that was **Visual Studio Code** (`Code.app` → `Code Helper (Plugin)` → `claude` → `zsh`).
  A different runtime (Terminal, a packaged `.app`, a launchd daemon) needs its **own** grant.
- TCC changes require the host app to be **fully quit and relaunched** — a window reload is not enough.
- Symptom when denied: `Operation not permitted` (not "file not found"). Confirm it's TCC and not the
  command sandbox by retrying unsandboxed before concluding.

### Active store discovery

- There are **multiple `Data-*.sqlite` account stores** (one per Reminders account). At capture time:
  4 stores, only `Data-1FB0F4BF-274D-45EE-B37E-16474CF58CA7.sqlite` had data (9010 reminders); the
  other three (incl. `Data-local` = "On My Mac") had **0 reminders**.
- Select the active store **deterministically by max `ZREMCDREMINDER` row count** — NOT by file size or
  mtime (mtimes get touched on app launch; sizes mislead). `pick_active_store()` does this.

### Snapshot / WAL safety

- Never open the live store. File-copy the triplet (`.sqlite` + `-wal` + `-shm`) into
  `temp/apple-reminders/`, then open the **copy** with `mode=ro`. `PRAGMA quick_check` = `ok` on every
  copy. Whole-snapshot wall-clock ~0.29s; full discover→snapshot→extract ~0.18–0.29s.
- **Perf note for Phase 2 (measured 2026-06-26):** one sync currently copies **~219 MB** — the code globs
  *all four* account stores' triplets (3 are empty, ~9 MB) plus the 209 MB active store. The 209 MB is
  **not reminder content and not fragmentation** (free space is only 287 KB, so `VACUUM` won't help). By
  on-disk size (`dbstat`): `ACHANGE` + its txn index = **111 MB / 53%** (Core Data persistent-history
  change tracking), `ZREMCDOBJECT` = **52 MB / 25%** (CloudKit object state), `ZREMCDREMINDER` = **37 MB /
  18%** — and even that is mostly sync metadata (`ZCKSERVERRECORDDATA` 18.9 MB + `ZRESOLUTIONTOKENMAP_V3`
  10 MB); the real title rich-text (`ZTITLEDOCUMENT`) is ~1.2 MB. **So ~85% of the copy is CloudKit/Core-Data
  sync bookkeeping the extractor never reads.** The copy is fast (~0.2s sequential SSD read); the cost is
  disk churn (~5 GB/day at hourly sync). Cheap optimizations: (1) snapshot only the **active** store, not
  all four; (2) **skip snapshot+extract when the active store's mtime is unchanged** since last sync.
  Copying only the read columns would need a live read-handle, which breaks the no-live-handle invariant —
  so full file-copy stays, and ~209 MB is the price of doing it safely.

### Schema generation

- This is the **REMCD / CloudKit schema** (`ZREMCD*` tables), **not** the legacy `ZREMINDER` schema.
  Code resolves the table dynamically (`ZREMCDREMINDER` → fallback `ZREMINDER`) so it survives either.
- Key tables: `ZREMCDREMINDER` (reminders), `ZREMCDBASELIST` (lists), `ZREMCDBASESECTION` (sections),
  `ZREMCDHASHTAGLABEL` (tag labels). Core Data bookkeeping cols are `Z_PK` / `Z_ENT` / `Z_OPT`.

### Verified field mapping

| Contract field | Source column(s) | Notes |
|---|---|---|
| `reminder_id` | `ZREMCDREMINDER.ZCKIDENTIFIER` | Stable UUID **string**, present on all rows — no need to decode the raw `ZIDENTIFIER` UUID **blob**. |
| `title` | `ZTITLE` | Plaintext; also mirrored in `ZTITLEDOCUMENT` blob (all rows). |
| `is_completed` | `ZCOMPLETED` | 8935 completed / 75 active at capture. |
| `due_at` / `completed_at` / `created_at` / `updated_at` | `ZDUEDATE` / `ZCOMPLETIONDATE` / `ZCREATIONDATE` / `ZLASTMODIFIEDDATE` | **Core Data epoch**: seconds since 2001-01-01 UTC. Convert: `unix = z + 978307200`. |
| `list_name` | `ZLIST` → `ZREMCDBASELIST.ZNAME` | 8 lists referenced at capture. |
| `parent_reminder_id` | `ZPARENTREMINDER` (local `Z_PK`) → parent's `ZCKIDENTIFIER`; fallback `ZCKPARENTREMINDERIDENTIFIER` | 16 subtasks linked & operator-verified. `ZPARENTREMINDER` is a **local PK**, so build a `Z_PK → ZCKIDENTIFIER` map first. |
| `sort_hint` | `ZICSDISPLAYORDER` | Per-list ordering also encoded in list blob `ZREMINDERIDSMERGEABLEORDERING(_V2_JSON)` if exact order ever matters. |
| `tags_json` | best-effort `#hashtag` regex over `ZTITLE` | **Low fidelity.** Plaintext regex over-matches (suite #s, invoice #s, URL fragments). Tightened to leading-letter + space-anchored → 1 real tag found. Canonical labels live in `ZREMCDHASHTAGLABEL` (2 rows); high-fidelity per-reminder tags require `ZRESOLUTIONTOKENMAP` / `_V2_JSON` / `_V3_JSONDATA` or `ZTITLEDOCUMENT`. **Deferred.** |
| `notes` | `ZNOTESDOCUMENT` (blob) | `ZNOTES` plaintext is **empty on modern stores**. Notes moved to `ZNOTESDOCUMENT` = **zlib-compressed** (`789C` magic) archived attributed string, text likely UTF-16. Extractor inflates + best-effort ASCII recovery, and returns `None` rather than mojibake (13 rows have notes). **Full-fidelity decode deferred.** |
| `section_name` | `ZREMCDBASESECTION.ZDISPLAYNAME` via `ZLIST`; membership = list blob `ZMEMBERSHIPSOFREMINDERSINSECTIONSASDATA` | Section **names are queryable**; only the reminder→section **membership** is in the per-list blob (no FK on the reminder). 0 sections in this store, so untested. **Deferred.** |

### Counts at capture (sanity baseline)

9010 total reminders · 8935 completed · 75 active · 6554 with due date · 16 subtasks · 8 lists ·
2 hashtag labels · 0 sections · 13 with notes (blob). Marked-for-deletion rows filtered via
`ZMARKEDFORDELETION`.

### Failure modes (typed, surfaced — never silent)

- Store dir unreadable → `AppleRemindersAccessError` with FDA remediation text.
- Missing required table/column → `AppleRemindersSchemaError` naming the exact missing symbol.
- Missing **optional** columns → recorded in `mapping_fallbacks`, extraction continues (graceful drift).
- Empty / unrecognized store → `AppleRemindersSchemaError`.

### Deferred decode work (with exact starting points)

1. **Notes:** parse the archived attributed string inside zlib `ZNOTESDOCUMENT` (handle UTF-16).
2. **Sections:** decode list-level `ZMEMBERSHIPSOFREMINDERSINSECTIONSASDATA` to map reminders → section,
   join section names from `ZREMCDBASESECTION.ZDISPLAYNAME`.
3. **High-fidelity tags:** parse `ZRESOLUTIONTOKENMAP_V3_JSONDATA` / `ZTITLEDOCUMENT` instead of the
   plaintext regex.
4. **Phase 2:** collector registration + storage (intentionally not started).

## Phase 0 - Access + Schema Spike

Objective: prove access and field recoverability in the real runtime context before collector work.

### Observable checklist

- [x] Confirm runtime can read the Reminders store directory with Full Disk Access applied to the actual host app/runtime. _(FDA granted to VS Code; pre-grant denial confirmed via unsandboxed retry.)_
- [x] Discover active `Data-*.sqlite` file(s) deterministically across known roots. _(By max reminder-row count: `Data-1FB0F4BF`, 9010 rows; 3 other stores empty.)_
- [x] Produce a safe snapshot (`.sqlite`, `-wal`, `-shm`) in `temp/apple-reminders/` without modifying live store. _(File copy, `quick_check`=ok on all copies, ~0.29s.)_
- [x] Dump schema metadata (`sqlite_master`, candidate `ZREMCD*` tables) to `temp/apple-reminders/schema.txt`.
- [x] Extract 20+ reminders into normalized contract. _(All 9010 extracted into `AppleReminder`.)_
- [x] Manually verify at least 5 records against Reminders UI: plain, notes, tagged, sectioned, parent-child. _(Operator vouched 2026-06-25 — lists/active/subtasks/tag confirmed against the app. NOTE: this store has 0 sections + notes deferred, so those two categories were not UI-verifiable here.)_
- [x] Record timing baseline for discovery, snapshot, extract, and total wall-clock. _(Full pipeline ~0.18–0.29s; see report.)_

### QA checklist

- [x] No write operations executed against live Reminders store. _(File copy only; copies opened `mode=ro`.)_
- [x] Spike output includes machine/runtime context and exact timestamp. _(`PHASE0-SPIKE-REPORT.md`.)_
- [x] Failure modes (permission denied, missing WAL files, schema mismatch) are explicitly logged. _(Typed errors: `AppleRemindersAccessError` / `AppleRemindersSchemaError` + `mapping_fallbacks`.)_
- [x] Evidence files are redacted for sensitive personal content before committing. _(`temp/` is gitignored; redacted sample has no titles/notes — nothing committed.)_

## Phase 1 - Read-only Extractor + Snapshot Pipeline

Objective: ship a deterministic local extractor that remains robust across schema drift.

### Observable checklist

- [x] Implement extractor module under `src/rebalance/ingest/` with clear entrypoint and no live-store writes. _(`apple_reminders.py`, entrypoint `extract_apple_reminders()`.)_
- [x] Add path resolver that tries known roots plus controlled glob fallback. _(`discover_stores_dir()` + `Data-*.sqlite` glob.)_
- [x] Add snapshot helper that copies `.sqlite`, `-wal`, and `-shm` atomically into temp working folder. _(`snapshot_stores()`.)_
- [x] Implement dynamic schema mapper (no hardcoded `Z_ENT` assumptions). _(Resolves tables/columns via `sqlite_master`/`PRAGMA table_info`; selects only present columns.)_
- [x] Emit normalized reminders rows with explicit field-level null/default behavior. _(`AppleReminder` dataclass; deferred fields explicit `None`.)_
- [x] Add structured logs for rows extracted, rows skipped, and mapping fallbacks used. _(Counts only — no titles/notes logged.)_

### QA checklist

- [x] Extraction succeeds on snapshot-only input (no dependency on live handle). _(Reads the snapshot copy `mode=ro`; never the live store.)_
- [x] Mapper degrades gracefully when optional columns are absent. _(Tested: `test_graceful_degradation_when_optional_columns_absent`.)_
- [x] Unit tests cover UUID conversion, Core Data epoch conversion, and parent-child linking. _(Epoch + parent-child covered; stable id is `ZCKIDENTIFIER` string so no UUID-blob decode needed — finding noted.)_
- [x] Sensitive fields are masked in logs and fixtures. _(Logs counts only; redacted sample omits titles/notes; test fixtures use synthetic data.)_

## Phase 2 - Collector Registration + Storage

Objective: integrate Apple Reminders as a first-class source via orchestrator workflow.

### Ingest scope (decided 2026-06-26)

- **Scope = the default list only**, targeted **by name** (`"Reminders"`), exposed as config —
  the default-list preference is NOT stored in this SQLite, so it can't be auto-detected; only the
  conventional name is available. Default name `"Reminders"`, overridable.
- **Known tradeoff (accepted):** the default list is 8,147 rows but only **14 active**; the other 61
  of 75 active reminders live in non-default lists (Cars, Crystal & Noel, Billing, …) and are
  intentionally **not** ingested under this scope. Revisit by widening the list allowlist if those are
  wanted later. (Per-list counts captured in [Verified Discovery](#verified-discovery-phase-0-and-1-findings).)
- **Completed history:** store all rows from the in-scope list (history is cheap) but index
  `is_completed` so Phase 3 can default to active-only and avoid a completed-history flood.
- The `extract_*` functions stay pure readers; the storage layer (`ensure_apple_reminders_schema`,
  `upsert_apple_reminders`, `sync_apple_reminders`) lives in the same module (mirroring
  `sleuth_reminders.py`) and is the **only writer** — the list filter is applied there at the storage
  boundary, in `sync_apple_reminders`.

### Observable checklist

- [x] Register `apple_reminders` collector in `src/rebalance/ingest/index_ops.py`. _(Opt-in `included_in_all=False` — macOS+FDA-only; never in a default/launchd `all` run.)_
- [x] Create/ensure source table schema (incl. `is_completed` index) and upsert path for normalized contract. _(`ensure_apple_reminders_schema` + `upsert_apple_reminders`; indexes on completed/active/list/parent.)_
- [x] Apply the configurable list filter (default `"Reminders"`) at the storage boundary. _(`sync_apple_reminders` filters to `get_apple_reminders_list_name()`; live run = 8147 scoped rows, only `Reminders`.)_
- [x] Wire source into index/status freshness reporting. _(`get_index_status` → `sources.apple_reminders` = reminders/active/last_synced_at.)_
- [x] Add integration tests for first sync, unchanged sync, updated row, completed row, and deleted/hidden handling. _(7 storage tests; 16 total in file.)_
- [x] Validate `refresh_index` route behavior with scope-specific dry-run and real run. _(Both verified live via the registry dispatcher: 0 errors, 8147 ingested, idempotent re-run.)_

### QA checklist

- [x] Collector follows one-writer-per-table discipline. _(Only `upsert_apple_reminders` writes `apple_reminders`; `extract_*` are read-only.)_
- [x] Collector is reachable through orchestrator; no direct leaf-write surfaces for users. _(Collector → `sync_apple_reminders`; same single path CLI/MCP would call.)_
- [x] Source sync is idempotent across repeated runs. _(Verified live: 2nd sync = 8147 unchanged, 0 ins/upd/retired.)_
- [x] Test suite includes at least one fixture with tags + parent-child reminders. _(Tags + parent-child covered; **sections deferred** — 0 in source, so a sections fixture is N/A this phase.)_

## Phase 3 - Query Surface + Product Integration

Objective: make reminders queryable/useful without collapsing source boundaries.

### Read-surface semantics (for operators/consumers)

- Accessor: `list_apple_reminders(db, *, include_completed=False, include_retired=False,
  list_name=None, has_due=None, due_before=None, due_after=None, order_by="due", limit=None)`
  in `src/rebalance/ingest/apple_reminders.py`.
- **Safe by default:** returns only **active, non-completed, non-retired** reminders. The synced
  (default) list is mostly completed history, so callers must opt in (`include_completed=True`) to see it.
- **Freshness caveat:** the table reflects the **last `sync_apple_reminders` run** — a point-in-time
  snapshot of the local store, not live. `is_active=0` means the reminder was deleted in Apple (or left
  the configured list) since a prior sync; it's retained for audit, hidden from reads by default.
- **Read path is pure `sqlite3`** — no macOS/EventKit/private-framework dependency, so any host with the
  rebalance DB can read, not just the capture machine. A not-yet-synced source returns `[]` (never raises).
- **Source identity** stays explicit: `apple_reminders` table + accessor, distinct from `sleuth_reminders`.

### Observable checklist

- [x] Add read-side accessor (`list_apple_reminders` or equivalent gather hook) with filters for due/completed/list/section. _(due/completed/list/retired/limit/order_by filters; **section filter omitted** — sections deferred from Phase 1/2.)_
- [ ] Add optional product surfaces where reminders are useful (e.g., daily context, pulse side panel) without conflating with Sleuth. _(Deferred — explicitly optional; accessor is ready to wire. Surface choice is the next decision.)_
- [x] Document source semantics and freshness caveats in user/operator docs. _(Read-surface semantics section above + accessor docstring.)_
- [x] Add regression tests for query filters and empty-source behavior. _(10 read-surface tests: defaults, completed/retired, list, has_due, due_before, ordering/NULLs-last, limit, empty-source, bad order_by; 26 total in file.)_

### QA checklist

- [x] Source identity remains explicit (`apple_reminders` vs `sleuth_reminders`). _(Separate table + separate accessor.)_
- [x] Query defaults are safe and predictable (no accidental completed-history flood). _(Default read = 14 active live, not the 8147 total; verified.)_
- [x] No private-framework dependency introduced as a hard requirement for read path. _(Read path is pure `sqlite3`.)_
- [ ] UX copy states local-only read behavior clearly. _(Deferred with the product surface — no user-facing surface added yet.)_

## Phase 4 - Hardening + Upgrade Safety

Objective: ensure ongoing reliability through macOS updates and schema drift.

### Observable checklist

- [ ] Add schema drift guardrails and health warning if required columns/tables cannot be mapped.
- [ ] Add a lightweight version/profile fingerprint in logs to aid future breakage triage.
- [ ] Add fallback handling for unreadable store paths at runtime with actionable remediation.
- [ ] Run cross-version validation on at least two macOS versions or snapshots.
- [ ] Add maintenance runbook entry for TCC/FDA troubleshooting.

### QA checklist

- [ ] Upgrade failure path is explicit and non-destructive.
- [ ] Drift detection reports exact missing symbols and suggested operator action.
- [ ] Hardening changes do not widen data collection scope.
- [ ] Docs remain aligned with actual runtime behavior after final implementation.

## Explicit Non-Goals

- Writing back to Apple Reminders.
- Forcing section/membership edits through direct SQLite writes.
- Replacing Sleuth reminders.
- Default semantic indexing of personal reminder history before source quality proves stable.

## Risks and Mitigations

- TCC/FDA access variance by runtime: verify in each execution context and document exact grant target.
- Core Data schema churn: rely on dynamic mapping + drift logs rather than static SQL assumptions.
- WAL consistency edge cases: snapshot strategy includes WAL/SHM and avoids live-store mutation.
- Privacy exposure in logs/fixtures: redact content and avoid committing sensitive rows.
