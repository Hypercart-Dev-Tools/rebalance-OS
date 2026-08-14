---
title: "3-Eyes finding: collector sync stale (77h)"
slug: collector-sync-stale-77h
status: "DRAFT (machine-authored by 3-Eyes; unverified)"
created: 2026-08-10
updated: 2026-08-10
owner: 3-Eyes (auto) · Noel (operator)
doc_type: bugfix
goal: "Triage the warn signal 3-Eyes surfaced from collector-health."
ratings_provisional: true
source_job: collector-health
severity: warn
---

# 3-Eyes finding — collector sync stale (77h)

**Severity:** warn

## Summary

last completed sync was 77h ago (threshold 26h)

## Raw signal

```
log: /Users/noelsaw/Documents/rebalance-OS/temp/logs/daily_sync_2026-08-07.log
state: complete
age_hours: 77.1
```

> Drafted by 3-Eyes. Provisional — a human owns promotion (PDDA selection rule:
> `eligible = risk<=2 AND not ratings_provisional`).
