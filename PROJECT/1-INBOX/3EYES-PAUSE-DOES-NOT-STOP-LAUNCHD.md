---
title: "three_eyes pause does not prevent launchd from firing the job"
status: "Captured 2026-08-14; GitHub issue NOT yet filed (api.github.com unreachable)"
created: 2026-08-14
updated: 2026-08-14
owner: noel
gh_issue: TBA
roadmap_exempt: false
doc_type: project
goal: >
  Repair the pause mechanism the whole fleet's maintenance windows depend on. Pause currently
  reports success while the job continues to fire on schedule.
---

# `three_eyes pause` does not prevent launchd from firing the job

> **File this as a GitHub issue when connectivity returns.** It was captured here because
> `gh` could not reach api.github.com on 2026-08-14 ("Timeout trying to log in to github.com
> account noelsaw1 (keyring)").

## What

`three_eyes pause <id>` returns success and records paused state, but the launchd job still fires
on schedule and runs to completion.

## Evidence — live, 2026-08-14, during the GH-250 reclaim window

Ten managed jobs were paused at **21:08**, all reporting success:

```
paused github-sync
paused pulse-sync
paused daily-sync
paused collector-health
paused vault-sync
paused pulse-web-sync
paused obsidian-daily-sync
paused obsidian-rollover
paused selfcheck
paused skill-sync
```

At roughly **21:45**, `com.rebalance-os.pulse-web-sync` fired anyway, attached to `rebalance.db`,
and broke the reclaim's post-batch WAL checkpoint at batch 94 of 268:

```
ERROR: WAL checkpoint not clean after batch 94: (1, 10086, 10086)
```

Confirmed via `lsof` on the database: PID 70813, a child of `scripts/pulse_web_sync.sh`. The same
then happened with `github-sync` (PID 24867) on the retry, also while "paused".

Only `launchctl bootout` actually quiesced the fleet. Once every job was booted out, the reclaim
ran to completion without interruption.

## Why it matters

Pause is the mechanism a maintenance window depends on. A pause that returns success while the job
keeps running is worse than no pause, because the operator believes the fleet is quiet. Here it
cost one aborted run of a destructive 2.68M-row delete against a 14.6 GB production database —
safe only because the operation's own checkpoint gate caught the intruder.

The blast radius is wider than GH-250: any pause used for triage or quarantine may be doing
nothing at all.

## Second, related defect

`utils/gh250/fence-writers.sh` `cmd_verify` asserts that a paused job's `three_eyes why` output
contains **`OPEN/quarantined`**. A paused job actually prints:

```
  breaker:  closed (consecutive failures: 0, last: None)
  reason:   paused via CLI
```

so verify reports every correctly-paused job as NOT paused, and the fence can never be satisfied.
Note `reason: paused via CLI` **persists after resume**, so it is not a reliable pause indicator
either — there may currently be no trustworthy way to read pause state at all. That is the thing
to settle first, because the fence fix depends on it.

## Direction for a fix

1. Establish whether pause is *intended* to unload the job or to make the shim exit early. If the
   latter, `shims/run-job.sh` must consult pause state before doing work — check whether it does.
2. Give pause state one authoritative, machine-readable accessor (`three_eyes is-paused <id>`
   exiting 0/1) instead of grepping human-readable `why` prose.
3. Repoint `fence-writers.sh` at that accessor.
4. Add a test that asserts a paused job does not execute, not merely that pause returned 0 — the
   existing tests cover the call, not the effect, which is why this survived to production.

Found while executing GH-250 R4 (see `PROJECT/2-WORKING/GH-250-VECTOR-BLOAT/RECLAIM-RUNBOOK.md`
status block, which records all four broken safety mechanisms from that window).
