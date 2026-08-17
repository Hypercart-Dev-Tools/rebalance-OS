---
title: "3-Eyes finding: collector sync degraded (2 unexplained error(s))"
slug: collector-sync-degraded-2-unexplained-error-s
status: "DRAFT (machine-authored by 3-Eyes; unverified)"
created: 2026-08-14
updated: 2026-08-14
owner: 3-Eyes (auto) · Noel (operator)
doc_type: bugfix
goal: "Triage the info signal 3-Eyes surfaced from collector-health."
ratings_provisional: true
source_job: collector-health
severity: info
---

# 3-Eyes finding — collector sync degraded (2 unexplained error(s))

**Severity:** info

## Summary

daily_sync_2026-08-14.log: sync_outcome=degraded — IncompleteRead(180405 bytes read, 43940 more expected)

## Raw signal

```
log: /Users/noelsaw/Documents/rebalance-OS/temp/logs/daily_sync_2026-08-14.log
sync_outcome: degraded
scopes: calendar, code, dashboard, email, github, next_actions, semantic, sleuth, sync, vault
errors: 2 recorded, 0 matched a known-issue rule

unsuppressed errors:
  - IncompleteRead(180405 bytes read, 43940 more expected)
  - refusing to start: only 7.5 GB available, floor is 7.7 GB
```

> Drafted by 3-Eyes. Provisional — a human owns promotion (PDDA selection rule:
> `eligible = risk<=2 AND not ratings_provisional`).
