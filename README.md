> Your workday "OS"

---

## Who this is for

- **Dev and design agency owners** juggling 5+ client repos, scattered notes, and back-to-back meetings with no time to connect the dots
- **Solopreneurs and indie hackers** who live in Obsidian but lose hours tracking where their attention actually goes
- **Technical founders** who want AI-assisted clarity on their own work — without sending their notes, commits, or calendar to a cloud service

If you've ever opened your laptop in the morning and genuinely not known where to start, this is for you.

---

## The problem

Your work lives in three places that never talk to each other: your notes, your code repos, and your calendar. You context-switch constantly, lose track of which projects are getting too much attention (and which aren't getting enough), and spend the first 30 minutes of every day reconstructing what you were doing yesterday.

AI assistants could help — but they can't see your Obsidian vault, your GitHub activity, or your Google Calendar. And sending all of that to a cloud LLM isn't an option for client work.

<img width="1882" height="1516" alt="rebalance" src="https://github.com/user-attachments/assets/eb60a254-d452-4839-a900-0ffedd72758f" />

---

## What it does

**rebalance OS** is a local-first morning briefing engine that ingests your Obsidian vault, GitHub activity, and calendar into a queryable SQLite database — then lets any MCP-capable host or agent (ChatGPT, Gemini, Claude, Copilot, Cursor, Continue, and others where MCP is supported) answer questions about your own work, flag over-investment in specific projects, and surface what actually needs your attention today.

---

## Use cases

**Morning briefing**
Ask "What's my day look like?" and get today's meetings, yesterday's commit activity, and a summary of relevant notes — in one shot, from your local machine.

**Project balance check**
"Am I over-investing in client X?" surfaces commit velocity, PR activity, and note density per project. Flags when one repo is consuming >40% of your attention.

**Knowledge retrieval**
"What did I decide about the LTVera embedding pipeline?" Semantic search across your entire vault, ranked by relevance, answered by a local LLM.

**Handoff prep**
"Summarize everything I know about Project Y" pulls notes, recent commits, and open issues into a coherent brief — useful for client updates, team handoffs, or just getting back up to speed after a break.

**Coming soon: Slack activity** (via Sleuth bolt app integration) — adds team communication context to the balance picture.

---

## High-level architecture

```
Data sources
  Google Calendar  ──┐
  GitHub activity  ──┤──▶  scheduler (daily) ──▶ SQLite + sqlite-vec
  Obsidian vault   ──┤      (launchd on macOS,   (chunks, embeddings,
  Slack [planned]  ──┤       Task Scheduler on    github_activity,
  Email [planned]  ──┘       Windows, cron on     calendar_events)
                              Linux)
                                     │
                                     ▼
                           MCP server (Python)
                           rebalance tools:
                             ask
                             query_notes
                             search_vault
                             github_balance
                             review_timesheet
                             classify_event
                                     │
             ┌───────────────────────┼────────────────────────┐
             ▼                       ▼                        ▼
      ChatGPT/Gemini           Claude/Copilot          Cursor/Continue
      (where MCP works)       (MCP clients)             (MCP clients)
```

The MCP server speaks standard JSON-RPC — no LLM-specific logic inside it. Any MCP-compatible client works without modification.

For layer roles, tool surface, server configuration, and host adapter setup (Claude Desktop, Cursor, VS Code, Continue), see **[MCP.md](./MCP.md)**.

---

## Why Markdown files and local LLMs make this possible

Obsidian stores everything as plain `.md` files. No proprietary database, no sync lock-in, no API needed — just a folder on your disk. That makes ingestion a simple recursive file scan: parse frontmatter, chunk by headings, extract tags and wikilinks, embed, and index. The entire vault becomes a queryable vector store in a single SQLite file.

Local LLMs — such as Qwen3 via Ollama or LM Studio-compatible models — close the loop. Your vault content can stay local and be queried without sending note content to a hosted LLM by default. GitHub and Google Calendar data are pulled from their APIs, then cached and queried locally. The model runs on-device (optimized for Apple Silicon via MLX), retrieves context from the local vector store, and answers in seconds.

The result is an AI assistant that actually knows your work — because it's reading the same files you are.

---

## Tech stack

| Layer | Tool |
|---|---|
| Notes | Obsidian (plain `.md`) |
| Vector DB | SQLite + `sqlite-vec` |
| Embeddings | Qwen3-Embedding-0.6B via `mlx-embeddings` (Apple Silicon MLX) |
| LLM synthesis | Qwen3-0.6B via `mlx-lm` (on-device, Layer 1) |
| Calendar | Google Calendar API (direct client, OAuth2) |
| GitHub | GitHub REST API + PAT |
| MCP server | Python `mcp` SDK (FastMCP, stdio) |
| LLM clients | Any MCP host (Claude Code, Copilot, Cursor, Continue, Claude Desktop, and others) |

---

## Roadmap

- [x] Architecture and design
- [x] Project registry + MCP onboarding tools
- [x] GitHub activity scanner + 30-day A/B/C band classification
- [x] GitHub artifact sync + local semantic query (issues, PRs, comments, reviews, commits)
- [x] GitHub readiness inference from local repo signals (milestones, linked PRs, branches, releases)
- [x] GitHub issue <-> PR close-candidate reconciliation with high/medium-confidence recommendations
- [x] Obsidian vault ingester (parse, chunk, keywords, links)
- [x] Qwen3 embedding pipeline (sqlite-vec, semantic search)
- [x] Google Calendar integration (OAuth2, 1-year retention)
- [x] `ask` tool — multi-source natural language query with local LLM synthesis
- [x] Temporal context (day-of-week, work/off/vacation awareness)
- [x] Daily scheduler scripts (launchd plist, install helper)
- [x] Calendar daily/weekly reports with project aggregation and time totals
- [x] Configurable hours format (decimal or h:m) for calendar reports
- [x] Agent review layer for calendar events (`review_timesheet`, `classify_event` MCP tools)
- [x] DRY calendar helpers (shared datetime parsing, duration calc, connection setup)
- [x] CI test suite (GitHub Actions, Python 3.12/3.13, 68 tests)
- [ ] Morning briefing assembler
- [ ] Project weight system (neglect score, momentum decay, avoidance ratio)
- [ ] Email integration (Gmail API, starred/important threads only, forward-only)
- [ ] Slack integration via Sleuth bolt app
- [ ] GitHub readiness inference layer (deploy/review/release heuristics over the local corpus)
- [ ] Email → project auto-correlation (alias map + co-occurrence)

## Getting Started

### Prerequisites

- macOS with Apple Silicon (M1+) — required for mlx-embeddings
- Python 3.12+
- An Obsidian vault (local folder with `.md` files)
- A GitHub Personal Access Token with `repo:read` scope ([create one here](https://github.com/settings/tokens))
- Claude Code (CLI or VS Code extension)

### Step 1 — Clone and install

```bash
git clone https://github.com/Hypercart-Dev-Tools/rebalance-OS.git
cd rebalance-OS
python3 -m venv .venv
.venv/bin/pip install -e ".[embeddings]"
```

### Step 2 — Ingest your vault

```bash
# Parse all .md files, chunk by headings, extract keywords and links
.venv/bin/rebalance ingest notes --vault /path/to/your/vault --database rebalance.db

# Generate semantic embeddings (downloads Qwen3-Embedding-0.6B on first run, ~1min)
.venv/bin/rebalance ingest embed --database rebalance.db
```

### Step 3 — Connect GitHub

```bash
# Store your PAT
.venv/bin/rebalance config set-github-token ghp_your_token_here

# Scan recent activity (commits, PRs, issues across all your repos)
.venv/bin/rebalance github-scan --token ghp_your_token_here --database rebalance.db

# Sync detailed GitHub artifacts into the local SQLite corpus
.venv/bin/rebalance github-sync-artifacts \
  --repo owner/repo \
  --database rebalance.db

# Embed the local GitHub corpus for semantic retrieval
.venv/bin/rebalance github-embed --database rebalance.db

# Query the local GitHub corpus without re-reading GitHub live
.venv/bin/rebalance github-query "What is close to deploy?" --database rebalance.db
```

### Step 4 — Connect Google Calendar (optional)

OAuth Desktop app credentials are already bundled in the repo. You do **not** need to create a Google Cloud project or download a `client_secret.json`.

**4a. Install with calendar support**

```bash
pip install -e ".[calendar]"
```

**4b. Authorize this device**

```bash
python scripts/setup_calendar_oauth.py --test
```

A browser window opens — log in with your Google account and click **Allow**. The script prints your available calendars and their IDs. Your token is saved locally at `~/.config/gcalcli/oauth` (never in the repo).

If you want MCP agents to create events, re-run auth with write access:

```bash
python scripts/setup_calendar_oauth.py --write-access --test
```

> **Joining a team?** If a teammate sent you a pre-filled `calendar_config.json`, place it at `temp/calendar_config.json` and skip to step 4d.

**4c. Create your config**

```bash
mkdir -p temp
cp calendar_config.example.json temp/calendar_config.json
```

Edit `temp/calendar_config.json` with your preferences:

| Field | What to put here |
|-------|-----------------|
| `calendar_id` | Calendar ID from step 4b, or `"primary"` for your main calendar |
| `exclude_titles` | Exact event titles to hide from reports (e.g., `"Lunch"`, `"Check Slack"`) |
| `aggregator_skip_words` | Broad terms skipped in project grouping labels only (e.g., `"wrap"`, `"setup"`) |
| `timezone` | Your local timezone (e.g., `"America/Los_Angeles"`) |
| `hours_format` | `"decimal"` (default, e.g. `4.50h`) or `"hm"` (e.g. `4h 30m`) |

**4d. Sync and run reports**

```bash
# Pull events (use --days-back 365 for initial backfill)
.venv/bin/rebalance calendar-sync --days-back 30

# Generate reports
.venv/bin/rebalance calendar-daily-report
.venv/bin/rebalance calendar-weekly-report
.venv/bin/rebalance calendar-weekly-report --vault /path/to/vault --write-week-note
```

For the full guide — including team setup, Claude Code prompts, and project definitions — see [GOOGLE_CALENDAR.md](./GOOGLE_CALENDAR.md).

### Step 5 — Start using with Claude Code

The `.mcp.json` at the project root auto-registers the MCP server. Open the project in Claude Code:

```bash
cd rebalance-OS
claude
```

Then ask:

```
"What should I focus on today?"
"Am I over-investing in any projects this week?"
"What meetings do I have tomorrow and what should I prep?"
"What did I decide about the embedding pipeline?"
```

Claude Code calls the `ask` tool behind the scenes — it gathers your project registry, GitHub activity, vault notes, and calendar events, synthesizes a first-pass answer via a local Qwen3 model, then Claude reviews and presents a refined answer.

### Claude Desktop App

#### Manual config (recommended for now)

1. Open **Claude → Settings → Developer → Edit Config** to open `~/Library/Application Support/Claude/claude_desktop_config.json`.
2. Add the rebalance server (use absolute paths):

   ```json
   {
     "mcpServers": {
       "rebalance": {
         "command": "/absolute/path/to/rebalance-OS/.venv/bin/python",
         "args": ["-m", "rebalance.mcp_server"],
         "env": {
           "REBALANCE_DB": "/absolute/path/to/rebalance-OS/rebalance.db"
         }
       }
     }
   }
   ```

3. Quit and reopen Claude Desktop. The rebalance tools appear in the tool picker (hammer icon).
4. Ask *"What should I work on today?"* to verify.

For detailed setup, troubleshooting, and other MCP hosts, see [MCP.md — Claude Desktop](./MCP.md#claude-desktop).

#### Extension (`.mcpb`) — coming soon

rebalance OS will also ship as a Claude Desktop Extension. The extension packaging step (`mcpb pack`) requires bundling all Python dependencies into the archive. This is not yet automated — use the manual config above for daily use. See [manifest.json](./manifest.json) for the extension spec.

### Other MCP hosts

The server works with any MCP-compatible client. Config files are provided for:

- **Claude Code** — `.mcp.json` (auto-loaded on `cd rebalance-OS && claude`)
- **VS Code (Copilot/Continue)** — `.vscode/mcp.json` (auto-loaded on workspace open)
- **Claude Desktop** — manual config (see above) or extension (`.mcpb`, coming soon)
- **Cursor** — see [MCP.md](./MCP.md) for config snippet

### CLI reference

All tools are also available as CLI commands:

```bash
rebalance ask "What should I work on today?" --database rebalance.db
rebalance ask "What should I work on today?" --database rebalance.db --no-llm  # raw context only
rebalance query "embedding pipeline" --database rebalance.db                   # semantic search
rebalance search "binoid" --database rebalance.db                              # keyword search
rebalance ingest notes --vault /path/to/vault --database rebalance.db          # re-ingest (delta)
rebalance ingest embed --database rebalance.db                                 # embed new chunks
rebalance github-scan --token ghp_... --database rebalance.db                  # refresh GitHub data
rebalance github-close-candidates --repo owner/name --database rebalance.db    # open issues likely fixed by merged PRs
rebalance calendar-sync --database rebalance.db                                # refresh calendar
rebalance calendar-daily-report                                                # today's events + project breakdown
rebalance calendar-weekly-report                                               # this week's summary + aggregator
rebalance calendar-weekly-report --vault /path/to/vault --write-week-note     # write week-of-YYYY-MM-DD.md and re-index it
rebalance calendar-daily-totals                                                # daily event count + duration stats
```

---

## License

Copyright 2025-2026 Hypercart DBA Neochrome, Inc.

Licensed under the **Apache License, Version 2.0**.

You may use, reproduce, modify, and distribute this software and its documentation under the terms of the Apache 2.0 License. Attribution is required — any redistribution must retain the above copyright notice.

See [APACHE-LICENSE-2.0.txt](./APACHE-LICENSE-2.0.txt) for the full license text, or visit https://www.apache.org/licenses/LICENSE-2.0.

---

## Contributing

Not open to contributions yet — getting the core right first. Watch the repo and come back when the first milestone lands.

---

*Built by [Hypercart](https://hypercart.com) — tools for agencies and solopreneurs who build on WordPress.*
