# Marathon Phase p3-gh202-0802
STATUS: Open
NEXT: claude

<!-- marathon-drive: task=MARATHON-P3-GH202-0802-TURN builder=claude reviewer=agy round-cap=5 -->

## Phase Brief

# Marathon preflight packet — gh-202-clio-malformed-row-test

- Generated: 2026-08-02T17:45:58Z
- Mode: gh-bundle
- Sources: /Users/matthewtaylor/htdocs/rebalance-OS/PROJECT/2-WORKING/GH-202-CLIO-MALFORMED-ROW-TEST.md 
- Target root: /Users/matthewtaylor/htdocs/rebalance-OS (development @ 5b992a281)
- Suggested branch: `marathon/gh-202-clio-malformed-row-test-2026-08-02` (branch_ready=false — carve-out: risk=1/independent zone, proceed on the current branch without asking)
- Verdict: ready
- Gate: `bash test/clio-exporter.sh`

- Artifacts: test/clio-exporter.sh
- Suggested turn budget: `RELAY_TURN_TIMEOUT_S=600` (sized to ≈ 338 LOC across 1 artifact(s); a build that also edits tests needs headroom over the 300s default)


This packet is the producer's output. The orchestrator launches the run; the planner does not
(GUIDING-PRINCIPLES.md §8).

## Acceptance criteria — the build is DONE when these hold (inlined from the capture doc)
- [ ] `test/clio-exporter.sh` gains a fixture exercising a malformed/truncated
- [ ] The fixture asserts the exporter's actual current behavior (drop the row,
- [ ] `bash test/clio-exporter.sh` green.

## Scope lock — builder, do exactly this and nothing else
- Edit ONLY: `test/clio-exporter.sh` (plus the relay file). Any other edit is reverted and FAILS the turn.
- Do NOT run ANY test or gate yourself — not `bash test/clio-exporter.sh`, and NOT `test/clio-exporter.sh` either. Those tests create temporary git fixtures/files inside your isolated worktree, which containment treats as off-lane edits and can discard your whole turn. Read them as specs instead; the harness runs the real gate after your turn, outside the worktree.
- Do NOT analyze the roadmap, file issues, or refactor adjacent code. Implement the acceptance criteria above — nothing more.

## Suggested marathon-drive.sh invocation

```bash
XYZ_HARNESS_CONTEXT=swarm XYZ_SESSION_ID=gh-202-clio-malformed-row-test RELAY_WORKTREE_ISOLATION=1 .xyz/relay-automation/marathon-drive.sh \
  --phase-brief <packet>/packet.md \
  --reviewer agy \
  --builder codex \
  --artifact test/clio-exporter.sh \
  --pre-advance-cmd 'bash test/clio-exporter.sh' \
  --require-clean
```

## Files in this packet
- `run-candidate.json` — normalized run candidate (provenance + contract + checks)
- `freshness.json` — branch state + fix-still-required probes
- `readiness.json` — remediation readiness verdict
- `lane-plan.json` — Codex / agy / orchestrator lane assignment
- `marathon-invocation.txt` — the invocation hint above


---

▶ TAKE YOUR TURN (claude — BUILDER role)

You are the BUILDER for this phase. Read the phase brief above and implement it.
1. Implement the brief by creating/editing the artifact file(s): test/clio-exporter.sh
2. Append a build block to this relay file: `### Round N · Builder · claude` summarizing what you did (files touched, key decisions).
3. Use this exact tick binary (run it from any directory): /Users/matthewtaylor/htdocs/rebalance-OS/.xyz/bin/tick
   - /Users/matthewtaylor/htdocs/rebalance-OS/.xyz/bin/tick claim MARATHON-P3-GH202-0802-TURN --agent claude --paths "phases/10days-2026-08-02--p3-gh202-0802/RELAY.md,test/clio-exporter.sh"
   - /Users/matthewtaylor/htdocs/rebalance-OS/.xyz/bin/tick ping MARATHON-P3-GH202-0802-TURN --agent claude
   - /Users/matthewtaylor/htdocs/rebalance-OS/.xyz/bin/tick release MARATHON-P3-GH202-0802-TURN --agent claude --to agy
4. Edit ONLY these paths: phases/10days-2026-08-02--p3-gh202-0802/RELAY.md and test/clio-exporter.sh. Do NOT run git. Do NOT touch any other file — the harness commits for you.
5. HAND OFF EXPLICITLY (GH-268): after releasing the token, end your turn by naming who acts next —
   "handing off to agy — agy, take your turn." A turn that ends without that line
   leaves a human guessing whether the relay is waiting on them or has stalled. Do this EVERY round,
   not just the first.

---

▶ TAKE YOUR TURN (agy — REVIEWER role)

You are the REVIEWER for this phase. Read the latest builder block above AND review the artifact file(s) on disk: test/clio-exporter.sh. REVIEW THE WHOLE FILE, NOT JUST THE DIFF (GH-268): a beta test had this loop reach 'Approved' in two rounds while an independent audit of the same branch found 20 issues (1 critical, 4 high) — every one of them in the pre-existing code the change sat on, which nobody had read. Pre-existing defects in a file you are touching are IN SCOPE; say so explicitly if you find none. DECLARE IT: your review block MUST contain a literal 'swept file: yes' or 'swept file: no' line — without it a reviewer that skipped the sweep is indistinguishable in the transcript from one that did it and found nothing, which is exactly how those 20 issues stayed invisible.
1. Append a review block: `### Round N · Reviewer · agy` followed by your assessment.
2. If changes needed: add `**Verdict:** Changes requested` then: /Users/matthewtaylor/htdocs/rebalance-OS/.xyz/bin/tick release MARATHON-P3-GH202-0802-TURN --agent agy --to claude
3. If satisfied: add `**Verdict:** Approved`, set `STATUS: Approved`, then: /Users/matthewtaylor/htdocs/rebalance-OS/.xyz/bin/tick done MARATHON-P3-GH202-0802-TURN --agent agy
4. Use this exact tick binary (run it from any directory) for all token operations: /Users/matthewtaylor/htdocs/rebalance-OS/.xyz/bin/tick
   Edit ONLY phases/10days-2026-08-02--p3-gh202-0802/RELAY.md (your review block + STATUS). Do NOT edit the artifact yourself — request changes instead. Do NOT run git.
5. HAND OFF EXPLICITLY (GH-268): end your turn by naming who acts next — "handing off to claude —
   claude, take your turn" when requesting changes, or "relay closed, no further turn needed" when
   approving. The beta report singled this out: the Reviewer turn did not tell the user to go back to the
   Producer, so the relay looked stalled when it was simply waiting. Do this EVERY round.
