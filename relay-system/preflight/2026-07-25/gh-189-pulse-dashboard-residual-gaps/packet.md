# Marathon preflight packet — gh-189-pulse-dashboard-residual-gaps

- Generated: 2026-07-25T06:22:25Z
- Mode: gh-bundle
- Sources: /Users/noelsaw/Documents/rebalance-OS/PROJECT/2-WORKING/GH-189-PULSE-DASHBOARD-RESIDUAL-GAPS.md 
- Target root: /Users/noelsaw/Documents/rebalance-OS (development @ b5c9e3559)
- Suggested branch: `marathon/gh-189-pulse-dashboard-residual-gaps-2026-07-25` (branch_ready=false — carve-out: risk=1/independent zone, proceed on the current branch without asking)
- Verdict: ready
- Gate: `.venv/bin/python -m pytest tests/ -k "doctor or pulse_web" -q`

- Artifacts: src/rebalance/doctor.py,scripts/pulse_web.py

- Suggested turn budget: `RELAY_TURN_TIMEOUT_S=900` (sized to ≈ 4719 LOC across 2 artifact(s); a build that also edits tests needs headroom over the 300s default)

This packet is the producer's output. The orchestrator launches the run; the planner does not
(GUIDING-PRINCIPLES.md §8).

## Acceptance criteria — the build is DONE when these hold (inlined from the capture doc)
- [ ] Health banner shows an absolute-anchored timestamp (via `format_timestamp()`),
- [ ] Repo-pie labels show short repo names (org prefix stripped), matching the
- [ ] No new time module or new stripping rule introduced — reuse existing helpers.
- [ ] `pytest -k "doctor or pulse_web"` green.

## Scope lock — builder, do exactly this and nothing else
- Edit ONLY: `src/rebalance/doctor.py,scripts/pulse_web.py` (plus the relay file). Any other edit is reverted and FAILS the turn.
- Do NOT run the full gate (`.venv/bin/python -m pytest tests/ -k "doctor or pulse_web" -q`) or any scoped/single-file variant of it yourself — even a single-file invocation can silently run the whole suite if the gate script is a compound (e.g. `a && b`) command, and any resulting artifacts trip containment as off-lane. Read the acceptance criteria and your own diff as the verification; the harness runs the real gate after your turn, outside the worktree.
- Do NOT analyze the roadmap, file issues, or refactor adjacent code. Implement the acceptance criteria above — nothing more.

## Suggested marathon-drive.sh invocation

```bash
XYZ_HARNESS_CONTEXT=swarm XYZ_SESSION_ID=gh-189-pulse-dashboard-residual-gaps .xyz/relay-automation/marathon-drive.sh \
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
