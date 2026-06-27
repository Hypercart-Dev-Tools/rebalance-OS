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
| **Phase 5.0 write spike CONVERGENCE PROVEN (2026-06-27).** Full EventKit create→read→update→converge→delete→absence loop passes from a signed LaunchServices app bundle with Reminders + Full Disk Access grants; identifier mapping is 1:1. Build harness `scripts/build_apple_reminders_write_spike_app.sh` + self-locating bundle landed. → **Now: Phase 5.1 write-surface design.** _Earlier:_ **Phases 0–4 complete (2026-06-27), incl. the P3 product surface.** P0–P2: FDA access, deterministic discovery, WAL-safe snapshot, dynamic REMCD mapper, extraction operator-verified; `apple_reminders` collector (opt-in) + storage (reconcile-don't-delete) verified live via `refresh_index` (8147, idempotent). P3: `list_apple_reminders` read accessor (safe-by-default) **+ read-only Apple Reminders column on the pulse "Today" dashboard** (live-verified on :8767). P4: schema-drift health (`doctor` + `index_status`), schema fingerprint, FDA/drift runbook. **31 module tests + 60 in the surface sweep pass.** | **Ship / review.** Plan is functionally complete. Deferred by choice: cross-version validation (needs 2nd macOS), snapshot perf wins (active-store-only, mtime-skip), notes/sections full decode. |

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
- [Phase 5 - Optional Write-Back Track](#phase-5---optional-write-back-track)
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
- If write-back is ever pursued, it is a **separate deferred track** with its own spike, safety gates, and runtime surface; it is not a prerequisite for the read-only collector.

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
- [x] Add optional product surfaces where reminders are useful (e.g., daily context, pulse side panel) without conflating with Sleuth. _(Read-only **Apple Reminders** column added to the pulse "Today" dashboard — `scripts/pulse_web.py` `render_hero`, third column beside the two Obsidian columns; soonest-due active items via `list_apple_reminders`. Distinct from Sleuth reminders, which stay in their own surfaces.)_
- [x] Document source semantics and freshness caveats in user/operator docs. _(Read-surface semantics section above + accessor docstring.)_
- [x] Add regression tests for query filters and empty-source behavior. _(10 read-surface tests: defaults, completed/retired, list, has_due, due_before, ordering/NULLs-last, limit, empty-source, bad order_by; 26 total in file.)_

### QA checklist

- [x] Source identity remains explicit (`apple_reminders` vs `sleuth_reminders`). _(Separate table + separate accessor.)_
- [x] Query defaults are safe and predictable (no accidental completed-history flood). _(Default read = 14 active live, not the 8147 total; verified.)_
- [x] No private-framework dependency introduced as a hard requirement for read path. _(Read path is pure `sqlite3`.)_
- [x] UX copy states local-only read behavior clearly. _(Column is read-only — no checkboxes; empty state reads "Apple Reminders, read-only.")_

## Phase 4 - Hardening + Upgrade Safety

Objective: ensure ongoing reliability through macOS updates and schema drift.

### Observable checklist

- [x] Add schema drift guardrails and health warning if required columns/tables cannot be mapped. _(`apple_reminders_health()` → `drift` status names the missing symbols; surfaced via `doctor` (`_check_apple_reminders`) as WARN and via `get_index_status` `sources.apple_reminders.health`. Required-symbol loss still raises `AppleRemindersSchemaError`.)_
- [x] Add a lightweight version/profile fingerprint in logs to aid future breakage triage. _(`compute_schema_fingerprint` = macOS + sqlite versions + reminder table + column count + `columns_sha`; logged each sync, persisted to `apple_reminders_sync_meta`.)_
- [x] Add fallback handling for unreadable store paths at runtime with actionable remediation. _(`AppleRemindersAccessError` carries the FDA remediation; the collector catches `AppleRemindersError` and returns a structured `{error}` result instead of crashing the refresh.)_
- [~] Run cross-version validation on at least two macOS versions or snapshots. _(**Partial — needs a 2nd machine.** Proxy in place: `test_drift_extraction_degrades_and_flags` + `test_fingerprint_captures_schema_and_changes_on_drift` prove graceful degradation and that the fingerprint shifts when the schema changes. True multi-macOS validation is deferred to whenever a second OS version is available.)_
- [x] Add maintenance runbook entry for TCC/FDA troubleshooting. _(See "TCC/FDA + drift runbook" below.)_

### QA checklist

- [x] Upgrade failure path is explicit and non-destructive. _(Drift → fields go null + WARN, never a crash or data loss; required-symbol loss raises a named error before any write.)_
- [x] Drift detection reports exact missing symbols and suggested operator action. _(`drift_fallbacks` lists `missing_*` symbols; `remediation` text included.)_
- [x] Hardening changes do not widen data collection scope. _(Read-only still; only adds a meta table + fingerprint of schema shape — no new reminder fields collected.)_
- [x] Docs remain aligned with actual runtime behavior after final implementation. _(Plan reflects shipped behavior; live-verified via doctor/status.)_

### TCC/FDA + drift runbook

**Symptom: sync returns `{"error": "...Operation not permitted..."}` or `AppleRemindersAccessError`.**
1. The host process lacks Full Disk Access. Grant FDA to the *actual* host app (e.g. Visual Studio Code,
   Terminal, or — for the scheduled job — the launchd-spawned runtime), then **fully quit and relaunch** it
   (a window reload is not enough). See [Verified Discovery → Access](#verified-discovery-phase-0-and-1-findings).
2. Confirm it's TCC and not a command sandbox: retry the read unsandboxed before concluding.

**Symptom: `rebalance doctor` shows `apple reminders: WARN — schema drift … missing: …`.**
1. A macOS update likely reshaped the Core Data schema. The extractor degrades gracefully (affected fields
   go null), so no crash — but mapping needs review.
2. Compare the live store's columns against the [Verified field mapping](#verified-discovery-phase-0-and-1-findings)
   table; the `columns_sha` in `apple_reminders_sync_meta` / sync logs confirms the schema changed.
3. Update `_OPTIONAL_REMINDER_COLUMNS` / table candidates in `apple_reminders.py` as needed; re-sync.

**Symptom: `doctor` shows `apple reminders: OK — not enabled (opt-in)`.** Expected on machines that never
synced — `apple_reminders` is `included_in_all=False`. Enable by running `refresh_index(scope=["apple_reminders"])`.

## Phase 5 - Optional Write-Back Track

Objective: document the narrowest plausible path to Apple Reminders write-back without contaminating the current read-only ingest design.

This phase is **explicitly deferred**. It does not change the current goal, sequence, or safety invariant of Phases 0-4. The intent is to preserve the findings from the adjacent Swift project and avoid re-research if product direction changes later.

### Architecture decision for any future write path

- **Do not** promote direct SQLite mutation to the default write surface.
- Use **EventKit first** for plain reminder CRUD, recurrence, due dates, and list assignment.
- Use **ReminderKit / private framework** only if section CRUD is a hard requirement.
- Use **direct SQLite + token-map updates** only for the narrow gap EventKit/ReminderKit cannot cover reliably: section membership sync.
- Keep the write surface **separate from `refresh_index()`**. Refresh is an ingest/orchestration path; write-back needs its own mutation contract, audit trail, confirmation flow, and failure handling.

### What to borrow from `text-replacement-studio-macos`

Useful patterns to reuse:

- **Dry-run first, explicit apply second** (`plan` vs `--apply`) so the operator sees intended mutations before anything touches Apple-owned storage.
- **Timestamped backups before live writes** so the failure path starts with a restorable checkpoint.
- **Mock-target save harness** for dangerous paths: exercise the real writer against a throwaway Core Data-shaped DB and assert resulting state.
- **Transaction discipline** around explicit write boundaries, preflight validation, and "fail before mutate" behavior.
- **Thin Swift wrapper / bridge** around the writer surface so rebalance can keep the orchestration contract small and typed.

Things **not** to borrow directly:

- The other repo's **table-level row mutation logic** (`Z_PK` / `Z_ENT` / tombstone handling) is specific to Text Replacements and does not model `remindd`, CloudKit token maps, list-level counters, or section membership blobs.
- The other repo's **merge / replace semantics** are a poor fit for reminders, where per-item mutation and sync-side effects matter more than whole-set replacement.
- The other repo's **SQLite-as-primary-writer posture** is too risky here. For Reminders, SQLite should be the last-resort layer, not the first one.

### Phase 5.0 - Technical Spike (write path)

Objective: prove the smallest write path that survives real sync behavior before any product integration.

#### Observable checklist

- [x] Implement a tiny **native helper spike** (Swift preferred) outside the collector path that can:
      request Reminders permission, create one reminder via EventKit, update it, then delete it.
      _Implemented as `scripts/apple_reminders_write_spike.swift` plus app-bundle helper `scripts/apple_reminders_write_spike_app.swift` and plist companions._
- [x] Verify the helper works from the **actual intended runtimes**: interactive shell first, then the agent-hosted process tree, then a launchd-like context if relevant.
      _Verified the opposite is also important: launch mode changes TCC behavior materially. Direct CLI / agent-hosted launches fail; LaunchServices app-bundle launch can prompt + grant._
- [x] Record the **stable identifier mapping** across layers: EventKit reminder id, `ZCKIDENTIFIER`, and any local PKs needed for follow-on section membership work. _(**1:1, no translation needed.** EventKit `calendarItemIdentifier` == `calendarItemExternalIdentifier` == the extractor's `reminder_id` (`ZCKIDENTIFIER`); all three were `2CC71CE6-…` for the same reminder. Local `Z_PK` is only needed for parent-child / section blobs, not for the EventKit CRUD path.)_
- [x] Confirm write-after-read convergence: create/update/delete through EventKit, then re-read through the existing read-only snapshot extractor and verify the normalized row shape reflects the mutation. _(**Proven live 2026-06-27.** Full loop passed: create → extractor-sees-it → update (title+notes+completed) → extractor-converges → delete → extractor-absence, all 8 probes green, ~1.3s end-to-end.)_
- [ ] If section support is required, add a **second micro-spike** limited to section CRUD via ReminderKit or equivalent private API surface. _(Still deferred — only if sections become a hard requirement.)_
- [ ] If section membership is required, prove the exact SQLite sync sequence on a scratch list only:
      membership blob write, checksum write, token-map bump, connection close, wait, sync trigger.
- [x] Capture timings, required permissions, failure modes, and rollback steps in this doc before any Phase 5.1 work starts.

#### QA checklist

- [x] No spike path writes directly to the live SQLite store for ordinary CRUD that EventKit can perform. _(All create/update/delete go through EventKit; SQLite is read-only via the extractor.)_
- [x] Every destructive action has preview/logging and an obvious recovery step. _(Each phase is a logged `probe`; on any failure the spike runs `cleanupLeftover()` to remove the test reminder — verified live on the FDA-missing run, which left no orphan.)_
- [x] The spike is scoped to one disposable test list or clearly tagged test reminders, not the operator's general task corpus. _(Single reminder, unique `RBOS-WRITE-SPIKE-APP-<ts>` prefix, created and deleted within the run.)_
- [~] Live verification includes both **Reminders UI visibility** and **read-side extractor visibility**. _(Read-side extractor visibility proven across create/update/delete. UI visibility not separately asserted — the reminder is created and deleted within ~1.3s, so it is not durably visible in the app by design; deferred as low-value given extractor convergence is proven.)_

#### Phase 5.0 findings (2026-06-26 to 2026-06-27)

- Implemented two repo-local write spikes:
  `scripts/apple_reminders_write_spike.swift` / `scripts/apple_reminders_write_spike_Info.plist`
  for CLI-style launch, and `scripts/apple_reminders_write_spike_app.swift` /
  `scripts/apple_reminders_write_spike_app_Info.plist` for a real AppKit bundle launch.
- First finding: the original app-bundle helper had a lifecycle bug. The bundle launched, but the
  AppKit delegate path never ran, so no permission request occurred. Fix was to bootstrap the app
  explicitly through `NSApplication.shared` rather than relying on the earlier implicit delegate setup.
- Second finding: **launch mode changes TCC behavior**.
  Direct execution from the shell / VS Code / Codex-owned process tree still fails before mutation:
  `requestFullAccessToReminders` returns not granted, status stays `not_determined`, and no operator
  prompt appears.
- The decisive TCC breadcrumb from `log show`:
  `Prompting policy for hardened runtime; service: kTCCServiceCalendar requires entitlement com.apple.security.personal-information.calendars but it is missing for responsible=... com.microsoft.VSCode ...`
  Translation: when the helper is launched under the VS Code-owned responsible process tree, macOS
  suppresses the Reminders/Calendar permission flow before the app can get a user-facing prompt.
- Launching the same helper as a normal app bundle through **LaunchServices** changed the outcome:
  the helper reached the EventKit permission request and TCC logged
  `AUTHREQ_PROMPTING ... service=kTCCServiceReminders`.
- The working app-bundle path also required **broader privacy keys**, not just the modern reminders
  one. The final plist now carries:
  `NSRemindersFullAccessUsageDescription`, `NSRemindersUsageDescription`,
  `NSCalendarsFullAccessUsageDescription`, and `NSCalendarsUsageDescription`.
- After resetting this bundle's TCC entries and relaunching the signed app bundle normally,
  the permission flow succeeded and TCC recorded a durable grant:
  `kTCCServiceReminders|com.rebalanceos.apple-reminders-write-spike-app|2|...`
- With that grant in place, the app-bundle spike progressed past the gate and successfully reached:
  EventKit authorization granted, default Reminders list resolution, and **creation of a disposable
  test reminder**.
- What is still **not** proven end-to-end:
  full create → extractor visibility → update → extractor convergence → delete → extractor absence.
  The successful LaunchServices run used cwd `/`, so the helper's repo-root fallback resolved
  incorrectly and the read-side verification artifact path was wrong. Re-running the app-bundle helper
  directly from the terminal with `RBOS_REPO_ROOT=...` is **not a substitute** because that puts the
  process back under the VS Code/Codex responsible tree and reintroduces the TCC suppression path.
- Durable artifacts:
  `temp/apple-reminders/PHASE5-WRITE-SPIKE.json` for the failing CLI/runtime path and
  `temp/apple-reminders/PHASE5-WRITE-SPIKE-APP.json` plus the status log for the app-bundle path.
- Updated conclusion:
  the current **agent-hosted VS Code process tree is not a viable EventKit write runtime** for Apple
  Reminders, but a **signed, LaunchServices-launched app bundle is viable** for at least permission
  grant and create-path mutation.
- Best next spike, if write-back becomes important:
  keep the app-bundle runtime, fix repo-root discovery independent of terminal env vars, then rerun the
  full create/update/delete + extractor convergence loop there before designing any product-facing write
  surface.

#### Phase 5.0 follow-up — build harness + self-location (2026-06-27)

Picking the spike back up on `feat/apple-reminders-write`:

- **Repo-root discovery fixed (cwd/env-independent).** The app-bundle spike now resolves the repo root
  from a value **baked into `Info.plist` at build time** (key `RBOSRepoRoot`), read via
  `Bundle.main.object(forInfoDictionaryKey:)`. Resolution order in `appRepoRoot()` is now:
  `RBOS_REPO_ROOT` env (shell testing only) → baked `RBOSRepoRoot` → cwd heuristic → walk-up from the
  bundle. Under a LaunchServices launch (cwd=`/`, no inherited env), the baked key is the canonical path —
  this removes the failure that made the earlier successful run write its artifact to the wrong place.
- **Build/sign/launch harness added:** `scripts/build_apple_reminders_write_spike_app.sh`. It compiles the
  Swift (`swiftc -parse-as-library`, required because the file uses `@main`), assembles the `.app` under
  `temp/apple-reminders/build/` (gitignored), injects the absolute repo root into `Info.plist`, ad-hoc
  codesigns with the stable bundle id (keeps the TCC grant durable across rebuilds), and `--launch`
  `open`s it via LaunchServices. **Note:** `swiftc` fails under Claude Code's Bash sandbox (module-cache
  writes to `/var/folders` are blocked) — build with the sandbox disabled.
- **Second TCC gate identified — the app bundle also needs Full Disk Access.** The convergence check
  re-reads the Reminders **SQLite group container** directly (`extract_apple_reminders`), which is FDA
  territory (`kTCCServiceSystemPolicyAllFiles`), *separate* from the EventKit Reminders prompt
  (`kTCCServiceReminders`). The app bundle is a brand-new host identity with neither grant. So the
  operator must grant the bundle **both**: approve the Reminders prompt on launch **and** add the bundle
  under System Settings → Privacy & Security → Full Disk Access. Confirmed empirically: even from the
  FDA-granted VS Code tree, an out-of-tree read of the store returns `AppleRemindersAccessError` until the
  responsible host has FDA. Without #2 the `*_extractor_visibility` probes fail even after a clean
  Reminders grant. The harness prints both requirements on build.
- **Operator-gated step (cannot be automated headless):** the actual convergence run requires a human to
  launch the signed bundle via LaunchServices and click "Allow" on the TCC prompt(s). No CLI agent
  (Claude/Codex/agy) can satisfy this — they all run under the suppressed VS Code/terminal responsible
  tree. Run: `scripts/build_apple_reminders_write_spike_app.sh --launch`, grant both, then inspect
  `temp/apple-reminders/PHASE5-WRITE-SPIKE-APP.json` (live progress in the sibling `.status.txt`).

#### Phase 5.0 CONVERGENCE PROVEN (2026-06-27 14:51Z)

**Phase 5.0 is functionally complete** for the EventKit CRUD path. After granting the app bundle both
EventKit Reminders access (prompt) and Full Disk Access (manual, no prompt — the FDA list never prompts;
this tripped the first run), the app-bundle spike passed the full loop end-to-end:

| Probe | Result |
|---|---|
| `permission` | granted, status `authorized` |
| `create_eventkit` | reminder created in list `Reminders` (`2CC71CE6-…`) |
| `create_extractor_visibility` | extractor saw it |
| `update_eventkit` | title + notes + completion written |
| `update_extractor_visibility` | extractor reflected updated title + completed state |
| `delete_eventkit` | deleted |
| `delete_extractor_visibility` | extractor no longer returns it |

Total wall-clock ~1.3s. **Identifier mapping is 1:1** (EventKit `calendarItemIdentifier` ==
`calendarItemExternalIdentifier` == extractor `reminder_id`/`ZCKIDENTIFIER`).

**Proven runtime contract for any write-back surface:** writes must execute from a **signed,
LaunchServices-launched app bundle** holding **two TCC grants — Reminders (EventKit) AND Full Disk
Access** (the latter only because read-back convergence goes through the SQLite extractor; a pure-EventKit
read-back would not need FDA). No CLI/agent-hosted runtime can satisfy this. EventKit alone covers
create/update/complete/delete + list assignment; SQLite/private frameworks remain unneeded until sections
are required. Artifact: `temp/apple-reminders/PHASE5-WRITE-SPIKE-APP.json`.

### Phase 5.1 - Write Surface Design

Objective: design a safe product-facing mutation path only after the spike proves the underlying primitives.

#### Proposed design (2026-06-27, grounded in the Phase 5.0 runtime contract)

**The binding constraint shapes the whole design.** Phase 5.0 proved that EventKit writes only succeed
from a **signed, LaunchServices-launched app bundle** — never from the rebalance Python process (it lives
under the agent/VS Code responsible tree, where TCC suppresses the grant). So the write surface is **not**
in-process Python calling EventKit. It is a Python **orchestrator that delegates to an out-of-process
signed helper** over a typed request/response contract. The proven spike is already a degenerate,
single-op instance of exactly this shape.

**Topology (two processes, one writer):**

```
rebalance core (Python, agent/CLI-hosted)        signed helper app bundle (the ONLY writer)
  apple_reminders_write.py                          AppleRemindersHelper.app  (LaunchServices-launched)
    1. build request (plan|apply) ─ write ─▶ temp/apple-reminders/write-io/<request_id>.req.json
    2. `open` the helper bundle ───────────▶ helper reads req, dispatches ops via EventKit
    3. wait for response ◀── write ─────────── helper writes <request_id>.resp.json, exits
    4. on apply: re-run sync_apple_reminders() to reconcile local table from Apple (source of truth)
    5. append request+response to write-audit log
```

- **Why `open`, not exec:** invoking the bundle's binary directly would re-parent it under the agent tree
  and re-trigger TCC suppression. Launch must go through LaunchServices (`open`), which makes launchd the
  responsible process and lets the bundle's durable grant apply.
- **File-based IPC** (request/response JSON in `temp/apple-reminders/write-io/`) keeps the contract
  language-agnostic and auditable; `open --args` passes the request path, the baked `RBOSRepoRoot`
  Info.plist key locates the I/O dir.

**Helper TCC footprint — recommend dropping the FDA requirement.** The spike needed *two* grants only
because it confirmed convergence through the SQLite extractor (FDA territory). For the product helper,
**confirm each write via EventKit self-read-back** (`calendarItem(withIdentifier:)`) instead — the helper
already holds the Reminders grant, so it needs **no FDA**. Local-table convergence is a *separate*
concern handled by re-running the existing read collector (`sync_apple_reminders`) on whichever host
already has FDA. Net: the **product write helper needs only the Reminders grant**; FDA stays confined to
the read path where it already lives.

**Identifier contract (no mapping layer):** because EventKit `calendarItemIdentifier` ==
`calendarItemExternalIdentifier` == `ZCKIDENTIFIER` == the local `reminder_id`, Python addresses
reminders by the same `reminder_id` it already stores. For `create` (id doesn't exist yet), the caller
supplies a `client_token`; the helper echoes it back alongside the new `reminder_id`.

**Operations & single writer:** `create`, `update`, `complete`, `delete` (Phase 5.1); `move_to_section`
deferred to a later phase (needs ReminderKit/SQLite, see Phase 5.0 non-goals). The helper is the **one
writer** to Apple Reminders; Python never touches EventKit or the live SQLite. Python's local
`apple_reminders` table is **never written by the write path** — it is reconciled only by
`sync_apple_reminders` after an apply, so the local table can never claim a success the live store
disagrees with (closes the key QA item).

**Request / response contract (schema_version 1):**

```jsonc
// request: <request_id>.req.json
{ "schema_version": 1, "request_id": "<uuid>", "mode": "plan" | "apply",
  "confirm_destructive": false,                 // required true for delete / bulk under apply
  "operations": [
    { "op": "create",   "client_token": "c1", "list_name": "Reminders",
      "title": "...", "notes": "...", "due_at": "<iso8601|null>", "priority": 0 },
    { "op": "update",   "reminder_id": "<uuid>", "fields": { "title": "...", "due_at": "..." } },
    { "op": "complete", "reminder_id": "<uuid>" },
    { "op": "delete",   "reminder_id": "<uuid>" } ] }

// response: <request_id>.resp.json
{ "schema_version": 1, "request_id": "<uuid>", "mode": "...",
  "host_runtime": "com.rebalanceos.apple-reminders-helper", "authorization_status": "authorized",
  "started_at": "...", "finished_at": "...",
  "results": [ { "op": "create", "client_token": "c1", "status": "ok|skipped|error",
                 "reminder_id": "<uuid|null>", "readback_ok": true, "detail": "..." } ] }
```

**Dry-run / apply:** `mode:"plan"` resolves and validates every target (reminder exists, list exists,
fields well-typed) and returns the intended diff **without mutating**. `mode:"apply"` executes. `delete`
and bulk mutations require `mode:"apply"` **and** `confirm_destructive:true`, else they are returned as
`skipped` with a reason.

**Backups / recovery:** EventKit `delete` is not cheaply reversible (re-create yields a *new* id), so
before an apply that contains `delete`/`update`, the helper captures the full current field-set of each
affected reminder into a timestamped restore file (`temp/apple-reminders/write-backups/<request_id>.json`).
Recovery is re-create-from-backup (new id), documented as such — not a true in-place undo.

**Audit log:** every request+response pair is appended to an audit trail
(`apple_reminders_write_audit` table, or `temp/apple-reminders/write-audit/<ts>-<request_id>.json`):
timestamp, op, target ids, mode, confirm flag, per-op outcome, readback result.

**Failure semantics:** auth denial → structured error, zero mutation. Validation failures are caught in
the `plan` phase before any apply. Within an `apply`, EventKit has no cross-item transaction, so ops are
per-item with `continue-on-error`; the response reports each, and Python's post-apply `sync_apple_reminders`
makes the local table match whatever Apple actually committed (partial-failure-safe). Sync lag is
tolerated by polling the reconcile until convergence or a timeout, with the convergence status surfaced.

**Module placement:** new `src/rebalance/ingest/apple_reminders_write.py` (orchestrator), separate from
`index_ops.py` / `refresh_index()` and exposed via its own CLI/MCP verb — never the ingest path. The
helper evolves from `apple_reminders_write_spike_app.swift` into `apple_reminders_helper_app.swift`
(generalize the proven create/update/delete primitives behind the op dispatcher; reuse the same build
harness). One-time operator setup: build + sign the helper, grant it Reminders once.

**Resolved by cross-model consult (2026-06-27, Codex; agy lane unavailable — interactive auth):**
1. **IPC = on-demand `open`** for v1 (B/LaunchAgent only once *measured* cold-launch latency dominates,
   or an action needs burst/background-retry writes).
2. **Audit = dedicated SQLite table** `apple_reminders_write_audit` storing the immutable request/response
   JSON blobs + `request_id` + `reminder_id` + helper identity/version + timestamps + status.
3. **Write scope = restricted to the configured ingest list** in v1 (consult graded this a **Blocker**):
   writing to a list the read path never ingests breaks the post-apply reconcile invariant. Widen only
   when the read model becomes multi-list.

**Hardening folded in from the consult (all v1 requirements):**
- **Idempotency keyed by `request_id`** — a Python-side timeout *after* a successful EventKit create must
  not create a duplicate on retry. The helper records applied `request_id`s and no-ops a replay (the
  `client_token` is for correlation, not retry-safety).
- **Serialize writes** through a single helper-side lock/queue — "one writer" is insufficient if multiple
  Python callers race request order vs. the post-write sync.
- **Verify helper identity on every launch** — Python checks the bundle id + code-signing identity before
  trusting a response (confused-deputy guard).
- **Three explicit states** per mutation: `accepted` → `applied_in_eventkit` → `reconciled_locally`
  (EventKit mutation and local-table reconcile are separate failure domains; the audit row carries all
  three).
- **Atomic file IPC** (write tmp → `fsync` → `rename`) + explicit per-request timeouts; `open` proves the
  helper *launched*, never that the write *succeeded* — only the response file (or EventKit read-back)
  proves that.

#### Observable checklist

- [ ] Define a dedicated write orchestrator (`create_reminder`, `update_reminder`, `complete_reminder`, `delete_reminder`, later `move_to_section`) rather than overloading ingest commands.
- [ ] Define the write contract fields and the single writer for each mutation type.
- [ ] Add structured audit logging for every mutation attempt, including timestamp, operation, target ids, dry-run/apply, and outcome.
- [ ] Add explicit confirmation / dry-run support for destructive mutations and bulk operations.
- [ ] Add integration tests with mock harness coverage for auth denial, validation failure, sync lag, and partial failure.

#### QA checklist

- [ ] The write path stays logically separate from the read-only collector and does not weaken Phases 0-4 safety guarantees.
- [ ] EventKit remains the primary write layer for ordinary reminder CRUD.
- [ ] Private-framework and direct-SQLite code paths are optional, feature-gated, and only used for capabilities unavailable in public APIs.
- [ ] A failed write cannot silently leave rebalance's local table claiming success when the live store disagrees.

## Explicit Non-Goals

- Writing back to Apple Reminders as part of the **current core delivery path**.
- Forcing section/membership edits through direct SQLite writes as the **default** implementation strategy.
- Replacing Sleuth reminders.
- Default semantic indexing of personal reminder history before source quality proves stable.

## Risks and Mitigations

- TCC/FDA access variance by runtime: verify in each execution context and document exact grant target.
- Core Data schema churn: rely on dynamic mapping + drift logs rather than static SQL assumptions.
- WAL consistency edge cases: snapshot strategy includes WAL/SHM and avoids live-store mutation.
- Privacy exposure in logs/fixtures: redact content and avoid committing sensitive rows.
