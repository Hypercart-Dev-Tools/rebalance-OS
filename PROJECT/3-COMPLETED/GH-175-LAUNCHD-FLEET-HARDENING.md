---
title: Audit — no launchd job on this Mac declared a memory limit, nice value, or single-instance lock (37 plists)
status: "Done — items 1/3/4/5 shipped via PR #182 (item 1 via #181), item 2 struck as unenforceable, finding 6 fixed as device config. Merged to development 2026-07-20"
gh_issue: 175
created: 2026-07-19
updated: 2026-07-20
branch: development
supersedes: []
synthesizes: []
goal: >
  Device-level audit prompted by the GH-172 kernel panic. Found that the unbounded posture was not
  specific to the embedding stack — 37 LaunchAgent plists on the Mac Studio, and not one declared a
  resource limit, a nice value, or a single-instance lock. Remediation hardens the fleet: the job
  guard wired into the embedding leaves, per-job peak-RSS logging so the next incident is
  attributable, Nice on batch jobs, and a de-collided schedule.
---

# launchd fleet hardening (GH-175)

## Contents
- [Findings](#findings)
- [Corrections made to the audit itself](#corrections-made-to-the-audit-itself)
- [Remediation — implemented](#remediation--implemented)
- [Item 2 — struck](#item-2--struck)
- [Resulting schedule](#resulting-schedule)
- [Verification](#verification)

## Findings

1. **No single-instance guard anywhere** (high) — all 11 rebalance backing scripts checked; zero
   `flock`/lockfile/pidfile hits. launchd will not start a second copy of the *same label*, but
   offers no protection against a manual re-run stacking on a scheduled one (the GH-172 path), nor
   against different labels invoking the same work.
2. **Three jobs embed, none bounded** (high) — `daily-sync` (6:30), `github-sync` (:45),
   `vault-sync` (:15) all reach `refresh_index` → embed. Schedule-staggered, which is likely why
   this had not fired sooner.
3. **Schedule collisions** (low) — four jobs fired at `:00`.
4. **Ten KeepAlive daemons, no ceilings** (medium) — an OOM kill becomes a silent restart loop.
5. **No observability into job memory** (high) — jetsam records only `Python`, which is exactly why
   GH-172 could not be attributed from the panic log alone.
6. **Three jobs failing silently** (medium) — `servers-monitor` exit 127, `ollama` exit 1,
   `postgresql@17` exit 1.

## Corrections made to the audit itself

The first revision of this issue was wrong in three ways, corrected in place with the evidence:

- **Inventory was 16 of 37 plists.** Omitted `homebrew.mxcl.ollama` (a local LLM runtime — the one
  process class that routinely holds multi-GB weights), `mysql`, `postgresql@17`, and six running
  `com.neochro.*` daemons. An audit headlined "nothing declares a memory limit" that omits the LLM
  runtime understates its own case.
- **Finding 4 claimed `pulse-server` was "the only always-on daemon."** It is one of **ten**.
- **Finding 6 did not exist** — it was surfaced only by completing the inventory.

## Remediation — implemented

**Item 1 — wire the job guard (PR #181).** The only item that actually closes GH-172. Applied at
the library leaves rather than the launchd wrappers, because the causing run was agent-spawned.
See [GH-172-EMBEDDING-JOB-GUARD.md](GH-172-EMBEDDING-JOB-GUARD.md).

**Item 4 — per-job peak RSS logging (PR #182).** `MemoryCeiling` already tracked `peak_rss` and
printed it on exit, but nothing persisted it. `record_peak_rss()` now appends a JSONL row to
`temp/logs/job_rss.jsonl` on **every** exit path — clean, raised, or ceiling-tripped — from both
in-process `guard()` and wrapper `run_guarded()`:

```json
{"ts": "...", "job": "rebalance-embed", "pid": 57379, "peak_rss_bytes": 0,
 "peak_rss_gb": 0.0, "total_memory_gb": 64.0, "max_rss_gb": 22.4,
 "tripped_reason": null, "exit_code": 0, "duration_s": 0.0}
```

The next incident reads `rebalance-embed peaked at 45.8 GB` instead of anonymous `Python`. Writing
is best-effort by construction — every exception swallowed, because observability must never take
down the thing it observes.

**Item 3 — `Nice` on batch jobs (PR #182).** `Nice=5` added to `daily-sync`, `github-sync`,
`vault-sync`, `pulse-sync`, `pulse-web-sync`. Not to `pulse-server` (a serving daemon). Each
template carries a comment stating this is responsiveness hygiene and **not** a GH-172 mitigation,
so the rationale cannot drift back.

**Item 5 — de-collide the schedule (PR #182).** `pulse-web-sync` colliding with `pulse-sync` at
`:00` was not merely CPU contention — it is a derived read-only stage over what `pulse-sync`
writes, so firing in the same minute risked reading half-written state. That makes this a
correctness fix, not only hygiene.

**Finding 6** was fixed as device configuration by a parallel session (stale plist path, duplicate
ollama service, stale `postmaster.pid` whose PID had been recycled to nginx). No repo diff.

## Item 2 — struck

"Add `HardResourceLimits` to each plist as an OS-level backstop" **does not work on macOS**.
`HardResourceLimits` → `ResidentSetSize` maps to `RLIMIT_RSS`, which Darwin defines but does not
enforce:

```
$ ulimit -m
unlimited
$ ulimit -m 102400
bash: ulimit: max memory size: cannot modify limit: Invalid argument
```

Under a nominal 100 MB cap a process allocated 300 MB unimpeded (peak RSS 307 MB). `RLIMIT_AS` is
an alias for `RLIMIT_RSS` on Darwin and equally unenforced. Adding these would produce jobs that
look bounded under config review and are not — worse than omitting them, because it retires the
concern without fixing it. Memory enforcement on this platform must be in userspace, which is what
`MemoryCeiling` does.

## Resulting schedule

No two jobs share a slot (verified programmatically across all 12 templates):

| Minute | Job |
|---|---|
| :00 | `pulse-sync` (hourly anchor — the derived stages moved off it, not this one) |
| :07 / :22 / :37 / :52 | `pulse-warning-watch` (same 15-min cadence, off the quarter hours) |
| :08 / :38 | `pulse-web-sync` |
| :10 | `health-check` |
| :15 | `vault-sync` |
| :25 | `health-check-triage` (8, 14, 20) |
| 6:30 | `daily-sync` |
| :45 | `github-sync` |
| 0:40 | `obsidian-rollover` |
| 18:05 | `git-pulse-daily-synthesis` |
| 18:20 | `obsidian-daily-sync` |

Note this is *same-minute* de-confliction. It does not address run-window overlap — `daily-sync`
runs ~25-30 min from 06:30 and still spans `github-sync` at :45. That overlap was fixed separately
by GH-131's bounded SQLite retry and is deliberately unchanged here.

## Verification

- All 12 plist templates pass `plutil -lint` after rendering.
- Programmatic collision check across every `(hour, minute)` slot: none.
- Wrapper-mode smoke test writes a real record end-to-end.
- 16 guard tests pass; full suite shows zero regressions against the `origin/development` baseline.
