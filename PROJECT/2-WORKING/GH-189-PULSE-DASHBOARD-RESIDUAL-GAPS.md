---
gh_issue: 189
source: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/189
title: "Pulse dashboard: 2 residual gaps from GH-135 (bare relative in health banner, org prefixes in repo-pie labels)"
status: "Triage 2026-07-25 (/10days sweep). Re-verified against a pre-existing, un-fired brief in PROJECT/2-WORKING/MARATHON-2026-07-21/briefs/p4-189-gh135-residual-gaps.md (authored 2026-07-21, still current)."
doc_type: pdda-spec
priority: P3
effort: 1
complexity: 1
risk: 1
ratings_provisional: true
created: 2026-07-25
updated: 2026-07-25
---

# GH-189 — 2 residual presentation gaps from the dashboard consistency pass (issue #135)

Contract auto-drafted by /10days, informed by the pre-existing MARATHON-2026-07-21
brief (`briefs/p4-189-gh135-residual-gaps.md`) — artifacts/lanes not yet
operator-verified against the latest code state.

## Problem

Two named presentation-only gaps left out of GH-135's acceptance:

1. `src/rebalance/doctor.py:1192` still builds
   `f"last scan {health.age_hours / 24:.1f}d ago"` (and the hours variant) with no
   absolute-timestamp anchor; `format_timestamp()` (`src/rebalance/tz_utils.py`) is
   the shared helper GH-135 introduced elsewhere for this and isn't used here.
2. `scripts/pulse_web.py`'s `render_repo_pie()` still feeds the full
   `repo_full_name` (org/repo) straight into repo-pie label data with no short-name
   stripping, unlike `render_open_prs()` which already does
   `pr["repo_full_name"].split("/")[-1]`.

**Note: overlaps GH-160 in `src/rebalance/doctor.py` — do not run in the same wave
as GH-160.**

## Acceptance

- [ ] Health banner shows an absolute-anchored timestamp (via `format_timestamp()`),
      not a bare relative "Nd ago".
- [ ] Repo-pie labels show short repo names (org prefix stripped), matching the
      `render_open_prs()` convention.
- [ ] No new time module or new stripping rule introduced — reuse existing helpers.
- [ ] `pytest -k "doctor or pulse_web"` green.

## Swarm Preflight Contract

```json
{
  "target":      { "repo": ".", "ref": "development" },
  "gate":        ".venv/bin/python -m pytest tests/ -k \"doctor or pulse_web\" -q",
  "fix_probes": [
    { "type": "grep_present", "path": "src/rebalance/doctor.py", "pattern": "age_hours / 24" }
  ],
  "artifacts":   [ "src/rebalance/doctor.py", "scripts/pulse_web.py" ],
  "artifacts_new": [],
  "remediation": { "source": "issue#189", "criteria": "Health banner uses format_timestamp(); repo-pie labels strip org prefix" },
  "lanes":       { "agy_safe": [ "scripts/pulse_web.py" ], "orchestrator_only": [] }
}
```
