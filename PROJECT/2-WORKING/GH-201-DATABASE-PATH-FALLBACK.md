---
gh_issue: 201
source: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/201
title: "Explicit --database pointing at a nonexistent path silently falls back to the canonical DB"
status: "Triage 2026-07-25 (/10days sweep). Confirmed live: resolve_database_path() unchanged since the issue was spun out of GH-198's Phase 0."
doc_type: pdda-spec
priority: P2
effort: 1
complexity: 1
risk: 1
ratings_provisional: true
created: 2026-07-25
updated: 2026-07-25
---

# GH-201 — explicit --database silently falls back to the canonical DB

Contract auto-drafted by /10days from the issue text — artifacts/lanes not yet operator-verified.

## Problem

`resolve_database_path()` (`src/rebalance/paths.py:162-194`) treats an explicit
`--database` path as candidate #1 in an ordered list, with the canonical DB appended
unconditionally as candidate #3; the resolution loop returns the first candidate that
`.exists()`, regardless of which candidate it was. If the operator passes
`--database /nonexistent/path.db`, the function silently falls through to the
canonical DB instead of raising — masking typos and pointing-at-the-wrong-copy
mistakes with no signal. `--database` is wired through 18+ CLI commands via this one
resolver, so the fix is centralized but touches a widely shared function's error
contract.

## Acceptance

- [ ] An explicit `--database` path that does not exist raises a clear error instead
      of silently resolving to the canonical DB.
- [ ] Callers that legitimately want fallback-to-canonical (if any) keep working —
      audit call sites before changing the default contract.
- [ ] `pytest -k "paths or database"` green.

## Swarm Preflight Contract

```json
{
  "target":      { "repo": ".", "ref": "development" },
  "gate":        ".venv/bin/python -m pytest tests/ -k \"paths or resolve_database\" -q",
  "fix_probes": [
    { "type": "grep_present", "path": "src/rebalance/paths.py", "pattern": "def resolve_database_path" },
    { "type": "path_absent", "path": "tests/test_paths.py" }
  ],
  "artifacts":   [ "src/rebalance/paths.py", "tests/test_paths.py" ],
  "artifacts_new": [ "tests/test_paths.py" ],
  "remediation": { "source": "issue#201", "criteria": "Explicit --database at a nonexistent path raises instead of silently falling back to the canonical DB" },
  "lanes":       { "agy_safe": [ "tests/test_paths.py" ], "orchestrator_only": [] }
}
```
