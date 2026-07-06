---
title: "Cross-day velocity / unfinished-work signal (observe-first, from the existing pulse snapshot)"
owner: Noel
gh_issue: 116
source: "https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/116"
status: "Active (2-WORKING) — Phase 1 shipped 2026-07-06 (MARATHON-2026-07-06 Lane A). Phase 2 gated on an observation window."
created: 2026-07-05
updated: 2026-07-06
branch: marathon/2026-07-06
doc_type: project
goal: >
  Determine whether diffing the daily pulse snapshot across day boundaries can produce two cheap,
  legible signals per project — an activity streak (velocity proxy) and a "was active, now silent,
  still has open issues" possible-stall flag — and if proven, feed them into `rank_next_actions` as
  one more candidate source. Observe-first: prove the signal before it touches ranking.
non_goals: >
  Not an NLP re-parse of the vault's Gemini-generated prose (`0. Today's Notes.md` / `0. Yesterday.md`
  AI Daily Summary / Git Pulse Daily Summary blocks) — those are a rendered summary of data we already
  have in structured form; re-summarizing a summary is lossy and unnecessary. Not a new DB table or new
  MCP tool in v1 (mirrors GH-101's own v1 scope). Not a re-ranker on day one — Phase 1 is log/report only.
  Not a new Reb→XYZ export channel — see [Relationship to GH-102](#relationship-to-gh-102-dont-open-a-second-seam).
related:
  - src/rebalance/ingest/next_actions.py
  - src/rebalance/ingest/pulse.py
  - src/rebalance/ingest/github_watch.py
  - src/rebalance/ingest/github_scan.py
  - PROJECT/2-WORKING/GH-102-XYZ-REBALANCE-INTEGRATION.md
  - PROJECT/2-WORKING/GH-101-SIGNAL-QUALITY-CONTRACT.md
  - PROJECT/1-INBOX/PDDA-INTEGRATION/ROADMAP-SIGNAL-SCAN.md
  - PROJECT/1-INBOX/GEMINI-WHATS-NEXT-VAULT.md
effort: 2
complexity: 2
risk: 2
phases: 2
---

# Cross-day velocity / unfinished-work signal

## Status

| What was just completed | What's next |
|---|---|
| **Phase 1 shipped 2026-07-06** via `relay-xyz` (Producer=codex, Reviewer=agy, Approved r1; `relay-system/2026-07-06/gh116-phase1.md`), driven in an isolated worktree/branch (`marathon/2026-07-06`). `compute_deep_work_signals()` added to `next_actions.py`; one `rebalance doctor` "deep work" line wired in `doctor.py`. Independently re-verified (`PYTHONPATH=src pytest tests/test_next_actions.py tests/test_doctor.py` → 63 passed; live `rebalance doctor` shows `OK deep work — no possible-stall projects in the last 7 days`). No change to `rank_next_actions()` output or the vault. | Operator: observe the `deep work` signal over the stated window; then decide Phase 2 (folding it into ranking) per the doc's kill-gate. |

## Table of contents
- [The question](#the-question)
- [Key design decision — diff the structured snapshot, not the vault prose](#key-design-decision--diff-the-structured-snapshot-not-the-vault-prose)
- [Relationship to GH-102 — don't open a second seam](#relationship-to-gh-102-dont-open-a-second-seam)
- [Should this directly influence What To Do Next?](#should-this-directly-influence-what-to-do-next)
- [Phase 1 — compute + observe-only report](#phase-1--compute--observe-only-report)
- [Phase 2 — fold into ranking (gated)](#phase-2--fold-into-ranking-gated)
- [Anti-goals](#anti-goals)

## The question

Operator's ask: given `0. Today's Notes.md` and `0. Yesterday.md`, could an AI infer (a) what didn't
fully finish, and (b) whether there's velocity on a given project? **Yes to both — but not by reading
those two files.**

Both files are rendered output: the `AI Daily Summary` block is Gemini prose synthesized from
`collect_pulse_snapshot()` ([pulse.py:520](../../src/rebalance/ingest/pulse.py#L520)), and the
`Git Pulse Daily Summary` block is Gemini prose over the same day's git activity
(`utils/git_pulse_daily_synthesis.py`). Asking an LLM to re-read that prose and infer streak/stall
state would be summarizing a summary — lossier and more expensive than reading the structured data
those summaries were generated from, which is already sitting in the DB.

## Key design decision — diff the structured snapshot, not the vault prose

Reuse `collect_pulse_snapshot()` for "today" and call it again scoped to yesterday's date range (it is
already day-parameterized — the daily sync job at
[obsidian_daily_sync.py](../../utils/obsidian_daily_sync.py) and
[git_pulse_daily_synthesis.py](../../utils/git_pulse_daily_synthesis.py) both call it this way once
per run). Diff the two structured snapshots per project — no vault read, no second LLM call needed for
the base signal:

- **Streak (velocity proxy):** count of consecutive days, walking back from today, with nonzero
  commit/activity rows for that repo. A rolling count computed live at read time — not stored,
  mirroring GH-101's "not a new table in v1" precedent.
- **Possible-stall flag:** repo had activity yesterday, zero activity today, **and** still has ≥1 open
  GitHub issue/PR referencing it (checked against real issue state via the existing
  `github_scan`/`github_watch` collectors — [github_watch.py:227](../../src/rebalance/ingest/github_watch.py#L227)
  `watched_repo_is_active_work()`, [github_scan.py:747](../../src/rebalance/ingest/github_scan.py#L747)
  `is_idle`). This is a **flag, never a claim** — "went quiet with an open issue" is evidence a human or
  the ranker can weigh, not a verdict that work is unfinished (a repo can go quiet because it shipped
  and the issue just hasn't been closed yet).

No new table, no new MCP tool, no vault write, no LLM call required for v1 — it's arithmetic over rows
that already exist.

## Relationship to GH-102 — don't open a second seam

The operator's stated end-goal — "another source of data for the sibling XYZ repo to look for tasks
when building a marathon file" — is, structurally, exactly
[GH-102's Seam #3](GH-102-XYZ-REBALANCE-INTEGRATION.md#phase-3--seam-3-reb--xyz-lane-seeding-return-path)
("Reb's ranked *What to do next* emits cross-repo tick lanes... Reb priorities seed XYZ marathon
queues," via a `roadmap_signals.json` projection file). GH-102 already **kill-gates** that seam behind
Phase 2 (the `xyz` collector) proving the *forward* signal earns its place in the ranking, and its own
anti-goals explicitly say **"Not #3-before-#1."** That gate hasn't opened yet (Phase 2 is itself gated
on GH-101, whose Phase 2 is implemented 2026-07-05 and pending review).

**This doc does not reopen or route around that gate.** Its scope stops at making `rank_next_actions`
itself smarter with one more well-behaved candidate signal. If the signal proves out, it becomes one
more input to the *same* ranker that GH-102's Seam #3 will eventually export — no new cross-repo
channel, no second `roadmap_signals`-shaped table, no direct write to anything XYZ reads. The XYZ
delivery mechanism is already designed; it's just not open yet. Building a second pipe around it here
would violate GH-102's own "single-authority ownership" invariant (Reb owns priorities/ranking; one
seam carries them out, not two).

## Should this directly influence What To Do Next?

**Not directly, not yet.** Recommendation: Phase 1 ships as observe-only — a report surfaced in
`rebalance doctor` output (and/or a line appended near, not inside, the rendered
`Dashboards/What To Do Next.md` — see
[GEMINI-WHATS-NEXT-VAULT.md](GEMINI-WHATS-NEXT-VAULT.md)'s single-writer contract, which this must not
violate). This mirrors the discipline the repo already applies to itself: GH-102 Phase 4
("outcome-attribution... observe-first, log-don't-act") and GH-101's "not a relevance-ranking engine in
v1." A signal that sounds intuitively true (streaks feel like velocity) still needs a proving window
before it is trusted to move real ranking decisions — the cost of being wrong here is a bad "what to
work on" nudge, which is cheap to avoid by just watching it for a couple weeks first.

Only after a stated observation window with a concrete litmus (see Phase 2) does it become one more
low-tier candidate in `_operator_candidates()`
([next_actions.py:497](../../src/rebalance/ingest/next_actions.py#L497)), reusing the existing tier
system (sleuth/assigned(0) > github items(1) > calendar(2) > commits(3) > comments(4) > vault(5)) rather
than inventing a parallel scoring path.

## Phase 1 — compute + observe-only report

**Contract:** new pure function `compute_deep_work_signals(db, today, lookback_days=7)` (home:
`next_actions.py`, next to the other candidate-building helpers) returning, per project: `streak_days`,
`possible_stall: bool`, `evidence` (the specific dates/rows backing the flag — no black-box claims).
Surfaced via `rebalance doctor` as a new line per flagged project; **not** wired into
`rank_next_actions()` or any vault write in this phase.

**Acceptance:**
- Unit tests seed 7 days of fixture activity rows and assert: a 5-day-streak repo reports
  `streak_days=5`; a repo active yesterday/silent today with an open issue reports
  `possible_stall=True` with the backing evidence; a repo silent for unrelated reasons (no open issues)
  reports `possible_stall=False`.
- `rebalance doctor` shows the flagged projects, if any, with their evidence — legible without reading
  code.
- No change to `rank_next_actions()` output, the vault, or any existing table.

## Phase 2 — fold into ranking (gated)

**Kill-gate (evaluate before writing Phase 2 code):** over a stated observation window (e.g. 2 weeks),
did `possible_stall` flag at least N real cases the operator agrees were actually stalled (not just
quiet-because-done)? Declare N up front; don't eyeball it. If the false-positive rate is high, stop —
document why and either retune the heuristic or drop it.

**If the gate passes:** register it as one more tier-5-or-lower candidate in `_operator_candidates()`,
reusing the existing rank-key tier system — additive, reversible (removing the candidate source returns
ranking to today's baseline).

**If the gate fails:** Phase 1's report-only surface is a complete, useful outcome on its own — stop
here, same discipline GH-102 applies to its own Phase 3/4 kill-gates.

## Anti-goals

- Not a second Reb→XYZ export channel — GH-102 Seam #3 already owns that, and it stays kill-gated.
- Not an LLM re-parse of the vault's own generated prose — diff the structured snapshot instead.
- Not a new table or new MCP tool in v1.
- Not a ranking change on day one — Phase 1 is observe/report only.
- Not a write into `Dashboards/What To Do Next.md` — that file's single-writer contract belongs to
  `rank_next_actions` per GEMINI-WHATS-NEXT-VAULT.md; this doc's report surfaces elsewhere.

## Verification (per ROUTER §7 / PDDA.md)

`rebalance doctor` clean + `pytest tests/` green before any success claim on Phase 1 or 2 code.
`utils/pdda/pdda.sh run` clean before/after this doc's promotions.
