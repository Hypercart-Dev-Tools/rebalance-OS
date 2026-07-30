# Marathon preflight packet — gh-166-vault-ingest-lag

- Generated: 2026-07-30T20:10:37Z
- Mode: gh-bundle
- Sources: /Users/matthewtaylor/htdocs/rebalance-OS/PROJECT/2-WORKING/GH-166-VAULT-INGEST-LAG.md 
- Target root: /Users/matthewtaylor/htdocs/rebalance-OS (development @ a4d22c43e)
- Suggested branch: `marathon/gh-166-vault-ingest-lag-2026-07-30` (branch_ready=false — carve-out: risk=1/independent zone, proceed on the current branch without asking)
- Verdict: ready
- Gate: `.venv/bin/python -m pytest tests/ -k "index_ops or vault_sync" -q`

- Artifacts: src/rebalance/ingest/index_ops.py,src/rebalance/health.py
- Suggested turn budget: `RELAY_TURN_TIMEOUT_S=900` (sized to ≈ 2243 LOC across 2 artifact(s); a build that also edits tests needs headroom over the 300s default)


This packet is the producer's output. The orchestrator launches the run; the planner does not
(GUIDING-PRINCIPLES.md §8).

## Acceptance criteria — the build is DONE when these hold (inlined from the capture doc)
- [ ] `index_status`/`doctor` surfaces vault ingest lag as a direct, degrading-health
- [ ] Pending-embed rows stuck past a reasonable threshold are distinguished from an
- [ ] `pytest -k "index_ops or vault or semantic_index"` green.

## Scope lock — builder, do exactly this and nothing else
- Edit ONLY: `src/rebalance/ingest/index_ops.py,src/rebalance/health.py` (plus the relay file). Any other edit is reverted and FAILS the turn.
- Do NOT run the full gate (`.venv/bin/python -m pytest tests/ -k "index_ops or vault_sync" -q`) yourself — it can create files that trip containment and discard your turn. Verify with ONLY the specific test for the file(s) you changed; the harness runs the gate after your turn.
- Do NOT analyze the roadmap, file issues, or refactor adjacent code. Implement the acceptance criteria above — nothing more.

## Suggested marathon-drive.sh invocation

```bash
XYZ_HARNESS_CONTEXT=swarm XYZ_SESSION_ID=gh-166-vault-ingest-lag RELAY_WORKTREE_ISOLATION=1 .xyz/relay-automation/marathon-drive.sh \
  --phase-brief <packet>/packet.md \
  --reviewer agy \
  --builder codex \
  --artifact src/rebalance/ingest/index_ops.py,src/rebalance/health.py \
  --pre-advance-cmd '.venv/bin/python -m pytest tests/ -k "index_ops or vault_sync" -q' \
  --require-clean
```

## Files in this packet
- `run-candidate.json` — normalized run candidate (provenance + contract + checks)
- `freshness.json` — branch state + fix-still-required probes
- `readiness.json` — remediation readiness verdict
- `lane-plan.json` — Codex / agy / orchestrator lane assignment
- `marathon-invocation.txt` — the invocation hint above
