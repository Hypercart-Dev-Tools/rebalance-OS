# rebalance OS — ARCHITECTURE.md

> How data flows through the system. For execution decisions see [PROJECT.md](./PROJECT.md), for tool specs see [MCP.md](./MCP.md).

---

## Core Pipeline

```
Signals (data sources)
  │
  ▼
Ingest Layer (source-specific collectors)
  │
  ▼
SQLite + sqlite-vec (unified local store)
  │
  ▼
Query Layer (context gathering + prompt assembly)
  │
  ▼
Two-Layer LLM
  ├── Layer 1: Local Qwen3 (fast first-pass synthesis)
  └── Layer 2: Host Agent (review, adapt, present)
  │
  ▼
User (via MCP host: VS Code, Claude Desktop, etc.)
```

Every data source follows the same pattern: **collect → normalize → store → query**. Adding a new source means implementing one collector and one `_gather_*` function. The query layer and LLM layers are source-agnostic.

---

## Signal Sources

Each source has a priority, a collector module, and a target table. For detailed field specs and status, see [PROJECT.md — Signals](./PROJECT.md).

| Priority | Source | Collector | Storage | Vectorized | Status |
|----------|--------|-----------|---------|------------|--------|
| P1 | GitHub | `github_scan.py` + `github_knowledge.py` + `github_readiness.py` + `github_reconciliation.py` | `github_activity`, `github_repo_meta`, `github_branches`, `github_items`, `github_comments`, `github_documents`, `github_embeddings` | Yes — structured repo signals plus semantic corpus for issues, PRs, comments, reviews, commit messages, and issue/PR reconciliation | Active |
| P1 | Obsidian Vault | `note_ingester.py` + `embedder.py` | `vault_files`, `chunks`, `keywords`, `links`, `embeddings` | **Yes** — Qwen3-Embedding-0.6B, 1024-dim, sqlite-vec | Active |
| P2 | Google Calendar | `calendar.py` | `calendar_events` table (1 year retention) | No — structured event data | Active |
| P3 | Slack / Sleuth | TBD | `tasks` table (planned) | TBD | Planned |
| P4 | Email | TBD | TBD | TBD | Planned |

### Adding a New Source

1. **Collector** — write a module in `src/rebalance/ingest/` that fetches, normalizes, and stores data in SQLite. Follow the pattern of `github_scan.py` (fetch → dataclass → upsert) or `note_ingester.py` (walk → parse → upsert).
2. **Schema** — add tables to `db.py:ensure_schema()` for structured data. Use existing tables for unstructured text that should be embedded.
3. **Context gatherer** — add a `_gather_<source>_context()` function in `querier.py`. It reads from SQLite and returns `list[dict]`.
4. **Prompt section** — add a block in `_build_prompt()` to format the new context for the LLM.
5. **MCP tool** (optional) — add a dedicated tool in `mcp_server.py` if the source warrants direct querying beyond the `ask` tool.

No changes needed to the query layer, LLM synthesis, or MCP transport.

---

## Storage Layer

Single SQLite file at the path resolved from `REBALANCE_DB` env var. sqlite-vec extension loaded for vector operations.

### Tables by Domain

```
Project Registry (writer: registry.py)
  project_registry          — canonical project metadata

GitHub (writer: github_scan.py)
  github_activity            — per-repo event counts, keyed by (login, repo, scan_date)
  github_repo_meta           — repo-level metadata such as default branch and issue/project support
  github_branches            — local branch inventory for promotion/release inference

Vault Ingestion (writer: note_ingester.py)
  vault_files                — one row per .md file, with content_hash for delta detection
  chunks                     — heading-based chunks, FK to vault_files (CASCADE delete)
  keywords                   — TF-IDF top-K per chunk, FK to chunks (CASCADE delete)
  links                      — wikilinks and embeds, FK to vault_files (CASCADE delete)

Embeddings (writer: embedder.py)
  embeddings                 — sqlite-vec virtual table, float[1024], keyed by chunk_id
  embedding_meta             — model name, dimension, last embed timestamp

Google Calendar (writer: calendar.py)
  calendar_events            — event id, summary, start/end, location, attendees, description
                               Keyed by Google event ID (INSERT OR REPLACE). 1 year retention.
```

### Delta Strategy

Both ingest pipelines use hash-based delta detection:

- **Vault notes**: SHA-256 of raw file bytes stored in `vault_files.content_hash`. On re-ingest, unchanged files are skipped entirely. Changed files are deleted (CASCADE clears chunks/keywords/links) and re-inserted.
- **GitHub activity**: keyed by `(login, repo_full_name, scan_date)` with `ON CONFLICT REPLACE`. Each scan overwrites that day's data.
- **Embeddings**: chunks without a corresponding `embeddings` row get embedded. Model version change triggers full re-embed via `embedding_meta`.
- **Calendar**: keyed by Google event ID with `INSERT OR REPLACE`. Re-sync overwrites existing events and adds new ones. 1 year retention; no auto-cleanup.

---

## Query Layer

`querier.py` is the central orchestrator. A single `ask()` call:

1. **Gathers context** from all sources in parallel-ready functions:
   - `_gather_project_context()` — registry entries + repos map
   - `_gather_github_context()` — per-project activity summary
   - `_gather_vault_context()` — semantic search (embed query → ANN)
   - `_gather_vault_activity()` — recently modified files
   - `_gather_calendar_context()` — upcoming + recent events from `calendar_events`
   - *(future: `_gather_slack_context()`, etc.)*

2. **Assembles a prompt** with all context formatted into labeled sections.

3. **Synthesizes** via local Qwen3 LLM (mlx-lm). Returns both synthesis and raw context.

### Two-Layer LLM Architecture

```
User question
  │
  ▼
ask() tool ──▶ Local Qwen3-0.6B (Layer 1)
  │              - Sees all raw context
  │              - Fast first-pass synthesis
  │              - Runs on-device via MLX
  │
  ▼
Returns to host agent (Layer 2)
  │              - Claude, Copilot, Gemini, etc.
  │              - Reviews synthesis + raw context
  │              - Fact-checks against raw data
  │              - Adapts, refines, presents to user
  │
  ▼
User sees final answer
```

**Why two layers?** The local model is fast and private — it never sends vault content to the cloud. But it's small (0.6B) and makes mistakes. The host agent is larger, smarter, and can fact-check against the raw context that's returned alongside the synthesis. The user gets speed + accuracy + privacy.

**`skip_synthesis=True`** bypasses Layer 1 entirely and returns raw context only. Use this when the host agent is capable enough to do its own synthesis (e.g., Claude).

---

## MCP Tool Surface

Tools are registered in `mcp_server.py:create_server()`. All tools share the same `database_path` resolved at server startup from `REBALANCE_DB`.

| Category | Tool | Purpose |
|----------|------|---------|
| Query | `ask` | Natural language query across all sources (with optional local LLM synthesis) |
| Query | `query_notes` | Semantic search (embedding-based) |
| Query | `search_vault` | Keyword search (TF-IDF) |
| Query | `github_balance` | Per-project GitHub activity summary |
| Registry | `list_projects` | Query project registry |
| Onboarding | `onboarding_status` | Check setup completion |
| Onboarding | `setup_github_token` | Validate and store GitHub PAT |
| Onboarding | `run_preflight` | Discover project candidates (read-only) |
| Onboarding | `confirm_projects` | Write registry and sync |

Tool specs (params, returns, dependencies): see [MCP.md](./MCP.md).

---

## Module Map

```
src/rebalance/
  __init__.py              — package version
  __main__.py              — CLI entry point
  cli.py                   — typer commands (ingest, config, query, ask, search)
  mcp_server.py            — FastMCP server, all tool registrations
  ingest/
    config.py              — secrets storage (temp/rbos.config)
    registry.py            — project registry sync (Markdown ↔ YAML ↔ SQLite)
    preflight.py           — onboarding discovery + confirmation
    github_scan.py         — GitHub Events API collector + balance query
    db.py                  — shared DB connection, schema, sqlite-vec loading
    md_parser.py           — pure markdown parsing (frontmatter, wikilinks, tags, chunking)
    note_ingester.py       — vault walker, delta detection, TF-IDF keywords
    embedder.py            — mlx-embeddings batch embed + ANN query
    calendar.py            — Google Calendar API collector + SQLite persistence
    querier.py             — multi-source context gathering + local LLM synthesis
```

---

## License

Copyright 2025 Hypercart DBA Neochrome, Inc.

Licensed under the **Apache License, Version 2.0**. See [APACHE-LICENSE-2.0.txt](./APACHE-LICENSE-2.0.txt).
