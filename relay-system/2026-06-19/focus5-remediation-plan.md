# RELAY · Focus 5 ranking bug — remediation plan review
<!--
  Single source of truth for this two-agent relay.
  Read this ENTIRE file before doing anything. Act only on your turn.
-->

NEXT: Reviewer
STATUS: Open
ROUND: 1 / 5

## ▶ TAKE YOUR TURN — read this first (works for ANY agent: Claude, Codex, Gemini)
The operator just said "take your turn on this file." Everything you need is **in this file** — don't wait for pasted instructions.
1. **Read this whole file** (header, Setup, Ground rules, every turn in the Log).
2. **Check it's your turn:** `NEXT` (top) names the role to act. Confirm you are the agent bound to it (see Setup) **and** the last Log block isn't already yours. If not → STOP and reply "wrong window — nudge the <other> window."
3. **Do your role's work** on the artifact named in Setup (read the real files; cite `file:line`):
   - **Reviewer:** review vs the Definition of Done → graded findings (`[Blocker]`/`[Should]`/`[Nit]`/`[Pass]`), each with a concrete proposed fix → set a **Verdict** (Approved | Changes requested | Blocked). Do **not** edit the artifact; you only append findings here. Because the artifact is a **non-executable plan doc**, your basis is `textual only` / `N/A` — re-read the artifact file itself when confirming claims, never just this log.
   - **Producer:** for every open finding log a disposition (Implemented / Modified / Declined + why), make the change, then add new work.
4. **Append ONE block** at the very bottom, directly **above** the marker line (`<!-- ↓↓↓ NEXT TURN ... -->`). Never edit earlier turns. Header it `### Round N · <Role> · <your-label> · <date time>`.
5. **Update the header:** flip `NEXT` to the other role; set `STATUS` (`Approved` closes the relay — Reviewer only; else leave `Open`); the Producer bumps `ROUND` when opening a new cycle.
6. **Stop.** Tell the operator your one-line result.

## Setup
- Artifact under review: `PROJECT/2-WORKING/FOCUS-5-RANKING-BUG-AND-REMEDIATION.md`
- Supporting source (read-only context): `src/rebalance/ingest/focus5_scan.py`, `src/rebalance/web.py`, `src/rebalance/ingest/index_ops.py`
- Definition of Done: The remediation plan is technically correct, **complete vs its own diagnosis** (every root-cause issue maps to a phase; no dropped/contradicted claim), and each phase is **actionable with verifiable QA** — an engineer could implement it without guessing. Flag any incorrect claim about the code, any gap between diagnosis and plan, and any phase whose QA can't actually be checked.
- Producer: Claude (Opus 4.8) — owns the plan
- Reviewer: Codex CLI (headless, cli-driven)
- Handoff: cli-driven (codex)
- Started: 2026-06-19

## Ground rules
1. This file is the single source of truth. If it isn't written here, assume the other agent doesn't know it. The two agents are different tools (Claude + Codex) and never share memory.
2. Read the whole file. Take a turn only if `NEXT` names your role — otherwise reply "not my turn" and stop.
3. One turn = one block appended at the very bottom, above the marker. Never edit earlier turns. Then update `NEXT`, `STATUS`, `ROUND` at the top.
4. Stay tight. Requests and findings are bullets, not essays.
5. **The Reviewer never edits the artifact.** It proposes graded findings, each with a concrete suggested fix where possible. The Producer decides each proposal and implements the approved ones — logging a disposition (Implemented / Modified / Declined + reason) for every one.
6. Grade every finding: `[Blocker]` must fix · `[Should]` strong rec · `[Nit]` optional · `[Pass]` checked and sound. Answer the Producer's "Re-review this" questions in an `Answers:` block.
7. The Reviewer posts a Verdict every turn. The relay ends on **Approved** — to get proposals actioned in-thread set `Changes requested`, not `Approved`. If max `ROUND` ends without `Approved`, set `STATUS: Escalated`.
8. (Commits) This relay log is git-tracked; the Producer commits the artifact + log each turn. The Reviewer is a headless subprocess that edits nothing — its block is appended by the Producer-side orchestrator and committed as `comments only`.
10. **Evidence contract.** Producer logs a one-line `Verification:`. Reviewer logs a verdict `Basis:` — for this doc artifact that is `N/A — non-executable artifact` / `textual only`. The read must be against the artifact file, not this log.
11. **Reconcile claims against the file.** Confirm each plan claim against the real source (`focus5_scan.py`, `web.py`, `index_ops.py`) — a plan that misstates the code is a `[Blocker]`.

## Roles
- **Producer** — Claude: owns the plan doc, decides + implements proposals.
- **Reviewer** — Codex: reviews vs the DoD, proposes graded findings, sets a verdict. Never edits the artifact.

---
## Log

### Round 1 · Producer · Claude · 2026-06-19
**Did:** Wrote the remediation plan `PROJECT/2-WORKING/FOCUS-5-RANKING-BUG-AND-REMEDIATION.md`. It documents a /debug-mantra trace (8-run ledger) and isolates three root-cause issues:
- **A (primary):** no ranking mode surfaces "most recent active repos" — `dirty_first` sorts `(at_risk, recency)` and `my_work` pins dirty repos to `now`, both burying clean-but-recently-committed repos. Proven by re-ranking the stored signals: pure `_recency` surfaces the operator's actual active repos.
- **B (contributing):** the roster is a frozen snapshot — Focus 5 is opt-in (not scheduled) and PR #72 removed on-view recompute, so it only refreshes on manual ↻ Refresh.
- **C (secondary):** `rebalance-OS` is outside the single scan root (`/Documents/GH Repos`), so it's never discovered.

Plan: Phase 1 add `rank_recent_activity` (default), Phase 2 two views (Focus 5 = recency, Dirty Five = dirty_first), Phase 3 scheduled refresh (decided), Phase 4 add rebalance-OS to scan roots. Each phase has a QA checklist.

**Review this:**
- Are the code claims accurate? Specifically `rank_dirty_first` sort_key `(at_risk, recency)` and `rank_my_work` pinning dirty→now (`focus5_scan.py` ~lines 157–182), and `_recency` excluding `index_mtime_ts` (~142–149).
- Is the proposed `rank_recent_activity` (sort_key `(_recency(s),)`, eligibility `_eligible_as_my_work`) correct, and does making it the **default** have any downside vs the documented "don't lose WIP" intent of dirty_first?
- Completeness: does every diagnosed issue (A/B/C) map to a phase with checkable QA? Any dropped consideration (e.g. tie-breaking when recency ties, repos with no operator commits, the off-roster "needs attention" strip semantics under the new default)?
- Any missing root cause the diagnosis didn't consider?

**Verification:** N/A — non-executable artifact (plan doc). Code claims were derived from reading the cited source + re-ranking stored signals during the trace.
**Open questions:** Should `rank_recent_activity` still surface a purely-dirty repo with no operator commits, and if so where should it rank vs a clean recently-committed repo?
**Commit:** <pending>

<!-- ↓↓↓  NEXT TURN GOES ABOVE THIS LINE — keep this marker last  ↓↓↓ -->
