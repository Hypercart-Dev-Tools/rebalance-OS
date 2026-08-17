# GH-219 — Codex plan review, rounds 1 & 2 (2026-07-27)

> Issue: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/219
> Artifact reviewed: [GH-219-REBALANCE-MEMORY.md](GH-219-REBALANCE-MEMORY.md)
> Reviewer: Codex (via `/relay-xyz`, Path A headless) · Producer: claude-a
> Outcome: **8 findings — 3 Blockers, 4 Shoulds, 1 Pass. All accepted and applied.**

## Why this file exists (and why it is tracked, not in `.xyz/`)

The original relay thread lived at `.xyz/relay-system/2026-07-27/marathon-mlx-memory-plan.md`.
**It was destroyed on 2026-07-27 ~16:59 UTC** when `xyz-sync.sh update` re-vendored the harness
and replaced the whole `.xyz/` tree, taking `relay-system/` and `.tick/events/` with it. `.xyz/` is
gitignored, so nothing was recoverable from git; no backup existed.

The findings survived only because the Codex CLI transcripts persisted outside the harness
(`$TMPDIR/codex-turn-17533.log`, `$TMPDIR/codex-turn-r2-36333.log`) and because the review had been
read into the working session.

Several commits and the ROADMAP cite "Codex r1/r2" as the justification for the plan's shape. That
evidence needs to live somewhere durable. It now does — **in the tracked tree**, not in a
gitignored, re-vendorable directory.

The lesson is the same one recorded in `WORKTREE-SAFETY.md` §13 the same morning: content that has
never been committed has never been hashed into an object, and is one command away from being
gone. `.xyz/` is disposable *by design*; it is the wrong home for a review record.

---

## Round 1 — findings (verbatim)

> - **[Should] (a) Regression archaeology:** the asserted negative "No code regression" over-claims
>   its evidence. The quoted scope is only "`embedder.py`, `semantic_index.py`,
>   `ingest/_job_guard.py`, `utils/job_guard.py`, or `doctor.py`"; it does not exclude recent
>   changes to invocation entry points, launchd environment/configuration, or runtime/OS state.
>   Recast this as "no direct embedding-path edit found," and add those surfaces plus OS/MLX
>   runtime updates to the candidate checklist.
>
> - **[Should] (a) Regression archaeology:** 90 minutes is a defensible cap on *triage*, but not on
>   all four promised investigations—locating an unknown live index, reconstructing 14-day growth,
>   diffing historical plists, and proving trigger/contention. Keep the non-extendable cap, but
>   define the minimum evidence and an explicit "unobservable within budget" result for each
>   candidate; otherwise "not found" ambiguously reads as "ruled out."
>
> - **[Blocker] (b) 70–80% claim:** the only confirmed event is PID 1391, while the plan itself says
>   PIDs 16871 and 2886 have "no `job_rss.jsonl` record at all." Lane 1 measures a chosen embedding
>   pass but contains no required process/run correlation that can determine whether the two
>   unattributed episodes are unguarded embedding entry points or a second workload. Require an
>   invocation-wide run ID / PID-to-entry-point record and make resolving or explicitly bounding
>   those episodes a prerequisite to claiming the 70–80% outcome (not a prerequisite to shipping
>   the immediate cache cap).
>
> - **[Blocker] (b) 70–80% claim:** "peak `phys_footprint`" alone cannot establish whole-machine
>   starvation is solved: it omits aggregate concurrent footprint and gives no numerical bound until
>   after implementation. Before Lane 2, define a measurable process and machine-level pass
>   criterion (including concurrent jobs), then add a Lane-1 decision table: cache rises → apply the
>   cache remedy; cache is flat → halt #215 as written, record the refutation, and escalate to a
>   separately scoped diagnosis. "Redirects Lane 2" is not a bounded plan.
>
> - **[Should] (c) Stopping rule:** "a second, non-embedding path reaching a comparable footprint"
>   is too narrow and "comparable" is undefined. It misses an uninstrumented `rebalance-embed` entry
>   point, concurrent moderate consumers, or the same path failing the bound. Reopen when a named
>   threshold of either process or aggregate footprint prevents the stated machine-level bound;
>   otherwise stop after a representative workload/day with a defined minimum number of passes.
>   Replace "free_gb never approaches zero" and "single-digit GB" with numerical limits.
>
> **Verdict: Changes requested.**

**Disposition:** all five implemented in `e67700a`.

---

## Round 2 — findings (verbatim)

> - **[Pass] (a) Recent-change / regression analysis:** the plan now states the negative at the
>   scope actually checked, explicitly preserves entry points, launchd configuration, and OS/Metal
>   as candidates, and gives the 90-minute lane per-candidate evidence/outcome rules rather than
>   treating absence as exclusion. `GH-219-REBALANCE-MEMORY.md:70-86`, `:162-183`.
>
> - **[Should] (a) Recent-change / regression analysis:** two Lane 0.5 exclusion tests do not test
>   the hypothesis they label excluded. "No 3-Eyes job touches an embedding entry point" excludes a
>   direct trigger but not the stated *contention* theory, and "all callers enumerated and guarded"
>   says nothing about whether a caller/cadence changed before 07-25.
>   `GH-219-REBALANCE-MEMORY.md:90-106`, `:170-171`. Make both results `UNOBSERVABLE` unless logs
>   establish the relevant temporal/overlap evidence; retain their narrower tests as useful
>   sub-findings.
>
> - **[Should] (b) 70–80% delivery:** the process, aggregate, and machine bounds plus attribution
>   requirement credibly repair the previous single-metric gap.
>   `GH-219-REBALANCE-MEMORY.md:391-401`, `:433-447`. But 8 GB/16 GB are asserted as the contract
>   without an operational derivation or a decision if a representative, healthy pass legitimately
>   needs more; Lane 3 is simultaneously to be "sized from Lane 1." `:243-249`, `:393-398`. State
>   the headroom calculation/baseline that justifies these targets and make a
>   legitimate-but-over-budget result a bounded decision (revise the contract once from measured
>   evidence, or close/escalate), not an implicit permanent failure.
>
> - **[Blocker] (c) Stopping rule:** the project still has no terminal outcome for its own expected
>   failure paths. Lane 1 says `REFUTED`/`UNOBSERVABLE` halts the marathon, while project acceptance
>   still requires a zero-breach 12-pass day; likewise a persistent breach formally "reopens scope."
>   `GH-219-REBALANCE-MEMORY.md:211-220`, `:414-429`, `:433-457`. Combined with "every" owned
>   process/path and ad-hoc entry points, this can be an infinite discovery/remediation loop. Freeze
>   Lanes 5–6 to named inventories/cutoff dates, define a finite verification attempt, and add
>   terminal states: **Completed** only on the acceptance list; **Blocked/diagnosis split** on
>   refutation, unobtainable telemetry, or a persistent breach after that attempt—close this project
>   without claiming the 70–80% result and open one separately scoped successor. New surfaces after
>   the cutoff follow the existing new-issue rule unless they meet a measured reopen threshold.
>
> **Verdict: Changes requested.**

**Disposition:** all four addressed in `b65f558` (the Pass required no action).

---

## Close

Closed as **`STATUS: Closed` by operator decision — NOT reviewer-approved.** Codex's r2 verdict was
"Changes requested" and it never saw the r2 fixes. Recording this distinction matters: the plan has
been through two adversarial rounds and every finding was applied, but no reviewer ever signed off
on the final state.

The r1 blockers materially changed the plan (PID→entry-point attribution; a numeric machine-level
contract). The r2 blocker closed the hole that widening to 8 lanes opened — without terminal states,
a project built on a refutable hypothesis had no exit condition at all.

Transcripts, while they last (`$TMPDIR`, not durable):
`codex-turn-17533.log` (r1), `codex-turn-r2-36333.log` (r2).
