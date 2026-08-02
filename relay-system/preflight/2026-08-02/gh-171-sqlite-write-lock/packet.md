# Marathon preflight packet — gh-171-sqlite-write-lock

- Generated: 2026-08-02T17:46:00Z
- Mode: gh-bundle
- Sources: /Users/matthewtaylor/htdocs/rebalance-OS/PROJECT/2-WORKING/GH-171-SQLITE-WRITE-LOCK.md 
- Target root: /Users/matthewtaylor/htdocs/rebalance-OS (development @ 5b992a281)
- Suggested branch: `marathon/gh-171-sqlite-write-lock-2026-08-02` (branch_ready=false — not cut yet; ask the operator before proceeding, per GUIDING-PRINCIPLES.md §8)
- Verdict: ready
- Gate: `.venv/bin/python -m pytest tests/ -k "github_scan or github_client or github_knowledge" -q`

- Artifacts: src/rebalance/ingest/github_knowledge.py,scripts/github_sync.sh
- Suggested turn budget: `RELAY_TURN_TIMEOUT_S=900` (sized to ≈ 1032 LOC across 2 artifact(s); a build that also edits tests needs headroom over the 300s default)


This packet is the producer's output. The orchestrator launches the run; the planner does not
(GUIDING-PRINCIPLES.md §8).

## Acceptance criteria — the build is DONE when these hold (inlined from the capture doc)
- [ ] A long `github_sync` run no longer blocks unrelated writers for its full
- [ ] No write transaction spans a network call in the touched code paths.
- [ ] `pytest -k "github_scan or github_client or github_knowledge"` green.
- [ ] `rebalance doctor` clean.

## Scope lock — builder, do exactly this and nothing else
- Edit ONLY: `src/rebalance/ingest/github_knowledge.py,scripts/github_sync.sh` (plus the relay file). Any other edit is reverted and FAILS the turn.
- Do NOT run the full gate (`.venv/bin/python -m pytest tests/ -k "github_scan or github_client or github_knowledge" -q`) yourself — it can create files that trip containment and discard your turn. Verify with ONLY the specific test for the file(s) you changed; the harness runs the gate after your turn.
- Do NOT analyze the roadmap, file issues, or refactor adjacent code. Implement the acceptance criteria above — nothing more.

## Suggested marathon-drive.sh invocation

```bash
XYZ_HARNESS_CONTEXT=swarm XYZ_SESSION_ID=gh-171-sqlite-write-lock RELAY_WORKTREE_ISOLATION=1 .xyz/relay-automation/marathon-drive.sh \
  --phase-brief <packet>/packet.md \
  --reviewer agy \
  --builder codex \
  --artifact src/rebalance/ingest/github_knowledge.py,scripts/github_sync.sh \
  --pre-advance-cmd '.venv/bin/python -m pytest tests/ -k "github_scan or github_client or github_knowledge" -q' \
  --require-clean
```

## Files in this packet
- `run-candidate.json` — normalized run candidate (provenance + contract + checks)
- `freshness.json` — branch state + fix-still-required probes
- `readiness.json` — remediation readiness verdict
- `lane-plan.json` — Codex / agy / orchestrator lane assignment
- `marathon-invocation.txt` — the invocation hint above
