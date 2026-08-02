# Marathon preflight packet — gh-186-scheduler-eintr-crash

- Generated: 2026-08-02T17:46:05Z
- Mode: gh-bundle
- Sources: /Users/matthewtaylor/htdocs/rebalance-OS/PROJECT/2-WORKING/GH-186-SCHEDULER-EINTR-CRASH.md 
- Target root: /Users/matthewtaylor/htdocs/rebalance-OS (development @ 5b992a281)
- Suggested branch: `marathon/gh-186-scheduler-eintr-crash-2026-08-02` (branch_ready=false — not cut yet; ask the operator before proceeding, per GUIDING-PRINCIPLES.md §8)
- Verdict: ready
- Gate: `.venv/bin/python -m pytest tests/ -k scheduler -q`

- Artifacts: scripts/github_sync.sh,scripts/lib/scheduler_common.sh
- Suggested turn budget: `RELAY_TURN_TIMEOUT_S=300` (sized to ≈ 125 LOC across 2 artifact(s); a build that also edits tests needs headroom over the 300s default)


This packet is the producer's output. The orchestrator launches the run; the planner does not
(GUIDING-PRINCIPLES.md §8).

## Acceptance criteria — the build is DONE when these hold (inlined from the capture doc)
- [ ] A transient interpreter-bootstrap `EINTR` is retried (bounded, e.g. 1-2 retries)
- [ ] Retry is scoped to the actual interpreter-startup failure mode, not a blanket
- [ ] `rebalance doctor` / scheduler tests green.

## Scope lock — builder, do exactly this and nothing else
- Edit ONLY: `scripts/github_sync.sh,scripts/lib/scheduler_common.sh` (plus the relay file). Any other edit is reverted and FAILS the turn.
- Do NOT run the full gate (`.venv/bin/python -m pytest tests/ -k scheduler -q`) yourself — it can create files that trip containment and discard your turn. Verify with ONLY the specific test for the file(s) you changed; the harness runs the gate after your turn.
- Do NOT analyze the roadmap, file issues, or refactor adjacent code. Implement the acceptance criteria above — nothing more.

## Suggested marathon-drive.sh invocation

```bash
XYZ_HARNESS_CONTEXT=swarm XYZ_SESSION_ID=gh-186-scheduler-eintr-crash RELAY_WORKTREE_ISOLATION=1 .xyz/relay-automation/marathon-drive.sh \
  --phase-brief <packet>/packet.md \
  --reviewer agy \
  --builder codex \
  --artifact scripts/github_sync.sh,scripts/lib/scheduler_common.sh \
  --pre-advance-cmd '.venv/bin/python -m pytest tests/ -k scheduler -q' \
  --require-clean
```

## Files in this packet
- `run-candidate.json` — normalized run candidate (provenance + contract + checks)
- `freshness.json` — branch state + fix-still-required probes
- `readiness.json` — remediation readiness verdict
- `lane-plan.json` — Codex / agy / orchestrator lane assignment
- `marathon-invocation.txt` — the invocation hint above
