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
| P1 | GitHub | `github_scan.py` + `github_knowledge.py` + `github_readiness.py` + `github_reconciliation.py` + `semantic_index.py` | canonical GitHub tables (`github_activity`, `github_repo_meta`, `github_items`, `github_comments`, `github_commits`, `github_check_runs`, `github_links`, etc.) plus derived `semantic_documents` / `semantic_embeddings` | Yes — unified semantic index across GitHub artifacts; older `github_documents` / `github_embeddings` remain for legacy per-source tools | Active |
| P1 | Obsidian Vault | `note_ingester.py` + `embedder.py` + `semantic_index.py` | canonical vault tables (`vault_files`, `chunks`, `keywords`, `links`) plus derived `semantic_documents` / `semantic_embeddings` | Yes — legacy vault `embeddings` plus the unified semantic index | Active |
| P2 | Google Calendar | `calendar.py` | `calendar_events` table (default window 30d back / 7d forward; no auto-deletion) | No — structured event data | Active |
| P3 | Sleuth reminders (Slack) | `sleuth_reminders.py` | `sleuth_reminders` table | No — structured reminder rows | Active |
| P4 | Email (Gmail) | `gmail.py` + `semantic_index.py` | `email_messages` plus derived `semantic_documents` / `semantic_embeddings` | Yes — via the unified semantic index | Experimental |

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
                     │                                                             github_documents [legacy]
                     │                                                          ─ github_embeddings [legacy vec0]
                     ├▶ semantic_index.py        unified backfill + embed      ──▶ semantic_documents
                     │                                                             semantic_embeddings (vec0)
                     │                                                             semantic_embedding_meta
                     ├▶ github_readiness.py      release-state inference       ── (reads only)
                     └▶ github_reconciliation.py issue ↔ PR matching           ── (reads only)

Obsidian Vault ──────▶ note_ingester.py          walk *.md, chunk, TF-IDF,    ──▶ vault_files, chunks,
  (filesystem)       │                             wikilinks                       keywords, links
                     ├▶ embedder.py              Qwen3-Embedding-0.6B         ──▶ embeddings (legacy vec0, 1024-dim)
                     │                             via mlx-embeddings
                     └▶ semantic_index.py        unified backfill + embed      ──▶ semantic_documents
                                                                                  semantic_embeddings (vec0)
                                                                                  semantic_embedding_meta

Google Calendar ─────▶ calendar.py               OAuth pickled token,         ──▶ calendar_events
  (Calendar API)                                   30d back / 14d forward

Sleuth Web API ──────▶ sleuth_reminders.py       Bearer auth, stdlib urllib,  ──▶ sleuth_reminders
  (Vultr dev :2020)                                GET /workspace/<name>/
                                                   reminders?format=rebalance

Gmail API ───────────▶ gmail.py                  newest-N inbox messages      ──▶ email_messages
  (ADC auth)         │
                     └▶ semantic_index.py        unified backfill + embed     ──▶ semantic_documents
                                                                                  semantic_embeddings (vec0)

Project Registry ────▶ registry.py +              MD registry → projects.yaml ──▶ project_registry
  (vault markdown)     preflight.py                → SQLite projection
```

### Invocation points

| Source | CLI | MCP tool(s) | Daily-sync step |
|---|---|---|---|
| GitHub activity | `rebalance github-scan` | `github_balance` | 3 |
| GitHub artifacts | `rebalance github-sync-artifacts`, `github-embed`, `github-query` | `query_github_context`, `github_release_readiness`, `github_close_candidates` | on demand |
| Obsidian vault | `rebalance ingest notes`, `ingest embed`, `query`, `search` | `query_notes`, `search_vault` | 1 + 2 |
| Unified semantic index | `rebalance semantic-backfill`, `semantic-embed`, `semantic-query` | `semantic_query` | 6 |
| Google Calendar | `rebalance calendar-sync`, `calendar-create-event`, `calendar-snap-edges`, `calendar-daily-report`, `calendar-weekly-report` | `create_calendar_event`, `review_timesheet`, `classify_event`, `snap_calendar_edges` | 4 |
| Sleuth reminders | `rebalance sleuth-sync` | `sleuth_sync_reminders` | 5 |
| Email (Gmail) | no stable CLI surface yet; refreshed through orchestration | covered indirectly via `refresh_index(scope=["email"])` and `semantic_query` | on demand |
| Project registry | `rebalance ingest preflight`, `ingest sync` | `list_projects`, `run_preflight`, `confirm_projects`, `onboarding_status` | on demand |
| Orchestration / health | `rebalance dashboard`, `rebalance profile-sync` | `index_status`, `refresh_index`, `list_watched_repos`, `publish_pulse`, `diagnose_repo` | n/a |

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
  github_documents           — per-artifact embeddable document rows (legacy per-source semantic path)
  github_embeddings          — sqlite-vec virtual table for artifact embeddings (legacy)
  github_embedding_meta      — model name + dim for the legacy GitHub corpus

Vault Ingestion (writer: note_ingester.py)
  vault_files                — one row per .md file, with content_hash for delta detection
  chunks                     — heading-based chunks, FK to vault_files (CASCADE delete)
  keywords                   — TF-IDF top-K per chunk, FK to chunks (CASCADE delete)
  links                      — wikilinks and embeds, FK to vault_files (CASCADE delete)

Legacy Vault Embeddings (writer: embedder.py)
  embeddings                 — sqlite-vec virtual table, float[1024], keyed by chunk_id
  embedding_meta             — model name, dimension, last embed timestamp

Unified Semantic Index (writer: semantic_index.py; schema in db.py::ensure_semantic_schema)
  semantic_documents         — derived cross-source document layer (vault, github, email)
  semantic_embeddings        — sqlite-vec virtual table keyed by semantic_documents.id
  semantic_embedding_meta    — model name + dim for the unified semantic index

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

Email (writer: gmail.py)
  email_messages             — newest-N inbox messages mirrored locally for semantic backfill.
                               Gmail sync is read-only and currently consumed through the
                               unified semantic layer rather than a first-class MCP query tool.
```

### Delta Strategy

Each ingestor defines how it reconciles a fresh fetch with stored rows:

- **Vault notes**: SHA-256 of raw file bytes stored in `vault_files.content_hash`. On re-ingest, unchanged-content files have their `last_modified` refreshed if the on-disk mtime moved forward (a "touch") but skip all parsing and embedding work — surfaced as `touched_files` in the ingest result. Changed-content files are deleted (CASCADE clears chunks/keywords/links) and re-inserted.
- **GitHub activity**: keyed by `(login, repo_full_name, scan_date)` with `ON CONFLICT REPLACE`. Each scan overwrites that day's data.
- **GitHub artifacts**: keyed by `(repo_full_name, item_type, number)` for items; comments/commits/checks keyed by GitHub ID. `ON CONFLICT REPLACE` on every sync, with a `since_days` lookback to skip untouched artifacts.
- **Legacy vault embeddings**: chunks without a corresponding `embeddings` row get embedded. Model version change triggers full re-embed via `embedding_meta`.
- **Unified semantic index**: `semantic_documents` is backfilled from vault, GitHub, and email source tables. `semantic_embeddings` only re-embeds rows whose `content_hash` changed or whose `embedded_model_version` no longer matches current settings.
- **Calendar**: keyed by Google event ID with `INSERT OR REPLACE`. Re-sync overwrites existing events and adds new ones within the requested window (default 30d back / 7d forward; 365d on demand for backfill). No auto-deletion.
- **Sleuth reminders**: keyed by `reminder_id`. Column-level diff against the stored row decides insert/update/unchanged; `first_seen_at` is set on insert and never overwritten; `last_seen_at` and `last_synced_at` refresh on every sync. Missing reminders are NOT deleted — terminal states (`completed`, `canceled`) remain as history.
- **Email**: keyed by Gmail `message_id`. The refresh path mirrors the newest inbox window into `email_messages`, then backfills those rows into `semantic_documents`. Older rows can remain in the semantic layer even if they fall out of the current fetch window.

---

## Query Layer

All consumers read from the same SQLite file. The query layer is source-agnostic.

```
SQLite @ $REBALANCE_DB
   │
   ├──▶ semantic_index.py::query() ── unified semantic search across vault,
   │                                   GitHub, and email (`semantic_query` MCP tool)
   │
   ├──▶ querier.py::ask()          ── layered context gathering across vault,
   │                                   GitHub, calendar, project registry,
   │                                   vault activity, temporal context,
   │                                   then optional local Qwen3 synthesis
   │
   ├──▶ daily_report.py /          ── per-day / per-week calendar rollups
   │    weekly_report.py              with project classification
   │
   ├──▶ index_ops.py               ── orchestrated refreshes, watched-repo
   │                                   derivation, source freshness, drift checks
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

There are now two primary query paths:

1. **Unified semantic retrieval** via `semantic_index.query()` and the `semantic_query` MCP tool. This is the preferred cross-source vector path for vault + GitHub + email.
2. **Narrative synthesis** via `querier.py::ask()`, which still assembles broader multi-source context and can run the local Qwen layer.

`querier.py` remains the central orchestrator for `ask()`:

1. **Gathers context** from all sources in parallel-ready functions:
   - `_gather_project_context()` — registry entries + repos map
   - `_gather_github_context()` — per-project activity summary (from `github_activity`)
   - `_gather_github_semantic_context()` — legacy semantic recall over the GitHub-only corpus
   - `_gather_vault_context()` — legacy vault semantic search
   - `_gather_vault_activity()` — recently modified files
   - `_gather_calendar_context()` — upcoming + recent events from `calendar_events`
   - `_gather_temporal_context()` — day-of-week / weekend / holiday framing for the prompt
   - *(future: richer `_gather_sleuth_context()` / email-specific narrative gatherers — both sources already land in local SQLite, but the unified semantic path is the main retrieval surface today)*

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

Four ways the pipeline runs:

1. **Interactive CLI** — `rebalance <subcommand>` via the Typer app. Ad-hoc and one-shot workflows (`calendar-create-event`, `github-release-readiness`, `sleuth-sync --json`, `profile-sync`, etc.). `rebalance` invoked with no arguments launches the live dashboard (mode 4).

2. **Unattended scheduled syncs** — three launchd jobs cooperate:

   - **Daily full sync** ([scripts/daily_sync.sh](scripts/daily_sync.sh) / [scripts/com.rebalance-os.daily-sync.plist](scripts/com.rebalance-os.daily-sync.plist)) at 06:30 local time, plus on boot/login if 06:30 was missed. Calls `refresh_index(scope=["all"])`, which runs vault → github → calendar → sleuth → unified semantic index. Per-scope failures are captured in the result's `errors` list rather than aborting the run.
   - **Hourly vault refresh** ([scripts/vault_sync.sh](scripts/vault_sync.sh) / [scripts/com.rebalance-os.vault-sync.plist](scripts/com.rebalance-os.vault-sync.plist)) at HH:15 from 06:15 to 23:15. Calls `refresh_index(scope=["vault"])` only — keeps notes edited mid-day visible in the dashboard / pulse / semantic search without waiting for the next morning's full sync. Vault ingest is cheap (~0.02s with no changes) and fully offline.
   - **Hourly pulse publish** ([scripts/pulse_sync.sh](scripts/pulse_sync.sh) / [scripts/com.rebalance-os.pulse-sync.plist](scripts/com.rebalance-os.pulse-sync.plist)) on the hour, 06:00 to 23:00. Renders the operator pulse markdown and pushes it to the configured private repo, but only when the rendered content actually changed since the previous run.

3. **MCP tool handlers** — [src/rebalance/mcp_server.py](src/rebalance/mcp_server.py) wraps ingestors and readers as MCP tools. Host agents (Claude Code / Claude Desktop) call these on demand. `REBALANCE_DB` env var resolves the shared DB path.

4. **Live dashboard** — [scripts/dashboard.py](scripts/dashboard.py) is a Rich Live monitor that polls the local SQLite every 2 seconds (cheap; no network) and runs `refresh_index(scope=["github"])` in a background thread every 10 minutes so the underlying data actually changes. Launch via `rebalance` (no args) or `rebalance dashboard`. Press `r` to trigger an immediate GitHub refresh, `q` (or Ctrl+C) to quit. Theming and cadence are env-var controlled (`PULSE_INVERSE`, `PULSE_TICK`, `PULSE_AUTO_MIN`, `REBALANCE_TZ`). The dashboard is intentionally read-only against the same DB the MCP server and the launchd jobs write to.

---

## MCP Tool Surface

Tools are registered in `mcp_server.py:create_server()`. All tools share the same `database_path` resolved at server startup from `REBALANCE_DB`.

| Category | Tool | Purpose |
|----------|------|---------|
| Index | `index_status` | Snapshot source freshness, row counts, semantic-index health, and drift between source tables and the unified semantic layer |
| Index | `refresh_index` | Single orchestration entry point for vault / github / calendar / sleuth / email / semantic refresh flows |
| Index | `list_watched_repos` | Show the merged monitored-repo set: project registry ∪ recent GitHub activity − ignored repos |
| Query | `ask` | Natural language query across all sources (with optional local LLM synthesis) |
| Query | `semantic_query` | Preferred vector search over the unified semantic index (`semantic_documents` + `semantic_embeddings`) |
| Query | `query_notes` | Vault semantic search (embedding-based) |
| Query | `search_vault` | Vault keyword search (TF-IDF) |
| Query | `query_github_context` | Legacy GitHub-only semantic search over the older per-source artifact index |
| Query | `github_balance` | Per-project GitHub activity summary |
| Query | `github_release_readiness` | Infer milestone/release readiness from the local GitHub corpus |
| Query | `github_close_candidates` | Suggest open issues that likely map to merged PRs |
| Diagnostics | `diagnose_repo` | Walk the watched-repos + sync funnel for a single repo (optionally a `sha` or `pr`) and explain coverage + freshness gaps; opt-in `live=True` distinguishes "we never synced" from "PAT can't see it" |
| Publishing | `publish_pulse` | Render today's + yesterday's activity into markdown and commit/push it to the configured private pulse repo when content changed |
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
    agent_tags.py           — classify pulse rows by source (`claude-cloud`,
                              `codex-cloud`, `lovable`, `local-vscode`, `human`)
    config.py              — secrets storage (temp/rbos.config)
    registry.py            — project registry sync (Markdown ↔ YAML ↔ SQLite)
    preflight.py           — onboarding discovery + confirmation
    github_scan.py         — GitHub Events API collector + per-project balance query
    github_knowledge.py    — per-repo artifact sync (issues/PRs/comments/commits/checks) + embedding
    github_readiness.py    — release-readiness inference over the local GitHub corpus (read-only)
    github_reconciliation.py — issue ↔ PR close-candidate inference (read-only)
    db.py                  — shared DB connection, schema, sqlite-vec loading
    index_ops.py           — single orchestration layer behind `refresh_index()`,
                              `index_status()`, and `list_watched_repos()`
    md_parser.py           — pure markdown parsing (frontmatter, wikilinks, tags, chunking)
    note_ingester.py       — vault walker, delta detection, TF-IDF keywords
    embedder.py            — mlx-embeddings batch embed + ANN query
    calendar.py            — Google Calendar API collector + SQLite persistence
    gmail.py               — Gmail inbox mirroring for local email capture
    sleuth_reminders.py    — Sleuth Web API collector (Bearer auth, urllib) + upsert
    slack_users.py         — Slack user-id → friendly-name lookup, file-mtime cached;
                              feeds the dashboard sleuth panel and the pulse markdown
    diagnose.py            — repo-level diagnostic that walks the watched-repos +
                              sync funnel for one repo (optionally sha/PR) — backs
                              the diagnose_repo MCP tool
    profile_sync.py        — daily-sync log parser that surfaces per-repo GitHub
                              timings; backs the rebalance profile-sync subcommand
    pulse.py               — pulse snapshot collection, markdown render, and
                              conditional commit/push orchestration
    querier.py             — multi-source context gathering + local LLM synthesis
    semantic_index.py      — unified semantic document backfill, embedding, and query

scripts/                   — Operator entry points (not part of the importable package)
  dashboard.py             — Rich Live terminal dashboard (mode 4 above)
  daily_sync.sh            — daily_sync launchd entry (mode 2)
  vault_sync.sh            — hourly vault-only launchd entry (mode 2)
  pulse_sync.sh            — hourly pulse-publish launchd entry (mode 2)
  install_scheduler.sh     — install/reload the daily launchd job
  install_vault_scheduler.sh — install/reload the hourly vault launchd job
  install_pulse_scheduler.sh — install/reload the hourly pulse launchd job
```

---

## License

Copyright 2025 Hypercart DBA Neochrome, Inc.

Licensed under the **Apache License, Version 2.0**. See [APACHE-LICENSE-2.0.txt](./APACHE-LICENSE-2.0.txt).
