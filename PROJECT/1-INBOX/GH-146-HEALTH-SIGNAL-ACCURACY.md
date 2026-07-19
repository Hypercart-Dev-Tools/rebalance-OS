---
gh_issue: 146
source: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/146
title: Collector health signal reports a working system as broken
status: "Proposed (1-INBOX — not yet active)"
created: 2026-07-18
doc_type: bugfix
effort: 2
complexity: 2
risk: 2
phases: 3
---

# GH-146 — Collector health signal reports a working system as broken

## Why this exists

Months of "the collectors are unstable" investigation traced to the **health signal**, not the
collectors. On 2026-07-18, seven of eight non-ok checks were the health check misreading a
working system. The one genuinely-real finding (`email data`, 31 days stale) had been buried in
that noise the whole time.

Evidence: `temp/health-reporter.log.jsonl` (6 hourly runs, 2026-07-18) and
`temp/logs/daily_sync_*.log`.

## Root cause A — any transient error fails the whole daily sync

`scripts/daily_sync.sh` ends with:

```bash
sys.exit(1 if result.get("errors") else 0)
```

Any error from any sub-source during a ~49-minute multi-source refresh fails the entire job. The
2026-07-18 run completed all its work and wrote a full log, then exited 1 solely because of:

```json
"errors": [{ "scope": "github", "error": "Rate limited fetching /user" }]
```

A GitHub rate limit — transient, expected, self-healing. It poisons the exit status → launchd
records status 1 → `doctor` WARNs `launchd:daily-sync` hourly → `health_issue_reporter` files and
comments → an operator investigates → nothing is broken → repeat tomorrow.

**7 of the last 10 daily-sync runs ended `finished with errors`.**

## Root cause B — doctor trusts a stale launchctl exit status

`doctor`'s launchd check reports "last run exited with status 1" as *current* health. For a
multi-source job the run's own JSON already states exactly which sources succeeded and which
degraded; the exit code is a lossy summary of it, and `launchctl` retains the last status
indefinitely.

## Root cause C — device-scoped checks warn on the wrong device

`pulse collector:Noel's MBP 16" M1 Pro` (2.0d) and `pulse collector:noel's MacBook Pro 14"`
(7.0h) are **laptops that are not always on**. They warn on the Mac Studio, where nothing is
wrong. Same class: `scheduler:git-pulse-daily-synthesis — scheduled job is not loaded on this
device` (by design).

## Observed warns, 2026-07-18 (6/6 hourly runs unless noted)

| Check | Detail | Class |
|---|---|---|
| `launchd:daily-sync` | last run exited with status 1 | A |
| `launchd:vault-sync` (1/6) | last run exited with status 1 | A (documented 0.24% transient) |
| `pulse collector:MBP 16"` | ALERT — last scan 2.0d ago | C |
| `pulse collector:MacBook Pro 14"` (4/6) | STALE — last scan 7.0h ago | C |
| `scheduler:git-pulse-daily-synthesis` (1/6) | not loaded on this device | C |
| `sleuth` | published export stale — heartbeat 11.0h ago | needs triage |
| `deep work` | quiet 2026-07-19 after 2026-07-18 | needs triage |
| **`email data`** | **107 rows, last sync 31 days ago** | **genuinely real — separate issue** |

## Asks (acceptance criteria)

1. **Exit semantics** — `scripts/daily_sync.sh` distinguishes fatal from partial/transient
   errors. A rate limit or single-source staleness must not fail the run; degradation is
   reported in the JSON where it already lives.
2. **doctor launchd check** — reads the run's JSON result rather than treating a stale
   `launchctl` exit status as current truth.
3. **Device scoping** — checks bound to a specific device do not warn on other devices.

Expected effect: daily warn count from 8 to roughly 1.

## Out of scope

- `email data` 31-day staleness — the one apparently-real collector defect; file separately.
- The collector sentinel loop ([AGY-SENTINEL.md](../2-WORKING/AGY-SENTINEL.md)) — deliberately
  deferred. Against a truthful health signal it has almost nothing to do, which is correct.
  Building it against the current signal would industrialize the noise: its §2 would classify
  `launchd:daily-sync — exited with status 1` as a **Real defect** (non-zero exit, hard-failure
  signature), file, branch, attempt a code fix, fail twice, and escalate — because there is no
  code bug, only a semantics bug about what counts as failure.
