---
title: Apple Reminders Unified Integration Plan
doc_type: project-plan
status: active
owner: Noel Saw
created: 2026-06-25
updated: 2026-06-26
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
| **Phases 0 + 1 complete (2026-06-25).** FDA granted to VS Code; access gate passed. Active store discovered deterministically (`Data-1FB0F4BF`, 9010 reminders). WAL-safe snapshot pipeline + dynamic REMCD schema mapper shipped in `src/rebalance/ingest/apple_reminders.py` with 9 unit tests (epoch, parent-child linking, graceful degradation). Read-only extraction verified live: 9010 reminders, 0 skipped, 8 lists, ~0.18s. Evidence: `temp/apple-reminders/PHASE0-SPIKE-REPORT.md`. Tags best-effort; notes + sections explicitly deferred. | **Paused before Phase 2 (deliberate).** Resume = collector registration in `index_ops.py` + `apple_reminders` table/upsert. Before that, optionally: eyeball 5 records vs the Reminders UI, and decide whether to invest in full-fidelity notes/section decode. |

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
- **Perf note for Phase 2:** the active store is ~209 MB and is copied in full each run. Fine for a spike;
  consider snapshot reuse / `VACUUM INTO` / incremental strategy if sync frequency rises.

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

### Observable checklist

- [ ] Register `apple_reminders` collector in `src/rebalance/ingest/index_ops.py`.
- [ ] Create/ensure source table schema and upsert path for normalized contract.
- [ ] Wire source into index/status freshness reporting.
- [ ] Add integration tests for first sync, unchanged sync, updated row, completed row, and deleted/hidden handling.
- [ ] Validate `refresh_index` route behavior with scope-specific dry-run and real run.

### QA checklist

- [ ] Collector follows one-writer-per-table discipline.
- [ ] Collector is reachable through orchestrator; no direct leaf-write surfaces for users.
- [ ] Source sync is idempotent across repeated runs.
- [ ] Test suite includes at least one fixture with tags + sections + parent-child reminders.

## Phase 3 - Query Surface + Product Integration

Objective: make reminders queryable/useful without collapsing source boundaries.

### Observable checklist

- [ ] Add read-side accessor (`list_apple_reminders` or equivalent gather hook) with filters for due/completed/list/section.
- [ ] Add optional product surfaces where reminders are useful (e.g., daily context, pulse side panel) without conflating with Sleuth.
- [ ] Document source semantics and freshness caveats in user/operator docs.
- [ ] Add regression tests for query filters and empty-source behavior.

### QA checklist

- [ ] Source identity remains explicit (`apple_reminders` vs `sleuth_reminders`).
- [ ] Query defaults are safe and predictable (no accidental completed-history flood).
- [ ] No private-framework dependency introduced as a hard requirement for read path.
- [ ] UX copy states local-only read behavior clearly.

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

- [ ] Implement a tiny **native helper spike** (Swift preferred) outside the collector path that can:
      request Reminders permission, create one reminder via EventKit, update it, then delete it.
- [ ] Verify the helper works from the **actual intended runtimes**: interactive shell first, then the agent-hosted process tree, then a launchd-like context if relevant.
- [ ] Record the **stable identifier mapping** across layers: EventKit reminder id, `ZCKIDENTIFIER`, and any local PKs needed for follow-on section membership work.
- [ ] Confirm write-after-read convergence: create/update/delete through EventKit, then re-read through the existing read-only snapshot extractor and verify the normalized row shape reflects the mutation.
- [ ] If section support is required, add a **second micro-spike** limited to section CRUD via ReminderKit or equivalent private API surface.
- [ ] If section membership is required, prove the exact SQLite sync sequence on a scratch list only:
      membership blob write, checksum write, token-map bump, connection close, wait, sync trigger.
- [ ] Capture timings, required permissions, failure modes, and rollback steps in this doc before any Phase 5.1 work starts.

#### QA checklist

- [ ] No spike path writes directly to the live SQLite store for ordinary CRUD that EventKit can perform.
- [ ] Every destructive action has preview/logging and an obvious recovery step.
- [ ] The spike is scoped to one disposable test list or clearly tagged test reminders, not the operator's general task corpus.
- [ ] Live verification includes both **Reminders UI visibility** and **read-side extractor visibility**.

### Phase 5.1 - Write Surface Design

Objective: design a safe product-facing mutation path only after the spike proves the underlying primitives.

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
