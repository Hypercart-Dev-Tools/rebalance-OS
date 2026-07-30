# Marathon preflight packet — gh-160-doctor-crash-loop-detection

- Generated: 2026-07-30T20:10:39Z
- Mode: gh-bundle
- Sources: /Users/matthewtaylor/htdocs/rebalance-OS/PROJECT/2-WORKING/GH-160-DOCTOR-CRASH-LOOP-DETECTION.md 
- Target root: /Users/matthewtaylor/htdocs/rebalance-OS (development @ a4d22c43e)
- Suggested branch: `marathon/gh-160-doctor-crash-loop-detection-2026-07-30` (branch_ready=false — not cut yet; ask the operator before proceeding, per GUIDING-PRINCIPLES.md §8)
- Verdict: ready
- Gate: `.venv/bin/python -m pytest tests/ -k "doctor or launchd_predicate" -q`

- Artifacts: src/rebalance/doctor.py,tests/test_launchd_predicate.py
- Suggested turn budget: `RELAY_TURN_TIMEOUT_S=900` (sized to ≈ 1536 LOC across 2 artifact(s); a build that also edits tests needs headroom over the 300s default)


This packet is the producer's output. The orchestrator launches the run; the planner does not
(GUIDING-PRINCIPLES.md §8).

## Acceptance criteria — the build is DONE when these hold (inlined from the capture doc)
- [ ] A KeepAlive-managed job that is crash-looping (exiting non-zero repeatedly,
- [ ] Existing GH-146 SIGTERM-not-a-crash handling is preserved (a live long-running
- [ ] `pytest -k "doctor or launchd"` green, including a new regression test for the

## Scope lock — builder, do exactly this and nothing else
- Edit ONLY: `src/rebalance/doctor.py,tests/test_launchd_predicate.py` (plus the relay file). Any other edit is reverted and FAILS the turn.
- Do NOT run the full gate (`.venv/bin/python -m pytest tests/ -k "doctor or launchd_predicate" -q`) yourself — it can create files that trip containment and discard your turn. Verify with ONLY the specific test for the file(s) you changed; the harness runs the gate after your turn.
- Do NOT analyze the roadmap, file issues, or refactor adjacent code. Implement the acceptance criteria above — nothing more.

## Suggested marathon-drive.sh invocation

```bash
XYZ_HARNESS_CONTEXT=swarm XYZ_SESSION_ID=gh-160-doctor-crash-loop-detection RELAY_WORKTREE_ISOLATION=1 .xyz/relay-automation/marathon-drive.sh \
  --phase-brief <packet>/packet.md \
  --reviewer agy \
  --builder codex \
  --artifact src/rebalance/doctor.py,tests/test_launchd_predicate.py \
  --pre-advance-cmd '.venv/bin/python -m pytest tests/ -k "doctor or launchd_predicate" -q' \
  --require-clean
```

## Files in this packet
- `run-candidate.json` — normalized run candidate (provenance + contract + checks)
- `freshness.json` — branch state + fix-still-required probes
- `readiness.json` — remediation readiness verdict
- `lane-plan.json` — Codex / agy / orchestrator lane assignment
- `marathon-invocation.txt` — the invocation hint above
