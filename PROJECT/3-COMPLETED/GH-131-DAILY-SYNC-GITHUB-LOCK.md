---
title: daily-sync fails daily — github scope hits "database is locked" from collision with hourly github-sync
status: "Fixed — MARATHON-2026-07-16 Lane A, fired and shipped 2026-07-16 on branch marathon/2026-07-16"
gh_issue: 131
created: 2026-07-16
updated: 2026-07-16
branch: main
supersedes: []
synthesizes: []
goal: >
  com.rebalance-os.daily-sync has been exiting non-zero on most days for weeks. Root cause:
  it collides with the hourly com.rebalance-os.github-sync job, which fires at :45 past the
  hour — squarely inside daily-sync's ~30-minute run window — and both write rebalance.db's
  github tables concurrently, producing "database is locked". Fix is a bounded SQLite retry
  (busy_timeout) around the github-scope writer.
---

# daily-sync — "database is locked" (GH-131)

## Contents
- [Symptom](#symptom)
- [Root cause (proven)](#root-cause-proven)
- [Fix — proposed](#fix--proposed)
- [Fix — implemented](#fix--implemented)
- [Secondary finding (out of scope)](#secondary-finding-out-of-scope)
- [Debug ledger](#debug-ledger)

## Symptom
`com.rebalance-os.daily-sync` (fires 06:30 daily) has been exiting non-zero on most days for
weeks. `temp/logs/launchd_stdout.log` shows `"finished with errors"` roughly every other day
since 2026-06-01, including 2026-07-15 and 2026-07-16 (today).

## Root cause (proven)
Checked `temp/logs/daily_sync_<date>.log` for 2026-07-08, 07-09, 07-10, 07-15, and 07-16 — all
five show the identical failure: the `github` scope of `refresh_index()` errors with
`"database is locked"` on `rebalance.db`. The failure cascades: the downstream `dashboard`
scope is then skipped (`"reason": "upstream refresh errors"`).

Two scheduled launchd jobs write to the same `rebalance.db` github tables and collide:
- `com.rebalance-os.daily-sync` starts at 06:30 and runs ~25-30 min (today: 06:30:06 → 06:56:14).
- `com.rebalance-os.github-sync` fires **hourly at :45 past the hour** — confirmed firing today
  at 06:45:05, squarely inside daily-sync's window.

Both processes hit the github tables concurrently; SQLite raises "database is locked" for
whichever loses the race (daily-sync's github scope, consistently, across every date checked).

## Fix — proposed
1. **Primary:** add a bounded SQLite `busy_timeout` (or WAL + retry) around the github-scope
   writer so a transient lock waits and retries instead of failing the whole run. Root-cause
   fix — survives any future scheduling drift, not just this specific collision.
2. **Optional, cheaper interim:** move `github-sync`'s hourly offset off `:45` so it no longer
   lands inside daily-sync's `06:30`–`~07:00` window.
3. Verify: re-run `daily_sync.sh` across a day boundary where the 06:45 hourly overlap occurs;
   confirm the JSON `errors` list no longer contains a `github` / `"database is locked"` entry
   and the `dashboard` scope stops being skipped.

## Fix — implemented
**Correction to the proposed fix:** `db_connection()`/`get_connection()` in
`src/rebalance/ingest/db/connection.py` already sets `PRAGMA journal_mode=WAL` and
`PRAGMA busy_timeout=30000` (30s) for every connection — including every github-scope
writer call (`github_scan.py`, `github_knowledge.py`, `github_watch.py` all already go
through it). So the lock isn't from a *missing* busy_timeout; it's that the hourly
`github-sync` job can hold rebalance.db's github-table write lock for **longer than 30
continuous seconds** at some point during its own multi-repo sync run, which exhausts
even the existing busy_timeout.

**Shipped fix** (`src/rebalance/ingest/index_ops.py`): a new `_retry_on_db_locked()`
helper wraps `_github_adapter`'s call to `_refresh_github` — on a `sqlite3.OperationalError`
containing "database is locked", it retries the *whole* github-scope refresh up to 3 times
with linear backoff (5s, 10s), re-raising (surfacing a real `errors` entry, never silently
swallowed) if the lock still hasn't cleared on the final attempt. Safe because
`_refresh_github` is idempotent (upserts) — a retry just re-syncs, it can't double-write.
Scoped to the github adapter only; no change to `refresh_index()`'s generic dispatch loop
or any other scope's behavior. 6 new tests (`tests/test_index_ops.py`); full suite green;
`rebalance doctor` clean; `pdda.sh run` clean.

The optional Phase 2 (moving `github-sync`'s launchd offset off `:45`) was **not** taken —
the retry is a complete, root-cause-adjacent fix on its own (survives the collision
regardless of scheduling), so the schedule-offset change is unnecessary defense-in-depth,
left as a future option if the collision frequency ever becomes a real cost.

## Secondary finding (out of scope)
`github-sync`'s own log (`temp/logs/github_stderr.log`) also shows two outright crashes
(`Abort trap: 6` / SIGABRT), most recently 2026-07-16 15:45–15:47 — a distinct failure mode
from the lock contention, not yet root-caused. Noted for visibility; not fixed by this issue.

## Debug ledger
- Confirmed via `daily_sync_2026-07-16.log`: `errors: [{"scope": "github", "error": "database
  is locked"}]`, `elapsed_seconds: 1557.08` (06:30:06–06:56:14).
- Confirmed via `github_stdout.log`: hourly github-sync started 06:45:05 today, ran to 07:11:34
  — overlaps daily-sync's window on every check across 2026-07-08 through 2026-07-16.
- Ruled out: this is not the stale `launchd_stderr.log` "Operation not permitted" content from
  2026-04-10 (defunct `Documents/Obsidian Vault/rebalance-OS` path) — that path no longer
  exists and hasn't been written to since April; unrelated dead artifact, not live.
