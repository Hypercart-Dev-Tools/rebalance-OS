# RELAY · Green Board 0.70.0 candidate QA
<!--
  Single source of truth for this two-agent relay. Read the ENTIRE file before acting.
  Scaffolded by relay-automation/new-relay.sh on 2026-08-15.
-->

NEXT: Producer
STATUS: Open
ROUND: 1 / 4

## ▶ TAKE YOUR TURN — read this first (works for ANY agent: Claude, Codex, agy)
1. **Read this whole file** (header, Setup, Ground rules, every block in the Log).
2. **Check it's your turn:** `NEXT` (top) names the role to act. Confirm you are bound to it and the
   last Log block isn't already yours. If not → STOP and reply "wrong window — nudge the <other> window."
3. **Do your role's work** on the artifact named in Setup:
   - **Reviewer:** review vs the Definition of Done → graded findings
     (`[Blocker]`/`[Should]`/`[Nit]`/`[Pass]`), each with a concrete fix → set a **Verdict**
     (Approved | Changes requested | Blocked). **Review the whole file, not just the diff** (GH-268):
     a beta test had this loop reach `Approved` in two rounds while an independent audit of the same
     branch found 20 issues (1 critical, 4 high) — every one of them in the pre-existing code the
     change sat on, which nobody had read. Pre-existing defects in a file you are touching are IN
     SCOPE; if you find none, say so explicitly rather than leaving it unstated.
     **Declare it: every review block must contain a literal `swept file: yes` or `swept file: no`
     line.** Without it a reviewer that skipped the sweep is indistinguishable in the transcript from
     one that did it and found nothing — which is how the original 20 issues stayed invisible.
     Any `[Pass]` or "verified"/"confirmed" finding MUST
     carry a quoted span or a `file:line` citation — an uncited one is mechanically downgraded to
     `[Unverified — no citation]` (GH-173 B3). Do **not** edit the artifact; only append findings here.
   - **Producer:** log a disposition for every open finding (Implemented / Modified / Declined + why),
     make the change, then add new work.
4. **Append ONE block** at the very bottom, directly **above** the marker line. Never edit earlier turns.
5. **Update the header:** flip `NEXT`; set `STATUS` (`Approved` closes — Reviewer only; else `Open`);
   the Producer bumps `ROUND` when opening a new cycle. If the max `ROUND` ends without `Approved`,
   set `STATUS: Escalated`.
6. **Commit only the relay file** (`relay(green-board-0-70-0-candidate-qa): <role> r<N>`); no push. **Stop** and report one line.
7. **Hand off explicitly — EVERY turn, not just the first** (GH-268). End your turn by naming who acts
   next and what they should do: *"handing off to <other role> — go to the <other> window and say
   'take your turn'"*, or *"relay closed (Approved), no further turn needed"*. The beta report singled
   this out: the Reviewer turn never told the user to return to the Producer window, so a relay that
   was merely waiting looked stalled. A turn that ends without this line is not finished.

## Setup
- Artifact under review: **greenboard-candidates.md** (embedded below — read it here).
- Reviewer: codex   ·   Producer: claude-a
- Started: 2026-08-15

### Artifact — greenboard-candidates.md
```
# 0.70.0 "Green Board" — candidate list for QA

**Reframed:** Green Board becomes the **public-facing RC**. That widens the bar from "our tests
pass" to "a stranger can clone this and succeed", which pulls `/front-door` and `/shakedown` in as
exit gates rather than afterthoughts.

**Scoping decision (operator, 2026-08-15):** 3-Eyes is **out**. It is a diagnostic tool, not core
product; fixing diagnostics while the core ships is a distraction. This removes #272, #269, #247,
#246, #232 and the 3-Eyes half of #195 from consideration regardless of merit.

## Measured ground truth (2026-08-15, this machine)

| Observation | Result |
|---|---|
| `pytest tests/` from repo root | **1,727 passed, 10 xfailed, 0 failed** (2m45s) |
| `pytest tests/` from `/tmp` | **10 FAILED**, 1,713 passed, 4 skipped (1m41s) |
| Failing set from foreign cwd | 9x `test_gh250_fencing.py`, 1x `test_launchd_predicate.py` |
| `mcp>=1.0.0,<2` pin (#225 A) | **present** in `pyproject.toml:19`; `mcp.server.fastmcp` imports fine |
| Unguarded `mlx` imports in tests (#225 B) | **none found** |
| `which -a rebalance` (#261) | dead `.venv-py314-backup` shim still **first on PATH** |

The headline is that **development is not red from the repo root** — the premise both #178 and #225
were written against. What survives is *working-directory dependence*, which is a different and
narrower defect.

## Candidates

### Tier 1 — RC blockers (a stranger hits these)

| # | Title | Status | Why it blocks an RC |
|---|---|---|---|
| **#255** | tests pass/fail depending on invoking directory | **CONFIRMED reproducing** — 10 failures from `/tmp` | A green badge that only holds from one directory is not a green badge. Directly contradicts the RC claim. |
| **#261** | stale `.venv-py314-backup` shim shadows `rebalance` on PATH | **CONFIRMED reproducing** | First `rebalance` on PATH is dead, failing with a bare `command not found` naming a nonexistent python3.14. This is a first-five-minutes failure. |

### Tier 2 — needs revalidation before it earns a slot

| # | Title | Suspicion |
|---|---|---|
| **#178** | development is red: 10 failing + 6 state-sensitive | Likely **largely stale** — suite is green from root. The "6 state-sensitive" half may survive as a duplicate of #255. Needs a per-test verdict, not a blanket close. |
| **#225** | MCP dead on fresh install + MLX tests on CI | Both halves appear **already fixed**. Candidate for closure, not for scheduling. |
| **#233** | `test_pulse_self_repair`: fails on macOS, passes on Linux CI | Not observed in either run above. Platform-divergence class — same family as #255. |
| **#231** | `test_job_guard_wiring`: fixture never pins compressor ceiling | Not observed above; machine may not have been loaded enough to trigger. Environment-sensitive by construction. |
| **#242** | CLIO suites claim dual-interpreter pass while running bash twice | A **false-pass in the test layer**. If real, it inflates confidence in exactly the suite an RC leans on. Not covered by the runs above (shell suites, not pytest). |

### Tier 3 — the operator's DRY question

**#266 Architectural Audit (Complexity, DRY, System Stability)** is OPEN with four PRs merged
(#267, #268, #270, plus `7983436f` collapsing 4 duplicate ISO parsers, `8b92ee81` adding an import
linter). The operator wants verification that DRY was **actually achieved**, not merely attempted.

This is a verification task, not a fix task. Needs: what did the audit claim, what did the merged
PRs deliver, and what duplication demonstrably remains today?

Note #266 is currently assigned to **0.71.0** in RELEASES.md, not 0.70.0.

### Process gates (new, from the RC reframe)

- `/front-door` — clone-to-working audit: competing READMEs, install scripts, auth gates, doc-vs-code
  drift, and committed secrets. #261 is exactly what this catches.
- `/shakedown` — CWD-sensitive path resolution in script-calling skills. Note the thematic rhyme:
  #255 and #261 are both path/cwd-resolution defects, and `/shakedown` exists for that class.

## Questions for QA

1. **Is Tier 1 correct and complete?** Anything in the open-issue list that blocks a public RC and
   is missing here — particularly install, onboarding, secrets, or first-run failures?
2. **Are the Tier 2 suspicions right?** Especially: is #225 genuinely closeable, and is #178 stale
   or does a real subset survive?
3. **Is the 10-failure set from a foreign cwd one root cause or several?** 9 are GH-250 fencing
   tests touched yesterday. Are those cwd-dependent by construction, or did yesterday's roster
   change introduce it? This matters — if introduced yesterday, it is a regression, not #255.
4. **Does #266 belong in 0.70.0 rather than 0.71.0**, given the operator wants DRY verified now
   and an RC is a natural checkpoint for it?
5. **What is the honest exit criterion** for a public-facing RC? The current one
   (`pytest` green from any working directory) is a fixture-and-happy-path assertion — the same
   shape of gate that pronounced the GH-250 runbook "complete and verified" while four of its
   mechanisms were broken against the live fleet. What criterion would actually catch a bad RC?
```
- Definition of Done: _<fill in the acceptance criteria the Reviewer grades against>_

## Ground rules
1. This file is the single source of truth. The agents never share memory — read the whole file.
2. Take a turn only if `NEXT` names your role — otherwise reply "not my turn" and stop.
3. One turn = one block appended at the very bottom, above the marker. Never edit earlier turns.
4. Stay tight — findings are bullets, not essays. Grade every finding.
5. **The Reviewer never edits the artifact.** It proposes graded findings; the Producer implements.
6. The relay ends on **Approved** (Reviewer only). End each turn by committing just this file; no push.

## Log

### Reviewer — codex · round 1

swept file: yes

- [Blocker] The Definition of Done is still a placeholder, so this relay has no acceptance contract to grade (`relay-system/2026-08-15/green-board-0-70-0-candidate-qa.md:127`). Fix: replace it with measurable RC criteria covering a clean-clone install, the documented first-run path, required supported CWDs, `/front-door`, `/shakedown`, and the evidence each produces.
- [Should] `/front-door` and `/shakedown` are labels, not executable gates: neither specifies environment, command, expected result, owner, or retained evidence (`relay-system/2026-08-15/green-board-0-70-0-candidate-qa.md:104-109`). Fix: define a short checklist for each gate, including a clean environment that cannot inherit the stale PATH shim, and make successful completion an explicit exit criterion.
- [Should] The cited foreign-CWD pytest result does not establish the public-RC failure mode by itself: it runs `pytest tests/` from `/tmp`, while the document says the bar is what a stranger can clone and succeed with (`relay-system/2026-08-15/green-board-0-70-0-candidate-qa.md:51-53,63-65`). Fix: record the documented user command(s), supported invocation directories, and clean-clone reproduction; then scope #255 to the actual supported contract rather than “any working directory.”
- [Should] The #266 evidence is internally ambiguous: it says “four PRs merged” but lists three PR numbers and two commit IDs (`relay-system/2026-08-15/green-board-0-70-0-candidate-qa.md:95-97`). Fix: reconcile the exact merged changes and attach the audit claim, evidence of each delivered change, remaining duplication, and a release-placement decision.
- [Should] Tier 2 leaves several RC-relevant items as suspicions without an owner or a revalidation command, particularly #233, #231, and #242 (`relay-system/2026-08-15/green-board-0-70-0-candidate-qa.md:89-91`). Fix: add per-item reproduction/validation steps, result, and disposition before deciding that the Tier 1 set is complete.
- [Pass] The explicit 3-Eyes exclusion prevents diagnostic scope from silently entering this RC (`relay-system/2026-08-15/green-board-0-70-0-candidate-qa.md:55-57`).

Verdict: Changes requested

<!-- ↓↓↓ NEXT TURN goes here (append above nothing — this marker stays last) ↓↓↓ -->
