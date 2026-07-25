---
gh_issue: 139
source: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/139
title: "health_issue_reporter dedupes on title: renaming a check orphans the old issue and files a twin"
status: "Triage 2026-07-25 (/10days sweep). PR #147 (2026-07-19) deleted the duplicate-emitter code path that caused the immediate 6-issue/3-machine incident, but explicitly deferred the issue's actual named defect (registry-level stable dedup key). Remains open and reproducible."
doc_type: pdda-spec
priority: P2
effort: 1
complexity: 2
risk: 2
ratings_provisional: true
created: 2026-07-25
updated: 2026-07-25
---

# GH-139 — health_issue_reporter dedupes on title, not a stable id

Contract auto-drafted by /10days from the issue text — artifacts/lanes not yet operator-verified.

## Problem

`scripts/health_issue_reporter.py` keys open-issue dedup on the human-facing title
(`title = f"{ISSUE_TITLE_PREFIX} {check['name']}"`, then `open_issues.get(title)`).
Renaming a check's name orphans its old GitHub issue (never closed, never matched
again) and immediately files a fresh "twin" issue under the new title — the exact
incident that produced 6 duplicate issues across 3 machines. PR #147 removed a
second, redundant issue-emitter (`run_pulse_checks()`) that was doubling the effect,
but the dedup key itself is unchanged: `scripts/health_issue_reporter.py:15`'s own
docstring still says "Issues are matched by stable title." On a repeat sighting of
an already-open issue, only the `> **Seen:** N× · Last:` occurrence-counter line is
rewritten (`set_occurrence_count`); the Detail block itself is never refreshed, so a
changed root-cause detail on a re-fire goes unseen.

## Acceptance

- [ ] Dedup key is a stable, registry-level check id (not the display title) — a
      renamed check continues to match its existing open issue instead of orphaning it.
- [ ] Existing open duplicate issues (from the original 6-issue/3-machine incident)
      get a documented migration/reconciliation path, or an explicit note why they're
      left as an operator cleanup step.
- [ ] Detail block is refreshed on a repeat sighting, not just the occurrence counter.
- [ ] `pytest -k health_issue_reporter` green; no new duplicate-issue path introduced.

## Swarm Preflight Contract

```json
{
  "target":      { "repo": ".", "ref": "development" },
  "gate":        ".venv/bin/python -m pytest tests/ -k health_issue_reporter -q",
  "fix_probes": [
    { "type": "grep_present", "path": "scripts/health_issue_reporter.py", "pattern": "matched by stable title" },
    { "type": "grep_present", "path": "scripts/health_issue_reporter.py", "pattern": "open_issues\\.get" }
  ],
  "artifacts":   [ "scripts/health_issue_reporter.py", "tests/test_health_issue_reporter.py" ],
  "artifacts_new": [],
  "remediation": { "source": "issue#139", "criteria": "Dedup keyed on a stable registry check id; Detail block refreshed on repeat sighting" },
  "lanes":       { "agy_safe": [ "tests/test_health_issue_reporter.py" ], "orchestrator_only": [] }
}
```
