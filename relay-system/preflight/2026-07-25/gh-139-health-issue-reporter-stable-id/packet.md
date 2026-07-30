# Marathon preflight packet — gh-139-health-issue-reporter-stable-id

- Generated: 2026-07-25T06:22:15Z
- Mode: gh-bundle
- Sources: /Users/noelsaw/Documents/rebalance-OS/PROJECT/2-WORKING/GH-139-HEALTH-ISSUE-REPORTER-STABLE-ID.md 
- Target root: /Users/noelsaw/Documents/rebalance-OS (development @ b5c9e3559)
- Suggested branch: `marathon/gh-139-health-issue-reporter-stable-id-2026-07-25` (branch_ready=false — not cut yet; ask the operator before proceeding, per GUIDING-PRINCIPLES.md §8)
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
- Do NOT run the full gate (`.venv/bin/python -m pytest tests/ -k health_issue_reporter -q`) or any scoped/single-file variant of it yourself — even a single-file invocation can silently run the whole suite if the gate script is a compound (e.g. `a && b`) command, and any resulting artifacts trip containment as off-lane. Read the acceptance criteria and your own diff as the verification; the harness runs the real gate after your turn, outside the worktree.
- Do NOT analyze the roadmap, file issues, or refactor adjacent code. Implement the acceptance criteria above — nothing more.

## Suggested marathon-drive.sh invocation

```bash
XYZ_HARNESS_CONTEXT=swarm XYZ_SESSION_ID=gh-139-health-issue-reporter-stable-id .xyz/relay-automation/marathon-drive.sh \
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
