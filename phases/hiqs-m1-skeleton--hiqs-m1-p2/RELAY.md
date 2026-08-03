# Marathon Phase hiqs-m1-p2
STATUS: Approved
NEXT: codex

<!-- marathon-drive: task=MARATHON-HIQS-M1-P2-TURN builder=codex reviewer=agy round-cap=7 -->

## Phase Brief

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


---

▶ TAKE YOUR TURN (codex — BUILDER role)

You are the BUILDER for this phase. Read the phase brief above and implement it.
1. Implement the brief by creating/editing the artifact file(s): HiQS/hiqs/db.py,HiQS/tests/test_db.py
2. Append a build block to this relay file: `### Round N · Builder · codex` summarizing what you did (files touched, key decisions).
3. Use this exact tick binary (run it from any directory): /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick claim MARATHON-HIQS-M1-P2-TURN --agent codex --paths "phases/hiqs-m1-skeleton--hiqs-m1-p2/RELAY.md,HiQS/hiqs/db.py,HiQS/tests/test_db.py"
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick ping MARATHON-HIQS-M1-P2-TURN --agent codex
   - /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick release MARATHON-HIQS-M1-P2-TURN --agent codex --to agy
4. Edit ONLY these paths: phases/hiqs-m1-skeleton--hiqs-m1-p2/RELAY.md and HiQS/hiqs/db.py,HiQS/tests/test_db.py. Do NOT run git. Do NOT touch any other file — the harness commits for you.
5. HAND OFF EXPLICITLY (GH-268): after releasing the token, end your turn by naming who acts next —
   "handing off to agy — agy, take your turn." A turn that ends without that line
   leaves a human guessing whether the relay is waiting on them or has stalled. Do this EVERY round,
   not just the first.

---

▶ TAKE YOUR TURN (agy — REVIEWER role)

You are the REVIEWER for this phase. Read the latest builder block above AND review the artifact file(s) on disk: HiQS/hiqs/db.py,HiQS/tests/test_db.py. REVIEW THE WHOLE FILE, NOT JUST THE DIFF (GH-268): a beta test had this loop reach 'Approved' in two rounds while an independent audit of the same branch found 20 issues (1 critical, 4 high) — every one of them in the pre-existing code the change sat on, which nobody had read. Pre-existing defects in a file you are touching are IN SCOPE; say so explicitly if you find none. DECLARE IT: your review block MUST contain a literal 'swept file: yes' or 'swept file: no' line — without it a reviewer that skipped the sweep is indistinguishable in the transcript from one that did it and found nothing, which is exactly how those 20 issues stayed invisible.
1. Append a review block: `### Round N · Reviewer · agy` followed by your assessment.
2. If changes needed: add `**Verdict:** Changes requested` then: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick release MARATHON-HIQS-M1-P2-TURN --agent agy --to codex
3. If satisfied: add `**Verdict:** Approved`, set `STATUS: Approved`, then: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick done MARATHON-HIQS-M1-P2-TURN --agent agy
4. Use this exact tick binary (run it from any directory) for all token operations: /Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/.xyz/bin/tick
   Edit ONLY phases/hiqs-m1-skeleton--hiqs-m1-p2/RELAY.md (your review block + STATUS). Do NOT edit the artifact yourself — request changes instead. Do NOT run git.
5. HAND OFF EXPLICITLY (GH-268): end your turn by naming who acts next — "handing off to codex —
   codex, take your turn" when requesting changes, or "relay closed, no further turn needed" when
   approving. The beta report singled this out: the Reviewer turn did not tell the user to go back to the
   Producer, so the relay looked stalled when it was simply waiting. Do this EVERY round.

### Round 1 · Builder · codex

Implemented `HiQS/hiqs/db.py` as the persistence base: a runtime platform-derived app-data path,
SQLite WAL/foreign-key/30-second busy-timeout setup, and idempotent creation of the eight canonical
tables plus an external-content FTS5 index for `docs`. `docs_vec` uses the required `(doc_id, model)`
composite primary key and records dimensions. Added `HiQS/tests/test_db.py` with live pragma/schema,
idempotence/FTS, and coexistence tests for 384- and 1024-dimensional vectors for one document.

### Round 1 · Reviewer · agy

swept file: yes

Reviewed `HiQS/hiqs/db.py` and `HiQS/tests/test_db.py` in full.
- `db.py` implements `default_db_path()` targeting standard OS application data paths without hardcoding repo or absolute home dirs.
- Pragmas (`journal_mode=WAL`, `foreign_keys=ON`, `busy_timeout=30000`) are configured on every connection and validated live via SQLite queries in `test_db.py`.
- Schema defines all 8 required tables (`vault_files`, `github_activity`, `github_items`, `calendar_events`, `docs`, `docs_vec`, `projects`, `events`) and `docs_fts` virtual table with triggers.
- Column invariants verified (`github_items` carries both `updated_at` and `activity_at`, `calendar_events` has `organizer` and `attendees_json`, `docs` has `author`, `docs_vec` has composite PK `(doc_id, model)` and `dim`).
- Zero query/business logic in `db.py`, no migration table.
- Idempotency and multi-model vector coexistence (384-dim and 1024-dim) are fully covered by passing tests in `test_db.py`.

**Verdict:** Approved

relay closed, no further turn needed

