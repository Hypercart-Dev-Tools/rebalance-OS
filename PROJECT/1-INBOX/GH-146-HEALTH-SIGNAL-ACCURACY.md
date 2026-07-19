---
gh_issue: 146
source: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/146
title: Collector health signal reports a working system as broken
status: "Built — all 4 phases approved and merged on work/sentinel-process-review. Measured 6 warns → 5 against a target of 0; 3 known gaps remain (pulse-server -15 unfixed, daily-sync WARN-vs-INFO unresolved, device ids hardcoded). P1's effect is not observable until the next 06:30 sync."
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

## Root cause D — the deep-work stall check uses UTC "today"

`src/rebalance/doctor.py:1015` computes "today" as `datetime.now(timezone.utc).date()` and passes
it into `compute_deep_work_signals()`. The operator runs in Pacific time, so after 17:00 PDT the
UTC date is already the next day and every project is trivially "quiet" on a day that just began.

Live at 18:59 local on 2026-07-18: **five projects** all reported `quiet 2026-07-19 after
2026-07-18`. All false. This fires every evening and is the noisiest line in `doctor` output.

Same bug class as GH-129 (day-boundary tz pin, shipped 2026-07-14) — fixed there, missed here.
The fix is at the call site; `compute_deep_work_signals(db, today, ...)` correctly takes an
injected date, and `src/rebalance/tz_utils.py` already exposes `local_tz()`.

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

## Re-baselined 2026-07-18 19:00, after PR #147 merged

PR #147 (`marathon/2026-07-18-collectors`) reworked the health checks — 193 lines added to
`doctor.py` — while this capture was being written. It did **not** fix any root cause here, but it
changed the warn composition, so the original 8-warn table above is superseded:

| Change | Warn |
|---|---|
| **Gone** | `email data` (31d stale), `launchd:vault-sync` |
| **New** | `launchd:pulse-server` status **-15** (SIGTERM from a deliberate restart, reported as failure — root cause B, live), `signal health — figma: 38d` |
| **Unchanged** | `deep work`, `launchd:daily-sync`, `pulse collector:MBP 16"`, `scheduler:git-pulse-daily-synthesis` |

**Working baseline for this marathon: 5 warns** — `deep work`, `pulse collector:MBP 16"`,
`scheduler:git-pulse-daily-synthesis`, `launchd:daily-sync`, `launchd:pulse-server`.

`email data` dropping off is convenient but **unexplained**. Whether #147 fixed the Gmail
collector or merely stopped reporting it is unverified; do not assume that real defect resolved
itself.

## Outcome — measured 2026-07-18 19:47 PDT

Same host, same config, same moment; only the code differs. **6 warns → 5** (target was 0).

| Warn | Before | After | Verdict |
|---|---|---|---|
| `deep work` | `rebalance-OS: quiet 2026-07-19 after 2026-07-18` — 5 projects, UTC date | `Binoid: quiet 2026-07-18 after 2026-07-17` — 1 project, local date | ✅ P4. Surviving warn is legitimate |
| `scheduler:git-pulse-daily-synthesis` | present | gone | ✅ P3 |
| `pulse collector:` ×2 laptops | present | gone | ✅ P3 |
| `launchd:daily-sync` | `last run exited with status 1` | `launchctl status 1 is stale/unknown` | ⚠️ Honest now, but still WARNs |
| `launchd:pulse-server` | `exited with status -15` | unchanged | ❌ Not fixed |
| `sleuth`, `signal health figma` | present | present | — out of scope |

**Why P2 missed.** Its brief named `pulse-server -15` in prose but not as an acceptance
criterion. codex wrote 6 legitimate tests with verified fail-before/pass-after — **none covering
the -15 case** — and agy approved. The lesson generalizes past §4a of `AGY-SENTINEL.md`: a gate
over existing tests can't prove a new test exists, *and a new test existing can't prove it tests
what you asked for*. Acceptance criteria must name the **observable that must change**, not the
artifact that must appear. P3 and P4 stated theirs that way and both delivered.

**Verification performed by hand** (not taken on agy's word): every phase's new tests were run
against the immediately-prior commit's source. P1 4/4 fail, P2 6/6 fail, P3 4/4 fail, P4 2/4 fail
(the two tz-specific ones; the other two are guards that correctly pass either way).

## Follow-up work

1. `pulse-server -15` (SIGTERM) — the original named target, still open
2. Whether a stale/unknown launchd state should WARN at all, or report as OK/info
3. `_DEVICE_SCOPE_REGISTRY` hardcodes device ids in source; it will drift

## Asks (acceptance criteria)

1. **Exit semantics** — `scripts/daily_sync.sh` distinguishes fatal from partial/transient
   errors. A rate limit or single-source staleness must not fail the run; degradation is
   reported in the JSON where it already lives.
2. **doctor launchd check** — reads the run's JSON result rather than treating a stale
   `launchctl` exit status as current truth. Also covers `pulse-server` status -15 (SIGTERM).
3. **Device scoping** — checks bound to a specific device do not warn on other devices.
4. **Local day boundary** — the deep-work stall check pins "today" to the operator's local day
   via `tz_utils.local_tz()`, not UTC.

Expected effect: **5 warns → 0**.

## Out of scope

- `email data` 31-day staleness — the one apparently-real collector defect; file separately.
- `signal health — figma: 38d` — new from #147, not yet triaged.
- `src/rebalance/doctor.py:405` — a second `datetime.now(timezone.utc).date()` in a different
  check. P4 reports it; fixing it is deliberately deferred so the regression stays attributable.
- The collector sentinel loop ([AGY-SENTINEL.md](../2-WORKING/AGY-SENTINEL.md)) — deliberately
  deferred. Against a truthful health signal it has almost nothing to do, which is correct.
  Building it against the current signal would industrialize the noise: its §2 would classify
  `launchd:daily-sync — exited with status 1` as a **Real defect** (non-zero exit, hard-failure
  signature), file, branch, attempt a code fix, fail twice, and escalate — because there is no
  code bug, only a semantics bug about what counts as failure.
