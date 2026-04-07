# Calendar Setup — New User Guide

Complete step-by-step guide to get the calendar timesheet feature working on your device.

## Time Required

⏱️ **~15 minutes** (mostly waiting for OAuth consent screen)

## Prerequisites

- Python 3.12+ (check: `python3 --version`)
- Git (check: `git --version`)
- macOS, Linux, or Windows with bash
- A Google account with Google Calendar

## Step 1: Clone and Install

```bash
# Clone the repo
git clone https://github.com/Hypercart-Dev-Tools/rebalance-OS.git
cd rebalance-OS

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install rebalance with dependencies
pip install -e .
```

## Step 2: Create Google OAuth App

Only needed once — creates credentials for your Google account.

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click **Create Project**
3. Name it: `rebalance` (or your choice)
4. Go to **APIs & Services** → **Library**
5. Search for **Google Calendar API**
6. Click it → **Enable**
7. Go to **APIs & Services** → **Credentials**
8. Click **Create Credentials** → **OAuth client ID**
9. Select **Desktop app** as application type
10. Click **Create**
11. A dialog appears → Click **Download JSON**
12. Save the file somewhere safe (e.g., `~/Downloads/client_secret.json`)

## Step 3: Authorize Your Device

Run the OAuth setup script. This opens your browser for consent.

```bash
python scripts/setup_calendar_oauth.py \
  --client-secret ~/Downloads/client_secret.json \
  --test
```

**What happens:**
- Browser opens → Google consent screen
- Click **Allow** (rebalance requests read-only calendar access)
- Browser returns to terminal
- Script shows your available calendars and saves token locally

**Token is stored at:** `~/.config/gcalcli/oauth` (never in the repo)

## Step 4: Create Your Config

```bash
# Copy template
cp temp/calendar_config.json.template temp/calendar_config.json

# Edit with your settings
nano temp/calendar_config.json
# or open in your editor
```

**Edit these fields:**

```json
{
  "calendar_id": "primary",  // Or use ID from --test output above
  "exclude_keywords": [
    "Lunch",
    "Break",
    "Admin"
  ],
  "timezone": "America/New_York"  // Your timezone (IANA format)
}
```

**Find your timezone:** [IANA Timezone List](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)

## Step 5: Sync Calendar Events

```bash
# One-time backfill (1 year of events)
rebalance calendar-sync --days-back 365

# Check: should show "Synced: X events"
```

## Step 6: Test the Reports

```bash
# Daily report (today)
rebalance calendar-daily-report

# Weekly report (this week)
rebalance calendar-weekly-report

# Specific date
rebalance calendar-daily-report --date 2026-04-06
```

**Expected output:** Markdown-formatted report with:
- List of events (excluded items removed)
- Daily totals (event count + duration)
- Project aggregator (grouped tasks by keyword)

## Step 7: Schedule Daily Syncs (Optional)

Automatically sync calendar daily (keep events fresh).

**macOS/Linux (cron):**
```bash
# Open crontab editor
crontab -e

# Add this line (syncs at 6 AM daily):
0 6 * * * cd /path/to/rebalance-OS && .venv/bin/rebalance calendar-sync --days-back 30
```

**Windows (Task Scheduler):**
See `scripts/install_scheduler.sh` for launchd/Windows equivalents.

## Troubleshooting

**"OAuth token not found"**
→ Run Step 3 again (OAuth authorization)

**"Calendar ID not found"**
→ Run `scripts/setup_calendar_oauth.py --client-secret ... --test` to list your calendars
→ Copy the correct ID to `temp/calendar_config.json`

**"Python 3.12 required"**
→ Use `python3 --version` to check
→ Install Python 3.12+ or use a version manager (pyenv, conda)

**"sqlite-vec not available"**
→ Harmless warning — feature still works without it
→ Calendar reports don't use vector search anyway

**"Connection error"**
→ Check internet connection
→ Google OAuth needs browser access to `accounts.google.com`

## FAQ

**Q: Is my calendar data stored online?**
A: No. Events are synced to your local `rebalance.db` file only. OAuth token is in `~/.config/gcalcli/oauth`.

**Q: Can I change my calendar later?**
A: Yes — edit `calendar_id` in `temp/calendar_config.json` and run `calendar-sync` again.

**Q: Do I need to share my credentials?**
A: No. Each user creates their own OAuth app and authorizes on their own device.

**Q: Can I use multiple calendars?**
A: Not in the same report yet. Edit `calendar_id` in config to switch between calendars.

## Next Steps

- **Review daily reports** — adjust exclude keywords as needed
- **Set up weekly review** — use `rebalance calendar-weekly-report` in a recurring meeting note
- **Integrate with Claude Desktop** — see [MCP.md](./MCP.md) for adding calendar context to AI queries

## Support

- **Setup issues** → Check [CALENDAR_PORTABILITY_AUDIT.md](./CALENDAR_PORTABILITY_AUDIT.md)
- **Report issues** → See [CALENDAR_REPORTS.md](./CALENDAR_REPORTS.md) for format and customization
- **Configuration** → See [CALENDAR_SETUP_GUIDE.md](./CALENDAR_SETUP_GUIDE.md)

---

You're all set! Start with `rebalance calendar-daily-report` to see today's summary.
