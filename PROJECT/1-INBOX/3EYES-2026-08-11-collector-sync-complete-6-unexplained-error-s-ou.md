---
title: "3-Eyes finding: collector sync complete (6 unexplained error(s)) (outcome said complete)"
slug: collector-sync-complete-6-unexplained-error-s-ou
status: "DRAFT (machine-authored by 3-Eyes; unverified)"
created: 2026-08-11
updated: 2026-08-11
owner: 3-Eyes (auto) · Noel (operator)
doc_type: bugfix
goal: "Triage the info signal 3-Eyes surfaced from collector-health."
ratings_provisional: true
source_job: collector-health
severity: info
---

# 3-Eyes finding — collector sync complete (6 unexplained error(s)) (outcome said complete)

**Severity:** info

## Summary

daily_sync_2026-08-11.log: sync_outcome=complete — Remote end closed connection without response

## Raw signal

```
log: /Users/noelsaw/Documents/rebalance-OS/temp/logs/daily_sync_2026-08-11.log
sync_outcome: complete
scopes: calendar, code, dashboard, email, github, next_actions, semantic, sleuth, sync, vault
errors: 6 recorded, 0 matched a known-issue rule

unsuppressed errors:
  - Remote end closed connection without response
  - <urlopen error [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: self-signed certificate (_ssl.c:1032)>
  - <urlopen error [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: self-signed certificate (_ssl.c:1032)>
  - <urlopen error [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: self-signed certificate (_ssl.c:1032)>
  - <urlopen error [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: self-signed certificate (_ssl.c:1032)>
  - <urlopen error [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: self-signed certificate (_ssl.c:1032)>
```

> Drafted by 3-Eyes. Provisional — a human owns promotion (PDDA selection rule:
> `eligible = risk<=2 AND not ratings_provisional`).
