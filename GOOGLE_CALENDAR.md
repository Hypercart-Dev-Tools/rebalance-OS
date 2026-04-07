# Google Calendar Integration

Generate timesheet reports and daily/weekly summaries from your Google Calendar.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Prerequisites](#prerequisites)
3. [Setup](#setup)
   - [Step 1: Install dependencies](#step-1-install-dependencies)
   - [Step 2: Create a Google OAuth app](#step-2-create-a-google-oauth-app)
   - [Step 3: Authorize your device](#step-3-authorize-your-device)
   - [Step 4: Configure your calendar](#step-4-configure-your-calendar)
   - [Step 5: Sync and verify](#step-5-sync-and-verify)
4. [Report Commands](#report-commands)
5. [Configuration Reference](#configuration-reference)
6. [Scheduling Automatic Syncs](#scheduling-automatic-syncs)
7. [Troubleshooting](#troubleshooting)

---

## Quick Start

Already set up? These are the only commands you need day-to-day:

```bash
rebalance calendar-sync --days-back 30        # Pull latest events
rebalance calendar-daily-report               # Today's timesheet
rebalance calendar-weekly-report              # This week's timesheet
```

---

## Prerequisites

- Python 3.12+
- A Google account with Google Calendar
- Internet access for the one-time OAuth consent

---

## Setup

### Step 1: Install dependencies

```bash
git clone https://github.com/Hypercart-Dev-Tools/rebalance-OS.git
cd rebalance-OS
python3 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -e .
```

### Step 2: Create a Google OAuth app

You need your own OAuth credentials — this takes about 5 minutes:

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. **Create Project** → name it `rebalance` (or anything)
3. **APIs & Services → Library** → search **Google Calendar API** → **Enable**
4. **APIs & Services → Credentials** → **Create Credentials → OAuth client ID**
5. Application type: **Desktop app** → **Create**
6. Click **Download JSON** → save as `client_secret.json` somewhere safe (e.g., `~/client_secret.json`)

> Your credentials stay on your machine and are never shared or committed.

### Step 3: Authorize your device

```bash
python scripts/setup_calendar_oauth.py \
  --client-secret ~/client_secret.json \
  --test
```

- A browser window opens for Google's consent screen
- Click **Allow** (read-only calendar access)
- The script prints your available calendars and their IDs — copy the one you want to use
- Token is saved to `~/.config/gcalcli/oauth` (never inside the repo)

### Step 4: Configure your calendar

```bash
mkdir -p temp
cp calendar_config.example.json temp/calendar_config.json
```

Edit `temp/calendar_config.json`:

```json
{
  "calendar_id": "primary",
  "exclude_keywords": ["Lunch", "Break", "Admin"],
  "timezone": "America/New_York"
}
```

| Field | Description |
|-------|-------------|
| `calendar_id` | `"primary"` for your main calendar, or paste the ID from Step 3's `--test` output |
| `exclude_keywords` | Events containing these words (case-insensitive) are hidden from reports |
| `timezone` | Your local timezone in [IANA format](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones) |

> `temp/` is gitignored — your settings stay local.

### Step 5: Sync and verify

```bash
# One-time backfill (pulls 1 year of events)
rebalance calendar-sync --days-back 365

# Verify it worked
rebalance calendar-daily-report
```

You should see a markdown timesheet for today. Setup is complete.

---

## Report Commands

```bash
# Daily report
rebalance calendar-daily-report
rebalance calendar-daily-report --date 2026-04-06

# Weekly report (Sun–Sat)
rebalance calendar-weekly-report
rebalance calendar-weekly-report --date 2026-03-31

# Raw daily totals (count + hours per day)
rebalance calendar-daily-totals --days-back 30
```

**Report output includes:**
- Event list with local times (excluded items removed)
- Daily totals (event count + total duration)
- **Project Aggregator** — groups similar events by keyword and sums their time

**Project Aggregator example:**
```
### Project Aggregator (Similar Tasks)

- **Binoid**: 4 events, 7h 15m
- **Forms**: 2 events, 3h 45m
- **Slack**: 1 events, 1h 30m
```

---

## Configuration Reference

**File location:** `temp/calendar_config.json`

```json
{
  "calendar_id": "primary",
  "exclude_keywords": ["Lunch", "Break", "Admin"],
  "timezone": "America/New_York"
}
```

- **`calendar_id`** — `"primary"` works for most people. For a specific calendar (e.g., a shared work calendar), paste the ID shown by `setup_calendar_oauth.py --test`.
- **`exclude_keywords`** — Matching is case-insensitive substring. Add any event titles you want omitted from reports (they stay in the database).
- **`timezone`** — Report times are shown in this zone. UTC is preserved in the database. Find your zone at [IANA timezone list](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones).

**Changing calendars:** Update `calendar_id`, then re-sync:
```bash
rebalance calendar-sync --calendar-id <new_id> --days-back 365
```

---

## Scheduling Automatic Syncs

Keep your events fresh by running a daily sync automatically.

**macOS / Linux (cron):**
```bash
crontab -e
# Add (syncs at 6 AM daily):
0 6 * * * cd /path/to/rebalance-OS && .venv/bin/rebalance calendar-sync --days-back 30
```

**macOS (launchd) / Windows (Task Scheduler):** see `scripts/install_scheduler.sh`.

---

## Troubleshooting

| Error | Fix |
|-------|-----|
| `OAuth token not found` | Re-run Step 3 (`setup_calendar_oauth.py`) |
| `Calendar ID not found` | Run `--test` flag to list valid IDs, then update `temp/calendar_config.json` |
| `Python 3.12 required` | Use `pyenv` or `conda` to install Python 3.12+ |
| `sqlite-vec not available` | Harmless warning — calendar reports don't use vector search |
| `Connection error` | Check internet; OAuth needs access to `accounts.google.com` |
| Reports show wrong events | Verify `calendar_id` in config matches the calendar you synced |

**FAQ**

- **Is my calendar data stored online?** No — events are synced to your local `rebalance.db` only.
- **Can I change my calendar later?** Yes — edit `calendar_id` in `temp/calendar_config.json` and re-run `calendar-sync`.
- **Can I use multiple calendars?** Not in the same report. Switch calendars by updating `calendar_id` and re-syncing.
- **Do I need to share my credentials?** No — each user creates their own OAuth app and authorizes on their own device.
