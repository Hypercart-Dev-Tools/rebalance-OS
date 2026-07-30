---
gh_issue: 171
source: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/171
title: "github_sync.sh holds the single SQLite write lock across its network I/O, blocking all other writers"
status: "Triage 2026-07-25 (/10days sweep). Re-verified against a pre-existing, un-fired brief in PROJECT/2-WORKING/MARATHON-2026-07-21/briefs/p2-171-sqlite-write-lock.md (authored 2026-07-21, still current)."
doc_type: pdda-spec
priority: P1
effort: 1
complexity: 2
risk: 2
ratings_provisional: true
created: 2026-07-25
updated: 2026-07-25
---

# GH-171 — github_sync holds the SQLite write lock across network I/O

Contract auto-drafted by /10days, informed by the pre-existing MARATHON-2026-07-21
brief (`briefs/p2-171-sqlite-write-lock.md`) — artifacts/lanes not yet
operator-verified against the latest code state.

## Problem

`sync_github_repo()` (`src/rebalance/ingest/github_knowledge.py`) opens a SQLite
write transaction (WAL mode, single-writer) and then performs fetch-and-persist
*inside* it, so the transaction spans network latency (an ~49-minute run per GH-146)
rather than just the writes. `busy_timeout=30000` doesn't help — the holder isn't
blocked on disk, it's blocked on an SSL read from the GitHub API. Any other writer
(manual `rebalance refresh`, MCP tool writes, pulse collectors) gets a bare
`database is locked` for the run's full duration. **Note: overlaps GH-186 in
`scripts/github_sync.sh` — do not run in the same wave as GH-186.**

## ⛔ Hard invariants (carried from the prior brief)

- **Fetch-then-write, not fetch-inside-write.** Network calls happen outside any
  open write transaction; open a short write transaction only to persist
  already-fetched data.
- **Batch-commit long persist loops** — GH-169's backfill already established this
  pattern (commit every ~100 rows) elsewhere in the ingest layer; follow it.
- **Do not change what data is collected or how it's fetched** — transaction-
  boundary fix only, not a re-architecture of the sync itself.
- **Do not touch `_get_login()`'s 403 handling or the retry/backoff logic** in the
  shared HTTP client.

## Acceptance

- [ ] A long `github_sync` run no longer blocks unrelated writers for its full
      duration — verify with a concurrent-write test.
- [ ] No write transaction spans a network call in the touched code paths.
- [ ] `pytest -k "github_scan or github_client or github_knowledge"` green.
- [ ] `rebalance doctor` clean.

## Swarm Preflight Contract

```json
{
  "target":      { "repo": ".", "ref": "development" },
  "gate":        ".venv/bin/python -m pytest tests/ -k \"github_scan or github_client or github_knowledge\" -q",
  "fix_probes": [
    { "type": "grep_present", "path": "src/rebalance/ingest/github_knowledge.py", "pattern": "with db_connection" }
  ],
  "artifacts":   [ "src/rebalance/ingest/github_knowledge.py", "scripts/github_sync.sh" ],
  "artifacts_new": [],
  "remediation": { "source": "issue#171", "criteria": "sync_github_repo() no longer holds the write transaction open across network fetches" },
  "lanes":       { "agy_safe": [], "orchestrator_only": [] }
}
```
