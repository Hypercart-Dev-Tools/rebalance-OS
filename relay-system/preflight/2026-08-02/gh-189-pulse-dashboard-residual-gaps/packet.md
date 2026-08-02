# Marathon preflight packet — gh-189-pulse-dashboard-residual-gaps

- Generated: 2026-08-02T17:45:55Z
- Mode: gh-bundle
- Sources: /Users/matthewtaylor/htdocs/rebalance-OS/PROJECT/2-WORKING/GH-189-PULSE-DASHBOARD-RESIDUAL-GAPS.md 
- Target root: /Users/matthewtaylor/htdocs/rebalance-OS (development @ 5b992a281)
- Suggested branch: `marathon/gh-189-pulse-dashboard-residual-gaps-2026-08-02` (branch_ready=false — carve-out: risk=1/independent zone, proceed on the current branch without asking)
- Verdict: ready
- Gate: `.venv/bin/python -m pytest tests/ -k "doctor or pulse_web" -q`

- Artifacts: src/rebalance/doctor.py,scripts/pulse_web.py
- Suggested turn budget: `RELAY_TURN_TIMEOUT_S=900` (sized to ≈ 4721 LOC across 2 artifact(s); a build that also edits tests needs headroom over the 300s default)


This packet is the producer's output. The orchestrator launches the run; the planner does not
(GUIDING-PRINCIPLES.md §8).

## Acceptance criteria — the build is DONE when these hold (inlined from the capture doc)
- [ ] Health banner shows an absolute-anchored timestamp (via `format_timestamp()`),
- [ ] Repo-pie labels show short repo names (org prefix stripped), matching the
- [ ] No new time module or new stripping rule introduced — reuse existing helpers.
- [ ] `pytest -k "doctor or pulse_web"` green.

## Scope lock — builder, do exactly this and nothing else
- Edit ONLY: `src/rebalance/doctor.py,scripts/pulse_web.py` (plus the relay file). Any other edit is reverted and FAILS the turn.
- Do NOT run the full gate (`.venv/bin/python -m pytest tests/ -k "doctor or pulse_web" -q`) yourself — it can create files that trip containment and discard your turn. Verify with ONLY the specific test for the file(s) you changed; the harness runs the gate after your turn.
- Do NOT analyze the roadmap, file issues, or refactor adjacent code. Implement the acceptance criteria above — nothing more.

## Suggested marathon-drive.sh invocation

```bash
XYZ_HARNESS_CONTEXT=swarm XYZ_SESSION_ID=gh-189-pulse-dashboard-residual-gaps RELAY_WORKTREE_ISOLATION=1 .xyz/relay-automation/marathon-drive.sh \
  --phase-brief <packet>/packet.md \
  --reviewer agy \
  --builder codex \
  --artifact src/rebalance/doctor.py,scripts/pulse_web.py \
  --pre-advance-cmd '.venv/bin/python -m pytest tests/ -k "doctor or pulse_web" -q' \
  --require-clean
```

## Files in this packet
- `run-candidate.json` — normalized run candidate (provenance + contract + checks)
- `freshness.json` — branch state + fix-still-required probes
- `readiness.json` — remediation readiness verdict
- `lane-plan.json` — Codex / agy / orchestrator lane assignment
- `marathon-invocation.txt` — the invocation hint above
