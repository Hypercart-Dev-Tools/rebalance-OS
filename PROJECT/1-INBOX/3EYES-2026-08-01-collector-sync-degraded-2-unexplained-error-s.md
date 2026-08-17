---
title: "3-Eyes finding: collector sync degraded (2 unexplained error(s))"
slug: collector-sync-degraded-2-unexplained-error-s
status: "DRAFT (machine-authored by 3-Eyes; unverified)"
created: 2026-08-01
updated: 2026-08-01
owner: 3-Eyes (auto) · Noel (operator)
doc_type: bugfix
goal: "Triage the critical signal 3-Eyes surfaced from collector-health."
ratings_provisional: true
source_job: collector-health
severity: critical
---

# 3-Eyes finding — collector sync degraded (2 unexplained error(s))

**Severity:** critical

## Summary

daily_sync_2026-08-01.log: sync_outcome=degraded — database is locked

## Raw signal

```
log: /Users/noelsaw/Documents/rebalance-OS/temp/logs/daily_sync_2026-08-01.log
sync_outcome: degraded
scopes: calendar, code, dashboard, email, github, next_actions, semantic, sleuth, sync, vault
errors: 2 recorded, 0 matched a known-issue rule

unsuppressed errors:
  - database is locked
  - refusing to start: memory compressor holds 16.8 GB, ceiling is 16.0 GB (the machine is already under real pressure)
```

> Drafted by 3-Eyes. Provisional — a human owns promotion (PDDA selection rule:
> `eligible = risk<=2 AND not ratings_provisional`).
