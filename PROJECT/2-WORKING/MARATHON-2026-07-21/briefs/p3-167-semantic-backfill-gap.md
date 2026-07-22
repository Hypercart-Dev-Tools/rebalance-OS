---
title: "MARATHON-2026-07-21 P3 — GH-167 semantic-index backfill gap"
status: "Brief authored; phase not yet run"
created: 2026-07-21
updated: 2026-07-21
owner: noel
gh_issue: 167
roadmap_exempt: true
---

# Phase 3 — characterize and close the 302-document semantic-index gap

Part of **GH-167**. Issue: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/167
Disjoint from every other phase in this marathon. **Artifact:** `src/rebalance/ingest/semantic_index.py`
(`backfill_semantic_documents()`, line 484 at time of writing), `src/rebalance/ingest/index_ops.py`
(`github_documents_missing_from_semantic` drift computation, line 633).

## The problem

302 of 9084 `github_documents` rows are stored but were never projected into the semantic index
(8782 embedded). Every document that *is* in the index is fully embedded — this is not an
embedding backlog, it's a backfill step silently dropping ~3.3% of the corpus. A silently absent
document is worse than a slow one: `semantic_query` returns confident-looking results with no
signal that part of the corpus was never eligible to match.

## ⛔ Hard invariants

- **Characterize before fixing.** Do not guess at the shared cause and patch blind. Query the 302
  directly (join `github_documents` against whatever `backfill_semantic_documents()` uses to
  decide inclusion) and confirm what they have in common — likely candidates per the issue: a
  `doc_kind` the backfill doesn't handle, empty/oversized bodies, a repo later ignored, or rows
  failing a NOT NULL/dedup constraint. State the actual finding in the relay, not a guess.
- **First confirm the gap is stable, not growing.** Re-run `refresh_index(scope=["github"])` (or
  the equivalent backfill entry point) and re-check `github_documents_missing_from_semantic`. If
  it moved, that changes the fix (an ongoing skip vs. a one-time historical gap).
- **No re-architecture.** Do not change what GitHub artifacts are fetched or how ingestion works —
  this is a backfill/projection fix only.
- **Make the backfill loud about skips going forward**, even after the historical 302 are closed —
  a skip count + reason surfaced somewhere (log line or `index_status`), not a silent drop, so
  this class of gap doesn't quietly recur.

## Task

1. Add a read path (a query, or a small `peek_source`-style helper) that lists which documents are
   missing from the semantic index, so the 302 can be characterized rather than guessed at.
2. Run it, characterize the shared cause with concrete evidence.
3. Make `backfill_semantic_documents()` (or wherever the skip actually happens) report skips with
   reasons instead of silently dropping rows.
4. Fix the underlying skip once characterized, and backfill the 302 that are legitimately
   fixable. If any residual is an intentional exclusion (e.g. a doc_kind that genuinely shouldn't
   be searchable), document that explicitly rather than forcing it in.

## Acceptance

- [ ] The 302 are characterized by a concrete, evidenced shared cause — not assumed.
- [ ] The backfill reports skips with reasons (log or `index_status` field), not silent drops.
- [ ] `github_documents_missing_from_semantic` reaches 0, or any residual is explained by a
      documented, intentional exclusion.
- [ ] `pytest tests/ -k "semantic_index or index_ops"` green.
- [ ] `rebalance doctor` clean.

## Out of scope

Re-architecting GitHub ingestion or changing what artifacts are fetched (per the issue's own
stated boundary).
