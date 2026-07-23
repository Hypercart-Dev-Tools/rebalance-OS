---
title: "MARATHON-2026-07-21 P1 — GH-8 calendar tz day-boundary fix"
status: "Brief authored; phase not yet run"
created: 2026-07-21
updated: 2026-07-21
owner: noel
gh_issue: 8
roadmap_exempt: true
goal: >
  Marathon phase brief (harness input, not a tracked effort). Stop calendar queries from
  splitting days on the wrong boundary: Google returns offset-bearing timestamps that
  `sync_calendar()` stores raw, so `DATE(start_time)` filters slice on UTC and mis-bucket
  events near midnight local.
---

# Phase 1 — fix remaining timezone day-boundary bugs in calendar queries

Part of **GH-8**. Issue: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/8
Disjoint from every other phase in this marathon. **Artifact:** `src/rebalance/ingest/calendar.py`,
`src/rebalance/ingest/daily_report.py`, `src/rebalance/ingest/querier.py`.

## Status

| What was just completed | What's next |
|---|---|
| Brief authored 2026-07-21 for parent GH-8; marathon plan is `PROJECT/2-WORKING/MARATHON-2026-07-21/MARATHON.md` | **Not fired.** Execute as marathon phase `p1-8-calendar-tz-boundary`; disjoint write-set, so it may run in any wave. |

## The problem

Google Calendar API returns timestamps with local offsets (e.g. `2026-04-10T18:30:00-06:00`).
`sync_calendar()` stores these raw. Several query sites then filter by `DATE(start_time)`, and
SQLite's `DATE()` coerces to UTC before extracting the date — so an event near midnight local
time can be bucketed onto the wrong calendar day. Confirmed still live, current line numbers:

| File | Line | Function | Issue |
|---|---|---|---|
| `daily_report.py` | 230 (`get_day_data`, def at 211) | `WHERE DATE(start_time) >= ? AND DATE(start_time) <= ?` | boundary bug |
| `calendar.py` | 594 (`get_daily_totals`, def at 567) | same pattern | boundary bug |
| `querier.py` | 107 (`_local_now`/temporal-context helper) | `date_str + "T23:59:59"` / `"T00:00:00"` naive string comparison, no offset | boundary bug |

## ⛔ Hard invariants

- **The issue's own suggested reference file (`simple_report.py` / `_day_boundaries_utc()`) no
  longer exists in this repo** — it was removed or renamed sometime after the issue was filed
  (April 2026). Do not go looking for it; there is nothing to copy. Derive the fix directly.
- **Prefer Option B (query-side fix), not Option A (re-normalize storage).** Re-normalizing
  `sync_calendar()`'s storage to UTC needs a one-time re-sync and touches more surface than this
  phase should own. Fix the query boundary computation instead: compute local midnight for the
  target day(s) using `src/rebalance/tz_utils.py`'s `local_tz()`, convert that local midnight to
  UTC, and filter with `datetime(start_time) >= ? AND datetime(start_time) < ?` against the UTC
  bounds — not `DATE(...)`.
- **`querier.py`'s vacation-detection comparison is a separate bug shape** (naive string
  concatenation, not a `DATE()` coercion) but the same root cause (no timezone awareness). Fix it
  with the same UTC-boundary approach, not a special case.
- Do not touch `sync_calendar()`'s storage format — that's Option A, explicitly out of scope here.
- Do not touch anything in `simple_report.py`-adjacent report generators unless they share one of
  the three named functions above.

## Task

1. Add a small helper (or reuse one if this phase discovers a live equivalent to the dead
   `_day_boundaries_utc()` — grep for `boundaries` / `midnight` first) that, given a date and
   `local_tz()`, returns `(utc_start, utc_end)` for that local day.
2. Replace the `DATE(start_time)` filters in `daily_report.py:230` and `calendar.py:594` with a
   UTC-range comparison using that helper.
3. Replace `querier.py:107`'s naive string-boundary comparison with the same helper's output.
4. Update or add tests asserting an event stored with a non-UTC offset near local midnight lands
   on the correct local day (mirror the issue's own repro: an 18:30 -06:00 event and a 17:00
   -06:00 event on the same local day, one of which has a UTC date one day off).

## Acceptance

- [ ] All 3 call sites use a UTC-range boundary, not `DATE(...)` or naive string comparison.
- [ ] New/updated tests reproduce the issue's exact April 10 scenario and pass.
- [ ] `sync_calendar()`'s storage format is unchanged (Option B, not A).
- [ ] `pytest tests/ -k "calendar or daily_report or querier"` green.
- [ ] `rebalance doctor` clean.
