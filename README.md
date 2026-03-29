> Your workday OS

**Status: Coming soon — active development. Star to follow along.**

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
  Slack [soon]     ──┘       Task Scheduler on    github_activity)
                              Windows, cron on Linux)
                                     │
                                     ▼
                           MCP server (Python)
                           rebalance tools:
                             query_notes
                             github_balance
                             todays_agenda
                             search_vault
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
- [x] GitHub activity scanner + balance analysis
- [x] Obsidian vault ingester (parse, chunk, keywords, links)
- [x] Qwen3 embedding pipeline (sqlite-vec, semantic search)
- [x] Google Calendar integration (OAuth2, 1-year retention)
- [x] `ask` tool — multi-source natural language query with local LLM synthesis
- [x] Temporal context (day-of-week, work/off/vacation awareness)
- [ ] Morning briefing assembler + daily scheduler
- [ ] Project weight system (neglect score, momentum decay, avoidance ratio)
- [ ] Slack integration via Sleuth bolt app
- [ ] GitHub PR/issue body embedding (phase 2)

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
```

### Step 4 — Connect Google Calendar (optional)

Follow the OAuth setup in [PROJECT.md — P2 Google Calendar](./PROJECT.md) to create credentials, then:

```bash
# Backfill 1 year of events
.venv/bin/rebalance calendar-sync --database rebalance.db --days-back 365
```

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

### Claude Desktop App (extension)

rebalance OS ships as a Claude Desktop Extension (`.mcpb`). No terminal needed.

1. **Build the extension** (developers only):
   ```bash
   npx @anthropic-ai/mcpb pack
   ```
2. **Install:** Drag the `.mcpb` file into Claude Desktop → Settings → Extensions
3. **Configure:** Claude Desktop will prompt for:
   - **Obsidian Vault Path** — your vault folder
   - **GitHub PAT** (optional) — stored in OS keychain, never in plaintext
   - **Database Path** — defaults to `~/.rebalance/rebalance.db`
4. **Use:** Open Claude Desktop and ask questions. The extension's MCP tools are available immediately.

See [manifest.json](./manifest.json) for the full extension spec.

> **Note:** The extension packaging step (`mcpb pack`) requires bundling all Python dependencies into the archive. This is not yet automated — a build script that copies `src/rebalance/` + `lib/` into the extension structure is a next step. For now, use Claude Code or the manual MCP config for daily use.

### Other MCP hosts

The server works with any MCP-compatible client. Config files are provided for:

- **Claude Code** — `.mcp.json` (auto-loaded on `cd rebalance-OS && claude`)
- **VS Code (Copilot/Continue)** — `.vscode/mcp.json` (auto-loaded on workspace open)
- **Claude Desktop** — extension (`.mcpb`) or manual config in [MCP.md](./MCP.md)
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
rebalance calendar-sync --database rebalance.db                                # refresh calendar
```

---

## License

Copyright 2025 Hypercart DBA Neochrome, Inc.

Licensed under the **Apache License, Version 2.0**.

You may use, reproduce, modify, and distribute this software and its documentation under the terms of the Apache 2.0 License. Attribution is required — any redistribution must retain the above copyright notice.

See [APACHE-LICENSE-2.0.txt](./APACHE-LICENSE-2.0.txt) for the full license text, or visit https://www.apache.org/licenses/LICENSE-2.0.

---

## Contributing

Not open to contributions yet — getting the core right first. Watch the repo and come back when the first milestone lands.

---

*Built by [Hypercart](https://hypercart.com) — tools for agencies and solopreneurs who build on WordPress.*
