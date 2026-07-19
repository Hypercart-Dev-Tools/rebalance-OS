# Marathon Phase sig-p3-153-severity-buckets
STATUS: Open
NEXT: codex

<!-- marathon-drive: task=MARATHON-SIG-P3-153-SEVERITY-BUCKETS-TURN-2 builder=codex reviewer=agy round-cap=7 -->

## Phase Brief

# Phase p3 — GH-153: segment collector-panel checks into notices / warnings / errors

**Issue:** https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/153
**Artifact (single contended file):** `src/rebalance/doctor.py` (also edits `src/rebalance/health.py` — the renderer)
**Reviewer:** agy
**depends_on:** sig-p2-146-launchd-predicate (shares `doctor.py`; run only after p2 has landed)

## Mantra (recite before acting)
1. VERIFY, DON'T ASSUME — read the `Check` dataclass (`doctor.py:27`), the `OK/WARN/FAIL` constants (`doctor.py:22-24`), and how `src/rebalance/health.py` renders the "collector attention needed" panel, before coding.
2. TRACE THE REAL PATH — cite `file:line` for the Check → renderer flow.
3. FALSIFY YOUR HYPOTHESIS — confirm every `Check(...)` construction site so the new field has a sane default everywhere.
4. STAY IN YOUR LANE — edit `src/rebalance/doctor.py` and `src/rebalance/health.py` (+ tests). Do NOT re-open the launchd predicate p2 fixed; build on top of it.

## Problem
The panel renders every non-OK check at one flat severity ("14 warnings"), over-stating urgency: on 2026-07-18 that was ~2 self-inflicted (restart), 5 informational (device-scoping), and only a few genuinely actionable — all identical visually.

## Task
Introduce an explicit severity taxonomy:
- Add `severity ∈ {notice, warning, error}` to the `Check` dataclass, with a safe default (`warning`) so existing emitters keep compiling.
- Classify checks:
  - **notice** — device-scoping (`scheduler:<job> not loaded on this device`), a just-restarted/running daemon, freshness inside a soft threshold.
  - **warning** — real freshness breach, missing launchd fallback (`github token keyring-only`), data stale past its soft SLA.
  - **error** — a collector genuinely not scanning, invalid auth token, a sync that has actually stopped (e.g. the #152 stale-clone condition).
- In `health.py`, group + count the panel by bucket ("N errors · N warnings · N notices"); notices muted/collapsed by default.

## Acceptance / QA gate
- [ ] `Check` carries `severity`; every construction site sets or defaults it; no emitter breaks.
- [ ] Panel groups + counts per bucket; notices muted/collapsed by default.
- [ ] Fixture/regression test: the 2026-07-18 14-item set re-buckets to roughly `errors ≤ 3 · warnings · notices`, with the restart + device-scoping items demoted to **notices**.
- [ ] Scoped selector green: `.venv/bin/python -m pytest tests/ -k "doctor or health or severity" -q`.
- [ ] Anti-goal: do not re-open p2's predicate; do not restyle the web dashboard beyond the bucket grouping.

## Notes
- Maps cleanly onto the existing `OK/WARN/FAIL` string constants — consider whether `error` reuses `FAIL` or is a distinct render level; justify from the code.

## Debug mantra (auto-triggered — 1 prior attempt(s) on this phase did not reach Approved)

Before trying again, read /Users/noelsaw/Documents/GitHub-Repos/xyz-3-agents-swarm/relay-automation/DEBUG-MANTRA.md and follow its four-step discipline: reproduce reliably, know the fail path, question the hypothesis, treat this round as a breadcrumb for the next one.
Last recorded reason (/Users/noelsaw/Documents/GitHub-Repos/rebalance-OS/phases/marathon-2026-07-18-signal-health--sig-p3-153-severity-buckets/ESCALATION.md): `cap-or-close-mismatch`. Read it before re-guessing.
---

▶ TAKE YOUR TURN (codex — BUILDER role)

You are the BUILDER for this phase. Read the phase brief above and implement it.
1. Implement the brief by creating/editing the artifact file(s): src/rebalance/doctor.py,src/rebalance/health.py
2. Append a build block to this relay file: `### Round N · Builder · codex` summarizing what you did (files touched, key decisions).
3. Use this exact tick binary (run it from any directory): /Users/noelsaw/Documents/GitHub-Repos/xyz-3-agents-swarm/bin/tick
   - /Users/noelsaw/Documents/GitHub-Repos/xyz-3-agents-swarm/bin/tick claim MARATHON-SIG-P3-153-SEVERITY-BUCKETS-TURN-2 --agent codex --paths "phases/marathon-2026-07-18-signal-health--sig-p3-153-severity-buckets/RELAY.md,src/rebalance/doctor.py,src/rebalance/health.py"
   - /Users/noelsaw/Documents/GitHub-Repos/xyz-3-agents-swarm/bin/tick ping MARATHON-SIG-P3-153-SEVERITY-BUCKETS-TURN-2 --agent codex
   - /Users/noelsaw/Documents/GitHub-Repos/xyz-3-agents-swarm/bin/tick release MARATHON-SIG-P3-153-SEVERITY-BUCKETS-TURN-2 --agent codex --to agy
4. Edit ONLY these paths: phases/marathon-2026-07-18-signal-health--sig-p3-153-severity-buckets/RELAY.md and src/rebalance/doctor.py,src/rebalance/health.py. Do NOT run git. Do NOT touch any other file — the harness commits for you.

---

▶ TAKE YOUR TURN (agy — REVIEWER role)

You are the REVIEWER for this phase. Read the latest builder block above AND review the artifact file(s) on disk: src/rebalance/doctor.py,src/rebalance/health.py.
1. Append a review block: `### Round N · Reviewer · agy` followed by your assessment.
2. If changes needed: add `**Verdict:** Changes requested` then: /Users/noelsaw/Documents/GitHub-Repos/xyz-3-agents-swarm/bin/tick release MARATHON-SIG-P3-153-SEVERITY-BUCKETS-TURN-2 --agent agy --to codex
3. If satisfied: add `**Verdict:** Approved`, set `STATUS: Approved`, then: /Users/noelsaw/Documents/GitHub-Repos/xyz-3-agents-swarm/bin/tick done MARATHON-SIG-P3-153-SEVERITY-BUCKETS-TURN-2 --agent agy
4. Use this exact tick binary (run it from any directory) for all token operations: /Users/noelsaw/Documents/GitHub-Repos/xyz-3-agents-swarm/bin/tick
   Edit ONLY phases/marathon-2026-07-18-signal-health--sig-p3-153-severity-buckets/RELAY.md (your review block + STATUS). Do NOT edit the artifact yourself — request changes instead. Do NOT run git.
