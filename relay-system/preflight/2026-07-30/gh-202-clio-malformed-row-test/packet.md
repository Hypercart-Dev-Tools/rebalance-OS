# Marathon preflight packet — gh-202-clio-malformed-row-test

- Generated: 2026-07-30T20:10:36Z
- Mode: gh-bundle
- Sources: /Users/matthewtaylor/htdocs/rebalance-OS/PROJECT/2-WORKING/GH-202-CLIO-MALFORMED-ROW-TEST.md 
- Target root: /Users/matthewtaylor/htdocs/rebalance-OS (development @ a4d22c43e)
- Suggested branch: `marathon/gh-202-clio-malformed-row-test-2026-07-30` (branch_ready=false — carve-out: risk=1/independent zone, proceed on the current branch without asking)
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
