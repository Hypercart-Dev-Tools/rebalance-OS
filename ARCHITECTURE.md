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
| P2 | Google Calendar | `calendar.py` | `calendar_events` table (default window 30d back / 7d forward; no auto-deletion) | No — structured event data | Active |
| P3 | Sleuth reminders (Slack) | `sleuth_reminders.py` | `sleuth_reminders` table | No — structured reminder rows | Active |
| P4 | Email | TBD | TBD | TBD | Planned |

### Source → Table fanout

```
EXTERNAL SOURCES                  INGESTORS (src/rebalance/ingest/)                  STORAGE
                                                                                     (SQLite @ $REBALANCE_DB
                                                                                      + sqlite-vec)

GitHub REST API ─────▶ github_scan.py            user events (last 30d)       ──▶ github_activity
  (api.github.com)   │                                                            github_repo_meta
                     ├▶ github_knowledge.py      per-repo artifacts:           ──▶ github_items (issues/PRs)
                     │                             issues, PRs, comments,          github_comments
                     │                             reviews, commits, checks,       github_commits
                     │                             branches, milestones,           github_check_runs
                     │                             releases                        github_branches
                     │                                                             github_milestones
                     │                                                             github_releases
                     │                                                             github_links
                     │                                                             github_documents
                     │                                                          ─ github_embeddings (vec0)
                     ├▶ github_readiness.py      release-state inference       ── (reads only)
                     └▶ github_reconciliation.py issue ↔ PR matching           ── (reads only)

Obsidian Vault ──────▶ note_ingester.py          walk *.md, chunk, TF-IDF,    ──▶ vault_files, chunks,
  (filesystem)       │                             wikilinks                       keywords, links
                     └▶ embedder.py              Qwen3-Embedding-0.6B         ──▶ embeddings (vec0, 1024-dim)
                                                   via mlx-embeddings

Google Calendar ─────▶ calendar.py               OAuth pickled token,         ──▶ calendar_events
  (Calendar API)                                   30d back / 14d forward

Sleuth Web API ──────▶ sleuth_reminders.py       Bearer auth, stdlib urllib,  ──▶ sleuth_reminders
  (Vultr dev :2020)                                GET /workspace/<name>/
                                                   reminders?format=rebalance

Project Registry ────▶ registry.py +              MD registry → projects.yaml ──▶ project_registry
  (vault markdown)     preflight.py                → SQLite projection
```

### Invocation points

| Source | CLI | MCP tool(s) | Daily-sync step |
|---|---|---|---|
| GitHub activity | `rebalance github-scan` | `github_balance` | 3 |
| GitHub artifacts | `rebalance github-sync-artifacts`, `github-embed`, `github-query` | `query_github_context`, `github_release_readiness`, `github_close_candidates` | on demand |
| Obsidian vault | `rebalance ingest notes`, `ingest embed`, `query`, `search` | `query_notes`, `search_vault` | 1 + 2 |
| Google Calendar | `rebalance calendar-sync`, `calendar-create-event`, `calendar-snap-edges`, `calendar-daily-report`, `calendar-weekly-report` | `create_calendar_event`, `review_timesheet`, `classify_event`, `snap_calendar_edges` | 4 |
| Sleuth reminders | `rebalance sleuth-sync` | `sleuth_sync_reminders` | 5 |
| Project registry | `rebalance ingest preflight`, `ingest sync` | `list_projects`, `run_preflight`, `confirm_projects`, `onboarding_status` | on demand |

### Credentials

| Source | Secret store | Mechanism |
|---|---|---|
| GitHub | `temp/rbos.config` (JSON, gitignored) | PAT with `repo:read` |
| Google Calendar | `/Users/noelsaw/secrets/google-calendar.env` + pickled OAuth token | OAuth 2.0 user consent |
| Sleuth | `/Users/noelsaw/secrets/sleuth-web-api-development.env` (mode 600) | Bearer token, 64-hex |
| Obsidian vault | none | filesystem read only |

Env-file paths are currently **hardcoded as absolute paths** in [src/rebalance/cli.py](src/rebalance/cli.py) (`GOOGLE_CALENDAR_ENV_PATH`, `SLEUTH_ENV_PATH`) — not `~/secrets/` — so the repo is not portable across operator home directories today. Both files should sit at mode 600. Env files are parsed manually (no `python-dotenv`). Nothing with a secret value is committed. **TODO:** resolve via `Path.home() / "secrets" / ...` (or an env var) before any second operator onboards.

### Adding a New Source

1. **Collector** — write `src/rebalance/ingest/<source>.py` following the `sleuth_reminders.py` or `github_scan.py` shape: a dataclass for one record, a `sync_*()` function that fetches → normalizes → upserts, and a module-local `ensure_<source>_schema(conn)`. Use `db_connection(path, ensure_fn)` from `db.py`.
2. **Schema** — keep the `CREATE TABLE` inside `ensure_<source>_schema`. Only promote to `db.py` if more than one module needs it. Use existing tables for unstructured text that should be embedded.
3. **Credentials** — filesystem secrets live in `~/secrets/<source>.env` with a loader next to `_load_google_calendar_env` / `_load_sleuth_env` in `cli.py`. Never add credentials to `temp/rbos.config`.
4. **Context gatherer** — add a `_gather_<source>_context()` function in `querier.py`. It reads from SQLite and returns `list[dict]`.
5. **Prompt section** — add a block in `_build_prompt()` to format the new context for the LLM.
6. **CLI + MCP** — add a Typer subcommand in `cli.py`, and wrap as an MCP tool in `mcp_server.py` if the source needs on-demand querying beyond `ask`.
7. **Daily sync** — append a step to `scripts/daily_sync.sh` with the `&& OK || FAILED` guard if the source should refresh unattended.
8. **Tests** — add `tests/test_<source>.py` that stubs the outbound call (patch `urlopen` for HTTP, filesystem for local sources). Verify insert / unchanged / update semantics.

No changes needed to the query layer, LLM synthesis, or MCP transport.

---

## Storage Layer

Single SQLite file at the path resolved from `REBALANCE_DB` env var. sqlite-vec extension loaded for vector operations.

### Tables by Domain

```
Project Registry (writer: registry.py)
  project_registry          — canonical project metadata

GitHub activity (writer: github_scan.py)
  github_activity            — per-repo event counts, keyed by (login, repo, scan_date)

GitHub artifacts (writer: github_knowledge.py; schema in db.py::ensure_github_schema)
  github_repo_meta           — repo-level metadata (default branch, issue/project support)
  github_branches            — local branch inventory for promotion/release inference
  github_labels              — label dictionary per repo
  github_milestones          — open/closed milestones with due dates
  github_releases            — published tags/releases
  github_items               — issues and PRs (unified table, item_type discriminates)
  github_comments            — issue/PR/review comments
  github_commits             — PR commit history
  github_check_runs          — CI check results per head_sha
  github_links               — explicit and inferred issue↔PR cross-references
  github_documents           — per-artifact embeddable document rows
  github_embeddings          — sqlite-vec virtual table for artifact embeddings
  github_embedding_meta      — model name + dim for the GitHub corpus

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
                               Keyed by Google event ID (INSERT OR REPLACE). Default sync window
                               is 30 days back + 7 days forward (365-day backfill available via
                               the CLI). No automatic deletion; manual cleanup if pruning is needed.

Sleuth reminders (writer: sleuth_reminders.py)
  sleuth_reminders           — one row per Slack reminder, keyed by reminder_id (TEXT PK).
                               Upsert with diff-based insert/update/unchanged counts;
                               first_seen_at preserved across syncs. Rows are never
                               deleted — state transitions (scheduled → posted → completed)
                               are mirrored as UPDATEs.
```

### Delta Strategy

Each ingestor defines how it reconciles a fresh fetch with stored rows:

- **Vault notes**: SHA-256 of raw file bytes stored in `vault_files.content_hash`. On re-ingest, unchanged files are skipped entirely. Changed files are deleted (CASCADE clears chunks/keywords/links) and re-inserted.
- **GitHub activity**: keyed by `(login, repo_full_name, scan_date)` with `ON CONFLICT REPLACE`. Each scan overwrites that day's data.
- **GitHub artifacts**: keyed by `(repo_full_name, item_type, number)` for items; comments/commits/checks keyed by GitHub ID. `ON CONFLICT REPLACE` on every sync, with a `since_days` lookback to skip untouched artifacts.
- **Embeddings**: chunks without a corresponding `embeddings` row get embedded. Model version change triggers full re-embed via `embedding_meta`.
- **Calendar**: keyed by Google event ID with `INSERT OR REPLACE`. Re-sync overwrites existing events and adds new ones within the requested window (default 30d back / 7d forward; 365d on demand for backfill). No auto-deletion.
- **Sleuth reminders**: keyed by `reminder_id`. Column-level diff against the stored row decides insert/update/unchanged; `first_seen_at` is set on insert and never overwritten; `last_seen_at` and `last_synced_at` refresh on every sync. Missing reminders are NOT deleted — terminal states (`completed`, `canceled`) remain as history.

---

## Query Layer

All consumers read from the same SQLite file. The query layer is source-agnostic.

```
SQLite @ $REBALANCE_DB
   │
   ├──▶ querier.py::ask()          ── semantic + keyword recall across vault,
   │                                   GitHub corpus, calendar, project registry,
   │                                   vault activity, temporal context
   │                                   (optionally synthesized by local Qwen3)
   │
   ├──▶ daily_report.py /          ── per-day / per-week calendar rollups
   │    weekly_report.py              with project classification
   │
   ├──▶ github_scan.py             ── per-project commit/PR/issue counts
   │    ::get_github_balance()        (surfaced as the github_balance MCP tool)
   │
   ├──▶ github_readiness.py /      ── release-state inference + issue↔PR
   │    github_reconciliation.py       close candidates
   │
   └──▶ mcp_server.py              ── exposes all of the above as MCP tools
                                       to Claude Code, Claude Desktop, etc.
```

`querier.py` is the central orchestrator. A single `ask()` call:

1. **Gathers context** from all sources in parallel-ready functions:
   - `_gather_project_context()` — registry entries + repos map
   - `_gather_github_context()` — per-project activity summary (from `github_activity`)
   - `_gather_github_semantic_context()` — semantic recall over the GitHub corpus (`github_documents` + `github_embeddings`)
   - `_gather_vault_context()` — semantic search (embed query → ANN)
   - `_gather_vault_activity()` — recently modified files
   - `_gather_calendar_context()` — upcoming + recent events from `calendar_events`
   - `_gather_temporal_context()` — day-of-week / weekend / holiday framing for the prompt
   - *(future: `_gather_sleuth_context()`, etc. — `sleuth_reminders` is mirrored but not yet gathered)*

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

## Invocation Modes

Three ways the pipeline runs:

1. **Interactive CLI** — `rebalance <subcommand>` via the Typer app. Ad-hoc and one-shot workflows (`calendar-create-event`, `github-release-readiness`, `sleuth-sync --json`, etc.).

2. **Unattended daily sync** — [scripts/daily_sync.sh](scripts/daily_sync.sh) runs under launchd ([scripts/com.rebalance-os.daily-sync.plist](scripts/com.rebalance-os.daily-sync.plist)) at 06:30 local time. Current sequence:

   ```
   1. ingest notes       (vault delta walk)
   2. ingest embed       (embed new/changed chunks)
   3. github-scan        (if token present)
   4. calendar-sync      (30d back, 14d forward)
   5. sleuth-sync --all  (reminders mirror)
   ```

   Each step uses `&& OK || FAILED` so one bad source never aborts the whole run.

3. **MCP tool handlers** — [src/rebalance/mcp_server.py](src/rebalance/mcp_server.py) wraps ingestors and readers as MCP tools. Host agents (Claude Code / Claude Desktop) call these on demand. `REBALANCE_DB` env var resolves the shared DB path.

---

## MCP Tool Surface

Tools are registered in `mcp_server.py:create_server()`. All tools share the same `database_path` resolved at server startup from `REBALANCE_DB`.

| Category | Tool | Purpose |
|----------|------|---------|
| Query | `ask` | Natural language query across all sources (with optional local LLM synthesis) |
| Query | `query_notes` | Vault semantic search (embedding-based) |
| Query | `search_vault` | Vault keyword search (TF-IDF) |
| Query | `query_github_context` | Semantic search over the GitHub artifact corpus (issues, PRs, comments, reviews, commits) |
| Query | `github_balance` | Per-project GitHub activity summary |
| Query | `github_release_readiness` | Infer milestone/release readiness from the local GitHub corpus |
| Query | `github_close_candidates` | Suggest open issues that likely map to merged PRs |
| Registry | `list_projects` | Query project registry |
| Onboarding | `onboarding_status` | Check setup completion |
| Onboarding | `setup_github_token` | Validate and store GitHub PAT |
| Onboarding | `run_preflight` | Discover project candidates (read-only) |
| Onboarding | `confirm_projects` | Write registry and sync |
| Calendar | `create_calendar_event` | Create a Google Calendar event via local OAuth |
| Calendar | `review_timesheet` | Surface unclassified calendar events that need a project decision |
| Calendar | `classify_event` | Persist an include/exclude/project classification for an event |
| Calendar | `snap_calendar_edges` | Detect and (optionally) fix slightly overlapping events |
| Sync | `sleuth_sync_reminders` | Pull Slack reminders from the Sleuth Web API and upsert to SQLite |

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
    github_scan.py         — GitHub Events API collector + per-project balance query
    github_knowledge.py    — per-repo artifact sync (issues/PRs/comments/commits/checks) + embedding
    github_readiness.py    — release-readiness inference over the local GitHub corpus (read-only)
    github_reconciliation.py — issue ↔ PR close-candidate inference (read-only)
    db.py                  — shared DB connection, schema, sqlite-vec loading
    md_parser.py           — pure markdown parsing (frontmatter, wikilinks, tags, chunking)
    note_ingester.py       — vault walker, delta detection, TF-IDF keywords
    embedder.py            — mlx-embeddings batch embed + ANN query
    calendar.py            — Google Calendar API collector + SQLite persistence
    sleuth_reminders.py    — Sleuth Web API collector (Bearer auth, urllib) + upsert
    querier.py             — multi-source context gathering + local LLM synthesis
```

---

## License

Copyright 2025 Hypercart DBA Neochrome, Inc.

Licensed under the **Apache License, Version 2.0**. See [APACHE-LICENSE-2.0.txt](./APACHE-LICENSE-2.0.txt).
