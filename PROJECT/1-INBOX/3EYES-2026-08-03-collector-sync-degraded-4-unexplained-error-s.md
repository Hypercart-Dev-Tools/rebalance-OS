---
title: "3-Eyes finding: collector sync degraded (4 unexplained error(s))"
slug: collector-sync-degraded-4-unexplained-error-s
status: "DRAFT (machine-authored by 3-Eyes; unverified)"
created: 2026-08-03
updated: 2026-08-03
owner: 3-Eyes (auto) · Noel (operator)
doc_type: bugfix
goal: "Triage the info signal 3-Eyes surfaced from collector-health."
ratings_provisional: true
source_job: collector-health
severity: info
---

# 3-Eyes finding — collector sync degraded (4 unexplained error(s))

**Severity:** info

## Summary

daily_sync_2026-08-03.log: sync_outcome=degraded — job 'rebalance-embed' is already running (pid 15946); lock: /Users/noelsaw/.cache/rebalance-os/locks/rebalance-embed.lock

## Raw signal

```
log: /Users/noelsaw/Documents/rebalance-OS/temp/logs/daily_sync_2026-08-03.log
sync_outcome: degraded
scopes: calendar, code, dashboard, email, github, next_actions, semantic, sleuth, sync, vault
errors: 4 recorded, 0 matched a known-issue rule

unsuppressed errors:
  - job 'rebalance-embed' is already running (pid 15946); lock: /Users/noelsaw/.cache/rebalance-os/locks/rebalance-embed.lock
  - name 'ref' is not defined
  - HTTPSConnectionPool(host='oauth2.googleapis.com', port=443): Max retries exceeded with url: /token (Caused by SSLError(SSLEOFError(8, '[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol (_ssl.c:1032)')))
  - job 'rebalance-embed' is already running (pid 15946); lock: /Users/noelsaw/.cache/rebalance-os/locks/rebalance-embed.lock
```

> Drafted by 3-Eyes. Provisional — a human owns promotion (PDDA selection rule:
> `eligible = risk<=2 AND not ratings_provisional`).
