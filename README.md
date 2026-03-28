# obsidian-rag

> Your second brain, finally paying rent.

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

---

## What it does

**obsidian-rag** is a local-first morning briefing engine that ingests your Obsidian vault, GitHub activity, and calendar into a queryable SQLite database — then lets any MCP-compatible LLM (Claude, Copilot, Cursor, Continue) answer questions about your own work, flag over-investment in specific projects, and surface what actually needs your attention today.

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
  GitHub activity  ──┤──▶  cron (daily)  ──▶  SQLite + sqlite-vec
  Obsidian vault   ──┤         │                (chunks, embeddings,
  Slack [soon]     ──┘         │                 github_activity)
                               │
                               ▼
                     MCP server (Python)
                     obsidian-rag tools:
                       query_notes
                       github_balance
                       todays_agenda
                       search_vault
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
       Claude Desktop     VS Code agent      Cursor
       (MCP native)    (Copilot/Continue)  (MCP compatible)
```

The MCP server speaks standard JSON-RPC — no LLM-specific logic inside it. Any MCP-compatible client works without modification.

---

## Why Markdown files and local LLMs make this possible

Obsidian stores everything as plain `.md` files. No proprietary database, no sync lock-in, no API needed — just a folder on your disk. That makes ingestion a simple recursive file scan: parse frontmatter, chunk by headings, extract tags and wikilinks, embed, and index. The entire vault becomes a queryable vector store in a single SQLite file.

Local LLMs — specifically Qwen3 via Ollama — close the loop. Your notes, commits, and calendar events never leave your machine. There's no API key to manage for inference, no usage bill, and no terms-of-service risk with client data. The model runs on-device (optimized for Apple Silicon via MLX), retrieves context from the local vector store, and answers in seconds.

The result is an AI assistant that actually knows your work — because it's reading the same files you are.

---

## Tech stack

| Layer | Tool |
|---|---|
| Notes | Obsidian (plain `.md`) |
| Vector DB | SQLite + `sqlite-vec` |
| Embeddings | Qwen3-Embedding via Ollama |
| LLM | Qwen3-7B via Ollama (Apple Silicon optimized) |
| Calendar | `gcalcli` → Google Calendar API |
| GitHub | GitHub REST API + PAT |
| MCP server | Python `mcp` SDK (stdio + SSE) |
| LLM clients | Claude Desktop, VS Code, Cursor, any MCP host |

---

## Roadmap

- [x] Architecture and design
- [ ] Obsidian ingester (`ingest.py`)
- [ ] SQLite schema + sqlite-vec setup
- [ ] Qwen3 embedding pipeline
- [ ] GitHub activity scanner
- [ ] gcalcli calendar adapter
- [ ] MCP server with core tools
- [ ] Morning briefing CLI
- [ ] Slack integration via Sleuth bolt app

---

## License

Copyright 2025 Hypercart DBA Neochrome, Inc.

Licensed under the **Apache License, Version 2.0**.

You may use, reproduce, modify, and distribute this software and its documentation under the terms of the Apache 2.0 License. Attribution is required — any redistribution must retain the above copyright notice.

See [LICENSE](./LICENSE) for the full license text, or visit https://www.apache.org/licenses/LICENSE-2.0.

---

## Contributing

Not open to contributions yet — getting the core right first. Watch the repo and come back when the first milestone lands.

---

*Built by [Hypercart](https://hypercart.com) — tools for agencies and solopreneurs who build on WordPress.*
