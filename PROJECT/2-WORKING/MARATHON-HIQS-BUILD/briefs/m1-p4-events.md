---
title: "M1 p4 — events.py: the observability spine"
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
# M1 p4 — events.py: the observability spine

## Status

| What was just completed | What's next |
|---|---|
| Brief authored 2026-08-03 and preflighted — `marathon.sh --dry-run` resolves this phase in execution order. **Not yet run.** | Runs after `hiqs-m1-p2` is approved; writes to the schema it creates. |

**Canonical spec:** `HIQS-PROJECT.md` §8 (verbatim table + the status payload shape), §6.2 (degrade
rungs), L4/L6/L8 (unknown is a first-class state).

This is the most load-bearing module in Phase 0. §8 exists **before any source does** because the
plan's entire answer to the incumbent's 68 versions is "health is derived from what actually
happened, never from process archaeology".

## Build

`HiQS/hiqs/events.py`:
- `log_event(kind, source, status, payload)` — **the sole writer** to `events`. Append-only.
  `status` constrained to `ok|warn|error|unknown`.
- `status()` — the aggregator. Per-source freshness + row counts + last error tail + search mode +
  search quality + ranking quality, derived from `events` and table state. Returns the §8 JSON
  shape; `search.quality` and `ranking.quality` report **`unknown`** when never measured.

## Acceptance

- A test asserts exactly one function writes `events` (grep-pinned, per the Phase 0 gate).
- Round trip: `log_event()` → row → `status()` reads it back. If the event is not written, the test
  fails — telemetry is a contract side-effect, not optional.
- `status()` on an empty DB returns valid structured JSON with `unknown` for both quality fields
  and for search mode. **Never a default that reads healthy.**
- An unreadable probe yields `unknown`, not `ok` and not an exception (L6).
- A `status` value outside the four-token vocabulary is rejected at the write boundary.

## Do not

- Do not read process state, exit codes, or `launchctl` anywhere. §8 is explicit: health comes from
  the events table. L6 is six months of this repo's history disagreeing with the alternative.
- Do not add a second writer, a convenience wrapper that writes, or an "internal" bypass.
