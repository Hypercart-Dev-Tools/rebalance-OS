# Phase p2 — GH-146: doctor stops flagging a running/just-restarted daemon as broken

**Issue:** https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/146
**Artifact (single contended file):** `src/rebalance/doctor.py`
**Reviewer:** agy

## Mantra (recite before acting)
1. VERIFY, DON'T ASSUME — read `_check_launchd` and the surrounding launchctl-status parsing before coding.
2. TRACE THE REAL PATH — cite `file:line`.
3. FALSIFY YOUR HYPOTHESIS — confirm the exact status column semantics from `launchctl list` output the parser consumes.
4. STAY IN YOUR LANE — edit only `src/rebalance/doctor.py` (+ a test). Do NOT add the severity/bucket taxonomy (that is p3).

## Problem (verified 2026-07-18)
`_check_launchd` (`src/rebalance/doctor.py`, ~line 550-566) iterates `launchctl list` lines `pid \t status \t label` and does:
```python
if status.strip() not in ("0", "-"):
    checks.append(Check(f"launchd:{short}", WARN, f"last run exited with status {status.strip()}", ...))
```
Two defects:
1. **Ignores the live PID column.** After `launchctl kickstart -k`, a `KeepAlive` daemon shows `41142  -15  com.rebalance-os.pulse-server` — a live PID (running) with the *previous* instance's exit code. It is healthy (`curl :8767` → 200) yet gets WARNed.
2. **Treats signal-termination as failure.** `-15` is SIGTERM — the normal result of `kickstart -k`, logout, or a config reload — not a crash.

## Task
Correct the predicate:
- `OK` when the job has a **live PID** (pid column ≠ `-`), OR the last exit is `0` / `-` / a **negative** (signal) value.
- `WARN` only on a **positive non-zero** exit **AND no live PID**.
- Where a multi-source job writes its own JSON result (Root cause B intent), prefer that over the stale launchctl status if it is readily available — otherwise the PID/signal rule above is sufficient for this phase.

## Acceptance / QA gate
- [ ] Regression test: a running daemon with last-exit `-15` and a live PID reads `OK`, not `WARN`.
- [ ] A genuinely crashed job (positive non-zero exit, PID `-`) still `WARN`s.
- [ ] Negative (signal) statuses are treated as non-failures.
- [ ] Scoped selector green: `.venv/bin/python -m pytest tests/ -k "doctor or launchd" -q`.
- [ ] Anti-goal: no `severity` field / bucket taxonomy (p3 owns that); do not change unrelated checks.

## Notes
- #150 is the auto-filed symptom of this and should close once this lands.
- #146 Root cause A (`daily_sync.sh` exit-1 on transient error) is a **separate** artifact — out of scope here.
