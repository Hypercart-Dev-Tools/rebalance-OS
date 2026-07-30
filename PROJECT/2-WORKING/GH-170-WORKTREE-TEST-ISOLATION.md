---
gh_issue: 170
source: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/170
title: "Tests in a git worktree silently import the main checkout, so a green suite proves nothing"
status: "Triage 2026-07-25 (/10days sweep). Confirmed live: no root conftest.py or sys.path guard exists; #185 (canonical tracker) lists this as open and high-value."
doc_type: pdda-spec
priority: P1
effort: 1
complexity: 2
risk: 2
ratings_provisional: true
created: 2026-07-25
updated: 2026-07-25
---

# GH-170 — tests in a worktree silently import the main checkout

Contract auto-drafted by /10days from the issue text — artifacts/lanes not yet operator-verified.

## Problem

The package is installed editable from the main checkout (`pyproject.toml`
src-layout, `package-dir = {"" = "src"}`). No root `conftest.py` or `sys.path`/
`PYTHONPATH` guard exists to make a linked worktree's own `src/` take precedence, so
running `pytest` inside a worktree silently imports the main checkout's modules
instead of the worktree's changed code — a green suite in a worktree proves nothing
about the worktree's own changes. This directly undermines every
`isolation: "worktree"` marathon lane's gate check.

## Acceptance

- [ ] Running `pytest` from inside a linked worktree imports that worktree's own
      `src/` tree, not the main checkout's installed package.
- [ ] A regression test (or documented manual repro) proves the isolation: modify a
      function only in a worktree, assert the worktree's test run sees the change
      and the main checkout's test run does not.
- [ ] No behavior change for the normal (non-worktree) case.
- [ ] `pytest tests/` green from both the main checkout and a scratch worktree.

## Swarm Preflight Contract

```json
{
  "target":      { "repo": ".", "ref": "development" },
  "gate":        ".venv/bin/python -m pytest tests/ -q",
  "fix_probes": [
    { "type": "path_absent", "path": "conftest.py" }
  ],
  "artifacts":   [ "conftest.py", "tests/conftest.py", "pyproject.toml" ],
  "artifacts_new": [ "conftest.py" ],
  "remediation": { "source": "issue#170", "criteria": "pytest run inside a worktree resolves imports to that worktree's own src/, not the main checkout" },
  "lanes":       { "agy_safe": [], "orchestrator_only": [ "pyproject.toml" ] }
}
```
