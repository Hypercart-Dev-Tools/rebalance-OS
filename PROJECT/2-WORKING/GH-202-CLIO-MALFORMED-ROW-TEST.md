---
gh_issue: 202
source: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/202
title: "CLIO projection: no malformed-source-row test (residual acceptance gap from #156)"
status: "Triage 2026-07-25 (/10days sweep). Confirmed live: named as an outstanding acceptance-checklist item in GH-156's own completed doc; still unaddressed."
doc_type: pdda-spec
priority: P3
effort: 1
complexity: 1
risk: 1
ratings_provisional: true
created: 2026-07-25
updated: 2026-07-25
---

# GH-202 — CLIO exporter has no malformed-source-row test

Contract auto-drafted by /10days from the issue text — artifacts/lanes not yet operator-verified.

## Problem

GH-156's completed acceptance checklist lists "Malformed source rows and configured
exclusions retain current semantics" as unchecked. `utils/CLIO/prompt-log-to-md.sh`
(around line 491) documents that malformed lines are silently dropped, but
`test/clio-exporter.sh`'s 10 fixture cases contain zero case constructing a
malformed/truncated JSON line or unparseable timestamp — so that documented
behavior has no test proving it's intentional and won't regress.

## Acceptance

- [ ] `test/clio-exporter.sh` gains a fixture exercising a malformed/truncated
      source row (e.g. invalid JSON, missing required field, unparseable timestamp).
- [ ] The fixture asserts the exporter's actual current behavior (drop the row,
      continue processing the rest) rather than crashing or silently corrupting output.
- [ ] `bash test/clio-exporter.sh` green.

## Swarm Preflight Contract

```json
{
  "target":      { "repo": ".", "ref": "development" },
  "gate":        "bash test/clio-exporter.sh",
  "fix_probes": [
    { "type": "grep_absent", "path": "test/clio-exporter.sh", "pattern": "malformed" }
  ],
  "artifacts":   [ "test/clio-exporter.sh" ],
  "artifacts_new": [],
  "remediation": { "source": "issue#202", "criteria": "test/clio-exporter.sh has a fixture covering a malformed source row" },
  "lanes":       { "agy_safe": [ "test/clio-exporter.sh" ], "orchestrator_only": [] }
}
```
