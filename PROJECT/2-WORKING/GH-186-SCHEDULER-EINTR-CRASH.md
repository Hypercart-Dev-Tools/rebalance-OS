---
gh_issue: 186
source: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/186
title: "health: github-sync exited with status 1 (Fatal Python error)"
status: "Triage 2026-07-25 (/10days sweep). Confirmed live: no fix landed; same crash signature recurs across other scheduler jobs' logs."
doc_type: pdda-spec
priority: P2
effort: 1
complexity: 2
risk: 2
ratings_provisional: true
created: 2026-07-25
updated: 2026-07-25
---

# GH-186 — scheduler jobs crash on a rare CPython EINTR during interpreter bootstrap

Contract auto-drafted by /10days from the issue text — artifacts/lanes not yet operator-verified.

## Problem

`scripts/github_sync.sh` invokes `$PYTHON - <<'PY' ... PY` directly with no retry.
A rare macOS/CPython `EINTR` during interpreter bootstrap
(`<frozen getpath>`, `InterruptedError: [Errno 4] Interrupted system call`) kills the
process before any application code runs, and the launchd wrapper just propagates the
non-zero exit as a hard job failure. The same crash signature recurs across other
scheduler jobs' logs (`pulse-warning-watch`, `pulse_server`, `vault_sync`), confirming
it's a systemic gap in `scripts/lib/scheduler_common.sh` / the shared invocation
pattern, not isolated to github-sync.

## Acceptance

- [ ] A transient interpreter-bootstrap `EINTR` is retried (bounded, e.g. 1-2 retries)
      rather than immediately failing the job.
- [ ] Retry is scoped to the actual interpreter-startup failure mode, not a blanket
      retry-on-any-nonzero-exit that could mask real application errors.
- [ ] `rebalance doctor` / scheduler tests green.

## Swarm Preflight Contract

```json
{
  "target":      { "repo": ".", "ref": "development" },
  "gate":        ".venv/bin/python -m pytest tests/ -k scheduler -q",
  "fix_probes": [
    { "type": "grep_absent", "path": "scripts/lib/scheduler_common.sh", "pattern": "EINTR" }
  ],
  "artifacts":   [ "scripts/github_sync.sh", "scripts/lib/scheduler_common.sh" ],
  "artifacts_new": [],
  "remediation": { "source": "issue#186", "criteria": "A rare interpreter-bootstrap EINTR is retried instead of hard-failing the scheduled job" },
  "lanes":       { "agy_safe": [], "orchestrator_only": [ "scripts/lib/scheduler_common.sh" ] }
}
```
