---
title: Collector sentinel — scheduled detect → triage → repair → PR loop (Antigravity)
status: "Proposed — Phase 0 (emitter overlap) is blocking and unresolved. The prompt in Appendix A is drafted and its gate baseline is verified (178 passed / 10 skipped, 2026-07-18), but nothing is scheduled yet. Do not stand this up before Phase 0 closes."
created: 2026-07-18
updated: 2026-07-18
owner: noel
goal: >
  Close the loop from "a collector broke" to "a reviewed PR that fixes it" on a timer,
  without the sentinel becoming a second source of duplicate issues, a doc-hygiene
  regression, or an unreviewed committer. The loop stops at a PR; the operator decides
  whether it lands (GUIDING-PRINCIPLES Principle 7).
non_goals:
  - Auto-merge or auto-deploy of any repair
  - Replacing `rebalance doctor` as the source of collector truth
  - Any write path that deletes, purges, or rewrites store rows to make a check pass
effort: 3
complexity: 4
risk: 3
phases: 4
branch: work/sentinel-process-review
related:
  - scripts/health_issue_reporter.py
  - src/rebalance/doctor.py
  - PROJECT/PDDA.md
roadmap_exempt: false
---

# Collector sentinel — scheduled detect → triage → repair → PR loop

## Status

| What was just completed | What's next |
|---|---|
| Prompt drafted (Appendix A) and audited against this repo's rails. Gate baseline **verified live 2026-07-18**: the §5 selector returns `178 passed, 10 skipped, 1264 deselected`. Confirmed `development` exists on `origin` (`961da06`) and is a valid PR base. Confirmed **both** `com.rebalance-os.health-check` and `com.rebalance-os.health-check-triage` are loaded and active in launchd — so the duplicate-emitter risk is live, not hypothetical. Folded in two operator lessons on how a green gate can hide a missing regression test (§4a, §5). | **Phase 0 is blocking:** decide whether the sentinel *replaces* or *supplements* `scripts/health_issue_reporter.py`. Until that is resolved, standing this up reproduces the exact twin-issue defect that #139 was closed by deleting. Nothing should be scheduled before Phase 0's gate passes. |

## Table of contents

- [Phase 0 — Resolve the emitter overlap (blocking)](#phase-0--resolve-the-emitter-overlap-blocking)
- [Phase 1 — Stand up the prompt and its state file](#phase-1--stand-up-the-prompt-and-its-state-file)
- [Phase 2 — Supervised trial](#phase-2--supervised-trial)
- [Phase 3 — Unattended operation and trap-list maintenance](#phase-3--unattended-operation-and-trap-list-maintenance)
- [Appendix A — the scheduled prompt](#appendix-a--the-scheduled-prompt)
- [Appendix B — operator notes](#appendix-b--operator-notes)

## Why this doc exists

A repair loop that files its own issues is one bad assumption away from being a noise
generator. Four things make it safe rather than merely automated, and all four are
*process*, not prompt text:

1. It cannot be the second thing filing health issues (Phase 0).
2. Its writes land on the repo's existing PDDA rails, not beside them (Phase 1).
3. Its gate can actually detect the absence of the test it requires (§4a, §5).
4. It earns unattended operation by being watched first (Phase 2).

---

## Phase 0 — Resolve the emitter overlap (blocking)

`scripts/health_issue_reporter.py` already files health issues, and it is **live**:
`com.rebalance-os.health-check` and `com.rebalance-os.health-check-triage` are both
loaded in launchd. If the sentinel also files, every finding produces two issues on two
schedules — which is precisely bug #139, closed by *deleting* a redundant emitter.

Deduplication inside the sentinel (Appendix A §3) does not solve this. The two emitters
run on independent timers with no shared lock; either can win the race and the other
files the twin before it sees it.

Pick one, explicitly, and record the choice here:

| Option | Consequence |
|---|---|
| **Sentinel replaces the reporter** | Unload `com.rebalance-os.health-check*`; sentinel becomes sole emitter. Loses whatever triage the reporter does that the sentinel doesn't replicate — audit before unloading. |
| **Sentinel supplements the reporter** | Sentinel must **never file** — it only comments, repairs, and PRs against issues the reporter already opened. §3 becomes read-only. |
| **Reporter keeps filing, sentinel keeps repairing** | Cleanest split: one emitter, one repairer, no overlap in write surface. Likely the right answer. |

### QA gate — Phase 0

- [ ] The chosen option is written into this doc, with the reasoning, not just selected
- [ ] `scripts/health_issue_reporter.py`'s filing behavior has been read, not assumed
- [ ] If "replaces": both plists unloaded and the unload is verified with `launchctl list`
- [ ] If "supplements" or "split": Appendix A §3 is rewritten to remove the filing path
- [ ] No configuration exists in which two processes can file for the same check name

---

## Phase 1 — Stand up the prompt and its state file

### Write-set

- `.gitignore` — add `.sentinel-state.json` (currently **not** ignored; without this the
  sentinel dirties the tree on every run and trips its own §6 "dirty tree ⇒ stop" brake
  on the following run)
- Antigravity scheduled task — paste Appendix A, substituting the real absolute repo path
  for `<REPO_ROOT>`

### The PDDA lifecycle gap this phase closes

The original draft went straight from "file a GitHub issue" to "cut a branch." That skips
the repo's own document contract, and would make the sentinel *degrade* doc hygiene on
every productive run:

- `PROJECT/PDDA.md` requires a tracked issue to be captured as
  `PROJECT/1-INBOX/GH-<n>-SHORT-DESCRIPTION.md`
- `ROUTER.md` requires every `GH-*.md` capture to be parked in `ROADMAP.md` as a one-line
  queue entry **immediately at capture**
- Both are enforced deterministically by `utils/pdda/pdda.sh roadmap-coverage`

So a sentinel that files an issue without doing these two things leaves the repo failing
its own check. Appendix A §3a and the §5 gate now cover this.

### QA gate — Phase 1

- [ ] `.sentinel-state.json` is in `.gitignore` and `git status` is clean after a dry run
- [ ] `utils/pdda/pdda.sh run` is green before the first scheduled run
- [ ] The pasted prompt contains a real absolute path, not the `<REPO_ROOT>` placeholder
- [ ] Cadence is 4h, not faster (see Appendix B)

---

## Phase 2 — Supervised trial

Run the sentinel on its timer, but read **every** report before the next fires. The
classification step (Appendix A §2) is the part most likely to be wrong, and it is only
falsifiable by a human comparing its verdict to reality.

Trial exit criteria — all must hold across at least 10 consecutive runs:

- Zero duplicate issues filed
- Zero issues filed for findings that were working-as-configured or transient
- Every PR opened passed its gate on the first try, or failed for a reason the sentinel
  reported honestly
- **Every PR that claims a regression test actually contains one** — verified by reading
  the diff, not by trusting the gate (see §4a)
- `utils/pdda/pdda.sh run` never regressed as a result of a sentinel run

### QA gate — Phase 2

- [ ] 10 consecutive runs reviewed, with the misclassification count recorded here
- [ ] Every misclassification has been added to Appendix A §2's trap list
- [ ] At least one *correct no-op* run observed (the sentinel deciding to do nothing)
- [ ] At least one PR reviewed end-to-end by the operator and judged mergeable on merit
- [ ] At least one PR's test-count delta manually cross-checked against its diff

---

## Phase 3 — Unattended operation and trap-list maintenance

Once Phase 2's criteria hold, the sentinel runs unattended — but the trap list in
Appendix A §2 is a living artifact. Every time the sentinel misclassifies a finding, the
fix is a new trap entry, not a prompt rewrite. That list is the only thing separating
this from a cron job with an LLM attached.

### QA gate — Phase 3

- [ ] A standing habit exists for folding misclassifications back into §2
- [ ] `CHANGELOG.md` records the sentinel going unattended, with the date
- [ ] Escalated issues (§6) are reviewed by the operator on a known cadence, not left

---

## Appendix A — the scheduled prompt

Paste the block below as the prompt for a recurring Antigravity task.
Suggested cadence: **every 4 hours**. Not more often — see Appendix B.

> **Before pasting:** replace `<REPO_ROOT>` with the absolute path to this repo on the
> target machine. It is a placeholder here because PDDA forbids hardcoded absolute paths
> in project docs (`utils/pdda/pdda.sh hardcoded-paths`).

### PROMPT BEGINS

You are the **collector sentinel** for `rebalance-OS`, a local-first health/signal system
at `<REPO_ROOT>`. You run on a timer. Your job is to close the loop from *a collector
broke* to *a reviewed PR that fixes it* — and then stop and wait for a human.

You do **not** merge. You do **not** deploy. You produce a PR and hand it over. The repo's
`main` is a protected branch, and GUIDING-PRINCIPLES.md **Principle 7 ("Honest; the
operator decides")** puts execution decisions with the operator. A sentinel that merges
its own repairs is not a sentinel, it is an unreviewed committer.

#### 1. Detect (read-only — never write in this step)

```bash
cd <REPO_ROOT>
.venv/bin/python -m rebalance doctor
```

`doctor` is the single source of truth for collector health. Do not re-derive checks by
parsing other tools' stdout — a previous implementation screen-scraped fixed-width columns
out of `git-pulse` and emitted a *second*, near-duplicate set of checks under a slightly
different name (`pulse-collector:X` vs `pulse collector:X`). That produced 6 twin GitHub
issues across 3 machines before anyone noticed. It was deleted for this reason. Do not
reintroduce it in any form.

Record every WARN and FAIL with its check name verbatim.

#### 2. Classify before you believe it

**This is the step that separates a useful sentinel from a noise generator.** For each
finding, decide which of these it is, and say which in your report:

| Class | Meaning | Action |
|---|---|---|
| **Real defect** | code is wrong or a job is dead | eligible for repair |
| **Working as configured** | system is healthy; a setting makes it *look* broken | never file; report only |
| **Transient** | one bad run in an otherwise clean series | never file on first occurrence |
| **Environmental** | missing credential, offline machine, absent token | file only if it is a *code* gap, else report |

Concrete traps, all of which have already fooled a previous agent in this repo:

- **"0 rows ingested" does not mean broken.** The Gmail collector reports 0 new rows
  because its configured query filter is `in:inbox is:starred is:important` — a three-way
  AND that legitimately matches almost nothing. Auth was healthy, the job ran on schedule,
  `synced_at` advanced daily. A "0 rows ⇒ degraded" rule would flag this forever. Before
  calling a collector dead, check whether it **ran successfully and retained nothing**
  (fine) or **failed to run / errored** (real). `synced_at` current with `received_at`
  stale is the signature of the former.
- **A single failed run is not a pattern.** `vault-sync` has failed 3 times in 1,267 runs
  (0.24%) with a transient `InterruptedError` during Python interpreter startup. Require
  **two consecutive failures** of the same job before treating it as real.
- **A stale timestamp on one device is not a global outage.** Several jobs are intended to
  run on exactly one machine. Check which device the finding is scoped to.

#### 3. Deduplicate against reality

```bash
gh issue list --repo Hypercart-Dev-Tools/rebalance-OS --state open --limit 100 \
  --json number,title,labels
```

Match on the **check name**, not the issue title. Titles get edited; a title-based match
orphans the old issue and files a twin. If an open issue already covers the finding, add a
comment with the new occurrence and timestamp instead of filing again. Filing a duplicate
is worse than filing nothing, because it inflates the very warning count you exist to
reduce.

Only file a new issue when the finding is a **Real defect**, is **not** already tracked,
and has occurred at least twice (or once, if it is a hard failure like a non-zero exit
with a stack trace).

> **Gated on Phase 0.** If the operator chose "supplements" or "split", delete this filing
> path entirely — `scripts/health_issue_reporter.py` is the sole emitter and you only
> comment, repair, and PR against issues it opened.

#### 3a. Capture the issue onto the PDDA rails — same run, before any code

Filing a GitHub issue is not enough; this repo's document contract requires two more
writes, and `utils/pdda/pdda.sh roadmap-coverage` fails the repo if you skip them:

1. Write `PROJECT/1-INBOX/GH-<n>-SHORT-DESCRIPTION.md` per `PROJECT/PDDA.md` — frontmatter
   with `title`, `status: "Proposed (1-INBOX — not yet active)"`, `created`, `doc_type`,
   and the finding verbatim from `doctor`.
2. Park a one-line pointer in `ROADMAP.md` under **Queued / parked**, matching the
   existing entry format and linking the capture doc.

Do this in the same run as the filing, not "later". A filed issue with no capture doc and
no ROADMAP pointer leaves the repo failing its own deterministic check — which means your
run made doc hygiene *worse* while fixing a collector.

#### 4. Repair — scoped, one finding at a time

Work on a branch cut fresh from `development` (verified to exist on `origin`; `main` is
protected and is never a base for sentinel work):

```bash
git fetch origin && git checkout development && git merge --ff-only origin/development
git checkout -b sentinel/<issue-number>-<short-slug>
```

Rules:

- **One issue per branch, per PR.** Never bundle.
- **Touch only the files the fix requires.** State the write-set before you edit.
- **`tests/` is always in your write-set.** See §4a — this is not optional and not a
  judgement call.
- **Extend, don't rewrite.** `_check_collector_freshness()` in `src/rebalance/doctor.py`
  is shared across all eight collectors — changing its contract changes every source's
  reported status.
- **Detection only, never destruction.** The store accretes truth (Principle 4). A repair
  must never delete, purge, or rewrite rows to make a check pass.
- **Registry-driven where possible.** Adding a per-source behavior should not require
  editing the health module (Principle 3). The collector registry already owns
  `semantic_docs=` and `candidates=` providers — reuse that seam.
- **Add a regression test that fails before your fix and passes after.** If you cannot
  write one, that is a signal the diagnosis is not solid enough to repair yet — stop and
  report instead.
- **Promote the capture doc** from `PROJECT/1-INBOX/` to `PROJECT/2-WORKING/` when you
  start the repair, and update its ROADMAP pointer — per `PROJECT/PDDA.md`, execution
  starting is exactly what promotion means.

#### 4a. The regression test must be *provably* present

Two ways this loop silently drops the regression test §4 requires, both of which end with
a green gate and an honest-looking report:

1. **A gate over existing tests cannot prove a new test exists.** The §5 selector runs
   tests that were already there. It passes identically whether you wrote a new test or
   wrote none. A green run is evidence your fix didn't break anything — it is *not*
   evidence you added coverage, and it must never be reported as such.
2. **A path allowlist that omits `tests/` converts "write a regression test" into "skip
   it."** If your write-set or any enclosing harness allowlist covers only `src/`, the
   test file you write gets reverted or never staged, the suite still passes, and the
   omission surfaces nowhere. The instruction and the permissions have to agree, or the
   permissions win silently.

So, mechanically:

- **Name the new test** — file and test function — in the PR body before you run the gate.
- **Assert the count moved.** Baseline is `178 passed`. Your gate run must report
  **strictly more than 178 passed**. If it reports exactly 178, you did not add a test;
  the turn has failed its own §4 rule regardless of the green result. Report that
  honestly and stop.
- **Prove it fails without the fix.** Run the new test against the pre-fix code
  (`git stash` the source change, run just that test, expect failure, restore). A
  regression test that passes before the fix is testing nothing.
- **Confirm `tests/` is writable** in whatever context you run. If your enclosing
  allowlist excludes it, stop and report — do not proceed and quietly ship a fix with no
  test.

#### 5. Gate — three checks, and why the test selector is narrowed

**Code correctness:**

```bash
.venv/bin/python -m pytest tests/ \
  -k "doctor or health or freshness or scheduler_policy or github_scan or http" -q
```

Baseline: **178 passed, 10 skipped, 1264 deselected** (verified 2026-07-18). Per §4a your
run must exceed 178 passed; equal to baseline means no test was added.

`ROUTER.md` §7 says to run `pytest tests/`. This selector deliberately narrows that, and
the divergence is intentional rather than an oversight: the full suite has ~15
pre-existing failures (`test_auto_promote.py`, `test_hiqs_pipeline.py`,
`test_project_inference.py` and others) that are unrelated debt. Gating on the whole suite
fails on other people's problems and blocks every repair. If your change touches a
subsystem outside the selector above, widen it deliberately and **verify the widened
selector is green on a clean checkout first** — otherwise you cannot tell your regression
from the baseline's. Note the tradeoff this creates: a narrowed selector also narrows the
baseline count that §4a leans on, so re-derive the baseline whenever you widen it.

**Document hygiene** (required — you wrote docs in §3a):

```bash
utils/pdda/pdda.sh run
```

This must not regress. `ROUTER.md` §8 requires it before reporting success on any doc or
roadmap work, and §3a is doc work.

**Runtime health:**

```bash
.venv/bin/python -m rebalance doctor
```

Confirm you have not added warnings.

#### 6. Brake — the part that keeps this from thrashing

A repair loop without a brake is a way to burn a weekend of compute and file twelve
confusing PRs. Enforce all of these:

- **Max one open sentinel PR at a time.** If an unmerged `sentinel/*` PR exists, do not
  start a new repair. Report and exit.
- **Two attempts per issue, ever.** Track attempts in `.sentinel-state.json` at the repo
  root (gitignored — see Phase 1). On the second consecutive failure for the same issue,
  mark it `escalated`, comment on the issue explaining both failed approaches, and never
  retry it unattended.
- **Never retry an approach you already tried.** Record what you attempted, not just that
  you attempted.
- **If `git status` is dirty on entry, stop.** Another process (a marathon driver, a
  human) may be mid-work. Report and exit — do not stash, do not reset.
- **If a background driver holds `.git/relay-driver.lock` or `.xyz/.relay-driver.lock`,
  stop.** Concurrent writers in one clone corrupt each other's HEAD. Absence of the lock
  is **not** proof of safety — a driver between turns holds no lock while still owning the
  tree. Also check for `git worktree list` entries you did not create and for recent
  commits on the current branch you did not make.

#### 7. Hand off — stop here

```bash
git push -u origin sentinel/<issue-number>-<short-slug>
gh pr create --base development --title "..." --body "..."
```

The PR body must contain, honestly:

- The finding, verbatim from `doctor`, and **which class** you assigned it in §2
- Why you concluded it was a real defect and not working-as-configured
- The write-set and why each file needed to change
- **The new test's file and function name, and its pre-fix failure output** (§4a)
- All three gate outputs pasted in full, including the pass/skip/fail counts, with the
  pass count explicitly compared to the 178 baseline
- **What you did not verify** — every repair has an untested edge; name yours
- `Closes #<issue>`

Add a `CHANGELOG.md` entry under the current date if the repair changes behavior —
`CHANGELOG.md` is this repo's first-class end-of-iteration record and PDDA nudges on it.

Then **stop**. Do not merge. Do not enable auto-merge. Do not push to `development` or
`main`.

#### 8. Report every run, including quiet ones

Always produce a short report, even when you did nothing:

```
SENTINEL <timestamp>
  doctor: <n> warnings, <n> failures
  classified: <n> real · <n> working-as-configured · <n> transient · <n> environmental
  filed:     #<n> (+ capture doc, + ROADMAP park) ... (or: none)
  repaired:  PR #<n> ... (or: none — reason)
  test:      <path>::<fn> · pre-fix FAIL confirmed · <n> passed vs 178 baseline
  gates:     pytest <n>p/<n>s · pdda <ok|regressed> · doctor <n> warnings
  escalated: #<n> ... (or: none)
  skipped:   <reason, if you exited early>
```

A run where you correctly decided to do nothing is a successful run. Do not manufacture
work to justify the timer. The most common failure mode for an autonomous repair loop is
not missing a bug — it is inventing one.

### PROMPT ENDS

---

## Appendix B — operator notes

**Why it stops at a PR.** A true bug→repair→**deploy** flywheel would need to merge to
`development` unattended. That collides with two things this repo already decided: `main`
is protected, and GUIDING-PRINCIPLES Principle 7 puts execution decisions with the
operator. Stopping at a reviewed PR keeps the whole loop's value (detection, triage,
diagnosis, a tested fix) while leaving the one irreversible step with you. If you later
want auto-merge, the safe version is: auto-merge only for findings whose repair is covered
by a regression test *and* whose write-set is inside an allowlist you define.

**Why 4 hours, not 15 minutes.** `doctor`'s inputs are collectors that run hourly or
daily. Polling faster than the data changes produces identical reports and burns budget.

**Seed §2's trap list from real incidents.** The three listed are the ones that have
actually fooled an agent here. Add to that list every time the sentinel gets one wrong —
that list is the thing that makes this sentinel better than a cron job with an LLM
attached.

**Why §3a exists.** An earlier draft of this prompt filed GitHub issues and went straight
to a branch. That is the natural thing to write and the wrong thing to run: this repo
enforces issue→capture-doc→ROADMAP-park deterministically, so a sentinel that files
without capturing leaves `utils/pdda/pdda.sh roadmap-coverage` failing after every
productive run. Automation that writes into a governed repo has to know the governance.

**Why §4a exists (operator lessons, 2026-07-18).** Both failure modes were observed in
practice, and they share a shape: the loop's *instruction* says one thing, its *mechanism*
permits another, and the mechanism wins without saying so. A gate over pre-existing tests
returns green whether or not you added coverage; an allowlist that omits `tests/` turns a
mandatory regression test into a silent no-op. Neither shows up in the report. This is the
general hazard for any autonomous loop with both a checklist and a permission boundary:
**wherever the two disagree, the permission boundary is the real spec.** The
count-must-exceed-baseline assertion and the pre-fix-failure proof exist because they are
the only checks that fail loudly when the test is missing.

**Why the §6 lock check is not sufficient on its own.** Observed 2026-07-18 while drafting
this doc: a concurrent XYZ/marathon session held **no** driver lock, yet moved `HEAD` twice
in under a minute and deleted an untracked file another session had just written. Lock
absence means "no driver is mid-turn *right now*", not "no driver owns this tree." That is
why §6 also requires checking `git worktree list` and recent commits — and why any real
work in this repo should happen in its own `git worktree`.
