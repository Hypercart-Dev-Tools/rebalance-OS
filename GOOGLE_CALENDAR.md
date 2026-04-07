# Google Calendar — Timesheet Reports

Generate daily and weekly timesheet reports from your Google Calendar.

## Table of Contents

1. [Quick Start](#quick-start)
2. [First-Time Setup](#first-time-setup)
   - [Step 1: Get the credential file](#step-1-get-the-credential-file)
   - [Step 2: Authorize your device](#step-2-authorize-your-device)
   - [Step 3: Configure your calendar](#step-3-configure-your-calendar)
   - [Step 4: Sync and verify](#step-4-sync-and-verify)
3. [Running Reports](#running-reports)
4. [Customizing Your Config](#customizing-your-config)
5. [Keeping Events Up to Date](#keeping-events-up-to-date)
6. [Troubleshooting](#troubleshooting)

---

## Quick Start

Already set up? These are the only commands you need day-to-day:

```bash
rebalance calendar-sync --days-back 30    # Pull latest events
rebalance calendar-daily-report           # Today's timesheet
rebalance calendar-weekly-report          # This week's timesheet
```

---

## First-Time Setup

### Step 1: Get the credential file

Ask your admin for the `client_secret.json` file and save it somewhere on your machine — for example `~/client_secret.json`. This file is what gives the app permission to read your Google Calendar.

> You will not need to create anything in Google Cloud. The credential file is provided to you.

---

### Step 2: Authorize your device

Run this once to connect your Google account. It opens a browser window where you log in and click **Allow**.

```bash
python scripts/setup_calendar_oauth.py \
  --client-secret ~/client_secret.json \
  --test
```

After clicking Allow, the script will print a list of your Google Calendars and their IDs. **Copy the ID** of the calendar you want to use for timesheets — you'll need it in the next step.

> Your login token is saved locally at `~/.config/gcalcli/oauth` and is never stored in the repo.

---

### Step 3: Configure your calendar

```bash
mkdir -p temp
cp calendar_config.example.json temp/calendar_config.json
```

Open `temp/calendar_config.json` and fill in your details:

```json
{
  "calendar_id": "paste-your-calendar-id-here",
  "exclude_keywords": ["Lunch", "Break"],
  "timezone": "America/Los_Angeles"
}
```

| Field | What to put here |
|-------|-----------------|
| `calendar_id` | Paste the calendar ID printed in Step 2. Use `"primary"` for your main Google Calendar. |
| `exclude_keywords` | Event titles containing these words will be hidden from reports. Add anything you don't want tracked (e.g., "Lunch", "Check Slack"). |
| `timezone` | Your local timezone — e.g. `"America/Los_Angeles"`, `"America/New_York"`, `"America/Chicago"`. |

> This file is private to your machine and is never synced to GitHub.

---

### Step 4: Sync and verify

```bash
# Pull 1 year of events (run once to backfill)
rebalance calendar-sync --days-back 365

# Check it worked
rebalance calendar-daily-report
```

You should see a formatted timesheet for today. If you do, you're all set.

---

## Running Reports

### Daily report

```bash
rebalance calendar-daily-report                      # Today
rebalance calendar-daily-report --date 2026-04-06    # Specific date
```

### Weekly report (Sunday – Saturday)

```bash
rebalance calendar-weekly-report                     # This week
rebalance calendar-weekly-report --date 2026-03-31   # Any date in the week you want
```

### What's in each report

- **Events** — listed by time in your local timezone, with excluded items removed
- **Daily total** — event count and hours logged
- **Project Aggregator** — events grouped by keyword with combined totals

**Project Aggregator example:**

```
| Project  | Events | Hours  |
|----------|-------:|-------:|
| Binoid   | 4      | 7h 15m |
| Bloomz   | 2      | 3h 45m |
| CR       | 3      | 2h 30m |
```

---

## Customizing Your Config

Your config file lives at `temp/calendar_config.json`. It's private to your machine.

**Adding exclude keywords:**
Add any event title (or part of one) to stop it appearing in reports. Matching is case-insensitive.

```json
"exclude_keywords": ["Lunch", "Check Slack", "Blocked off", "Stand-up"]
```

**Switching to a different calendar:**
Re-run Step 2 with `--test` to see your calendar IDs, then update `calendar_id` and re-sync:

```bash
rebalance calendar-sync --days-back 365
```

**Changing your timezone:**
Common US options: `"America/Los_Angeles"`, `"America/Denver"`, `"America/Chicago"`, `"America/New_York"`

---

## Keeping Events Up to Date

Run this regularly (daily or weekly) to pull in new events:

```bash
rebalance calendar-sync --days-back 30
```

To automate it on macOS or Linux, add it to your crontab (`crontab -e`):

```
0 8 * * * cd /path/to/rebalance-OS && .venv/bin/rebalance calendar-sync --days-back 30
```

---

## Troubleshooting

| Problem | What to do |
|---------|-----------|
| Browser didn't open during setup | Re-run Step 2 — make sure you have internet access |
| Reports are empty | Check that `calendar_id` in your config matches what Step 2 printed |
| Wrong events showing up | Your `calendar_id` may be set to `"primary"` — re-run Step 2 with `--test` to find the right ID |
| Times look wrong | Update `timezone` in `temp/calendar_config.json` to your local timezone |
| Need to re-authorize | Re-run Step 2 — your previous token may have expired |

**Common questions**

- **Is my calendar data stored anywhere online?** No — events are pulled to your local machine only and never uploaded.
- **Can I change which calendar I use?** Yes — update `calendar_id` in your config and run `calendar-sync` again.
- **An event I want to hide keeps showing up** — add a word from its title to `exclude_keywords` in your config.
- **I got a new machine** — get the `client_secret.json` from your admin again and repeat Steps 2–4.
