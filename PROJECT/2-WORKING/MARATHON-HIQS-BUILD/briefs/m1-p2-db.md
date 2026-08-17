---
title: "M1 p2 — db.py: connection factory and the full 8-table schema"
status: "Brief authored; phase not yet run"
created: 2026-08-03
updated: 2026-08-03
owner: noel
gh_issue: TBA
roadmap_exempt: true
doc_type: project
goal: >
  Marathon phase brief (harness input, not a tracked effort). Builds one module of the HiQS
  v1.0 core against the contract in PROJECT/2-WORKING/HIQS-PROJECT.md, which stays canonical.
---
# M1 p2 — db.py: connection factory and the full schema

## Status

| What was just completed | What's next |
|---|---|
| Brief authored 2026-08-03 and preflighted — `marathon.sh --dry-run` resolves this phase in execution order. **Not yet run.** | Runs after `hiqs-m1-p1` is approved; needs its frozen dataclasses. |

**Canonical spec:** `HIQS-PROJECT.md` §9 (all 8 tables, verbatim SQL for `docs_vec`), §5 rule 2
(reconciliation), §19.2 (nothing private in the tree).

## Build

`HiQS/hiqs/db.py` — one thin `db_connection()` factory (§4 calls this the persistence base:
**zero logic**), plus `CREATE TABLE IF NOT EXISTS` for all 8 tables.

Connection: WAL, foreign keys ON, `busy_timeout=30000` (§9; L18 — this is half the fix for the
lock cascade, the other half is timeouts in the plugins).

**Every tenet-bearing column lands now, not later** (§9, Phase 0 gate). Decision 7 ships no
migration machinery, so a column added after M3 costs a re-ingest:
- `docs`: `source, id, title, body, url, ts, project, author` + the FTS5 index
- `docs_vec`: composite PK `(doc_id, model)`, with `dim` — copy the SQL in §9 exactly
- `github_items`: `author, assignee, updated_at, **activity_at**` (both timestamps — §9 explains why)
- `calendar_events`: `organizer, attendees_json`

## Acceptance

- Schema creation is idempotent — run it twice on one DB, no error, no duplicate index.
- A test inserts a 384-dim and a 1024-dim vector for the **same** `doc_id` under different `model`
  values and both persist. This is the property the Phase 1 head-to-head depends on.
- Pragmas are asserted by reading them back from a live connection, not by grepping the source.
- Timestamps stored UTC ISO-8601.

## Do not

- Do not put query logic, upsert policy, or business rules in `db.py`. It is the fan-in base;
  everything else reads it. A god-object here is what §4 exists to prevent.
- Do not resolve the DB path to anything under the repo, or to any absolute home directory (L11).
  Use the canonical app-data path (§13) via a helper that reads the platform at runtime.
- Do not write migrations or a version table.
