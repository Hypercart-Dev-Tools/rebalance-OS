---
title: "GH-146 P2 — doctor launchd check reads the run JSON, not a stale launchctl status"
status: "Brief authored; phase not yet run"
created: 2026-07-18
updated: 2026-07-18
owner: noel
gh_issue: 146
roadmap_exempt: true
goal: >
  Marathon phase brief (harness input, not a tracked effort). Make doctor's launchd check read
  the run's structured result instead of a launchctl exit status that persists indefinitely.
---

# GH-146 P2 — `doctor` launchd check reads the run JSON, not a stale `launchctl` status

## Status

| What was just completed | What's next |
|---|---|
| Brief authored 2026-07-18; parent capture is `PROJECT/1-INBOX/GH-146-HEALTH-SIGNAL-ACCURACY.md` | Execute as marathon phase `gh146-p2-launchd-json` (reviewer: agy) after P1. Blocks P3. |

## The defect

`doctor`'s launchd check reports `last run exited with status 1` as **current** health. Two
problems:

1. `launchctl` retains the last exit status indefinitely. A job that failed once and has
   succeeded every run since still reports the old status until the next run overwrites it. The
   check therefore reports history as if it were present state.
2. For a multi-source job the exit code is a lossy summary. The run's own JSON result already
   states exactly which sources succeeded and which degraded — strictly more information than
   the single byte the check currently keys on.

Observed 2026-07-18: `launchd:daily-sync — last run exited with status 1` on **6/6** hourly runs,
while `temp/logs/daily_sync_2026-07-18.log` shows the run completed all its work.

## Depends on P1

P1 makes the exit code *mean* something (fatal only) and adds a distinct log marker for
degraded-but-successful runs. Build on that contract — do not re-derive it, and do not change
what P1 established.

## What to build

For jobs that emit a structured run result, the launchd check should prefer that result over the
`launchctl` status:

- Read the run's JSON / log marker to determine what actually happened.
- Report **degraded** distinctly from **failed**. A run that succeeded with a rate-limited source
  is not the same as a run that did not happen, and the operator needs to see the difference at a
  glance.
- Treat a `launchctl` status with no corroborating recent run as **stale, not authoritative** —
  say so in the detail string rather than asserting current failure.
- Jobs with no structured result keep today's behavior. Do not regress them.

`_check_collector_freshness()` is shared across all eight collectors — changing its contract
changes every source's reported status. Extend; do not rewrite.

## Acceptance criteria

- `launchd:daily-sync` no longer WARNs when the most recent run succeeded or was degraded-only.
- A genuinely failed or never-run job still WARNs.
- A stale `launchctl` status with no recent run is reported as stale, not as a current failure.
- No other collector's reported status changes.

## Tests (required)

Add `tests/test_doctor_launchd.py`. `tests/` is explicitly in your artifact allowlist.

Cover at minimum:
- recent successful run + `launchctl` status 1 → **no** warn (the regression this phase exists for)
- recent degraded run → degraded, not failed
- recent genuinely-failed run → warn
- no recent run at all → stale/unknown, not a false "failed"
- a job with no structured result → unchanged behavior

The test must fail before your change and pass after. State which assertion demonstrates that.

## Verification

Run `.venv/bin/python -m rebalance doctor` and report the warn count before and after. The
expected direction is down; if it is not, say so rather than adjusting the test.

## Out of scope

- `scripts/daily_sync.sh` (P1 owns it — do not edit)
- Device scoping (P3 — it edits this same file *after* you; keep your diff tight)
- The `email data` 31-day staleness
