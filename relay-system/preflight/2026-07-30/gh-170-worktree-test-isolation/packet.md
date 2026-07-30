# Marathon preflight packet — gh-170-worktree-test-isolation

- Generated: 2026-07-30T20:10:43Z
- Mode: gh-bundle
- Sources: /Users/matthewtaylor/htdocs/rebalance-OS/PROJECT/2-WORKING/GH-170-WORKTREE-TEST-ISOLATION.md 
- Target root: /Users/matthewtaylor/htdocs/rebalance-OS (development @ a4d22c43e)
- Suggested branch: `marathon/gh-170-worktree-test-isolation-2026-07-30` (branch_ready=false — not cut yet; ask the operator before proceeding, per GUIDING-PRINCIPLES.md §8)
- Verdict: ready
- Gate: `.venv/bin/python -m pytest tests/ -q`

- Artifacts: conftest.py,tests/conftest.py,pyproject.toml
- Suggested turn budget: `RELAY_TURN_TIMEOUT_S=600` (sized to ≈ 234 LOC across 3 artifact(s); a build that also edits tests needs headroom over the 300s default)


This packet is the producer's output. The orchestrator launches the run; the planner does not
(GUIDING-PRINCIPLES.md §8).

## Acceptance criteria — the build is DONE when these hold (inlined from the capture doc)
- [ ] Running `pytest` from inside a linked worktree imports that worktree's own
- [ ] A regression test (or documented manual repro) proves the isolation: modify a
- [ ] No behavior change for the normal (non-worktree) case.
- [ ] `pytest tests/` green from both the main checkout and a scratch worktree.

## Scope lock — builder, do exactly this and nothing else
- Edit ONLY: `conftest.py,tests/conftest.py,pyproject.toml` (plus the relay file). Any other edit is reverted and FAILS the turn.
- Do NOT run the full gate (`.venv/bin/python -m pytest tests/ -q`) yourself — it can create files that trip containment and discard your turn. Verify with ONLY the specific test for the file(s) you changed; the harness runs the gate after your turn.
- Do NOT analyze the roadmap, file issues, or refactor adjacent code. Implement the acceptance criteria above — nothing more.

## Suggested marathon-drive.sh invocation

```bash
XYZ_HARNESS_CONTEXT=swarm XYZ_SESSION_ID=gh-170-worktree-test-isolation RELAY_WORKTREE_ISOLATION=1 .xyz/relay-automation/marathon-drive.sh \
  --phase-brief <packet>/packet.md \
  --reviewer agy \
  --builder codex \
  --artifact conftest.py,tests/conftest.py,pyproject.toml \
  --pre-advance-cmd '.venv/bin/python -m pytest tests/ -q' \
  --require-clean
```

## Files in this packet
- `run-candidate.json` — normalized run candidate (provenance + contract + checks)
- `freshness.json` — branch state + fix-still-required probes
- `readiness.json` — remediation readiness verdict
- `lane-plan.json` — Codex / agy / orchestrator lane assignment
- `marathon-invocation.txt` — the invocation hint above
