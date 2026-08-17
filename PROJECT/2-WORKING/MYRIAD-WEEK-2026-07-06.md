---
title: "Myriad — deferred parking-lot backlog (week of 2026-07-06)"
owner: noel@neochro.me
status: "Parking lot — non-critical items deferred out of agent completion messages by the /myriad skill. Not a tracked deliverable; items promote out individually when actioned."
created: 2026-07-06
updated: 2026-07-06
doc_type: backlog
roadmap_exempt: true
goal: >
  Weekly parking lot for deferred, non-critical follow-up items separated out of agent completion
  messages by the /myriad skill. Idempotent append log — the log_myriad.py helper owns writes
  (Monday-of-week resolution, fuzzy dedup, atomic append, read-back verification); do not hand-edit
  the dated item sections below.
---

# Myriad — Week of 2026-07-06

## Status

| What was just completed | What's next |
|---|---|
| Parking lot opened for the week of 2026-07-06; 1 item logged (file a Seam #4 GH issue). | Deferred by design — promote any item to a real `1-INBOX`/GH capture when actioned. The `/myriad` helper owns future appends under the dated sections. |

### 2026-07-06
- [x] File a distinct GH issue for Seam #4 (XYZ disposition overlay) so it's trackable independently of GH-102's phase list, mirroring how Seams #1-#3 map to their own scope. → filed [#122](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/122) 2026-07-07.
