# Google Calendar Setup Guide

## ✅ Authorization Complete

Your device has been authorized with Google Calendar. The OAuth token is stored at:
```
~/.config/gcalcli/oauth
```

## Available Calendars

Your account has access to these calendars:

- **Matt - Neochrome Work Schedule** (ID: `c_dih7iped3im5sescansv8uqab8@group.calendar.google.com`) — ✅ Owner access

(Plus 10 other calendars including Noel's Gmail, Travel, Errands, etc.)

## Quick Start

### 1. Initial Sync (One-time backfill)

Fetch 1 year of events from Matt's Work Schedule:

```bash
rebalance calendar-sync \
  --calendar-id c_dih7iped3im5sescansv8uqab8@group.calendar.google.com \
  --days-back 365 \
  --days-forward 7
```

### 2. View Daily Event Totals

Show combined daily event metrics (count + duration):

```bash
rebalance calendar-daily-totals --days-back 30
```

Output example:
```
📅 Daily Event Totals (last 30 days):

  2026-04-07 (Monday): 4 events, 2h 30m booked
  2026-04-06 (Sunday): 0 events, 0m booked
  2026-04-05 (Saturday): 1 event, 1h booked
  ...

📊 Summary:
  Days analyzed: 30
  Total events: 87
  Total hours: 45.5h
  Avg events/day: 2.9
  Avg hours/day: 1.5h
```

### 3. Regular Sync (Daily via cron/scheduler)

For daily updates, sync last 30 days:

```bash
rebalance calendar-sync \
  --calendar-id c_dih7iped3im5sescansv8uqab8@group.calendar.google.com \
  --days-back 30 \
  --days-forward 7
```

## Implementation Details

**New files:**
- `scripts/setup_calendar_oauth.py` — OAuth setup automation

**Extended modules:**
- `src/rebalance/ingest/calendar.py` — Added `DailyEventTotal` class and `get_daily_totals()` function
- `src/rebalance/cli.py` — Added `calendar-daily-totals` command, extended `calendar-sync` with `--calendar-id` parameter

**Database:**
- `calendar_events` table in SQLite stores: id, summary, start_time, end_time, location, attendees_json, calendar_id, status, description, fetched_at

## Next Steps

1. Run the initial sync to backfill calendar data
2. Check daily totals: `rebalance calendar-daily-totals --days-back 90`
3. Schedule regular syncs in your `scripts/daily_sync.sh` (update `calendar-sync` call to use `--calendar-id`)
4. Use calendar context in the `ask` tool for scheduling queries
