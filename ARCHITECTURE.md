# rebalance OS — ARCHITECTURE.md

> How data flows through the system. For execution decisions see [PROJECT.md](./PROJECT.md), for tool specs see [MCP.md](./MCP.md), for the *why* behind these decisions see [GUIDING-PRINCIPLES.md](./GUIDING-PRINCIPLES.md).

> **New maintainer? Start with [Maintainer Orientation](#maintainer-orientation-start-here)** — the load-bearing symbols, the two hubs, where to start reading, and one end-to-end trace. **This doc is load-bearing, not decorative:** `audit_modules` (the `audit_modules` MCP tool / [scripts/audit_modules.py](scripts/audit_modules.py)) and the PDDA gate enforce that collectors, render modules, and scheduled jobs stay documented here — update ARCHITECTURE.md in the *same PR* as any structural change.

---

## Core Pipeline

**INVARIANT**: **Compose, don't mutate**. No new query surfaces (like `semantic_query` vs `ask`) or UI renderers (web server vs static HTML) may be introduced without a plan to deprecate and replace the old one. If extending an existing pipeline, build reusable primitives in `src/rebalance/lib/` instead of duplicating logic in the caller.

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

Every raw incoming source follows the same pattern: **collect → normalize → store → query**. The collector registry in `index_ops.py` currently also includes derived local scans and post-ingest/export jobs (`code`, `semantic`, `sync`, `focus5`, `ask_self`), so not every registered scope is a raw upstream signal. The query layer and LLM layers are source-agnostic once data is in SQLite.

### Sync model (in plain English)

Every `refresh_index` run is **incremental** — nothing is re-downloaded from scratch. What "incremental" means depends on what the upstream API lets us ask for cheaply, but three patterns cover every source:

1. **Hash/ID delta** — only fetch or reprocess what actually changed. Used by: vault notes, GitHub artifacts, embeddings.
2. **Window refetch + upsert** — refetch a bounded time-or-count window every run and upsert by ID; nothing is auto-deleted. Used by: GitHub activity (last 30d events), calendar (30d back / 7d forward), email (newest 100 `in:inbox` messages).
3. **Full refetch + column-diff** — refetch the whole upstream set, compare row-by-row, and keep everything as history. Used by: sleuth reminders.

A few caps to know about up-front:

- **Email** is capped at the **newest 100 inbox messages per run** today (Phase 1, shipped 2026-05-12) — default filter `in:inbox`, overridable via `gmail_query_filter` in `temp/rbos.config`. Not "important and starred." See [PROJECT/1-INBOX/EMAIL-INGEST.md](PROJECT/1-INBOX/EMAIL-INGEST.md).
- **Calendar** refetches a **30-day back / 7-day forward window** by default; a 365-day backfill is available on demand via the CLI.
- **GitHub activity** is bounded by the GitHub Events API's own ~30-day retention.
- **Vault, sleuth, embeddings** are unbounded — they cover everything they can see.

Detailed per-source mechanics live in [Storage Layer → Sync semantics per source](#sync-semantics-per-source).

---

## Maintainer Orientation (start here)

New to the codebase? Read this section first — it is the mental model the rest of the doc assumes.

### The two hubs (the model that prevents confusion)

The system has **two** central things with *opposite* roles. Conflating them is the most common newcomer mistake:

- **Orchestration spine — fan-OUT.** `refresh_index()` plus the `COLLECTORS` registry in
  [src/rebalance/ingest/index_ops.py](src/rebalance/ingest/index_ops.py) reach **out** into every collector. This is the
  one intended write/refresh entry point. New ingestion work registers here (`register_collector(Collector(...))`).
- **Persistence base — fan-IN.** [src/rebalance/paths.py](src/rebalance/paths.py)::`resolve_database_path()` (answers *which* DB file)
  → `db_connection()` in [src/rebalance/ingest/db/](src/rebalance/ingest/db/) (answers *how* to open it). Everything reaches **down** to these.

They compose in a single hop (`refresh_index() → db_connection()`). Keeping orchestration and persistence in
**separate** nodes is *why the codebase has no god-object* despite `db_connection()` being the single most-connected
symbol: it is a thin, stateless connection factory (a dependency *sink*), not a place where logic lives. **Read from it
freely; think twice before changing it** — its blast radius is the whole system.

### Load-bearing symbols (you will see these in almost every file)

| Symbol | Where | What it is / why it's everywhere |
|---|---|---|
| `db_connection()` | `ingest/db/connection.py` | SQLite factory (WAL, foreign keys, 30s busy-timeout, sqlite-vec). Every collector opens its connection here. **High fan-in, zero business logic.** |
| `resolve_database_path()` | `paths.py` | "Which DB file" — layered resolver (`--database` flag → `REBALANCE_DB` → canonical app-data path → user config). Single source of truth for the DB location. |
| `_read_config()` / `_write_config()` | `ingest/config.py` | Layered config + secrets (`temp/rbos.config` + keyring/secret-store). |
| `CalendarConfig` | `ingest/calendar_config.py` | Validated calendar settings (event filters, signal weights). |
| `normalize_github_repo_name()` | `ingest/github_scan.py` | Canonical `owner/repo` string used across every GitHub path. |
| `refresh_index()` | `ingest/index_ops.py` | The orchestrated ingest entry point (see "two hubs" above). |
| `rank_next_actions()` | `ingest/next_actions.py` | Entry point for the "what to do next" engine (see [Query Layer](#the-next-actions-engine-what-to-do-next)). |
| `run_doctor()` | `doctor.py` | Health-check orchestrator; backs `rebalance doctor` (run it before claiming a change works). |

### Where to start reading when touching X

| If you're working on… | Start in | Then read |
|---|---|---|
| A data source (add/fix ingest) | `ingest/index_ops.py` (the `COLLECTORS` registry) + that source's `ingest/<source>.py` | [Adding a New Source](#adding-a-new-source) |
| The read / query side | `ingest/semantic_index.py` (retrieval primitive) + `ingest/querier.py` (`ask()` orchestrator) | [Query Layer](#query-layer) |
| Focus 5 roster / ranking | `ingest/focus5_scan.py` | the `web.py` `/focus-5` route |
| Apple Reminders | `ingest/apple_reminders.py` (read) + `ingest/apple_reminders_write.py` (write, via signed helper) | — |
| "What to do next" | `ingest/next_actions.py` | [The Next Actions engine](#the-next-actions-engine-what-to-do-next) |
| Web dashboard surfaces | `web.py` + `web_components.py` | [Invocation Modes](#invocation-modes) |
| Config / secrets | `ingest/config.py` + `paths.py` | [Credentials](#credentials) |
| Scheduling / launchd jobs | [SCHEDULER.md](SCHEDULER.md) + `scripts/*_sync.sh` | [Invocation Modes](#invocation-modes) |
| The database itself (schema/migrations) | `ingest/db/` (connection, schema, migrations) | [Storage Layer](#storage-layer) |

### One request, end-to-end (worked trace)

A `rebalance refresh` (or the `refresh_index` MCP tool) flows through real symbols like this:

1. **`refresh_index()`** [`index_ops.py`] resolves the scope and iterates the `COLLECTORS` registry (each entry added via `register_collector(Collector(...))`).
2. Each collector's **`sync_*()`** runs fetch → normalize → upsert — e.g. `sync_apple_reminders()`, `github_scan()`, `sync_sleuth_reminders()`.
3. The collector opens storage via **`db_connection(path, ensure_<source>_schema)`** and upserts (e.g. `sync_apple_reminders()` → `upsert_apple_reminders()` → `db_connection()`).
4. **Derived stages** follow (`code`, `semantic`, `sync`): the unified semantic index is rebuilt by `backfill_semantic_documents()` and embedded.
5. **Read side:** `semantic_index.query()` (raw retrieval primitive; MCP `semantic_query`) and `querier.ask()` (broad synthesis orchestrator) read the *same* SQLite via `resolve_database_path()` → `db_connection()`.
6. **Surfaces:** the `web.py` routes (`/focus-5`, `/auth-log`, what's-next), the Typer CLI, and the MCP tools all read through that one persistence base.

---

## Signal Sources

Raw incoming sources have a priority, a collector module, and a target table. For detailed field specs and status, see [PROJECT.md — Signals](./PROJECT.md).

| Priority | Source | Collector | Storage | Vectorized | Status |
|----------|--------|-----------|---------|------------|--------|
| P1 | GitHub | `github_scan.py` + `github_knowledge.py` + `github_readiness.py` + `github_reconciliation.py` | `github_activity`, `github_repo_meta`, `github_branches`, `github_items`, `github_comments`, `github_documents`, `github_embeddings` | Yes — structured repo signals plus semantic corpus for issues, PRs, comments, reviews, commit messages, and issue/PR reconciliation | Active |
| P1 | Obsidian Vault | `note_ingester.py` + `embedder.py` | `vault_files`, `chunks`, `keywords`, `links`, `embeddings` | **Yes** — Qwen3-Embedding-0.6B, 1024-dim, sqlite-vec | Active |
| P2 | Google Calendar | `calendar.py` | `calendar_events` table (default window 30d back / 7d forward; no auto-deletion) | No — structured event data | Active |
| P3 | Sleuth reminders (Slack) | `sleuth_reminders.py` | `sleuth_reminders` table | No — structured reminder rows | Active |
| P4 | Email (Gmail) | `gmail.py` + `semantic_index.py` | `email_messages` | Yes — subject + snippet participate in the unified semantic index | Active (Phase 1, shipped 2026-05-12): newest 100 `in:inbox` messages per run; metadata + snippet only, no body parsing yet |
| P4 | Figma comments | `figma.py` + `semantic_index.py` | `figma_comments` | Yes — registry-provider semantic docs for comments | Active (opt-in): requires a PAT plus explicit `figma_file_keys` allow-list |

### Other registered collector scopes

These are registered in `index_ops.py` and dispatch through the same `refresh_index()` orchestrator, but they are not raw upstream data sources:

| Scope | Kind | Purpose | Included in `all` |
|---|---|---|---|
| `code` | derived local scan | AST/code chunk collection into the unified semantic index | Yes |
| `semantic` | projection stage | Unified semantic backfill + embed maintenance | Yes |
| `sync` | export stage | Export calendar/email snapshots to the pulse sync repo | Yes |
| `focus5` | derived local scan | Build the device-local Focus 5 roster + signal cache | No |
| `ask_self` | derived local scan | Inventory ask_self indexes on this device | No |

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

Google Calendar ─────▶ calendar.py               OAuth token (keyring+JSON),  ──▶ calendar_events
  (Calendar API)                                   30d back / 7d forward

Sleuth Web API ──────▶ sleuth_reminders.py       Bearer auth, stdlib urllib,  ──▶ sleuth_reminders
  (Vultr dev :2020)                                GET /workspace/<name>/
                                                   reminders?format=rebalance

Gmail API ───────────▶ gmail.py                  desktop OAuth (gmail.readonly), ──▶ email_messages
  (gmail.googleapis.com)                           filter in:inbox by default,
                                                   newest 100 messages/run

Gmail MCP connector ─▶ gmail.py                  agent-pushed message payloads ─▶ email_messages
  (opt-in push path)                               via ingest_email_messages()

Figma Comments API ───▶ figma.py                 file-key allow-list + PAT    ──▶ figma_comments
  (api.figma.com)                                                                        │
                                                                                         └─▶ semantic_documents
                                                                                             semantic_embeddings

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
| Email (Gmail) | `rebalance refresh`, `semantic-backfill`, `semantic-query` | `refresh_index`, `semantic_query`, `ingest_gmail_messages` | 6 |
| Figma comments | `rebalance refresh` | `refresh_index` | opt-in |
| Focus 5 | `refresh_index(scope=["focus5"])`, `rebalance serve` / pulse server | web `/focus-5` route | opt-in |
| ask_self inventory | `refresh_index(scope=["ask_self"])` | `list_ask_self_repos` | opt-in |
| Project registry | `rebalance ingest preflight`, `ingest sync`, `onboard` | `list_projects`, `run_preflight`, `confirm_projects`, `onboarding_status` | on demand |

> Registry write discipline (Phase 5, `ingest/lifecycle.py`): discovery is
> read-only and stamps candidates with `provenance` (remote-activity /
> vault-note; local-scan reserved); `confirm_and_write` is the only curated
> write path; activity inference maintains only rows it created (marked
> `inference.generated_by`) and never touches curated rows; priority rules
> overlay at read time and are never persisted.

> Preferred write path: `refresh_index(scope=[...])` is the orchestrated entry
> point. Several source-specific CLI/MCP write commands still exist for
> historical/operator reasons, but some of them bypass the collector/orchestrator
> layer and call leaf ingest functions directly.

> **Sleuth production is read from a published file — no inbound access.** The
> Sleuth box pushes its reminders to a private git repo
> (`rebalance-git-pulse:sync/sleuth/reminders-<ws>.json`); rebalance-OS reads the
> local clone (`base_url` is a `file://`/local path). No SSH tunnel, no open port.
> See [SLEUTH_SYNC.md](SLEUTH_SYNC.md). (Dev still hits the API directly.)

### Credentials

| Source | Secret store | Mechanism |
|---|---|---|
| GitHub | OS keyring + out-of-repo secret store (`~/.config/rebalance-os/secrets`, `0600`) fallback; `gh` CLI as last-resort read fallback | PAT: classic `repo` scope, or fine-grained with All-repos read-only Contents/Metadata (public-only tokens hide private work); persisted to keyring + secret store for launchd reachability — no longer written to `temp/rbos.config` |
| Google Calendar | `google-calendar.env` (client credentials) via `resolve_secret_path()` + OAuth user-token in keyring with a JSON fallback at `~/.config/rebalance-os/secrets/google-calendar-oauth` (a legacy pickle migrates to JSON on read) | OAuth 2.0 user consent |
| Sleuth | OS keyring + secret store (`~/.config/rebalance-os/secrets/sleuth_web_api`); legacy `*.env` files still read for un-migrated devices | Bearer token, 64-hex |
| Gmail | Desktop OAuth token in keyring + JSON fallback at `~/.config/rebalance-os/secrets/google-gmail-oauth`, or MCP push-ingest mode | `gmail.readonly` desktop OAuth, or agent-pushed `ingest_gmail_messages` path when `gmail_ingest_method=mcp` |
| Figma | OS keyring + secret store for the PAT; `temp/rbos.config` holds only the (non-secret) file-key allow-list | Personal access token + explicit file selection |
| Obsidian vault | none | filesystem read only |

Env-file paths resolve via [src/rebalance/paths.py](src/rebalance/paths.py)::`resolve_secret_path(name)` — the layered chain is `REBALANCE_SECRETS_DIR` env var → `secrets_dir` field in `~/.config/rebalance-os/config.json` (set via `rebalance config set-secrets-dir`) → `~/secrets/` legacy default. The domain CLI loaders (for example, [src/rebalance/cli/calendar.py](src/rebalance/cli/calendar.py) and [src/rebalance/cli/sleuth.py](src/rebalance/cli/sleuth.py)) use this resolver, so the repo is portable across operator home directories without hardcoded env-file paths. Env files should sit at mode 600. Env files are parsed manually (no `python-dotenv`). Nothing with a secret value is committed.

### Adding a New Source

> **The current preferred way to add a source is the collector / `SourceModule`
> contract — see [src/rebalance/ingest/index_ops.py](src/rebalance/ingest/index_ops.py)
> and the developer guide [PLUGINS.md](./PLUGINS.md).** It covers the registry
> descriptor, the optional `semantic_docs` provider, secrets/keyring, numbered
> migrations, and tests, with Figma as the worked example. The steps below are
> the practical recipe for the built-in sources.

1. **Collector** — write `src/rebalance/ingest/<source>.py` following the `sleuth_reminders.py` or `github_scan.py` shape: a dataclass for one record, a `sync_*()` function that fetches → normalizes → upserts, and a module-local `ensure_<source>_schema(conn)`. Use `db_connection(path, ensure_fn)` from the `ingest/db/` package.
2. **Schema** — keep the `CREATE TABLE` inside `ensure_<source>_schema`. Only promote to the shared `ingest/db/` package if more than one module needs it. Use existing tables for unstructured text that should be embedded.
3. **Registry** — register the source in `index_ops.py` with `register_collector(Collector(...))`. Add `requires=...`, `semantic_docs=...`, and/or `candidates=...` metadata if the source needs preconditions, participates in the unified semantic index, or contributes next-action candidates to the HiQS ranking. The `candidates=` provider is how a source reaches the ranked "what to do next" verdict — no edit to the ranker's dispatch.
4. **Credentials** — if the source uses env-style secret files, resolve them through `resolve_secret_path()` and a small domain loader (see `cli/calendar.py` / `cli/sleuth.py`). Never hardcode secrets in repo files.
5. **Next-action candidates** — to feed the HiQS ranking, supply a `candidates=` provider on the `Collector` (a function `bundle → list[candidate dict]`, each Attested with `source`/`evidence`/`why`). `_operator_candidates()` walks the registry, so no ranker edit is needed. A source participates in `ask()` automatically once it is in the ranked bundle — `ask()` reads the whole ranking via `_gather_hiqs_context()`.
6. **Prompt section** — the HiQS section in `_build_prompt()` already renders every ranked source; add a bespoke `_build_prompt()` block only for context that is NOT a ranked next-action.
7. **CLI + MCP** — add thin wrappers in `src/rebalance/cli/*` and `src/rebalance/mcp/tools/*` if the source needs direct user-facing operations beyond `refresh_index()`.
8. **Scheduled refresh** — ensure `included_in_all` and any explicit scheduler usage match the source's intended unattended behavior.
9. **Tests** — add `tests/test_<source>.py` that stubs the outbound call (patch `urlopen` for HTTP, filesystem for local sources). Verify insert / unchanged / update semantics.

No changes needed to the query layer, LLM synthesis, or MCP transport.

---

## Storage Layer

Single SQLite file resolved by `src/rebalance/paths.py::resolve_database_path()`. Default canonical location is `~/Library/Application Support/rebalance-os/rebalance.db` on macOS (or `$XDG_DATA_HOME/rebalance-os/rebalance.db` on Linux); `REBALANCE_DB` env var, an `--database` flag, or a user-config override all win against the canonical path when set. sqlite-vec extension loaded for vector operations.

### Write discipline (one writer per table)

The single most important invariant for a new maintainer to preserve:

- **Reads are unrestricted.** Anything may open `db_connection()` and `SELECT`. The "Tables by Domain" list below names the *writer* for each table — that ownership is about **writes**, not reads.
- **One writer per table.** Each table is written by exactly one module (e.g. `github_activity` ← `github_scan.py`, `sleuth_reminders` ← `sleuth_reminders.py`, `semantic_documents` ← the `semantic` stage only). Do not add a second writer; extend the owning collector instead.
- **Writes go through the orchestrator.** New ingestion/refresh writes register as a `Collector` in `index_ops.py` and run under `refresh_index()` — not as a fresh leaf that opens `db_connection()` and upserts on its own.
- **Known, accepted exceptions (direct `db_connection()` writers outside `refresh_index`).** A few interactive/operator commands write directly *by design* — they are human-in-the-loop mutations, not unattended ingest: `rebalance github-sync-artifacts` (`cli/github.py::github_sync_artifacts()`) and the `rebalance apple-reminders` write path (`cli/apple_reminders.py`). Most other direct `db_connection()` calls from `cli/*` (`onboard`, `config-doctor`, `raw`, `dashboard-render`) are **reads**, which are fine. If you add a new direct *writer*, document it here and say why it can't go through the registry.

### Tables by Domain

```
Project Registry (writer: registry.py::sync_db(), the single low-level upsert)
  project_registry          — canonical project metadata. Rows are either curated
                               (write_semantics="confirmation_gated", written only
                               via the onboarding confirm_projects()/confirm_and_write()
                               path — see lifecycle.py) or machine_owned (never
                               clobbers a curated row of the same name). Two
                               machine_owned producers currently call sync_db():
                               project_inference.py's activity/calendar inference
                               (generated_by "activity_inference_v1") and GH-124's
                               commit-threshold auto-promotion (generated_by
                               "commit_threshold_v1", wired into _refresh_github()
                               in index_ops.py, immediately after the watchlist
                               guard). _is_inference_owned() recognizes both markers.

GitHub activity (writer: github_scan.py)
  github_activity            — per-repo event counts, keyed by (login, repo, scan_date)

GitHub artifacts (writer: github_knowledge.py; schema in `ingest/db/`)
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

Unified Semantic Index (single writer: the `semantic` collector stage in index_ops.py)
  semantic_documents         — canonical cross-source document rows (vault chunks +
                               GitHub issues/PRs/comments/commits, Gmail
                               messages, and registry-provider sources such as
                               Figma comments). Written exclusively by
                               _refresh_semantic_only() via
                               semantic_index.py::backfill_semantic_documents().
                               Consumed by semantic_query() and the LLM context layer.
  semantic_embeddings        — sqlite-vec virtual table, float[1024], keyed by
                               semantic_documents.id. Unified ANN search target.
  semantic_embedding_meta    — model name, dimension, embedder_version, last_embed_at

Vault Ingestion (writer: note_ingester.py)
  vault_files                — one row per .md file, with content_hash for delta detection
  chunks                     — heading-based chunks, FK to vault_files (CASCADE delete)
  keywords                   — TF-IDF top-K per chunk, FK to chunks (CASCADE delete)
  links                      — wikilinks and embeds, FK to vault_files (CASCADE delete)

Embeddings (writer: embedder.py)
  embeddings                 — sqlite-vec virtual table, float[1024], keyed by chunk_id
  embedding_meta             — model name, dimension, last embed timestamp

Email (writer: gmail.py)
  email_messages             — message metadata + snippet, keyed by Gmail message_id.
                               Upsert-only rolling window (newest matching messages);
                               also projected into semantic_documents.

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

Figma (writer: figma.py)
  figma_comments             — comment rows keyed by Figma comment key, synced from
                               an explicit file-key allow-list. Also projected into
                               semantic_documents via the registry-provider path.

Device-local inventories / derived jobs
  ask_self_indexes           — per-device inventory of ask_self indexes found on disk
  focus5_repo_signals        — cached per-repo Focus 5 signals for the current device
  focus5_roster              — persisted top-5 Focus 5 roster snapshot
```

### Sync semantics per source

Every source is incremental, but the meaning of "incremental" depends on what the upstream API supports. The three patterns from [Sync model](#sync-model-in-plain-english) map cleanly onto the table below:

- **Vault notes** — *hash delta.* SHA-256 of raw file bytes stored in `vault_files.content_hash`. On re-ingest, unchanged-content files have their `last_modified` refreshed if the on-disk mtime moved forward (a "touch") but skip all parsing and embedding work — surfaced as `touched_files` in the ingest result. Changed-content files are deleted (CASCADE clears chunks/keywords/links) and re-inserted.
- **GitHub activity** — *window refetch.* Keyed by `(login, repo_full_name, scan_date)` with `ON CONFLICT REPLACE`. Each scan re-pulls the user's last ~30 days of events and overwrites *today's* row only; older days are left alone.
- **GitHub artifacts** — *hash/ID delta with window.* Keyed by `(repo_full_name, item_type, number)` for items; comments/commits/checks keyed by GitHub ID. `ON CONFLICT REPLACE` on every sync, with a `since_days` lookback to skip artifacts that haven't been touched in that window.
- **Embeddings** — *hash delta.* Chunks (vault) or documents (GitHub corpus) without a corresponding embeddings row get embedded. A model-version change recorded in `embedding_meta` / `github_embedding_meta` triggers a full re-embed of that corpus.
- **Calendar** — *window refetch.* Keyed by Google event ID with `INSERT OR REPLACE`. Re-sync overwrites existing events and adds new ones within the requested window (default 30d back / 7d forward; 365d on demand for backfill). No auto-deletion — events removed upstream stay in the local DB until manually pruned.
- **Sleuth reminders** — *full refetch + column-diff.* Keyed by `reminder_id`. Column-level diff against the stored row decides insert/update/unchanged; `first_seen_at` is set on insert and never overwritten; `last_seen_at` and `last_synced_at` refresh on every sync. Missing reminders are NOT deleted — terminal states (`completed`, `canceled`) remain as history.
- **Email (Gmail)** — *window refetch, count-bounded.* Keyed by Gmail `message_id` with upsert. Each run pulls the newest 100 messages matching the configured filter (default `in:inbox`, override via `gmail_query_filter` in `temp/rbos.config`). Phase 1 stores metadata + Gmail snippet only — no full body, no historical backfill, no auto-delete. See [PROJECT/1-INBOX/EMAIL-INGEST.md](PROJECT/1-INBOX/EMAIL-INGEST.md).

---

## Query Layer

All consumers read from the same SQLite file. The query layer is source-agnostic.

**Read-side ownership model (Phase 3, Option C):**

| Surface | Role | Owner |
|---|---|---|
| `semantic_query()` MCP tool | Unified raw retrieval primitive | `semantic_index.query()` — owns source vocabulary, freshness, hybrid RRF |
| `chat_with_data()` | Citations-first interactive retrieval | `chat.py` — owns scope aliases (`work`/`code`/`all`), citation shaping; delegates retrieval to `semantic_index` |
| `ask()` | Broad mixed-context synthesis/orchestration | `querier.py` — owns project/calendar/temporal framing; not the canonical retrieval primitive |
| `query_notes()`, `query_github_context()` | Legacy per-source lookups | Facades over older per-source indexes; use `semantic_query()` for new work |

```
SQLite @ $REBALANCE_DB
   │
   ├──▶ semantic_index.query()     ── unified raw retrieval primitive
   │    (MCP: semantic_query)          source vocab + hybrid RRF
   │         │
   │         ├──▶ chat_with_data() ── citations-first presentation layer
   │         │    (dashboard /api/chat)  scope aliases, citation shaping
   │         │
   │         └──▶ ask() (partial)  ── contributes to synthesis context
   │
   ├──▶ querier.py::ask()          ── broad orchestrator: gathers project,
   │    (MCP: ask, CLI: ask)           calendar, temporal + semantic signals;
   │                                   synthesizes via local Qwen3 (optional)
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
   └──▶ mcp/server.py              ── exposes all of the above as MCP tools
                                       to Claude Code, Claude Desktop, etc.
```

`querier.py` is the synthesis orchestrator (not the retrieval primitive). A single `ask()` call:

1. **Gathers context** from all sources in parallel-ready functions:
   - `_gather_project_context()` — registry entries + repos map
   - `_gather_github_context()` — per-project activity summary (from `github_activity`)
   - `_gather_github_semantic_context()` — semantic recall over the GitHub corpus (`github_documents` + `github_embeddings`)
   - `_gather_vault_context()` — semantic search (embed query → ANN)
   - `_gather_vault_activity()` — recently modified files
   - `_gather_calendar_context()` — upcoming + recent events from `calendar_events`
   - `_gather_temporal_context()` — day-of-week / weekend / holiday framing for the prompt
   - `_gather_hiqs_context()` — the persisted **HiQS** ranked verdict (see below). A cheap
     cached read (`load_ranked_next_actions()`); it never recomputes. This is how Sleuth,
     Gmail, and Figma reach `ask()`: they are already in the one ranked bundle, so `ask()`
     surfaces them via the shared ranking rather than a per-source gatherer.

2. **Assembles a prompt** with all context formatted into labeled sections — including a
   `## HiQS — ranked next actions` section carrying each action's receipts. The ranking is
   also returned first-class on `QueryResult.hiqs`.

3. **Synthesizes** via local Qwen3 LLM (mlx-lm). Returns both synthesis and raw context.

### The Next Actions engine ("what to do next")

A distinct read-side subsystem in [src/rebalance/ingest/next_actions.py](src/rebalance/ingest/next_actions.py) — structurally one of the larger clusters in the codebase. It is **HiQS**: the single, unified work-signal pipeline — **one bundle spanning all six sources (GitHub, vault, Calendar, Sleuth/Slack, Gmail, Figma), one ranked verdict, read by every surface**. `ask()` and the dashboard's what's-next view read the *same* persisted ranking, so they cannot drift. It also drives the fixed vault file `Dashboards/What To Do Next.md`.

Pipeline (real symbols):

1. **`assemble_day_bundle()`** gathers the operator's own day signal across all six sources into an `OperatorBundle`, plus teammate deltas (`_gather_teammate_delta()`). Candidates are built by **`_operator_candidates()`, which WALKS the collector registry** — each source owns its candidate shape via the `candidates=` provider on its `Collector` (the same registry seam as `semantic_docs=`). A new work signal reaches the ranked verdict by registering a collector, never by editing this dispatch (GUIDING-PRINCIPLES Principle 3).
2. **`build_rank_prompt()`** formats the candidates; **`rank_next_actions()`** synthesizes the ranking. **Primary path = Gemini** (`get_gemini_api_key()` → `gemini-2.5-flash`); a deterministic local fallback (Qwen) keeps it working offline. `_parse_ranked_synthesis()` rejects placeholder echoes.
3. Output is a **`RankedNextActions`** (list of `RankedAction`), **persisted** to a cache table via `persist_ranked_next_actions()` and read back by `load_ranked_next_actions()`.
4. **`render_next_actions_markdown()`** writes the ranked list to the fixed vault file (single-writer, generated).
5. **Consumers:** the `web.py` what's-next route (`whatsnext_page()`) is the single WRITER (its `?refresh` path ranks + persists); `ask()` is a READER that exposes the persisted ranking as the first-class `QueryResult.hiqs` field. Neither re-ranks inline, so the two surfaces are structurally incapable of drifting.

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

1. **Interactive CLI** — `rebalance <subcommand>` via the Typer package under `src/rebalance/cli/`. Ad-hoc and one-shot workflows (`calendar-create-event`, `github-release-readiness`, `sleuth-sync --json`, `profile-sync`, `raw`, etc.). `rebalance` invoked with no arguments launches the live dashboard (mode 4). `rebalance raw [--minutes N] [--watch S] [--json]` is a calibration probe: 1 GitHub API request per invocation, classifies recent events as captured / pending / unwatched against the local pipeline state, used to verify that commits/PRs/issues are making it into rebalanceOS.

2. **Unattended scheduled syncs** — a launchd fleet of ten jobs. [SCHEDULER.md](SCHEDULER.md) is the policy table (single source of truth for labels, cadences, scopes, prerequisites, and outputs; enforced by `tests/test_scheduler_policy.py`). The six data/render jobs, conceptually:

   - **Daily all-scope sync** ([scripts/daily_sync.sh](scripts/daily_sync.sh) / [scripts/com.rebalance-os.daily-sync.plist.template](scripts/com.rebalance-os.daily-sync.plist.template)) at 06:30 local time, plus on boot/login if 06:30 was missed. Calls `refresh_index()` with no scope (the **default recipe**): all raw sources (`vault`, `github`, `calendar`, `sleuth`, `email`) followed by the derived/projection/export stages (`code`, `semantic`, `sync`). Note: `scope=["all"]` is *not* the same as the default recipe — after Phase 1b, `all` expands to raw sources only; the default no-scope path runs the full recipe including follow-on stages. Opt-in scopes (`figma`, `focus5`, `ask_self`) are never included automatically. Per-scope failures are captured in `errors` rather than aborting the run.
   - **Hourly vault refresh** ([scripts/vault_sync.sh](scripts/vault_sync.sh) / [scripts/com.rebalance-os.vault-sync.plist.template](scripts/com.rebalance-os.vault-sync.plist.template)) at HH:15 from 06:15 to 23:15. Calls `refresh_index(scope=["vault", "semantic"])` — keeps notes edited mid-day visible in **both** the dashboard/pulse (vault ingest) and **semantic search** (semantic projection stage). Vault ingest with no changes is ~0.02s; the semantic stage only embeds rows where content changed, so it is also cheap on idle runs.
   - **Hourly pulse publish** ([scripts/pulse_sync.sh](scripts/pulse_sync.sh) / [scripts/com.rebalance-os.pulse-sync.plist.template](scripts/com.rebalance-os.pulse-sync.plist.template)) on the hour, 06:00 to 23:00. Renders the operator pulse markdown and pushes it to the configured private repo, but only when the rendered content actually changed since the previous run.
   - **30-minute pulse-web refresh** ([scripts/pulse_web_sync.sh](scripts/pulse_web_sync.sh) / [scripts/com.rebalance-os.pulse-web-sync.plist.template](scripts/com.rebalance-os.pulse-web-sync.plist.template)) every 30 minutes from 06:00 to 23:30. Calls [scripts/pulse_web.py](scripts/pulse_web.py) to regenerate the local `web/pulse.html` mirror of the dashboard. Atomic via tmp+replace (a crashed run leaves the previous HTML intact). No network, no git push — separate from the markdown→private-repo flow above.
   - **Hourly GitHub sync** ([scripts/github_sync.sh](scripts/github_sync.sh) / [scripts/com.rebalance-os.github-sync.plist.template](scripts/com.rebalance-os.github-sync.plist.template)) — a narrower github-only refresh independent of the daily full sync, for environments that want fresher GitHub data without paying the full multi-source cost.
   - **Pulse server (long-running, not scheduled)** ([scripts/pulse_server.sh](scripts/pulse_server.sh) / [scripts/com.rebalance-os.pulse-server.plist.template](scripts/com.rebalance-os.pulse-server.plist.template)) — a FastAPI/uvicorn server on `127.0.0.1:8767` with `RunAtLoad` + `KeepAlive` (autostart at login, restart on crash, `ThrottleInterval=30s`). Adds an interactive layer (real Refresh button + filter) on top of the static `web/pulse.html` the pulse-web job regenerates, **and is the always-on JSON backend for the macOS Focus 5 Float app** ([macOS/Apps/Focus5Float](macOS/Apps/Focus5Float)) — it serves `/focus-5.json` (roster), `/focus-5/goals`, and `/focus-5/note` so the app works without a separate `rebalance serve` on `:8787`. Loopback bind is enforced in [scripts/pulse_server.py](scripts/pulse_server.py). Unlike the five scheduled jobs above, it runs continuously rather than firing on a calendar interval.

     **Drift gotcha (has bitten the Focus 5 app twice):** [scripts/pulse_server.py](scripts/pulse_server.py) does *not* mount `rebalance.web`'s app — it hand-re-declares a chosen *subset* of its routes by importing the renderers. Two consequences: (1) a route added to `web.py` is invisible on `:8767` until a matching wrapper is added to `pulse_server.py` (this is how `/focus-5.json` was missed); (2) because it's a `KeepAlive` daemon, any route change requires `launchctl kickstart -k gui/$UID/com.rebalance-os.pulse-server` to take effect — a long-running process keeps serving its old route table otherwise (this is how a freshly-added `/focus-5/goals` still 404'd).

   The remaining five jobs (health-check hourly, health-check-triage 3×/day, pulse-warning-watch every 15 min, obsidian-rollover at midnight, obsidian-daily-sync at 18:00) are operational/maintenance agents — see [SCHEDULER.md](SCHEDULER.md). The **obsidian-daily-sync** job ([utils/obsidian_daily_sync.sh](utils/obsidian_daily_sync.sh) / [scripts/com.rebalance-os.obsidian-daily-sync.plist.template](scripts/com.rebalance-os.obsidian-daily-sync.plist.template)) synthesizes a Gemini daily-activity summary from the structured `collect_pulse_snapshot()` output and lands it in an idempotent sentinel-bracketed block at the bottom of the vault's `0. Today's Notes.md`. Similarly, the **git-pulse-daily-synthesis** script ([utils/git_pulse_daily_synthesis.py](utils/git_pulse_daily_synthesis.py)) acts as a manual projection/export stage, aggregating multi-device git commit logs and synthesizing them into a separate block in the vault. Both scripts use Gemini-or-skip logic (no Qwen fallback) and feature late-run guards to prevent colliding with the 00:00 rollover.

   Wrapper scripts source [scripts/lib/scheduler_common.sh](scripts/lib/scheduler_common.sh) for env bootstrap (repo root, venv python, `PYTHONPATH`), per-day logs under `temp/logs/`, job-lifecycle events into `auth_activity.jsonl`, and log retention. Installers source [scripts/lib/install_common.sh](scripts/lib/install_common.sh) for one normalized flow: always-unload, render the `.plist.template` (`{{REBALANCE_DIR}}`, `{{PYTHON}}`, `{{HOME}}`), `plutil -lint`, load, poll-verify registration. The rendered plists in `~/Library/LaunchAgents/` are gitignored — the templates are the only checked-in form, so a clone on any machine installs cleanly with no per-user editing.

3. **MCP tool handlers** — [src/rebalance/mcp/server.py](src/rebalance/mcp/server.py) registers the tools; [src/rebalance/mcp_server.py](src/rebalance/mcp_server.py) remains as the backward-compatibility shim for older launch commands. Host agents (Claude Code / Claude Desktop) call these on demand. `REBALANCE_DB` env var resolves the shared DB path.

4. **Live dashboard** — [scripts/dashboard.py](scripts/dashboard.py) is a Rich Live monitor that polls the local SQLite every 2 seconds (cheap; no network) and runs `refresh_index(scope=["github"])` in a background thread every 10 minutes so the underlying data actually changes. Launch via `rebalance` (no args) or `rebalance dashboard`. Press `r` to trigger an immediate GitHub refresh, `q` (or Ctrl+C) to quit. Theming and cadence are env-var controlled (`PULSE_INVERSE`, `PULSE_TICK`, `PULSE_AUTO_MIN`, `REBALANCE_TZ`). The dashboard is intentionally read-only against the same DB the MCP server and the launchd jobs write to.

---

## MCP Tool Surface

Tools are registered in [src/rebalance/mcp/server.py](src/rebalance/mcp/server.py)::`create_server()`. [src/rebalance/mcp_server.py](src/rebalance/mcp_server.py) is a backward-compatibility shim so older launch commands still work. All tools share the same `database_path` resolved at server startup from `REBALANCE_DB`.

| Category | Tool | Purpose |
|----------|------|---------|
| Query | `ask` | Natural language query across all sources (with optional local LLM synthesis) |
| Query | `query_notes` | Vault semantic search (embedding-based) |
| Query | `search_vault` | Vault keyword search (TF-IDF) |
| Query | `query_github_context` | Semantic search over the GitHub artifact corpus (issues, PRs, comments, reviews, commits) |
| Query | `github_balance` | Per-project GitHub activity summary |
| Query | `github_release_readiness` | Infer milestone/release readiness from the local GitHub corpus |
| Query | `github_close_candidates` | Suggest open issues that likely map to merged PRs |
| Query | `semantic_query` | Unified vector search across vault + GitHub corpus (single ranked result set) |
| Diagnostics | `index_status` | Snapshot of every source + semantic index freshness (read-only) |
| Diagnostics | `refresh_index` | Orchestrated refresh of the local knowledge base (single entry point) |
| Diagnostics | `list_watched_repos` | Show merged set of repos being monitored (project registry ∪ activity − ignored) |
| Diagnostics | `diagnose_repo` | Walk the watched-repos + sync funnel for a single repo (optionally a `sha` or `pr`) and explain coverage + freshness gaps; opt-in `live=True` distinguishes "we never synced" from "PAT can't see it" |
| Registry | `list_projects` | Query project registry |
| Onboarding | `onboarding_status` | Check setup completion |
| Onboarding | `setup_github_token` | Validate and store GitHub PAT |
| Onboarding | `run_preflight` | Discover project candidates (read-only) |
| Onboarding | `confirm_projects` | Write registry and sync |
| Onboarding | `ingest_gmail_messages` | Agent-pushed Gmail ingest path for installs using `gmail_ingest_method=mcp` |
| Calendar | `create_calendar_event` | Create a Google Calendar event via local OAuth |
| Calendar | `review_timesheet` | Surface unclassified calendar events that need a project decision |
| Calendar | `classify_event` | Persist an include/exclude/project classification for an event |
| Calendar | `snap_calendar_edges` | Detect and (optionally) fix slightly overlapping events |
| Sync | `sleuth_sync_reminders` | Pull Slack reminders from the Sleuth Web API and upsert to SQLite |
| Sync | `publish_pulse` | Render today+yesterday activity to markdown and push to private pulse repo |
| Hygiene | `audit_modules` | Run [scripts/audit_modules.py](scripts/audit_modules.py) and return the structured JSON result. Verifies that ingest collectors / render modules / scheduled-job infrastructure are documented in ARCHITECTURE.md and CHANGELOG.md, and that recent commits' file changes appear in the latest CHANGELOG version section. Supports `init=True` to snapshot the baseline lockfile and `include_uncommitted=True` for a pre-commit working-tree preview |

Tool specs (params, returns, dependencies): see [MCP.md](./MCP.md).

---

## Module Map

```
src/rebalance/
  __init__.py              — package version
  __main__.py              — CLI entry point
  cli/                     — Typer command package split by domain
  mcp/                     — FastMCP server + tool modules
  mcp_server.py            — backward-compatibility shim to rebalance.mcp.server
  paths.py                 — centralized path resolver. `resolve_database_path()` and
                              `resolve_secret_path()` walk a layered chain (explicit
                              flag → env var → canonical app-data path → user
                              config → cwd walk-up for project marker). Single
                              source of truth for "where is the DB / secrets dir?"
                              `resolve_project_root(Path(__file__))` (walk-up) is the
                              stable repo-root resolver used throughout the codebase —
                              replaces all `parents[N]` hacks. `resolve_oauth_token_path(service)`
                              returns the canonical launchd-reachable token path for
                              Google OAuth services. Configure user defaults via
                              `rebalance config set-default-database` and `set-secrets-dir`.
  web.py                   — FastAPI local dashboard/web surfaces (`/`, `/focus-5`, `/auth-log`, etc.)
  doctor.py                — installation health checks; backs `rebalance doctor`
  ingest/
    config.py              — secrets storage (temp/rbos.config)
    registry.py            — project registry sync (Markdown ↔ YAML ↔ SQLite);
                              read_registry (pure read) vs load_registry (write-path)
    preflight.py           — onboarding discovery (read-only, provenance-stamped)
                              + confirmation — the only curated registry write path
    lifecycle.py           — Phase 5/6 lifecycle contract: setup stage map with
                              done/now/next/blocked/skipped statuses, executor
                              hints, and remediation (backs onboarding_status and
                              the /welcome skill), plus the project-lifecycle
                              ownership table (write semantics per stage —
                              discovery read_only, confirmation gated, inference
                              machine-owned, prioritization read-time overlay)
    local_repos.py         — local checkout discovery (Phase 6.1): scan
                              local_repo_roots for git checkouts, GitHub identity
                              from origin, unpushed-commit counts; feeds
                              provenance=local-scan candidates + the doctor's
                              unpushed-work check
    github_scan.py         — GitHub Events API collector + per-project balance query
    github_knowledge.py    — per-repo artifact sync (issues/PRs/comments/commits/checks) + embedding
    github_watch.py        — watched/external repo reconciliation and repo-watch logic
    github_readiness.py    — release-readiness inference over the local GitHub corpus (read-only)
    github_reconciliation.py — issue ↔ PR close-candidate inference (read-only)
    db/                    — shared DB connection, schema, migrations, sqlite-vec loading
    md_parser.py           — pure markdown parsing (frontmatter, wikilinks, tags, chunking)
    note_ingester.py       — vault walker, delta detection, TF-IDF keywords
    embedder.py            — mlx-embeddings batch embed + ANN query
    semantic_index.py      — unified semantic index: backfill, embed, and query across
                              vault + GitHub + email, plus registry-provider sources
                              such as Figma (semantic_documents / semantic_embeddings)
    index_ops.py           — single entry point for refresh_index() and index_status();
                              orchestrates the full ingest pipeline so agents don't
                              need to know individual CLI command ordering
    calendar.py            — Google Calendar API collector + SQLite persistence
    calendar_config.py     — OAuth token storage, classification rules, review-decision persistence
    calendar_helpers.py    — duration/math utilities consumed by calendar tools
    calendar_snap.py       — edge-snapping logic for slightly overlapping calendar events
    sleuth_reminders.py    — Sleuth Web API collector (Bearer auth, urllib) + upsert
    gmail.py               — Gmail collector / MCP push-ingest write path into email_messages
    figma.py               — Figma comments collector + registry-provider semantic_docs
    ask_self_scan.py       — device-local ask_self index inventory collector
    focus5_scan.py         — Focus 5 repo-signal scan + roster builder
    slack_users.py         — Slack user-id → friendly-name lookup, file-mtime cached;
                              feeds the dashboard sleuth panel and the pulse markdown
    diagnose.py            — repo-level diagnostic that walks the watched-repos +
                              sync funnel for one repo (optionally sha/PR) — backs
                              the diagnose_repo MCP tool
    profile_sync.py        — daily-sync log parser that surfaces per-repo GitHub
                              timings; backs the rebalance profile-sync subcommand
    pulse.py               — pulse markdown renderer; backs publish_pulse MCP tool
    agent_tags.py          — source-tagging for pulse rows (claude-cloud, codex-cloud,
                              lovable, local-vscode, human)
    project_classifier.py  — calendar event → project matcher for timesheet reports
    project_inference.py   — project inference from note titles / calendar summaries
    note_builder.py        — dashboard markdown renderer / write-back for the vault note
    audit.py               — structured audit logging (append_audit_entry)
    querier.py             — multi-source context gathering + local LLM synthesis

scripts/                   — Operator entry points (not part of the importable package)
  dashboard.py             — Rich Live terminal dashboard (mode 4 above)
  pulse_web.py             — render module: regenerates web/pulse.html (the local
                              browser mirror of the dashboard) from the same SQLite
                              knowledge base; atomic via tmp+replace; supports --watch
  _bootstrap.py            — single sys.path shim for directly-run scripts (src/ + scripts/)
  spike_welcome_status.py  — disposable Phase 6 spike: drives the lifecycle status
                              contract (sandbox walkthrough + --real "where am I")
  lib/scheduler_common.sh  — shared launchd job runtime: env bootstrap, dated logs,
                              job-lifecycle events, retention (sourced by *_sync.sh)
  lib/install_common.sh    — shared installer flow: always-unload, render template,
                              plutil -lint, load, poll-verify (sourced by install_*.sh)
  daily_sync.sh            — daily_sync launchd entry (mode 2)
  vault_sync.sh            — hourly vault-only launchd entry (mode 2)
  pulse_sync.sh            — hourly pulse-publish (markdown→private repo) launchd entry (mode 2)
  pulse_web_sync.sh        — 30-minute pulse-web (web/pulse.html) launchd entry (mode 2)
  github_sync.sh           — github-only launchd entry (mode 2)
  install_*.sh             — one installer per launchd job (see SCHEDULER.md for the
                              job ↔ installer table; all delegate to lib/install_common.sh)
  setup_calendar_oauth.py  — interactive OAuth consent flow for Google Calendar
  build_extension.py       — native extension builder
  ask-self-ingest.sh       — self-ingest shell wrapper (portable mode, requires ASK_SELF_PATH)
  ask-self-query.sh        — self-query shell wrapper (portable mode, requires ASK_SELF_PATH)
  audit_modules.py         — repository hygiene audit (Approach A): verifies ingest
                              collectors / render modules / scheduled-job infrastructure
                              are documented in ARCHITECTURE.md + CHANGELOG.md; supports a
                              baseline lockfile (audit_modules.lock), recent-commit coverage
                              against the live CHANGELOG version section, and a pre-commit
                              working-tree preview (--include-uncommitted). JSON output for
                              orchestrating agents; also exposed as the audit_modules MCP tool
```

---

## License

Copyright 2025 Hypercart DBA Neochrome, Inc.

Licensed under the **Apache License, Version 2.0**. See [APACHE-LICENSE-2.0.txt](./APACHE-LICENSE-2.0.txt).
