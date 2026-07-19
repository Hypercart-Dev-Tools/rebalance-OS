# Marathon Phase coll-p3-138-job-liveness
STATUS: Open
NEXT: codex

<!-- marathon-drive: task=MARATHON-COLL-P3-138-JOB-LIVENESS-TURN builder=codex reviewer=agy round-cap=5 -->

## Phase Brief

# Phase 3 — doctor warns when a SCHEDULER.md job is not loaded

Part of **GH-138**. Issue: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/138
Wave 1, runs concurrently with p1 and p2. **Artifact: `src/rebalance/doctor.py`.**

## The problem (found the hard way, 2026-07-18)

Three jobs sat in the [SCHEDULER.md](../../../SCHEDULER.md) policy table and were **not loaded
on this device**: `health-check`, `health-check-triage`, `pulse-warning-watch`. The dashboard
reported collector warnings the whole time; nothing escalated them, because every mechanism
that escalates was absent from `launchctl`.

`pulse-warning-watch` last wrote **2026-06-04**. Every auto-filed health issue froze at
**2026-06-27/28**. Nobody noticed for six weeks.

**Why the tests stayed green:** `tests/test_scheduler_policy.py:14` declares its own scope —
*"parsed with `plistlib` — no `launchctl`, no live LaunchAgents, no network."* It validates
plist **templates**. It cannot observe installed state, and passed throughout.

The generalizable defect: **SCHEDULER.md is repo-level policy describing per-device state.**
A job can be fully specified, tested, and documented while installed on zero machines.

## ⛔ Hard invariants

- **Keep `tests/test_scheduler_policy.py` hermetic.** Do not add `launchctl` or live
  LaunchAgents reads to it. Hermeticity is correct for CI; the liveness check belongs in
  doctor, which already runs per-device. Add a *separate* test with a stubbed launchctl.
- **Table-driven.** Adding a job to SCHEDULER.md must not require editing the checker
  (Principle 3 — extend by addition). If the checker needs a hardcoded job list, it is wrong.
- **Read-only.** Doctor reports; it does not install, load, or repair. Principle 7 — *honest;
  the operator decides*. Never auto-`launchctl load`.
- **Do not edit `scripts/health_issue_reporter.py`** — that is p1's artifact, running
  concurrently.
- **Do not modify `_check_collector_freshness()`** (`doctor.py:330`) — that is p4's target.
  Add a new check; do not refactor the existing freshness path.

## Task

Add a doctor check that reads the SCHEDULER.md policy table and reports any job not currently
loaded on this device.

1. Parse the job list from SCHEDULER.md's policy table (the table beginning ~L14). Treat the
   doc as the source of truth for *which* jobs should exist.
2. Compare against live state (`launchctl list`), matching on the `com.rebalance-os.*` label.
3. Report a job present in the table but absent from launchctl as a **warning**, with a hint
   naming its installer (`scripts/install_<job>_scheduler.sh`).
4. Distinguish *not loaded* from *loaded but last-exited-nonzero* — doctor already reports the
   latter (`launchd:daily-sync — last run exited with status 1`). These are different failures
   and must read differently.

## Watch for

- **The multi-device question is genuinely open.** Every health issue ever filed carries
  `Device: noels-MacBook-Pro-14.local`, so some jobs may be *intended* to run on exactly one
  machine. A naive checker will cry wolf on every other device. Surface this as a design
  question in the relay; do not silently pick a policy. Options: a per-job "expected devices"
  column in SCHEDULER.md, or warn-not-fail with a device-scoped suppression.
- **Parsing a markdown table is brittle.** If SCHEDULER.md's format is unstable, say so —
  a machine-readable job list may be the better seam. Don't build an elaborate parser quietly.
- The local reporter run log shows this job was hand-invoked 5× on 2026-05-30/31 and never
  scheduled. "I tested it manually" reading as "it's running" is the exact failure mode this
  check exists to catch.

## Acceptance

- [ ] A job in the SCHEDULER.md policy table that is not loaded on this device surfaces as a
      doctor warning naming the job and its installer.
- [ ] The check is table-driven — adding a job to SCHEDULER.md requires no checker edit
      (demonstrate by adding a fake row in a test).
- [ ] "Not loaded" and "loaded but failing" are distinguishable in doctor's output.
- [ ] `tests/test_scheduler_policy.py` remains hermetic and unmodified in scope.
- [ ] A new regression test asserts a policy-table job absent from a **stubbed** launchctl
      list is reported — no live launchctl in tests.
- [ ] Doctor never loads, installs, or repairs a job.
- [ ] The multi-device policy question is raised explicitly in the relay with a recommendation.
- [ ] Gate: `.venv/bin/python -m pytest tests/ -k "doctor or scheduler_policy" -q` green.
- [ ] `_check_collector_freshness()` unmodified (`git diff` proves it).

---

▶ TAKE YOUR TURN (codex — BUILDER role)

You are the BUILDER for this phase. Read the phase brief above and implement it.
1. Implement the brief by creating/editing the artifact file(s): src/rebalance/doctor.py
2. Append a build block to this relay file: `### Round N · Builder · codex` summarizing what you did (files touched, key decisions).
3. Use this exact tick binary (run it from any directory): /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick claim MARATHON-COLL-P3-138-JOB-LIVENESS-TURN --agent codex --paths "phases/marathon-2026-07-18-collectors--coll-p3-138-job-liveness/RELAY.md,src/rebalance/doctor.py"
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick ping MARATHON-COLL-P3-138-JOB-LIVENESS-TURN --agent codex
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick release MARATHON-COLL-P3-138-JOB-LIVENESS-TURN --agent codex --to agy
4. Edit ONLY these paths: phases/marathon-2026-07-18-collectors--coll-p3-138-job-liveness/RELAY.md and src/rebalance/doctor.py. Do NOT run git. Do NOT touch any other file — the harness commits for you.

---

▶ TAKE YOUR TURN (agy — REVIEWER role)

You are the REVIEWER for this phase. Read the latest builder block above AND review the artifact file(s) on disk: src/rebalance/doctor.py.
1. Append a review block: `### Round N · Reviewer · agy` followed by your assessment.
2. If changes needed: add `**Verdict:** Changes requested` then: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick release MARATHON-COLL-P3-138-JOB-LIVENESS-TURN --agent agy --to codex
3. If satisfied: add `**Verdict:** Approved`, set `STATUS: Approved`, then: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick done MARATHON-COLL-P3-138-JOB-LIVENESS-TURN --agent agy
4. Use this exact tick binary (run it from any directory) for all token operations: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick
   Edit ONLY phases/marathon-2026-07-18-collectors--coll-p3-138-job-liveness/RELAY.md (your review block + STATUS). Do NOT edit the artifact yourself — request changes instead. Do NOT run git.
