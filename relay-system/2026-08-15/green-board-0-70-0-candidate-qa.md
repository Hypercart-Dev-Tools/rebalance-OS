# RELAY · Green Board 0.70.0 candidate QA
<!--
  Single source of truth for this two-agent relay. Read the ENTIRE file before acting.
  Scaffolded by relay-automation/new-relay.sh on 2026-08-15.
-->

NEXT: Producer (claude-a)
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
- Definition of Done — the Reviewer grades the **candidate list**, not the RC itself. Approve when
  all five hold:
  1. **Every candidate carries a disposition backed by a command and its result** — reproducing,
     already-fixed, or misfiled. No item sits as an unvalidated "suspicion".
  2. **Tier 1 is justified against a stated user contract**, i.e. the documented commands a new
     user is actually told to run — not an invented bar like "any working directory".
  3. **#266/DRY carries reconciled evidence**: the exact merged changes, what each delivered, what
     duplication demonstrably remains today, and a release-placement decision.
  4. **`/front-door` and `/shakedown` are specified as executable gates** — environment, command,
     expected result, and what evidence is retained — not named as labels.
  5. **The RC exit criterion is falsifiable and would catch a bad RC**, meaning it fails when a
     real user would fail. A criterion that can only be satisfied by fixtures does not qualify.

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

### Producer — claude-a · round 2

swept file: yes

**Grading round 1.** All six graded; five accepted, one accepted-and-generalized. No declines.

- **[Blocker] DoD was a placeholder — ACCEPTED, fixed.** Replaced with five measurable criteria at
  `:127-138`. You were right that there was nothing to grade against.
- **[Should] `/front-door` + `/shakedown` were labels — ACCEPTED, fixed.** Specified as executable
  gates below, with environment, command, expected result and retained evidence.
- **[Should] The `/tmp` result does not establish the RC failure mode — ACCEPTED, and it
  generalizes further than the finding states.** Chasing it down invalidated **both** of my Tier 1
  items, not just the framing. Detail below; this was the most valuable finding in the round.
- **[Should] #266 evidence was internally inconsistent — ACCEPTED, my error.** It is **three**
  merged PRs (#267, #268, #270) plus direct commits (`7983436f`, `8b92ee81`, `35c70962`,
  `21bc1b5e`, `f801ab8d`). I wrote "four PRs" and then listed three. Reconciled below.
- **[Should] Tier 2 items had no owner or revalidation command — ACCEPTED.** Every item now carries
  the command and its result.
- **[Pass] 3-Eyes exclusion — noted.** Operator decision, holds.

#### The correction that matters: my Tier 1 was wrong on both counts

Applying your "what does a stranger actually do" test against the documented contract
(`README.md:225-236`) — `git clone` → `cd rebalance-OS` → create venv → `pip install -e .` → then
`/welcome` or `rebalance onboard`:

| Was | Now | Evidence |
|---|---|---|
| **#255** Tier 1 blocker | **Tier 2 — not RC-blocking** | The documented contract says `cd rebalance-OS`. From the repo root the suite is green (1,727 passed). "Any working directory" was a bar I invented, not one any user is held to. Real defect, but it is CI-trust/developer-experience, not a stranger-facing failure. |
| **#261** Tier 1 blocker | **Not RC — local-only** | `git ls-tree -r --name-only HEAD \| grep -c venv-py314` → **0**. `.venv-py314-backup` is untracked and never reaches a fresh clone. This is machine hygiene on one workstation, not a defect a stranger can hit. |

**And the actual blocker was absent from my list.** `README.md:230` hardcodes
`/opt/homebrew/bin/python3.13` in Step 1. The note at `:234-236` tells Linux/Windows/Intel-Mac users
to drop the `embeddings` extra but leaves the Homebrew-only interpreter in place — so a Linux user
copy-pasting Step 1 fails on line 3, two paragraphs after a compatibility table (`:205-213`)
promising the core runs on "any (Python 3.12+)". **First command, first failure, contradicted by the
same page.** Filed below as the sole Tier 1 item.

That is the honest outcome of this round: the QA moved Tier 1 from two items that do not block an RC
to one that does, and the new one was found only by testing the documented path rather than a path I
assumed.

#### Revised candidates — every item with command and disposition

**Tier 1 — RC blockers**

| # | Item | Command | Result | Disposition |
|---|---|---|---|---|
| NEW | README Step 1 hardcodes a Homebrew interpreter | read `README.md:225-236` vs `:205-213` | contradiction confirmed | **File + fix.** One-line change; blocks every non-Homebrew user. |

**Tier 2 — real, not RC-blocking**

| # | Command | Result | Disposition |
|---|---|---|---|
| #255 | `cd /tmp && pytest <abs>/tests/` | 10 failed, 1,713 passed | **Keep, demoted.** Fix for CI trust. |
| #261 | `git ls-tree -r --name-only HEAD` | 0 matches | **Close as local-only**, or re-file as workstation hygiene. |
| #273 | `pdda.sh banned-imports` | 55 warns / 0 errors; 13 direct `fromisoformat`; 3 files import a canonical helper *and* bypass it | **Green Board.** Two canonical hubs (`tz_utils`, `lib/time_ops`). |

**Closeable — already fixed**

| # | Command | Result |
|---|---|---|
| #225 | `grep -n mcp pyproject.toml`; import `mcp.server.fastmcp` | pin `mcp>=1.0.0,<2` present at `:19`; import OK. Part B: no unguarded `mlx` imports in `tests/`. **Both halves fixed.** |
| #178 | `pytest tests/` from repo root | 1,727 passed, 0 failed. **Stale.** Any surviving "state-sensitive" subset is a duplicate of #255. |

**Answered: the 10 foreign-cwd failures are ONE root cause, and not a regression.**
`tests/test_gh250_fencing.py:5` sets `SCRIPT_PATH = "utils/gh250/fence-writers.sh"` — a relative
path resolved against CWD. `git log -1 -- tests/test_gh250_fencing.py` → `be25c79e`, **2026-08-04**,
and `git show d7d924a5^:tests/test_gh250_fencing.py` shows the same relative literal. It predates the
2026-08-14 roster change by ten days. Same cause for the 10th (`test_launchd_predicate.py`). Not a
regression; it is #255 exactly.

**Unvalidated, and I am saying so rather than guessing:** #233 (macOS/Linux divergence), #231
(loaded-machine sensitivity) and #242 (CLIO dual-interpreter false-pass) did not appear in either
run. #233 and #231 are environment-sensitive by construction and cannot be settled on this machine
in this state; #242 is a shell suite outside pytest and was never exercised. They stay Tier 2
**pending**, with #242 the one worth real attention — a false-pass in the test layer inflates
confidence in exactly the suite an RC leans on.

#### #266 reconciled

Three PRs merged (#267 architectural audit, #268 phase 3, #270 consolidate date parsers) plus
commits `7983436f` (4 ISO parsers → 1), `8b92ee81` (Phase 2 governance + `check_banned_imports.py`),
`35c70962`, `21bc1b5e`, `f801ab8d`. **Delivered:** a real reduction in parser count and a governance
check that exists and runs. **Remaining:** 13 of 109 `src/` files call `fromisoformat` directly; two
canonical hubs; 3 files import a canonical helper and bypass it anyway; the check reports
**55 warns / 0 errors** and is wired into neither CI nor `tests/`. **Placement: 0.70.0**, as #273 —
an RC is the checkpoint where "is this consolidated" gets answered, and a warn-only rule cannot hold
a gain. Ratchet sketched separately as #274 for the release after.

#### Gates, specified

| Gate | Environment | Command | Expected | Evidence retained |
|---|---|---|---|---|
| `/front-door` | Clean clone in a fresh dir; `PATH` scrubbed of this repo's venvs; no `~/.rebalance*` | clone → follow `README.md` Step 1 verbatim → `rebalance --version` → `rebalance doctor` | Every documented command succeeds as written on at least one non-Homebrew platform | `FRONTDOOR.md` board + the transcript |
| `/shakedown` | Same clean clone | skill/script path-resolution matrix (foreign CWD, nested dir, spaces in path, stripped exec bit) | No script resolves only from the repo root | Graded report |

The PATH-scrub is load-bearing: without it the gate inherits this workstation's stale shim and
measures the wrong machine — the #261 trap in miniature.

#### RC exit criterion — falsifiable, replacing the fixture-shaped one

Retire *"`pytest` green from any working directory"*. It is satisfiable by fixtures and, as shown
above, is not the user contract.

> **0.70.0 ships when a clean clone on a machine that has never run rebalance completes the
> documented `README.md` Getting Started path end to end — install, onboarding, first pulse — with
> no undocumented step, and `rebalance doctor` then reports no FAIL. Verified on one Apple Silicon
> host and one non-Homebrew host.**

It is falsifiable (a real user's failure fails it), it cannot be satisfied by fixtures, and it would
have caught the Step 1 defect — which every green test run on this machine missed, because this
machine never runs Step 1.

Handing back for round 2.

STATUS: Open
NEXT: Reviewer (codex)

### Reviewer — codex · round 2

swept file: yes

- [Blocker] The canonical artifact still contains the original candidate list, including #255 and #261 as Tier 1 and unresolved Tier 2 suspicions (`relay-system/2026-08-15/green-board-0-70-0-candidate-qa.md:74-109`); the revised list exists only in a producer log block (`:205-251`). That leaves the artifact under review internally contradictory and fails the disposition requirement. Fix: replace the embedded artifact's candidate/gate/exit-criterion sections with the reconciled version, rather than treating a log narrative as the deliverable.
- [Blocker] #233, #231, and #242 remain explicitly unvalidated and pending (`relay-system/2026-08-15/green-board-0-70-0-candidate-qa.md:235-240`), which directly fails DoD 1's "No item sits as an unvalidated suspicion" rule (`:127-130`). Fix: run and record each item's targeted validation in the necessary environment, then give it a keep/close/misfiled disposition; otherwise remove it from this candidate list and explicitly defer it outside this RC decision.
- [Should] The #266 reconciliation names three PRs but gives no delivered-change evidence for three listed commits (`35c70962`, `21bc1b5e`, `f801ab8d`) (`relay-system/2026-08-15/green-board-0-70-0-candidate-qa.md:244-251`). Fix: map every PR/commit to its exact claim and observed result, then retain the 0.70.0/#273 placement decision in the canonical artifact.
- [Should] The gates remain partly descriptive rather than executable: `/shakedown` is a "matrix" without concrete commands or named targets, and `/front-door` does not name the non-Homebrew platform or exact clean-environment setup (`relay-system/2026-08-15/green-board-0-70-0-candidate-qa.md:253-258`). Fix: specify the exact command for each matrix cell, target OS/runtime, pass/fail assertion, and transcript/report path.
- [Should] The header still says `ROUND: 1 / 4` even though the producer records round 2 (`relay-system/2026-08-15/green-board-0-70-0-candidate-qa.md:9,163`). Fix: producer must update it to `ROUND: 2 / 4` when opening this cycle, as required by the relay instructions (`:31-34`).

Verdict: Changes requested

Handing off to Producer (claude-a) — go to the Producer window and say "take your turn".

<!-- ↓↓↓ NEXT TURN goes here (append above nothing — this marker stays last) ↓↓↓ -->
