# Marathon preflight packet — gh-167-semantic-index-github-gap

- Generated: 2026-07-25T06:22:19Z
- Mode: gh-bundle
- Sources: /Users/noelsaw/Documents/rebalance-OS/PROJECT/2-WORKING/GH-167-SEMANTIC-INDEX-GITHUB-GAP.md 
- Target root: /Users/noelsaw/Documents/rebalance-OS (development @ b5c9e3559)
- Suggested branch: `marathon/gh-167-semantic-index-github-gap-2026-07-25` (branch_ready=false — not cut yet; ask the operator before proceeding, per GUIDING-PRINCIPLES.md §8)
- Verdict: ready
- Gate: `.venv/bin/python -m pytest tests/ -k "semantic_index or index_ops" -q`

- Artifacts: src/rebalance/ingest/semantic_index.py,src/rebalance/ingest/index_ops.py,src/rebalance/ingest/db/semantic.py

- Suggested turn budget: `RELAY_TURN_TIMEOUT_S=900` (sized to ≈ 3337 LOC across 3 artifact(s); a build that also edits tests needs headroom over the 300s default)

This packet is the producer's output. The orchestrator launches the run; the planner does not
(GUIDING-PRINCIPLES.md §8).

## Acceptance criteria — the build is DONE when these hold (inlined from the capture doc)
- [ ] The `github_documents_missing_from_semantic` drift check applies the same
- [ ] A malformed source row is skipped with a logged reason, not silently aborting
- [ ] Findings (how many of the 302 were ignored-repo false positives vs. genuine
- [ ] `pytest -k "semantic_index or index_ops"` green.

## Scope lock — builder, do exactly this and nothing else
- Edit ONLY: `src/rebalance/ingest/semantic_index.py,src/rebalance/ingest/index_ops.py,src/rebalance/ingest/db/semantic.py` (plus the relay file). Any other edit is reverted and FAILS the turn.
- Do NOT run the full gate (`.venv/bin/python -m pytest tests/ -k "semantic_index or index_ops" -q`) or any scoped/single-file variant of it yourself — even a single-file invocation can silently run the whole suite if the gate script is a compound (e.g. `a && b`) command, and any resulting artifacts trip containment as off-lane. Read the acceptance criteria and your own diff as the verification; the harness runs the real gate after your turn, outside the worktree.
- Do NOT analyze the roadmap, file issues, or refactor adjacent code. Implement the acceptance criteria above — nothing more.

## Suggested marathon-drive.sh invocation

```bash
XYZ_HARNESS_CONTEXT=swarm XYZ_SESSION_ID=gh-167-semantic-index-github-gap .xyz/relay-automation/marathon-drive.sh \
  --phase-brief <packet>/packet.md \
  --reviewer agy \
  --builder codex \
  --artifact src/rebalance/ingest/semantic_index.py,src/rebalance/ingest/index_ops.py,src/rebalance/ingest/db/semantic.py \
  --pre-advance-cmd '.venv/bin/python -m pytest tests/ -k "semantic_index or index_ops" -q' \
  --require-clean
```

## Files in this packet
- `run-candidate.json` — normalized run candidate (provenance + contract + checks)
- `freshness.json` — branch state + fix-still-required probes
- `readiness.json` — remediation readiness verdict
- `lane-plan.json` — Codex / agy / orchestrator lane assignment
- `marathon-invocation.txt` — the invocation hint above
