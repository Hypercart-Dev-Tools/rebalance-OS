# ESCALATION — Marathon Phase gh146-p1-exit-semantics

> **RESOLVED 2026-07-18 — this phase SUCCEEDED. Do not read this file as a failed phase.**
>
> The escalation below is real but misleading out of context: `relay-drive-exit: 0` means the
> relay itself completed cleanly and **agy approved the work**. What failed was the *pre-advance
> gate*, which `marathon-drive` defaults to `bash validate.sh` — a script that exists in the
> xyz harness repo but **not** in rebalance-OS. It exited 127 (command not found) and halted the
> chain after an otherwise successful phase.
>
> Re-run with this repo's real gate
> (`PYTHONPATH=<worktree>/src <venv>/bin/python -m pytest tests/ -k '…' -q`) and the phase passes.
>
> P1's work is merged in this branch and independently verified:
> `scripts/daily_sync.sh` gained `classify_sync_outcome()`, `tests/test_daily_sync_exit.py`
> has 4 tests, and the fail-before/pass-after property was confirmed by hand (4 pass against the
> new script, 4 fail against `a03168d`).
>
> Kept rather than deleted because it is the record of a real harness gotcha worth not
> rediscovering. See `PROJECT/2-WORKING/GH-146-HEALTH-SIGNAL-ACCURACY/MARATHON-resume-p2.yaml`.

phase: gh146-p1-exit-semantics
task: MARATHON-GH146-P1-EXIT-SEMANTICS-TURN
relay-drive-exit: 0
reason: pre-advance-failed
resolution: superseded — phase approved and shipped; gate was misconfigured, not the work
relay-file: phases/gh-146-health-signal-accuracy--gh146-p1-exit-semantics/RELAY.md
