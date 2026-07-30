---
title: "MARATHON-2026-07-21 P2 — GH-171 SQLite write-lock-across-network-I/O fix"
status: "Brief authored; phase not yet run"
created: 2026-07-21
updated: 2026-07-21
owner: noel
gh_issue: 171
roadmap_exempt: true
goal: >
  Marathon phase brief (harness input, not a tracked effort). Stop `sync_github_repo()` from
  holding the SQLite write lock across network I/O, so a slow GitHub call can no longer
  block every other writer for the duration of the request.
---

# Phase 2 — stop github_sync from holding the SQLite write lock across network I/O

Part of **GH-171**. Issue: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/171
Disjoint from every other phase in this marathon. **Artifact:** `src/rebalance/ingest/github_knowledge.py`
(`sync_github_repo()`, line 351 at time of writing; `db_connection` context manager usage at
lines 273/400/894/955), `scripts/github_sync.sh` if it wraps transaction boundaries directly.

## Status

| What was just completed | What's next |
|---|---|
| Brief authored 2026-07-21 for parent GH-171; marathon plan is `PROJECT/2-WORKING/MARATHON-2026-07-21/MARATHON.md` | **Not fired.** Execute as marathon phase `p2-171-sqlite-write-lock`; disjoint write-set, so it may run in any wave. |

## The problem (measured live, 2026-07-19)

`sync_github_repo()` opens a SQLite write transaction (WAL mode, single-writer) and then performs
fetch-and-persist *inside* it, so the transaction spans network latency (an ~49-minute run per
GH-146) rather than just the writes. `busy_timeout=30000` doesn't help because the holder isn't
blocked on disk — it's blocked on an SSL read from the GitHub API. Any other writer (manual
`rebalance refresh`, MCP tool writes, pulse collectors, the GH-169 backfill) gets a bare
`database is locked` for the run's full duration, with no indication a scheduled job is the cause.

## ⛔ Hard invariants

- **Fetch-then-write, not fetch-inside-write.** Restructure so network calls happen outside any
  open write transaction; open a short write transaction only to persist already-fetched data.
- **Batch-commit long persist loops** — GH-169's backfill already established this pattern
  (commit every ~100 rows) elsewhere in the ingest layer; follow it, don't invent a new one.
- **Do not change what data is collected or how it's fetched** — this is a transaction-boundary
  fix, not a re-architecture of the sync itself.
- **Do not touch `_get_login()`'s 403 handling or the retry/backoff logic** in the shared HTTP
  client — unrelated, and explicitly called out as load-bearing by the adjacent #144 work.
- A concurrent writer should either proceed (if the fix works) or fail with a message identifying
  the holder — not a bare `database is locked`.

## Task

1. Confirm the exact transaction boundary in `sync_github_repo()` and any other `db_connection(...)`
   block in `github_knowledge.py` that wraps a network fetch — the four `with db_connection(...)`
   sites listed above are the starting point, not an assumed-complete list.
2. Restructure each offending block: fetch all needed data into memory first, then open the write
   transaction only around the persist step.
3. Where a persist loop is long, batch-commit rather than holding one transaction for the whole
   loop (mirror GH-169's backfill approach).
4. Set a non-zero default `busy_timeout` on the shared connection helper if one isn't already
   applied everywhere, as a mitigation for any remaining contention window — not a substitute for
   the transaction-boundary fix.
5. Optional, if time permits within this phase's turn budget: surface "a sync is holding the
   write lock" as a `doctor` check. If it doesn't fit, leave it as a noted follow-up rather than
   rushing it.

## Acceptance

- [ ] A long `github_sync` run no longer blocks unrelated writers for its full duration — verify
      with a concurrent-write test (open a second connection during a simulated slow fetch,
      assert it isn't blocked past a short, bounded window).
- [ ] No write transaction spans a network call in the touched code paths.
- [ ] `pytest tests/ -k "github_scan or github_client or github_knowledge"` green.
- [ ] `rebalance doctor` clean.
