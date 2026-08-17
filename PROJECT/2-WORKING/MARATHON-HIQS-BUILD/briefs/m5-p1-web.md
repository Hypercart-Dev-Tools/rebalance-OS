---
title: "M5 p1 — web.py: one page, one port, zero JS"
status: "Brief authored; phase not yet run"
created: 2026-08-03
updated: 2026-08-03
owner: noel
gh_issue: TBA
roadmap_exempt: true
doc_type: project
goal: >
  Marathon phase brief (harness input, not a tracked effort). Builds one module of the HiQS
  v1.0 core against the contract in PROJECT/2-WORKING/HIQS-PROJECT.md, which stays canonical.
---
# M5 p1 — web.py: one page

## Status

| What was just completed | What's next |
|---|---|
| Brief authored 2026-08-03 and preflighted — `marathon.sh --dry-run` resolves this phase in execution order. **Not yet run.** | Runs after **operator checkpoint B**. Fire M5 with `--builder codex`. |

**Canonical spec:** `HIQS-PROJECT.md` §10, §7 (the ranking it renders), §11 (~150 LOC), L10.

## Build

`HiQS/hiqs/web.py` — `hiqs serve` → **one** localhost page on `127.0.0.1:8790`, stdlib
`http.server`, **zero JS**, server-rendered, meta-refresh:
- next-actions ranking with receipts at top (source, author, time, link — all four, as fields)
- per-source health strip
- last-sync line
- search mode + last measured search quality + last measured ranking quality
- a `/refresh` link that triggers a sync and redirects back — the entire interactive layer

## Acceptance

- **One server, one port, one route table (L10).** A test greps for a second `http.server` handler
  and finds none. The incumbent's `pulse_server.py`/`web.py` route drift bit twice and is *still
  live there* — this is the lesson HiQS adopts from an open defect, not a closed one.
- **The page renders the persisted ranking; it does not re-rank.** Asserted, not assumed (L1).
- **Loopback only:** binds `127.0.0.1` and refuses a non-loopback `Host`/origin. Verified by an
  actual request that fails, not by reading the bind address.
- Unmeasured quality renders as `unknown`, never blank and never a default that reads healthy.
- Zero JavaScript in the served HTML — asserted by a test.

## Do not

- Do not add a second server, a second port, an API surface, or a websocket.
- Do not add client-side JS "just for the refresh". Meta-refresh plus a link is the design.
