---
title: Apple Reminders Unified Integration Plan
doc_type: project-plan
status: active
owner: Noel Saw
created: 2026-06-25
updated: 2026-06-25
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
| Consolidated the three Apple Reminders reference documents into one execution-ready plan with a single architecture path and explicit phase gates. | Phase 0: rerun the local access spike in an FDA-granted runtime, then capture schema + field-mapping evidence needed for collector implementation. |

## Table of Contents

- [Scope](#scope)
- [Source Synthesis](#source-synthesis)
- [Target Architecture](#target-architecture)
- [Data Contract (Normalized)](#data-contract-normalized)
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

## Phase 0 - Access + Schema Spike

Objective: prove access and field recoverability in the real runtime context before collector work.

### Observable checklist

- [ ] Confirm runtime can read the Reminders store directory with Full Disk Access applied to the actual host app/runtime.
- [ ] Discover active `Data-*.sqlite` file(s) deterministically across known roots.
- [ ] Produce a safe snapshot (`.sqlite`, `-wal`, `-shm`) in `temp/apple-reminders/` without modifying live store.
- [ ] Dump schema metadata (`sqlite_master`, candidate `ZREMCD*` tables) to `temp/apple-reminders/schema.txt`.
- [ ] Extract 20+ reminders into normalized contract.
- [ ] Manually verify at least 5 records against Reminders UI: plain, notes, tagged, sectioned, parent-child.
- [ ] Record timing baseline for discovery, snapshot, extract, and total wall-clock.

### QA checklist

- [ ] No write operations executed against live Reminders store.
- [ ] Spike output includes machine/runtime context and exact timestamp.
- [ ] Failure modes (permission denied, missing WAL files, schema mismatch) are explicitly logged.
- [ ] Evidence files are redacted for sensitive personal content before committing.

## Phase 1 - Read-only Extractor + Snapshot Pipeline

Objective: ship a deterministic local extractor that remains robust across schema drift.

### Observable checklist

- [ ] Implement extractor module under `src/rebalance/ingest/` with clear entrypoint and no live-store writes.
- [ ] Add path resolver that tries known roots plus controlled glob fallback.
- [ ] Add snapshot helper that copies `.sqlite`, `-wal`, and `-shm` atomically into temp working folder.
- [ ] Implement dynamic schema mapper (no hardcoded `Z_ENT` assumptions).
- [ ] Emit normalized reminders rows with explicit field-level null/default behavior.
- [ ] Add structured logs for rows extracted, rows skipped, and mapping fallbacks used.

### QA checklist

- [ ] Extraction succeeds on snapshot-only input (no dependency on live handle).
- [ ] Mapper degrades gracefully when optional columns are absent.
- [ ] Unit tests cover UUID conversion, Core Data epoch conversion, and parent-child linking.
- [ ] Sensitive fields are masked in logs and fixtures.

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
