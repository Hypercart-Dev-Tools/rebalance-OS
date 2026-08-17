---
title: "Radar report — rebalance-OS, 2026-07-18..2026-08-07"
status: "FINAL (evidence snapshot; immutable — a later run writes a new dated doc)"
created: 2026-08-07
updated: 2026-08-07
owner: Noel (operator)
goal: "Report the Run/Grow/Transform flow distribution, the recurring-defect targets worth one durable fix, and where RELEASES.md has drifted from what the repo is actually doing."
doc_type: report
---

# Radar report — rebalance-OS

**Window:** 2026-07-18 .. 2026-08-07 (21 days) · **Trunk:** `development`
**Prior window:** 2026-06-27 .. 2026-07-18 (21 days)
**Run:** 1 · **Generated:** 2026-08-07

Analysis was read-only. This doc and the `radar`-labelled tracking issue are the only writes.

---

## Lens 1 — Flow distribution

| Read | Run | Grow | Transform | Unclassified | Harness (excluded) | Denominator |
|---|---|---|---|---|---|---|
| **Window, mechanical** | 148 (77%) | 30 (16%) | 0 (0%) | 14 (7%) | 356 | 192 |
| **Window, adjusted** | 158 (82%) | 34 (18%) | 0 (0%) | 0 (0%) | 356 | 192 |
| **Prior, mechanical** | 112 (63%) | 39 (22%) | 0 (0%) | 26 (15%) | 118 | 177 |
| **Prior, adjusted** | 125 (73%) | 46 (27%) | 0 (0%) | 0 (0%) | 124 | 171 |

Totals: 548 commits in window, 295 in prior window (`git rev-list --no-merges --count`).

**Verdict: running harder, moving less.** Commit volume rose 295 → 548 (1.9×) while the Grow
share fell 27% → 18% — a third of the new-capability share gone. Harness commits went from 40%
to 65% of everything (118 → 356, 3×). The machinery is running more than the work is.

### Transform is 0% because it is unmeasurable, not because it is absent

`grep -rh '^rgt:' PROJECT/` returns **zero matches**. No governing doc in this repo can currently
declare Transform, so the lane is structurally blind. Prefix inference is forbidden from promoting
`refactor:`/`perf:` into it, and correctly so — but that leaves the number uninformative rather
than reassuring. Adding `rgt:` to the governing docs of the largest efforts is the cheapest way to
make this lane mean something on the next run.

### Unclassified subjects, window (14, verbatim)

```
 1 Fix three blockers to running the test suite and a marathon gate (GH-225, GH-228, GH-229) (#230)
 2 verdict(GH-219): #215 CONFIRMED on live hardware — GO on Lanes 2-7
 3 Remove Anthropic API key dependency in favor of Gemini
 4 Create GH-NEXT-SIMPLIFY-REPO-INTAKE.md
 5 Focus 5 Float: 3-Eyes job-health tile on /focus-5.json (GH-195)
 6 3-Eyes: adopt skill-sync + machine-local registry overlay (GH-195)
 7 Update GH-144-SENTINEL-PROMPT.md
 8 revert(GH-187): drop TopEdgeResizeHandle, park investigation and pause
 9 fix(GH-169) Phase 4 hardening: five defects found only by running it live
10 feat(GH-169) Phase 3: make commit-corpus completeness continuously derivable
11 fix(GH-169) Phase 2: stop the collector evicting events that never failed
12 feat(GH-169) Phase 1: local-git commit backfill, independent of the Events API
13 review(signal-health): strip trailing whitespace in doctor.py; refresh plan status
14 test+review(signal-health): regression tests for #152/#146/#153 + p1 hardening
```

**Why the adjustment matters.** Items 9–12 are `fix(GH-169) Phase 2` and `feat(GH-169) Phase 1`
— **the colon after the scope is missing**, so conventional-commit inference dropped four
correctly-typed commits on the floor. Items 5 and 6 use the *component* as the type
(`3-Eyes:`, `Focus 5 Float:`) and are plainly Grow. Adjusted assignment: 10 → Run, 4 → Grow.

Two mechanical findings worth fixing at the source:

- A malformed-prefix family (`type(scope) subject`, no colon) is in active use on GH-169.
- Component-as-type (`3-Eyes:`, `Focus 5 Float:`, `duel(...)`) is common enough that inference
  will keep undercounting Grow until either the convention or the parser changes.

---

## Lens 2 — Recurring-defect radar

### Signal yields (measured this run, not assumed)

| # | Signal | Yield | Contributed |
|---|---|---|---|
| 1 | `related:` frontmatter | 35 docs carry it, 20 refs extracted, 14 distinct targets | **0 clusters** |
| 2 | Shared seam (`fix:` by file) | 73 fix commits → 7 recurring seams, 13 concentrated | Anchored targets 1–2 |
| 3 | Issue-text similarity (160 issues) | 3 coherent defect classes | **Carried the run** |
| 4 | Doc-only / false closes | **0 found** | Nothing |
| 5 | `reported_from:` cross-repo | **0 docs — structurally unavailable** | Nothing |

Signal 1's extraction succeeded (20 refs from 35 docs is a real, non-zero yield — not the
parser-silence failure mode). It produced no clusters for a different reason: its most-cited
target, **#102 with 5 citations**, is integration *context* — sibling docs referencing the
XYZ/Rebalance integration as background, not defect kinship. Citation count conflated context
with kinship here, exactly as expected.

### Recurring seams (signal 2, after the recurrence discriminator)

A seam counts as recurring only with fixes spanning **≥2 distinct days AND ≥2 distinct
issues**. Seven passed:

| File | Commits | Days | Issues | Span |
|---|---|---|---|---|
| `src/rebalance/ingest/index_ops.py` | 3 | 3 | #131, #166, #167 | 07-24..07-27 |
| `src/rebalance/doctor.py` | 3 | 3 | #160, #169, #189 | 07-19..07-25 |
| `utils/3-eyes/shims/run-job.sh` | 3 | 2 | #195, +1 | 07-22..07-27 |
| `utils/job_guard.py` | 3 | 2 | #172, #219 | 07-19..07-27 |
| `src/rebalance/web.py` | 3 | 3 | #154, #195 | 07-18..07-22 |
| `src/rebalance/ingest/github_direct_commits.py` | 2 | 2 | #169, #248 | 07-19..08-04 |
| `scripts/pulse_web.py` | 2 | 2 | #154, #189 | 07-18..07-24 |

**Excluded as concentrated authoring, not recurrence:** GH-257 (the uninstaller) produced
**16 fix commits, all on 2026-08-04, all from issue #257**, each touching
`scripts/uninstall_rebalance.sh`, `tests/test_uninstall_rebalance.py`, and
`relay-system/2026-08-04/`. Ranked by raw commit count this is the repo's hottest seam by a wide
margin; by the discriminator it is one feature being hardened in one sitting. It is not a target.

---

### Target 1 — `RADAR-class-no-enforced-ceiling`

**6 issues over 12 days · 4 open · UNCLAIMED by any release band · still firing**

| Issue | State | Defect |
|---|---|---|
| #172 | closed | Hard kernel panic from unbounded concurrent embedding runs (90 GB resident on a 68.7 GB machine) |
| #210 | open | `job_guard` memory ceiling uses RSS, blind to compressed/swapped memory |
| #213 | open | Plan: memory-pressure defence — fix `job_guard` first, don't build a monitoring system |
| #222 | open | `vault-sync` aborts with `database is locked`: unbounded single-transaction writes |
| #231 | open | `test_job_guard_wiring`: fixture never pins the compressor ceiling, so 3 tests fail on state |
| #236 | open | `list_health_issues` pages until an empty response with no ceiling |

**Seam anchor:** [utils/job_guard.py](../../utils/job_guard.py) — recurring (3 commits, 2 days,
issues #172 and #219). **Governing doc:** only #213 has one
([PROJECT/1-INBOX/GH-213-MEMORY-PRESSURE-DEFENCE.md](GH-213-MEMORY-PRESSURE-DEFENCE.md)); #210,
#222, #231, #236 have none.

**The class:** work with no bound, or a bound that measures the wrong quantity. Unbounded
concurrency (#172), unbounded transaction size (#222), unbounded pagination (#236), a ceiling
reading RSS when the pressure is in the compressor (#210), and a test fixture that never pins that
ceiling so the check itself is non-deterministic (#231).

**Why it recurs:** each instance was fixed as a local bug. The ceiling was never made a shared,
enforced concept, so the next unbounded operation reintroduces it in a new place.

**Live evidence — this is not historical.** `refusing to start: memory compressor holds 21.1 GB,
ceiling is 16.0 GB` appears in **5 of the last 9 `temp/logs/daily_sync_*.log`** (07-31, 08-01,
08-02, 08-04, 08-06). Seven of the eight untracked `3EYES-*` captures in `PROJECT/1-INBOX/` record
`sync_outcome=degraded` or no outcome at all, across 2026-07-31..2026-08-06.

**What one durable fix retires:** #210 and #231 directly, unblocks #213, and stops the daily
collector degradation that is currently manufacturing a capture doc most mornings.

---

### Target 2 — `RADAR-class-guard-cannot-report-red`

**6 issues over 17 days · 3 open · partially claimed by 0.70.0**

| Issue | State | Defect |
|---|---|---|
| #160 | closed | `doctor`: a crash-looping KeepAlive daemon reports OK — live PID short-circuits the exit-status check |
| #177 | closed | CI never runs on `development` — the branch everything merges into was unguarded |
| #178 | open | `development` is red: 10 failing tests plus 6 state-sensitive |
| #225 | open | `development` is red: MCP integration broken on any fresh install |
| #228 | closed | pytest on macOS stalls in a Keychain authorization prompt loop |
| #255 | open | `test_hiqs_pipeline`: 5 tests pass or fail depending on the working directory |

**Seam anchor:** [src/rebalance/doctor.py](../../src/rebalance/doctor.py) — recurring (3 commits,
3 days, issues #160, #169, #189).

**The class:** a check that completes without being able to signal failure. A guard that
short-circuits on the wrong evidence (#160), a guard that never ran (#177), a suite whose result
depends on where it was invoked (#255) or on unpinned fixture state (#231, shared with target 1),
and a red trunk tolerated long enough to accumulate a second independent cause (#178 then #225).

**The collector has the same defect.** `3EYES-2026-08-04-collector-run-wrote-no-outcome.md`
records `"state": "no-outcome", "detail": "run finished but wrote no sync_outcome"` — a run that
finished with no way to say whether it worked.

**Claim status:** `0.70.0 Green Board` names #178, #255, and the utils/3-eyes CI failures.
**#225 — the second, independent red-build cause — is named by no band.**

---

### Target 3 — `RADAR-class-store-divergence`

**10 issues over 18 days · 6 open · CLAIMED by 0.69.0 Reclaim — context, not a finding**

#139, #166, #167, #169, #185, #246, #248, #250, #251, #252 — ingest succeeds while the store
disagrees with it: 302 documents fetched but never projected (#167), 2.65 M orphaned vectors at
12.1 GB / 92% of `rebalance.db` (#248), 19.4% of `development` history invisible to HiQS (#169),
a 90-minute writer lag with stuck pending-embed chunks (#166).

Seams: [src/rebalance/ingest/index_ops.py](../../src/rebalance/ingest/index_ops.py) and
[src/rebalance/ingest/github_direct_commits.py](../../src/rebalance/ingest/github_direct_commits.py),
both recurring.

Recorded for completeness and for the next run's aging clock. `0.69.0` claims this work explicitly
and the 2026-08-04 fix burst landed exactly on it — the plan and the repo agree here.

**Note the causal link to target 1:** the bloat this class describes is a plausible source of the
memory pressure that trips target 1's ceiling. Executing the 0.69.0 reclaim may reduce target 1's
symptom without fixing target 1's defect.

---

## Lens 3 — Release recalibration

`RELEASES.md` carries **two real unshipped blocks** (both substantive, neither a seed):

| Release | Codename | Target | Status |
|---|---|---|---|
| 0.69.0 | Reclaim | 2026-08-15 | Draft |
| 0.70.0 | Green Board | 2026-09-15 | Draft |

**The planned → issue join is impossible.** Both blocks have an empty `Milestone:` field, and
`gh api repos/Hypercart-Dev-Tools/rebalance-OS/milestones` returns **zero milestones**. All 79
open issues are milestone-orphaned, but with no milestones to belong to, that number measures the
missing binding — not backlog drift. Claim status below was therefore read from the block
`Description:` text, not joined.

- **0.69.0 ↔ reality: aligned.** The description names GH-250 end-to-end, and the 2026-08-04 fix
  burst landed on exactly that seam (#248/#250).
- **0.70.0 ↔ reality: partial.** Claims #178, #255, and the utils/3-eyes CI failures. Misses
  **#225**, the second independent red-build cause, opened 9 days after #178.
- **UNCLAIMED: target 1.** The only class producing live daily failures is described by neither
  band, while 0.69.0 ships in 8 days.
- **Also undescribed:** GH-257, the uninstaller, absorbed 16 fix commits in a single day and
  belongs to neither band. Real effort going where the plan does not look.

Advisory only. The plan says reclaim-then-green-the-board; the repo is also spending its mornings
on a memory ceiling nobody has scheduled.

---

## Degradation — what was unavailable and what it cost

| Condition | Effect | Handling |
|---|---|---|
| **RTK proxy truncates `git log` to 50 lines** | Would have bucketed 50 of 548 commits and reported a confidently wrong distribution — both windows returned exactly `50` | Bypassed with `rtk proxy git log`; verified against `git rev-list --count` (548 / 295) |
| `gh` reports "token is invalid" when sandboxed | Lens 2 signals 3–5 and all of Lens 3 would have been lost | All issue/milestone data fetched unsandboxed; token is valid |
| No `rgt:` keys in `PROJECT/**` | Transform lane structurally unmeasurable | Reported as 0% with the caveat stated, not as an absence of transform work |
| Zero milestones | Lens 3 planned→issue joins unavailable | Claim status read from `Description:` prose instead |
| Zero doc-only closures found | Signal 4 flat | 81 closed issues exist, so the signal was available and genuinely returned nothing |
| Zero `reported_from:` docs | Signal 5 structurally unavailable | Stated, not reported as a clean sweep |

---

## Checklist at generation time

Historical snapshot. The live copy is the `radar`-labelled tracking issue.

### RADAR-class-no-enforced-ceiling — 6 issues over 12 days · first-seen: 2026-08-07 · runs: 1

- [ ] Make the memory ceiling in `utils/job_guard.py` measure compressor-held memory, not RSS — #210
- [ ] Pin the compressor ceiling in the `test_job_guard_wiring` fixture so the 3 state-sensitive tests are deterministic — #231
- [ ] Bound the `vault-sync` write transaction so it cannot hold the SQLite lock unboundedly — #222
- [ ] Add a page ceiling to `list_health_issues` so a constant-return mock cannot loop forever — #236
- [ ] Acceptance: 7 consecutive `daily_sync` logs with zero `refusing to start` refusals and no `3EYES-*-degraded` capture

### RADAR-class-guard-cannot-report-red — 6 issues over 17 days · first-seen: 2026-08-07 · runs: 1

- [ ] Make the collector always write a `sync_outcome`, including on abnormal exit — `3EYES-2026-08-04-collector-run-wrote-no-outcome.md`
- [ ] Resolve #225 (MCP broken on fresh install) or add it to the 0.70.0 band — it is currently claimed by neither
- [ ] Make `test_hiqs_pipeline` independent of the pytest invocation directory — #255
- [ ] Acceptance: a deliberately broken daemon, a deliberately failing test, and a killed collector each produce a red signal in `doctor`, CI, and the sync outcome respectively

### RADAR-class-store-divergence — 10 issues over 18 days · first-seen: 2026-08-07 · runs: 1

- [ ] Tracked by release 0.69.0 Reclaim — no separate radar action; re-check the aging clock next run

### Measurement hygiene surfaced by this run

- [ ] Fix the malformed `fix(GH-169) Phase 2` prefix family (missing colon) so inference stops dropping typed commits
- [ ] Add `rgt:` to the governing docs of the largest efforts so the Transform lane stops reading a blind 0%
- [ ] Bind `Milestone:` in both `RELEASES.md` blocks, or create the milestones, so Lens 3 can join next run

---

## The ask

**0.69.0 ships in 8 days. `RADAR-class-no-enforced-ceiling` is unclaimed and failing daily.**
Does 0.69.0 absorb the ceiling class, or does it get its own band ahead of 0.70.0?
