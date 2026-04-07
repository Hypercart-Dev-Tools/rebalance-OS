# Google Calendar — Timesheet Reports

Generate daily and weekly timesheet reports from your Google Calendar.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Prerequisites](#prerequisites)
3. [First-Time Setup](#first-time-setup)
   - [Step 1: Authorize your device](#step-1-authorize-your-device)
   - [Step 2: Configure your calendar](#step-2-configure-your-calendar)
   - [Step 3: Sync and verify](#step-3-sync-and-verify)
4. [Team Quick Setup](#team-quick-setup)
5. [Claude Code Setup](#claude-code-setup)
6. [Project Definitions](#project-definitions)
   - [Canonical Source of Truth](#canonical-source-of-truth)
   - [Minimum Project Definition](#minimum-project-definition)
   - [Sync Project Definitions Into the Same Database](#sync-project-definitions-into-the-same-database)
7. [Running Reports](#running-reports)
8. [Customizing Your Config](#customizing-your-config)
9. [Keeping Events Up to Date](#keeping-events-up-to-date)
10. [Troubleshooting](#troubleshooting)

---

## Quick Start

Already set up? These are the only commands you need day-to-day:

```bash
rebalance calendar-sync --days-back 30    # Pull latest events
rebalance calendar-daily-report           # Today's timesheet
rebalance calendar-weekly-report          # This week's timesheet
```

---

## Prerequisites

Before running any setup or report commands, make sure your local environment is ready.

**Python 3.12+** is required (`pyproject.toml` specifies `requires-python = ">=3.12"`).

```bash
python3 --version   # Must be 3.12 or higher
```

**Create a virtual environment and install the project:**

```bash
python3 -m venv .venv
source .venv/bin/activate       # macOS / Linux
pip install -e .
```

**Install Google Calendar dependencies** (not bundled in the core package):

```bash
pip install google-api-python-client google-auth-oauthlib google-auth-httplib2
```

After this, `rebalance` should be available on your PATH (inside the venv):

```bash
rebalance --help
```

> If you see `command not found: rebalance`, make sure your virtual environment is activated (`source .venv/bin/activate`).

---

## First-Time Setup

### Step 1: Authorize your device

Run this once to connect your Google account. It opens a browser window where you log in and click **Allow**.

The required Google OAuth Desktop app credentials are already bundled in this repo for setup. Your developer does **not** need to:

- create a Google Cloud project
- download a separate `client_secret.json`
- edit OAuth client credentials by hand

Each developer authorizes their **own** Google account locally. The repo only provides the Desktop app client configuration needed to start the browser consent flow.

```bash
python scripts/setup_calendar_oauth.py --test
```

After clicking Allow, the script prints a list of your Google Calendars and their IDs. **Copy the ID** of the calendar you want to use — you'll need it in the next step.

> Your login token is saved locally at `~/.config/gcalcli/oauth` and is never stored in the repo.
> The OAuth token belongs to the authorizing user account on that machine. It is separate from the bundled Desktop app client configuration.

---

### Step 2: Configure your calendar

> **Already have a config file?** If a teammate sent you a `calendar_config.json` (e.g. via Slack), place it at `temp/calendar_config.json` and skip the rest of this step — go straight to [Step 3](#step-3-sync-and-verify). Your config is already filled in.

If you don't have a pre-filled config, create one from the template:

```bash
mkdir -p temp
cp calendar_config.example.json temp/calendar_config.json
```

Then open `temp/calendar_config.json` and fill in your details:

```json
{
  "calendar_id": "paste-your-calendar-id-here",
  "exclude_keywords": ["Lunch", "Break"],
  "timezone": "America/Los_Angeles"
}
```

| Field | What to put here |
|-------|-----------------|
| `calendar_id` | Paste the calendar ID printed in Step 1, or use `"primary"` for your main Google Calendar. |
| `exclude_keywords` | Event titles containing these words will be hidden from reports. |
| `timezone` | Your local timezone — e.g. `"America/Los_Angeles"`, `"America/New_York"`, `"America/Chicago"`. |

> This file is private to your machine and is never synced to GitHub.

---

### Step 3: Sync and verify

```bash
# Pull 1 year of events (run once to backfill)
rebalance calendar-sync --days-back 365

# Check it worked
rebalance calendar-daily-report
```

You should see a formatted timesheet for today. If you do, you're all set.

---

## Team Quick Setup

Got a pre-filled `calendar_config.json` from your team (e.g. via Slack)? This is the fastest path — you only need to do three things:

**1. Install dependencies**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
pip install google-api-python-client google-auth-oauthlib google-auth-httplib2
```

**2. Place the config file and authorize your device**

```bash
mkdir -p temp
# Move the config file your teammate sent into temp/calendar_config.json
```

Then run the one-time browser authorization:

```bash
python scripts/setup_calendar_oauth.py --test
```

A browser window opens — log in with your Google account and click **Allow**. That's all that's needed from you — the config is already set up.

**3. Sync and run a report**

```bash
rebalance calendar-sync --days-back 30
rebalance calendar-daily-report
```

You're done. The config already has the shared `calendar_id`, projects, and timezone — you only authorize once so the app can read your calendar on your behalf.

> **Why does each person need to authorize?** The repo includes the shared OAuth Desktop app credentials, but each person must grant consent for their own Google account. Your token is saved locally at `~/.config/gcalcli/oauth` and never stored in the repo.

---

## Claude Code Setup

If you are using Claude Code (Anthropic's CLI or VS Code extension), you can let it drive the setup and reporting for you. Open this file in a VS Code editor pane, select the entire document, and use one of the prompts below.

**Setup prompt — starting from scratch:**

> Please scan the highlighted document, install dependencies, and then run the local Google Calendar timesheet setup including authorization on this device.

**Setup prompt — if you already have a config file in `/temp`:**

> Please scan the highlighted document, install dependencies, and then run the local Google Calendar timesheet setup including authorization on this device. I already have a copy of the timesheet app config stored in the `/temp` folder.

Claude Code will:

1. Check that prerequisites are met (Python version, venv, dependencies).
2. Check whether `temp/calendar_config.json` already exists.
   - **If it exists** — use it as-is. Do not overwrite it.
   - **If it does not exist** — copy from the example and ask the user to fill in `calendar_id` and `timezone`.
3. Run `python scripts/setup_calendar_oauth.py --test` to open the browser consent flow.
4. Run `rebalance calendar-sync --days-back 30` to pull events.
5. Run a report to verify everything works.

**Running reports prompt:**

> Run the report for last week.

Claude Code will run `rebalance calendar-weekly-report` (and/or `calendar-daily-report`) with the appropriate `--date` flag.

**Important notes for Claude Code:**

- If `temp/calendar_config.json` already exists, do **not** overwrite it — the user or their teammate has already configured it.
- If `temp/calendar_config.json` does not exist, copy from the example: `cp calendar_config.example.json temp/calendar_config.json` and ask the user to fill in their `calendar_id` and `timezone`.
- Always run commands inside the project's virtual environment. If `rebalance` is not found, activate with `source .venv/bin/activate` first.
- The Google API packages (`google-api-python-client`, `google-auth-oauthlib`, `google-auth-httplib2`) must be installed in the venv before running the OAuth script.

---

## Project Definitions

### Canonical Source of Truth

Calendar reports do **not** maintain a separate project alias file.

The single source of truth for project names and aliases is:

- Canonical file: `Projects/00-project-registry.md` inside your Obsidian vault
- Machine projections: `projects.yaml` and `project_registry` in SQLite
- Non-Obsidian fallback: `projects` inside `temp/calendar_config.json`

For calendar reports, the important rule is:

- `calendar_events` and `project_registry` must exist in the **same SQLite database** if you want the Obsidian-backed project definitions to apply
- If `project_registry` is present, calendar reports use canonical project names and aliases from that registry first
- If `project_registry` is missing or empty, calendar reports fall back to `projects` in `temp/calendar_config.json`
- If neither source exists, reports fall back to heuristic keyword grouping

### Minimum Project Definition

At minimum, define each active project with:

- `name` — canonical label you want the report to show
- `tags` — optional but useful for consistency with the rest of the system
- `custom_fields.calendar_aliases` — calendar-specific aliases and abbreviations
- or, in non-Obsidian mode, `projects[].aliases` in `temp/calendar_config.json`

Example:

```yaml
active_projects:
  - name: CreditRegistry
    status: active
    summary: Internal credit data and reporting work.
    repos: [credit-registry]
    tags: ["#project-credit-registry"]
    custom_fields:
      calendar_aliases: ["CR", "Credit Registry", "CR CC"]

  - name: NeoNook
    status: active
    summary: Mobile and storefront work for NeoNook.
    repos: [neo-nook]
    tags: ["#project-neo-nook"]
    custom_fields:
      calendar_aliases: ["NN", "Neo Nook"]
```

Use `calendar_aliases` for:

- abbreviations like `CR`, `NN`, `BW`
- alternate spellings like `Credit Registry`
- recurring calendar-specific phrasing like `CR CC`

Do not put low-signal verbs like `fix`, `setup`, `test`, `change`, or `download` in project aliases.

### Non-Obsidian Fallback

If you are **not** using Obsidian, define your canonical calendar projects directly in `temp/calendar_config.json`:

```json
{
  "calendar_id": "primary",
  "exclude_keywords": ["Lunch", "Check Slack"],
  "timezone": "America/Los_Angeles",
  "projects": [
    {
      "name": "Bailiwik",
      "aliases": ["Bailiwik", "BW"]
    },
    {
      "name": "Normans Nursery",
      "aliases": ["Normans Nursery", "Norman's Nursery", "NN"]
    }
  ]
}
```

This is the simplest path if the developer only needs accurate timesheet grouping and does not need the Obsidian project registry workflow.

### Sync Project Definitions Into the Same Database

After editing your registry, run a pull sync so the canonical definitions are materialized into both `projects.yaml` and the SQLite `project_registry` table.

Installed CLI:

```bash
rebalance ingest sync \
  --mode pull \
  --vault /absolute/path/to/your/vault \
  --database /absolute/path/to/rebalance.db
```

Repo-local fallback:

```bash
PYTHONPATH=src python3 -m rebalance.cli ingest sync \
  --mode pull \
  --vault /absolute/path/to/your/vault \
  --database /absolute/path/to/rebalance.db
```

Use the **same** database path you use for calendar sync and calendar reports. If your calendar reports read from `rebalance.db`, then your ingest sync should also write `project_registry` into that same `rebalance.db`.

Verification:

```bash
sqlite3 /absolute/path/to/rebalance.db "SELECT name FROM project_registry ORDER BY name;"
```

If that query returns your projects, calendar reports can now use canonical project names and aliases.

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
- **Project Aggregator** — events grouped by canonical project names first, then keyword heuristics only when no project match exists
- Low-signal verbs and filler terms are skipped during grouping so labels stay closer to project names than task phrasing
- If `project_registry` has been synced into the same SQLite database, it is the primary source for canonical project names and aliases
- If no synced `project_registry` exists, the report uses `projects` from `temp/calendar_config.json`

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
Add any event title (or part of one) to stop it appearing in reports. Matching is case-insensitive. The same keywords are also ignored by the project aggregator when it picks grouping labels.

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
| Browser didn't open during setup | Re-run Step 1 — make sure you have internet access |
| Reports are empty | Check that `calendar_id` in your config matches what Step 1 printed |
| Wrong events showing up | Your `calendar_id` may be set to `"primary"` — re-run Step 1 with `--test` to find the right ID |
| Times look wrong | Update `timezone` in `temp/calendar_config.json` to your local timezone |
| Project names still look heuristic (`Cr`, `Ai`, `Smart`) | Sync your canonical registry into the same SQLite database so `project_registry` is available to the calendar report |
| I do not use Obsidian | Add `projects` directly to `temp/calendar_config.json`; the report will use that fallback automatically |
| Need to re-authorize | Re-run Step 1 — your previous token may have expired |

**Common questions**

- **Is my calendar data stored anywhere online?** No — events are pulled to your local machine only and never uploaded.
- **Do I need my own Google Cloud app or `client_secret.json`?** No — this repo already includes the Desktop app OAuth client configuration needed to start authorization on your machine.
- **Can I change which calendar I use?** Yes — update `calendar_id` in your config and run `calendar-sync` again.
- **An event I want to hide keeps showing up** — add a word from its title to `exclude_keywords` in your config.
- **How do I force canonical project labels in the aggregator?** Add `custom_fields.calendar_aliases` in `Projects/00-project-registry.md`, then run `rebalance ingest sync --mode pull` into the same SQLite database used by calendar reports.
- **What if I do not have an Obsidian registry yet?** Put canonical project names and aliases in `temp/calendar_config.json` under `projects`.
- **I got a new machine** — just clone the repo and repeat Steps 1–3. Everything you need is already included.
