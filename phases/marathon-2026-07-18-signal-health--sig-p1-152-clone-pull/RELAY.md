# Marathon Phase sig-p1-152-clone-pull
STATUS: Open
NEXT: codex

<!-- marathon-drive: task=MARATHON-SIG-P1-152-CLONE-PULL-TURN builder=codex reviewer=agy round-cap=5 -->

## Phase Brief

# Phase p1 — GH-152: give the git-pulse-sync export clone a pull/reconcile step

**Issue:** https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/152
**Artifact (single contended file):** `scripts/pulse_sync.sh`
**Reviewer:** agy

## Mantra (recite before acting)
1. VERIFY, DON'T ASSUME — confirm the exact current behaviour of `scripts/pulse_sync.sh` by reading it; do not infer from this brief.
2. TRACE THE REAL PATH — every claim cites `file:line` you actually read.
3. FALSIFY YOUR HYPOTHESIS — prove the "no pull step" claim against the source before coding.
4. STAY IN YOUR LANE — edit only `scripts/pulse_sync.sh` (and, if a test is required, a new test file under `tests/`). Do NOT touch `src/rebalance/doctor.py` or `health.py`.

## Problem (verified 2026-07-18)
`~/git-pulse-sync` (the file-source export clone the dashboard reads collector last-scan and the Sleuth heartbeat from) diverged from origin on **2026-07-10 06:50:45** — **86 commits ahead, 1016 behind**. `pulse_sync.sh` currently only **writes → commits → optionally pushes** (`publish_pulse(..., push=push)`, `PULSE_PUSH` gate) the local pulse file. It has **no `git pull` / `fetch` / `merge` step**, so nothing on this device reconciles the mirror with origin. Every freshness signal that reads the clone is frozen at July 10 while the collectors are actually ALIVE (`experimental/git-pulse/health-check.py`: last scan 1.0–2.5h ago).

## Task
Add a **fetch + reconcile** step so the export clone tracks origin, without discarding the local unpushed pulse-write commits.

Requirements:
- Fetch origin and integrate its commits into the local clone (rebase or merge of the auto-generated pulse-JSON commits; pick the strategy that preserves the 86 local commits and does not clobber them).
- Reconcile **before** the read that the dashboard depends on, or on a cadence that keeps the mirror fresh — justify the placement from the code.
- **No silent-happy errors** (repo rule): a failed fetch/merge must surface as a real non-zero/log-visible error, never be swallowed into an "all fresh" state.
- Idempotent and safe when already up to date (clean no-op).
- Respect the existing `PULSE_PUSH` semantics; do not change the push behaviour except as needed to add the pull side.

## Acceptance / QA gate
- [ ] A pull/reconcile step exists in `pulse_sync.sh` and is covered by a test that proves: origin commits are integrated, local pulse-write commits are preserved, no clobber.
- [ ] Fetch/merge failure is surfaced (non-zero or explicit error log), not masked.
- [ ] Idempotent when up to date.
- [ ] Scoped selector green: `.venv/bin/python -m pytest tests/ -k "pulse or sync" -q`.
- [ ] Anti-goal: no edits to `doctor.py` / signal logic / `health.py`.

## Notes
- The one-time reconciliation of the live clone (86 ahead / 1016 behind) is an operator action, out of scope for this code change.

---

▶ TAKE YOUR TURN (codex — BUILDER role)

You are the BUILDER for this phase. Read the phase brief above and implement it.
1. Implement the brief by creating/editing the artifact file(s): scripts/pulse_sync.sh
2. Append a build block to this relay file: `### Round N · Builder · codex` summarizing what you did (files touched, key decisions).
3. Use this exact tick binary (run it from any directory): /Users/noelsaw/Documents/GitHub-Repos/xyz-3-agents-swarm/bin/tick
   - /Users/noelsaw/Documents/GitHub-Repos/xyz-3-agents-swarm/bin/tick claim MARATHON-SIG-P1-152-CLONE-PULL-TURN --agent codex --paths "phases/marathon-2026-07-18-signal-health--sig-p1-152-clone-pull/RELAY.md,scripts/pulse_sync.sh"
   - /Users/noelsaw/Documents/GitHub-Repos/xyz-3-agents-swarm/bin/tick ping MARATHON-SIG-P1-152-CLONE-PULL-TURN --agent codex
   - /Users/noelsaw/Documents/GitHub-Repos/xyz-3-agents-swarm/bin/tick release MARATHON-SIG-P1-152-CLONE-PULL-TURN --agent codex --to agy
4. Edit ONLY these paths: phases/marathon-2026-07-18-signal-health--sig-p1-152-clone-pull/RELAY.md and scripts/pulse_sync.sh. Do NOT run git. Do NOT touch any other file — the harness commits for you.

---

▶ TAKE YOUR TURN (agy — REVIEWER role)

You are the REVIEWER for this phase. Read the latest builder block above AND review the artifact file(s) on disk: scripts/pulse_sync.sh.
1. Append a review block: `### Round N · Reviewer · agy` followed by your assessment.
2. If changes needed: add `**Verdict:** Changes requested` then: /Users/noelsaw/Documents/GitHub-Repos/xyz-3-agents-swarm/bin/tick release MARATHON-SIG-P1-152-CLONE-PULL-TURN --agent agy --to codex
3. If satisfied: add `**Verdict:** Approved`, set `STATUS: Approved`, then: /Users/noelsaw/Documents/GitHub-Repos/xyz-3-agents-swarm/bin/tick done MARATHON-SIG-P1-152-CLONE-PULL-TURN --agent agy
4. Use this exact tick binary (run it from any directory) for all token operations: /Users/noelsaw/Documents/GitHub-Repos/xyz-3-agents-swarm/bin/tick
   Edit ONLY phases/marathon-2026-07-18-signal-health--sig-p1-152-clone-pull/RELAY.md (your review block + STATUS). Do NOT edit the artifact yourself — request changes instead. Do NOT run git.
