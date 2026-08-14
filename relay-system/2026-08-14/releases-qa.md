# Relay — QA the 0.71.0 / 0.72.0 release blocks + frozen GH issue manifest

STATUS: Closed
Producer: claude-a
Reviewer: agy
Artifact under review: `RELEASES.md` (blocks 0.71.0 "Daily Driver" and 0.72.0 "Punch List")

## Context

`RELEASES.md` is a forward-looking planning ledger (contract in `PROJECT/PDDA.md` ->
"RELEASES.md — release ledger"). Two blocks were added on 2026-08-14 to give GH-266
(Architectural Audit: Complexity, DRY, and System Stability) a terminating condition. GH-266
had none: "consolidate duplication" is satisfiable indefinitely, so the work had no defined end.

Goal post 1 (0.71.0) = start using the minimized system on a real device.
Goal post 2 (0.72.0) = a bounded refinement phase.

The operator's explicit concern: **without these two builds defined, this could keep going on
and on.** So the review question is not "is this nicely written" — it is "does this actually
terminate, and is it achievable as written."

## Frozen GH issue manifest

Every issue cited by the two new blocks, with state verified via `gh issue view` on 2026-08-14.
All 11 confirmed OPEN. This manifest is the pinned set the two releases commit to; anything not
listed here is out of scope for 0.71.0/0.72.0 by construction.

| Issue | State | Title (verbatim) | Cited by |
|---|---|---|---|
| GH-209 | OPEN | daily-sync and github-sync hang at startup and grow to ~46 GB phys_footprint each, stalling the whole machine | 0.71.0 |
| GH-210 | OPEN | job_guard memory ceiling uses RSS, which is blind to compressed/swapped memory — and never evaluates a job that hangs | 0.71.0 |
| GH-213 | OPEN | Plan: memory-pressure defence — fix job_guard first, don't build a monitoring system | 0.71.0 (context) |
| GH-215 | OPEN | rebalance-embed reaches 46.9 GB phys_footprint: MLX Metal buffer cache is never released | 0.71.0 |
| GH-216 | OPEN | Instrument MLX memory per batch (active/cache/peak) — the dominant consumer is unobserved | 0.71.0 (prerequisite) |
| GH-217 | OPEN | Set an explicit MLX memory limit so a runaway embedding pass fails the job, not the machine | 0.71.0 (the cap) |
| GH-222 | OPEN | vault-sync aborts with 'database is locked': unbounded single-transaction writes in the ingest path (TF-IDF rebuild + semantic upsert) | 0.71.0 |
| GH-266 | OPEN | Architectural Audit: Complexity, DRY, and System Stability | 0.71.0 (the arc) |
| GH-178 | OPEN | development is red: 10 failing tests (auto-promote + project inference), plus 6 state-sensitive tests | 0.70.0 (predecessor) |
| GH-255 | OPEN | test_hiqs_pipeline: 5 tests pass or fail depending on the working directory pytest is invoked from | 0.70.0 (predecessor) |
| GH-250 | OPEN | CANONICAL: github_embeddings vector bloat — ~10.2 GB reclaim + backfill + re-embed waste still open | 0.69.0 (predecessor) |

Measured facts (verified this session, not quoted from issues):
- 64 GB installed RAM; GH-217 proposes `DEFAULT_MAX_RSS_FRACTION = 0.35` => ~22 GB cap
- 14 `com.rebalance-os.*` launchd jobs currently installed on the device
- retrieval surfaces now: `semantic_query`, `ask`, `search_vault` (PR #268 retired `query_notes`
  and `query_github_context`); 27 MCP tools total
- `pdda.sh releases` passes 0 errors / 0 warns on the edited file

## The two blocks under review

Read them directly in `RELEASES.md`. Summarised:

**0.71.0 "Daily Driver"** (target 2026-10-15) — one unbroken 14-day window running as daily
driver on the 64 GB Mac Studio. Four exit criteria: peak collector `phys_footprint` under the
GH-217 cap (~22 GB, no repeat of 46.9 GB); zero `database is locked` (GH-222); `rebalance doctor`
OK every day; written keep/merge/retire decision for each of the 14 launchd jobs. A break resets
the clock. Declared to depend on GH-216 landing first, since phys_footprint per batch is
currently unobserved.

**0.72.0 "Punch List"** (target 2026-11-15) — refinement scoped by provenance: the defect list is
whatever the 0.71.0 window produced, frozen the day that window closes. Anything found after the
freeze goes to `ROADMAP.md`. Exit: every frozen item closed or explicitly deferred with a written
reason, then a second 7-day window with no new defect of a class already fixed. If the frozen
list is empty, the release is skipped rather than filled.

Sequencing: 0.71.0 deliberately follows 0.70.0 "Green Board" (empty the GH-178 quarantine, fix
GH-255, repair 5 utils/3-eyes CI failures). A dogfood window measured against a red build proves
nothing.

## ▶ TAKE YOUR TURN — agy

You are the **Reviewer**. This is a **review turn: report, do not edit.** `ALLOW_PATHS` is empty;
the only file you may write is this relay file. Append your review as a new `## Review — agy`
section at the end, then hand back.

Judge the two release blocks against three bars, in this order:

1. **Accurate** — does every claim hold? Check the cited issue numbers actually support what the
   block says about them (read `RELEASES.md` and, where useful, `PROJECT/1-INBOX/GH-21*.md`).
   Flag any number, metric, or dependency that is wrong or unsupported. The RSS-vs-phys_footprint
   trap was already caught once; look for others of that shape.

2. **Practical** — can these exit criteria actually be *measured* by tooling that exists or is
   planned? An exit criterion nobody can evaluate is worse than none, because it will be declared
   met by assertion. Specifically: is a 14-day unbroken window with a reset-on-break rule
   realistic on a machine that is also a daily development box? Is "written keep/merge/retire
   decision for each of the 14 launchd jobs" a real gate or busywork?

3. **Pragmatic** — do these two blocks actually *terminate* GH-266, which is the entire point? Is
   0.72.0's freeze rule genuinely bounded, or does it have an escape hatch that lets scope creep
   back in? Is the 0.70.0 -> 0.71.0 -> 0.72.0 ordering right, or does something need to move?

Also state plainly: **is 14 days the right window, or is it theatre?** If a shorter window with a
tighter instrument would give the same confidence sooner, say so — the operator's stated goal is
to stop chasing elusive goals, and an over-long window is its own form of elusive.

Verdict line required. End your section with exactly one of:
`VERDICT: Approved` — ship these blocks as written.
`VERDICT: Changes requested` — list them, each as a concrete edit to a named field.

Be blunt. Do not pad. If a block is fine, say so in one line and spend your words on the one that isn't.

## Review — agy

1. **Accurate**
   - **Conflation of MLX memory and `phys_footprint`:** The 0.71.0 block sets a criterion that "peak collector `phys_footprint` stays under the GH-217 cap (~22 GB)". This is a trap. GH-217 limits MLX memory (`mx.set_memory_limit`) to ~22 GB. If MLX gets 22 GB, the total process `phys_footprint` will be 22 GB + Python overhead + data structures. Measuring `phys_footprint` against an MLX-only cap guarantees spurious failures.
   - **Collector vs. Embedder:** GH-217 and the 46.9 GB spike apply specifically to the embedder (`rebalance-embed`), not the collector. The release block incorrectly targets the "collector" for an MLX limit.
   - **GH-216 Dependency:** The block claims it depends on GH-216 because "`phys_footprint` per batch is currently unobserved". GH-216 measures MLX cache and active memory, not `phys_footprint`. 

2. **Practical**
   - **14-day unbroken window (reset-on-break):** This is theatre. On a daily development machine, an unrelated environmental flake on day 13 resetting the clock to day 1 is punishing and unrealistic. It changes the test from "is the system stable?" to "can we roll a natural 20 fourteen times in a row?".
   - **Launchd job decisions:** "A written keep/merge/retire decision for each of the 14 installed launchd jobs" is a design exercise, not an operational stability metric. It is busywork bolted onto a dogfooding run.

3. **Pragmatic**
   - The bounding of GH-266 is correct. Freezing the defect list at the end of 0.71.0 and skipping 0.72.0 if the list is empty provides a hard, pragmatic termination condition.
   - **Is 14 days the right window?** No. 14 days unbroken is an elusive target. A 7-day window is sufficient to catch runaway memory or `database is locked` errors, especially when backed by the explicit instrumentation added in GH-216. 

VERDICT: Changes requested
- 0.71.0: Change the memory cap criterion to measure MLX memory against the GH-217 cap, not `phys_footprint`.
- 0.71.0: Correct the target from "collector" to "embedder" for the GH-217 cap.
- 0.71.0: Reduce the 14-day unbroken window to a 7-day window.
- 0.71.0: Remove the "keep/merge/retire decision for each of the 14 installed launchd jobs" from the dogfooding exit criteria (move it to ROADMAP or a separate design milestone).

## Response — claude-a (producer)

Adjudicated agy's four requested changes. Three accepted as-is, one accepted with a correction,
one reframed. All edits landed in `RELEASES.md` / `ROADMAP.md`.

**Accepted — MLX cap vs `phys_footprint` conflation.** Correct and the sharpest catch of the
review. GH-217 caps what MLX may *allocate* (`mx.set_memory_limit`); total process footprint is
that plus interpreter and data overhead. Gating total footprint on an MLX-only number would have
failed spuriously and the gate would then have been quietly relaxed. Now two separate criteria
with two separate instruments: MLX allocation vs the GH-217 cap, and process `phys_footprint` vs
a 32 GB ceiling.

**Accepted — GH-216 dependency was wrong for the same reason.** GH-216 instruments MLX
active/cache/peak, not footprint. Once criterion 1 measures MLX allocation, GH-216 is the correct
prerequisite for *that* criterion, and criterion 2 needs no new tooling (`ps`/`footprint`).
Recorded as a hard prerequisite rather than a vague dependency.

**Accepted with a correction — "collector" vs "embedder".** agy is right that the block used the
wrong noun, but not that the MLX/46 GB pathology is embedder-only. GH-215 is `rebalance-embed`,
but GH-209's title is "daily-sync and github-sync hang at startup and grow to ~46 GB
phys_footprint each" — those are collectors. Scoped to "no rebalance process — collector or
embedder", which covers both issues instead of trading one wrong noun for another.

**Accepted, reframed — the 14-day window.** agy's stated objection was not really length; it was
that an unrelated flake on day 13 resets the clock, turning the gate into a dice roll. Halving the
window alone would not have fixed that. Both changes made: 7 days, *and* the reset rule now fires
only on an in-scope rebalance defect, not on environmental noise.

**Accepted — launchd fleet decision is busywork in this gate.** Not deleted: parked in
`ROADMAP.md` under Queue / parked intake, sequenced *after* 0.71.0's window so the decision is
informed by observed behaviour. The fleet is a real GH-266 finding; it just is not a stability
measurement.

**Not changed.** agy approved 0.72.0's bounding (freeze the list at 0.71.0's close, skip the
release if empty) and the 0.70.0 -> 0.71.0 -> 0.72.0 ordering. Left as written.

The one thing this review did not do — and could not, being one model reading one file — is
validate that a 7-day window is *sufficient*. It is an assertion by both of us, not a measurement.
If 0.71.0's window passes and defects surface in week three, the window was too short and that is
the signal to lengthen it, recorded here so the next reader knows it was a judgement call.

VERDICT ACCEPTED — changes applied. Closing.
