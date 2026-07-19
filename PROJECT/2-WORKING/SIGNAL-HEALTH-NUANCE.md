---
title: Signal-health nuance — stop the collector panel from over-stating urgency
status: In progress
created: 2026-07-18
updated: 2026-07-18
owner: noel
goal: >
  Make the "collector attention needed" panel tell the truth: fix the stale data source that
  reports live collectors as days-stale (#152), stop doctor flagging a running/just-restarted
  daemon as broken (#146), and segment the flat warning list into notices / warnings / errors so
  the header count reflects real urgency (#153).
related:
  - https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/152
  - https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/146
  - https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/153
---

# Signal-health nuance

> Companion marathon plan: [MARATHON-2026-07-18-SIGNAL-HEALTH/MARATHON.yaml](MARATHON-2026-07-18-SIGNAL-HEALTH/MARATHON.yaml)

## Status

| What was just completed | What's next |
|---|---|
| Diagnosed the 2026-07-18 "14 warnings" panel end-to-end. Root causes isolated and dated, three GH issues cut (#152 new, #146 augmented with the `-15`/live-PID case, #153 new). Marathon plan + three phase briefs authored on branch `marathon/2026-07-18-signal-health`. | Run preflight (`marathon.sh --dry-run` + baseline gate green), then fire the marathon: p1 #152 → p2 #146 → p3 #153 (p3 depends on p2). |

## Table of contents

- [Background — what the 14 warnings actually were](#background--what-the-14-warnings-actually-were)
- [Phase 1 — #152 export clone stopped pulling](#phase-1--152-export-clone-stopped-pulling)
- [Phase 2 — #146 doctor flags a running daemon as broken](#phase-2--146-doctor-flags-a-running-daemon-as-broken)
- [Phase 3 — #153 segment notices / warnings / errors](#phase-3--153-segment-notices--warnings--errors)
- [Deliberately not in this plan](#deliberately-not-in-this-plan)

## Background — what the 14 warnings actually were

The 2026-07-18 "Collector attention needed — 14 warnings" panel flattens three very different
severities into one count. Triaged against the live system:

- **2 self-inflicted** — `launchd:pulse-server` / `launchd:daily-sync` exited `-15` (SIGTERM) from a
  deliberate `kickstart -k` restart; the daemon was up and serving (PID present, HTTP 200) the whole
  time. → #146.
- **5 informational** — `scheduler:<job> not loaded on this device`: true by design on a box that
  isn't the designated runner. → #153 (should be *notices*).
- **3 correlated + real** — pulse collectors "8.5d stale" and the Sleuth heartbeat "July 10" all trace
  to one cause: the local export clone stopped pulling from origin on 2026-07-10, so every freshness
  signal that reads from it is frozen while the collectors themselves are ALIVE (verified by
  `experimental/git-pulse/health-check.py`: last scan 1.0h / 1.7h / 2.5h ago). → #152.
- **4 low-urgency/standing** — email 36d, github-token keyring-only (no launchd fallback), sleuth data
  3d (downstream of #152), MacBook Pro 14" 36.5d.

The through-line: correct-ish signals with no severity ranking, plus one genuinely stale data source,
plus one signal that misreads deliberate restarts as failures.

## Phase 1 — #152 export clone stopped pulling

**Artifact:** `scripts/pulse_sync.sh` · **Reviewer:** agy · disjoint write-set.

`~/git-pulse-sync` diverged from origin on **2026-07-10 06:50:45** — **86 commits ahead, 1016
behind**. `pulse_sync.sh` only writes → commits → optionally pushes the local pulse file; it has **no
`git pull`/`fetch`/`merge` step**, so nothing on this device reconciles the mirror. Every dashboard
freshness read (collector last-scan, Sleuth heartbeat) is frozen at July 10.

Direction: add a fetch + reconcile step for the auto-generated pulse commits (rebase/merge, or a
dedicated pull job) so the mirror tracks origin, without clobbering the 86 unpushed local commits.

### QA gate — Phase 1

- [ ] A pull/reconcile step exists and is exercised by a test (fetch + integrate origin; local
      pulse-write commits preserved; no clobber).
- [ ] Failure to pull surfaces as a real error/log line, never a silent "fresh" (see
      `no-silent-happy-errors`).
- [ ] Idempotent + safe when already up to date.
- [ ] Anti-goal: does **not** touch `doctor.py` / signal logic (that is p2/p3).

## Phase 2 — #146 doctor flags a running daemon as broken

**Artifact:** `src/rebalance/doctor.py` (`_check_launchd`, ~line 556) · **Reviewer:** agy.

`_check_launchd` WARNs on any launchctl exit status ∉ {`0`,`-`} and never consults the live PID
column. So a `KeepAlive` daemon that was just restarted (PID running, last exit `-15` = SIGTERM) is
reported "last run exited with status -15" while it is healthy and serving. Same class as #146 Root
cause B (doctor trusts a stale launchctl exit status).

Direction: `OK` when the job has a live PID, or the last exit is `0`/`-`/negative (signal); `WARN`
only on a positive non-zero exit **and** no live PID. Defer to a multi-source job's own JSON result
where available (Root cause A).

### QA gate — Phase 2

- [ ] A running daemon with last-exit `-15` reads `OK`, not `WARN` (regression test).
- [ ] A genuinely crashed job (positive non-zero exit, no live PID) still `WARN`s.
- [ ] SIGTERM / negative statuses are treated as non-failures.
- [ ] Anti-goal: no severity-bucket taxonomy yet (that is p3); this phase only corrects the predicate.

## Phase 3 — #153 segment notices / warnings / errors

**Artifact:** `src/rebalance/doctor.py` (the `Check` dataclass + per-check classification) plus
renderer wiring in `src/rebalance/health.py` · **Reviewer:** agy · **depends_on p2** (shares
`doctor.py`).

Add an explicit `severity ∈ {notice, warning, error}` to `Check`, classify each check, and have the
panel group + count by bucket (notices muted/collapsed by default). Device-scoping ("not loaded on
this device") and just-restarted daemons become **notices**; real freshness/auth breaches
**warnings**; a stopped sync (#152) an **error**.

### QA gate — Phase 3

- [ ] `Check` carries `severity`; every emitter sets it (default `warning`).
- [ ] Panel groups + counts per bucket; notices muted/collapsed by default.
- [ ] The 2026-07-18 14-item set re-buckets to roughly `errors ≤ 3 · warnings · notices`, with the
      restart + device-scoping items demoted to notices (fixture/regression test).
- [ ] Anti-goal: does not re-open the predicate correctness fixed in p2, and does not restyle the web
      dashboard beyond the bucket grouping.

## Deliberately not in this plan

- **#146 Root cause A** (`daily_sync.sh` exits 1 on any transient sub-source error) — real, but a
  distinct artifact (`scripts/daily_sync.sh`) and a separate behavioural call on transient-error
  handling. Sequence as a follow-up phase once `doctor.py` is stable.
- The **86-ahead / 1016-behind reconciliation** of the live `~/git-pulse-sync` clone is an operator
  action, not a code change — do it once by hand alongside p1 landing.
- **email 36d / github-token fallback** — standing config items, one command each; not marathon work.
