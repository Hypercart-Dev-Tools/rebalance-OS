---
gh_issue: 167
source: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/167
title: "302 GitHub documents fetched but never projected into the semantic index"
status: "Triage 2026-07-25 (/10days sweep). Re-verified against a pre-existing, un-fired brief in PROJECT/2-WORKING/MARATHON-2026-07-21/briefs/p3-167-semantic-backfill-gap.md (authored 2026-07-21, still current)."
doc_type: pdda-spec
priority: P2
effort: 1
complexity: 2
risk: 2
ratings_provisional: true
created: 2026-07-25
updated: 2026-07-25
---

# GH-167 — 302 GitHub documents fetched but never projected into the semantic index

Contract auto-drafted by /10days, informed by the pre-existing MARATHON-2026-07-21
brief (`briefs/p3-167-semantic-backfill-gap.md`) — artifacts/lanes not yet
operator-verified against the latest code state.

## Problem

Two disagreeing queries: `github_documents_for_semantic()`
(`src/rebalance/ingest/db/semantic.py`) filters OUT rows whose repo is in
`get_github_ignored_repos()`, but the freshness-drift check in
`src/rebalance/ingest/index_ops.py` (~line 624-635, feeding
`github_documents_missing_from_semantic`) does a plain LEFT JOIN with **no**
ignored-repo filter — so ignored-repo docs always show as "missing" even when the
projection is behaving as designed. Separately, `sync_github_documents()`
(`src/rebalance/ingest/semantic_index.py`) loops over every fetched row with no
per-row try/except, so one malformed row could silently abort a whole repo's
projection. Per the prior brief's hard invariant: **characterize before patching** —
state actual findings (real gap vs. ignored-repo false-positive vs. malformed-row
abort) with evidence before writing a fix.

## Acceptance

- [ ] The `github_documents_missing_from_semantic` drift check applies the same
      ignored-repo filter as the semantic-projection query, so they agree.
- [ ] A malformed source row is skipped with a logged reason, not silently aborting
      the rest of that repo's projection.
- [ ] Findings (how many of the 302 were ignored-repo false positives vs. genuine
      gaps vs. malformed-row aborts) are stated in the doc before any fix lands.
- [ ] `pytest -k "semantic_index or index_ops"` green.

## Swarm Preflight Contract

```json
{
  "target":      { "repo": ".", "ref": "development" },
  "gate":        ".venv/bin/python -m pytest tests/ -k \"semantic_index or index_ops\" -q",
  "fix_probes": [
    { "type": "grep_present", "path": "src/rebalance/ingest/index_ops.py", "pattern": "sd\\.source_type = 'github' AND sd\\.source_pk = gd\\.source_key\\s+WHERE sd\\.id IS NULL" }
  ],
  "artifacts":   [ "src/rebalance/ingest/semantic_index.py", "src/rebalance/ingest/index_ops.py", "src/rebalance/ingest/db/semantic.py" ],
  "artifacts_new": [],
  "remediation": { "source": "issue#167", "criteria": "Missing-doc drift check and projection query agree on ignored-repo filtering; malformed rows don't abort a repo's projection" },
  "lanes":       { "agy_safe": [], "orchestrator_only": [] }
}
```
