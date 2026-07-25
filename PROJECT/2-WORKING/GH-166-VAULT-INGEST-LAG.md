---
gh_issue: 166
source: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/166
title: "Vault ingest lags the writer: ~90min drift and 3 stuck pending-embed chunks"
status: "Triage 2026-07-25 (/10days sweep). Confirmed live via mcp__rebalance__index_status: ~51min drift + 2 stuck pending-embed rows observed at triage time."
doc_type: pdda-spec
priority: P2
effort: 1
complexity: 2
risk: 1
ratings_provisional: true
created: 2026-07-25
updated: 2026-07-25
---

# GH-166 — vault ingest lag and stuck pending-embed chunks go unmonitored

Contract auto-drafted by /10days from the issue text — artifacts/lanes not yet operator-verified.

## Problem

`_SIGNAL_HEALTH_RULES['vault']` (`src/rebalance/ingest/index_ops.py`) uses a 7-day
freshness window keyed only on `last_ingested_at`, with no computed lag field
(`last_modified_in_vault - last_ingested_at`) and no threshold tight enough to catch
a 51-90 minute drift — so `signal_health.vault` never trips away from `ok` for this
class of lag. Separately, `get_index_status()`'s
`semantic_documents_pending_embed` count is a raw count with no logic distinguishing
an in-flight run's normal tail from a genuinely stuck row (confirmed live: 2 rows
pending-embed at triage time). **Note: overlaps GH-167 in the same files
(`index_ops.py`, `semantic_index.py`) — must not run in the same wave as GH-167.**

## Acceptance

- [ ] `index_status`/`doctor` surfaces vault ingest lag as a direct, degrading-health
      metric (not just a 7-day freshness window).
- [ ] Pending-embed rows stuck past a reasonable threshold are distinguished from an
      in-flight run's normal tail, with a diagnosable reason.
- [ ] `pytest -k "index_ops or vault or semantic_index"` green.

## Swarm Preflight Contract

```json
{
  "target":      { "repo": ".", "ref": "development" },
  "gate":        ".venv/bin/python -m pytest tests/ -k \"index_ops or vault_sync\" -q",
  "fix_probes": [
    { "type": "grep_absent", "path": "src/rebalance/ingest/index_ops.py", "pattern": "ingest_lag" }
  ],
  "artifacts":   [ "src/rebalance/ingest/index_ops.py", "src/rebalance/health.py" ],
  "artifacts_new": [],
  "remediation": { "source": "issue#166", "criteria": "Vault ingest lag and stuck pending-embed rows are surfaced as diagnosable, degrading health signals" },
  "lanes":       { "agy_safe": [], "orchestrator_only": [] }
}
```
