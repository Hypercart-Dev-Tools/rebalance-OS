# Calendar Daily & Weekly Reports

Generate clean, actionable markdown reports from Google Calendar with automatic filtering, project grouping, and hourly totals.

## Architecture

**DRY & SOLID design:**
- `calendar_config.py` — Single config file (gitignored) for all users. Handles exclude keywords, calendar selection, timezone.
- `calendar.py` — Event syncing (unchanged, works with any calendar_id).
- `daily_report.py` — Core daily report logic: filtering, grouping similar tasks, generating markdown.
- `weekly_report.py` — Combines daily reports into Sun-Sat format with summary.
- `cli.py` — `calendar-daily-report` and `calendar-weekly-report` commands.

## Configuration

**File:** `temp/calendar_config.json` (gitignored)

```json
{
  "calendar_id": "c_dih7iped3im5sescansv8uqab8@group.calendar.google.com",
  "exclude_keywords": [
    "Start Day earlier",
    "Check Slack",
    "Lunch",
    "Start to wind-down",
    "Post Daily Timesheet"
  ],
  "timezone": "America/Los_Angeles"
}
```

**Config fields:**
- `calendar_id` — Google Calendar ID (email or group ID). Use `rebalance calendar-list` to find available calendars.
- `exclude_keywords` — Events with these keywords (case-insensitive) are excluded from reports but still synced to DB.
- `timezone` — Local timezone for report times (e.g., "America/Los_Angeles", "America/New_York").

## Usage

### Daily Report

```bash
# Today's report
rebalance calendar-daily-report

# Specific date
rebalance calendar-daily-report --date 2026-04-06
```

**Output includes:**
- Total event count and duration
- Event list (times in local timezone, excluded items removed)
- **Project Aggregator** — groups by keyword, counts, and sums

### Weekly Report

```bash
# This week
rebalance calendar-weekly-report

# Specific week (any date in the week)
rebalance calendar-weekly-report --date 2026-03-31
```

**Output includes:**
- Daily reports for Sun-Sat
- Totals per day
- Project aggregator per day
- Weekly summary with timezone and calendar info

## Project Aggregator Grouping

Automatically groups similar event names by **most common keywords**:

Example:
```
- "Binoid checkout message removal"     → Group: "Binoid"
- "Binoid emergency"                     → Group: "Binoid"
- "Binoid SEO"                           → Group: "Binoid"
- "Binoid site setup"                    → Group: "Binoid"

Result: **Binoid**: 4 events, 7h 15m
```

**Algorithm:**
1. Extract top 5 most common words from each event (3+ char words)
2. Group by first/primary keyword (case-insensitive substring)
3. Sum event counts and durations per group
4. Sort by total duration (descending)

## Example Output

### Daily Report (April 6, 2026)

```markdown
## Monday, April 06, 2026

**Total:** 5 events, 6h 22m

### Events (Excluded items removed)

- 10:15 AM — Binoid checkout message removal
- 10:45 AM — Slack work list, github tasks updates
- 12:15 PM — CR forms issue #13
- 2:58 PM — new github issue for FAQ structured data 745
- 3:30 PM — CR forms

### Project Aggregator (Similar Tasks)

- **Forms**: 2 events, 3h 45m
- **Slack**: 1 events, 1h 30m
- **New**: 1 events, 37m
- **Binoid**: 1 events, 30m
```

## Testing

Run the test suite:

```bash
python3 test_daily_report.py
```

This syncs 30 days of calendar data and generates both daily (April 6) and weekly (March 31-April 6) reports.

## Implementation Notes

- **No external dependencies** beyond existing rebalance stack (sqlite3, google-auth, etc).
- **Graceful degradation** — calendar reports work even if sqlite-vec is unavailable.
- **Timezone-aware** — all times converted to local TZ in reports, UTC preserved in DB.
- **Filtering is non-destructive** — excluded events stay in DB, hidden only in reports.
- **Event duration calculation** — uses end_time - start_time; all-day events get 0m duration.

## Customization

**Add/remove exclude keywords:**
Edit `temp/calendar_config.json` and run reports again. No code changes needed.

**Change timezone:**
Update `timezone` field in config. Report times will adjust automatically.

**Change calendar:**
Update `calendar_id` in config, then run:
```bash
rebalance calendar-sync --calendar-id <new_id> --days-back 365
```

Then run reports as normal.

---

Created: 2026-04-07 | Status: Beta
