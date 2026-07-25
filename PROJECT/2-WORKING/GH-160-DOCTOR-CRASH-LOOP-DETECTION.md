---
gh_issue: 160
source: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/160
title: "doctor: a crash-looping KeepAlive daemon reports OK (live PID short-circuits the exit-status check)"
status: "Triage 2026-07-25 (/10days sweep). Confirmed live: no commit/PR references #160."
doc_type: pdda-spec
priority: P2
effort: 1
complexity: 2
risk: 2
ratings_provisional: true
created: 2026-07-25
updated: 2026-07-25
---

# GH-160 — doctor misreads a crash-looping KeepAlive daemon as OK

Contract auto-drafted by /10days from the issue text — artifacts/lanes not yet operator-verified.

## Problem

`_check_launchd` (`src/rebalance/doctor.py:774-795`) treats any live PID as OK
regardless of exit-status history: `if has_live_pid or is_ok_status: OK`. A
`KeepAlive`-managed launchd job that is crash-looping (repeatedly exiting non-zero
and being immediately relaunched) always has a live PID at the moment `doctor` polls
it, so it reports healthy the entire time it's actually failing. This is the same
"live PID means fine" blind spot class as GH-146 (SIGTERM misread), but for the
crash-loop case specifically — GH-146's fix did not cover it, and
`tests/test_launchd_predicate.py:39` (`test_running_daemon_with_positive_last_exit_is_ok`)
pins the current blind-spot behavior as intended.

## Acceptance

- [ ] A KeepAlive-managed job that is crash-looping (exiting non-zero repeatedly,
      being relaunched) is detected as degraded, not OK, even though its current PID
      is live.
- [ ] Existing GH-146 SIGTERM-not-a-crash handling is preserved (a live long-running
      process after a clean SIGTERM restart must still read OK).
- [ ] `pytest -k "doctor or launchd"` green, including a new regression test for the
      crash-loop case.

## Swarm Preflight Contract

```json
{
  "target":      { "repo": ".", "ref": "development" },
  "gate":        ".venv/bin/python -m pytest tests/ -k \"doctor or launchd_predicate\" -q",
  "fix_probes": [
    { "type": "grep_present", "path": "src/rebalance/doctor.py", "pattern": "has_live_pid or is_ok_status" }
  ],
  "artifacts":   [ "src/rebalance/doctor.py", "tests/test_launchd_predicate.py" ],
  "artifacts_new": [],
  "remediation": { "source": "issue#160", "criteria": "Crash-looping KeepAlive daemon reports degraded, not OK, without breaking the GH-146 SIGTERM fix" },
  "lanes":       { "agy_safe": [ "tests/test_launchd_predicate.py" ], "orchestrator_only": [] }
}
```
