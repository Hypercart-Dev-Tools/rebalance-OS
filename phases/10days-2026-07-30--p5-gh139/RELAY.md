# Marathon Phase p5-gh139
STATUS: Open
NEXT: claude

<!-- marathon-drive: task=MARATHON-P5-GH139-TURN builder=claude reviewer=agy round-cap=5 -->

## Phase Brief

# Marathon preflight packet — gh-139-health-issue-reporter-stable-id

- Generated: 2026-07-30T20:10:38Z
- Mode: gh-bundle
- Sources: /Users/matthewtaylor/htdocs/rebalance-OS/PROJECT/2-WORKING/GH-139-HEALTH-ISSUE-REPORTER-STABLE-ID.md 
- Target root: /Users/matthewtaylor/htdocs/rebalance-OS (development @ a4d22c43e)
- Suggested branch: `marathon/gh-139-health-issue-reporter-stable-id-2026-07-30` (branch_ready=false — not cut yet; ask the operator before proceeding, per GUIDING-PRINCIPLES.md §8)
- Verdict: ready
- Gate: `.venv/bin/python -m pytest tests/ -k health_issue_reporter -q`

- Artifacts: scripts/health_issue_reporter.py,tests/test_health_issue_reporter.py
- Suggested turn budget: `RELAY_TURN_TIMEOUT_S=900` (sized to ≈ 1690 LOC across 2 artifact(s); a build that also edits tests needs headroom over the 300s default)


This packet is the producer's output. The orchestrator launches the run; the planner does not
(GUIDING-PRINCIPLES.md §8).

## Acceptance criteria — the build is DONE when these hold (inlined from the capture doc)
- [ ] Dedup key is a stable, registry-level check id (not the display title) — a
- [ ] Existing open duplicate issues (from the original 6-issue/3-machine incident)
- [ ] Detail block is refreshed on a repeat sighting, not just the occurrence counter.
- [ ] `pytest -k health_issue_reporter` green; no new duplicate-issue path introduced.

## Scope lock — builder, do exactly this and nothing else
- Edit ONLY: `scripts/health_issue_reporter.py,tests/test_health_issue_reporter.py` (plus the relay file). Any other edit is reverted and FAILS the turn.
- Do NOT run the full gate (`.venv/bin/python -m pytest tests/ -k health_issue_reporter -q`) yourself — it can create files that trip containment and discard your turn. Verify with ONLY the specific test for the file(s) you changed; the harness runs the gate after your turn.
- Do NOT analyze the roadmap, file issues, or refactor adjacent code. Implement the acceptance criteria above — nothing more.

## Suggested marathon-drive.sh invocation

```bash
XYZ_HARNESS_CONTEXT=swarm XYZ_SESSION_ID=gh-139-health-issue-reporter-stable-id RELAY_WORKTREE_ISOLATION=1 .xyz/relay-automation/marathon-drive.sh \
  --phase-brief <packet>/packet.md \
  --reviewer agy \
  --builder codex \
  --artifact scripts/health_issue_reporter.py,tests/test_health_issue_reporter.py \
  --pre-advance-cmd '.venv/bin/python -m pytest tests/ -k health_issue_reporter -q' \
  --require-clean
```

## Files in this packet
- `run-candidate.json` — normalized run candidate (provenance + contract + checks)
- `freshness.json` — branch state + fix-still-required probes
- `readiness.json` — remediation readiness verdict
- `lane-plan.json` — Codex / agy / orchestrator lane assignment
- `marathon-invocation.txt` — the invocation hint above


## Debug mantra (auto-triggered — 1 prior attempt(s) on this phase did not reach Approved)

Before trying again, read /Users/matthewtaylor/htdocs/rebalance-OS/.xyz/relay-automation/DEBUG-MANTRA.md and follow its four-step discipline: reproduce reliably, know the fail path, question the hypothesis, treat this round as a breadcrumb for the next one.

---

▶ TAKE YOUR TURN (claude — BUILDER role)

You are the BUILDER for this phase. Read the phase brief above and implement it.
1. Implement the brief by creating/editing the artifact file(s): scripts/health_issue_reporter.py,tests/test_health_issue_reporter.py
2. Append a build block to this relay file: `### Round N · Builder · claude` summarizing what you did (files touched, key decisions).
3. Use this exact tick binary (run it from any directory): /Users/matthewtaylor/htdocs/rebalance-OS/.xyz/bin/tick
   - /Users/matthewtaylor/htdocs/rebalance-OS/.xyz/bin/tick claim MARATHON-P5-GH139-TURN --agent claude --paths "phases/10days-2026-07-30--p5-gh139/RELAY.md,scripts/health_issue_reporter.py,tests/test_health_issue_reporter.py"
   - /Users/matthewtaylor/htdocs/rebalance-OS/.xyz/bin/tick ping MARATHON-P5-GH139-TURN --agent claude
   - /Users/matthewtaylor/htdocs/rebalance-OS/.xyz/bin/tick release MARATHON-P5-GH139-TURN --agent claude --to agy
4. Edit ONLY these paths: phases/10days-2026-07-30--p5-gh139/RELAY.md and scripts/health_issue_reporter.py,tests/test_health_issue_reporter.py. Do NOT run git. Do NOT touch any other file — the harness commits for you.
5. HAND OFF EXPLICITLY (GH-268): after releasing the token, end your turn by naming who acts next —
   "handing off to agy — agy, take your turn." A turn that ends without that line
   leaves a human guessing whether the relay is waiting on them or has stalled. Do this EVERY round,
   not just the first.

---

▶ TAKE YOUR TURN (agy — REVIEWER role)

You are the REVIEWER for this phase. Read the latest builder block above AND review the artifact file(s) on disk: scripts/health_issue_reporter.py,tests/test_health_issue_reporter.py. REVIEW THE WHOLE FILE, NOT JUST THE DIFF (GH-268): a beta test had this loop reach 'Approved' in two rounds while an independent audit of the same branch found 20 issues (1 critical, 4 high) — every one of them in the pre-existing code the change sat on, which nobody had read. Pre-existing defects in a file you are touching are IN SCOPE; say so explicitly if you find none. DECLARE IT: your review block MUST contain a literal 'swept file: yes' or 'swept file: no' line — without it a reviewer that skipped the sweep is indistinguishable in the transcript from one that did it and found nothing, which is exactly how those 20 issues stayed invisible.
1. Append a review block: `### Round N · Reviewer · agy` followed by your assessment.
2. If changes needed: add `**Verdict:** Changes requested` then: /Users/matthewtaylor/htdocs/rebalance-OS/.xyz/bin/tick release MARATHON-P5-GH139-TURN --agent agy --to claude
3. If satisfied: add `**Verdict:** Approved`, set `STATUS: Approved`, then: /Users/matthewtaylor/htdocs/rebalance-OS/.xyz/bin/tick done MARATHON-P5-GH139-TURN --agent agy
4. Use this exact tick binary (run it from any directory) for all token operations: /Users/matthewtaylor/htdocs/rebalance-OS/.xyz/bin/tick
   Edit ONLY phases/10days-2026-07-30--p5-gh139/RELAY.md (your review block + STATUS). Do NOT edit the artifact yourself — request changes instead. Do NOT run git.
5. HAND OFF EXPLICITLY (GH-268): end your turn by naming who acts next — "handing off to claude —
   claude, take your turn" when requesting changes, or "relay closed, no further turn needed" when
   approving. The beta report singled this out: the Reviewer turn did not tell the user to go back to the
   Producer, so the relay looked stalled when it was simply waiting. Do this EVERY round.
