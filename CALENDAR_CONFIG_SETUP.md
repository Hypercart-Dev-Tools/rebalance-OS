# Calendar Configuration Setup

Quick setup for calendar daily/weekly reports.

## Step 1: Create temp folder

```bash
mkdir -p temp
```

## Step 2: Copy example config

```bash
cp calendar_config.example.json temp/calendar_config.json
```

## Step 3: Edit your config

```bash
nano temp/calendar_config.json
# or open in your editor of choice
```

**Fields to customize:**

- `calendar_id` — Use "primary" for your main calendar, or paste a calendar ID from `setup_calendar_oauth.py --test` output
- `exclude_keywords` — Events with these words (case-insensitive) will be hidden from reports
- `timezone` — Your local timezone (IANA format, e.g., "America/Los_Angeles", "Europe/London")

## Step 4: Verify setup

```bash
# Check that config file exists
ls -la temp/calendar_config.json

# List available calendars to find your calendar_id
python scripts/setup_calendar_oauth.py --client-secret /path/to/client_secret.json --test
```

## Done!

Your config is now in place. The `temp/` folder is gitignored, so your settings stay on your device.

Run reports:
```bash
rebalance calendar-daily-report
rebalance calendar-weekly-report
```

See [CALENDAR_NEW_USER_SETUP.md](./CALENDAR_NEW_USER_SETUP.md) for full setup guide.
