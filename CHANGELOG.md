# Changelog

## [0.5.6] - 2026-04-07

### Fixed

- `rebalance calendar-sync` now reads `calendar_id` from `temp/calendar_config.json` instead of defaulting to `"primary"`. Previously, syncing always pulled from the user's personal calendar unless `--calendar-id` was passed explicitly, even when the config file pointed to a shared team calendar. The `--calendar-id` CLI flag still overrides when provided.

### Changed

- Updated `GOOGLE_CALENDAR.md` with Prerequisites, Team Quick Setup, and Claude Code Setup sections for smoother developer onboarding.

## [0.5.5] - 2026-04-07

### Added

- Calendar report project matching now supports a non-Obsidian fallback: if no synced `project_registry` exists in SQLite, reports load canonical project names and aliases from `temp/calendar_config.json`.

### Changed

- `calendar_config.json` now supports a `projects` list for lightweight local project definitions when a developer only needs calendar timesheet grouping without the full Obsidian registry workflow.

## [0.5.4] - 2026-04-07

### Changed

- Calendar report project aggregation now treats the synced `project_registry` projection as the canonical source of truth for project names and aliases, falling back to keyword grouping only for unmatched events.

### Fixed

- Daily and weekly calendar reports now preserve canonical project casing from the registry instead of reformatting matched names through heuristic title-casing.

## [0.5.3] - 2026-04-07

### Fixed

- Weekly and daily project aggregators now skip low-signal verb labels such as "can", "change", and similar filler terms, so grouped work is more maintainable and easier to scan.
- Project aggregation now reuses the same calendar exclude keyword config as event filtering, so one keyword source drives report cleanup across the calendar reporting flow.

## [0.5.2] - 2026-04-07 — Calendar config setup simplification

- Added `calendar_config.example.json` to repo root — template with instructions for new users.
- Added `CALENDAR_CONFIG_SETUP.md` — quick setup guide (4 steps: create temp folder, copy example, edit config, verify).
- Removed `temp/calendar_config.json.template` — now using example file from repo root instead.
- Updated README.md Step 4c — clearer instructions with code example for config setup.
- Verified `.gitignore` already includes `/temp` folder — user config stays private.

## [0.5.1] - 2026-04-07 — Calendar setup portability & documentation

- Added `CALENDAR_PORTABILITY_AUDIT.md` — comprehensive audit of setup and configuration portability; confirms zero hardcoded user data.
- Added `CALENDAR_NEW_USER_SETUP.md` — step-by-step guide for new users (OAuth setup, config, testing, scheduling).
- Added `temp/calendar_config.json.template` — template for user configuration (copy and edit).
- Enhanced `scripts/setup_calendar_oauth.py` — now lists all available calendars with IDs, and provides next-step instructions.
- Updated `README.md` Step 4 — detailed Google OAuth app creation and calendar setup for new users.
- Confirmed portability: ✅ All user data outside repo, ✅ No hardcoded credentials, ✅ OAuth per-user, ✅ Config per-user, ✅ Tokens system-native.

## [0.5.0] - 2026-04-07 — Calendar daily & weekly reports with project aggregator

- Added `calendar_config.py` — single gitignored config file per device for calendar selection, exclude keywords, and timezone.
- Added `daily_report.py` — generates markdown daily reports with event filtering, project aggregator grouping, and time totals.
- Added `weekly_report.py` — combines daily reports into Sun-Sat format with daily summaries and weekly overview.
- Added `rebalance calendar-daily-report` and `rebalance calendar-weekly-report` CLI commands.
- Project aggregator groups similar events by keyword, counts, and sums durations (e.g., "Binoid": 4 events, 7h 15m).
- Exclude keywords (e.g., "Lunch", "Check Slack") filter events from reports but keep them in database.
- Timezone-aware report times (configurable in temp/calendar_config.json, defaults to America/Los_Angeles).
- All reports generated in clean markdown format suitable for Obsidian, email, or archival.
- Updated `db.py` to gracefully handle systems without sqlite-vec extension support (system Python).
- Added CALENDAR_REPORTS.md documentation with usage, config, and examples.

## [0.4.2] - 2026-04-07 — Google Calendar multi-calendar + daily totals

- Extended `calendar.py` to support reading from any calendar (not just primary): `sync_calendar(calendar_id=...)` parameter.
- Added `DailyEventTotal` dataclass — aggregates event count and duration by day with helper methods (total_hours, __str__).
- Added `get_daily_totals(database_path, days_back, days_forward)` — calculates combined daily event metrics from calendar_events table.
- Added `rebalance calendar-daily-totals` CLI command — displays daily event summary (count, duration) with aggregate stats (total events, avg events/day, avg hours/day).
- Updated `calendar-sync` command to accept `--calendar-id` parameter (email or group ID).
- Updated PROJECT.md: documented calendar parameter, daily totals command, and updated access setup to use new `setup_calendar_oauth.py` script.
- Added `scripts/setup_calendar_oauth.py` — automated OAuth2 setup script that generates and stores token in `~/.config/gcalcli/oauth`.

## [0.4.1] - 2026-03-30 — Claude Desktop manual config + MCP.md tool surface update

- Added step-by-step Claude Desktop manual setup instructions to MCP.md (config path, absolute paths, troubleshooting table).
- Updated README.md: Claude Desktop section now leads with manual config (recommended) and moves `.mcpb` extension to "coming soon".
- Updated MCP.md tool surface: `ask`, `query_notes`, `search_vault`, and all onboarding tools (`onboarding_status`, `setup_github_token`, `run_preflight`, `confirm_projects`) moved from Planned to Live.
- Reduced Planned tool surface to `todays_agenda`, `morning_brief`, and `query_github_context`.

## [0.4.0] - 2026-03-29 — Google Calendar integration

- Added `calendar.py` — Google Calendar API collector that fetches events and persists to `calendar_events` SQLite table with 1-year retention.
- OAuth2 flow via `google-auth-oauthlib` with token stored at `~/.config/gcalcli/oauth`. Auto-refresh on expiry.
- Added `rebalance calendar-sync` CLI command with configurable `--days-back` (default 30, use 365 for initial backfill) and `--days-forward`.
- Wired calendar context into `ask` tool: upcoming events (next 2 days) + recent events (last 7 days) included in both prompt and raw context.
- Updated PROJECT.md: P2 Google Calendar now marked Active with full access setup docs, vectorization status noted on all signal sources.
- Updated ARCHITECTURE.md: signal sources table now includes Vectorized column, calendar added to storage layer and module map.

## [0.3.0] - 2026-03-29 — `ask` tool + multi-source query engine

- Added `querier.py` — general-purpose natural language query engine that gathers context from all data sources (project registry, GitHub activity, vault embeddings, vault file modification dates) and optionally synthesizes a first-pass answer via local Qwen3-0.6B LLM (mlx-lm).
- Added `ask` MCP tool — host agents call this with any natural language question and get back both a local LLM synthesis and raw structured context for review/refinement.
- Added `rebalance ask` CLI command with `--no-llm` flag for raw context only.
- Two-layer LLM architecture: local Qwen3 does fast on-device synthesis, host agent (Claude, Copilot, etc.) reviews and refines.
- Added `ARCHITECTURE.md` — documents data flow, signal pipeline pattern, two-layer LLM design, and how to add new data sources.

## [0.2.0] - 2026-03-29 — Vault ingestion + embeddings pipeline

- Added `db.py` — shared database layer with sqlite-vec extension loading, WAL mode, and schema creation for all vault/embedding tables.
- Added `md_parser.py` — pure markdown parsing: YAML frontmatter extraction, wikilink/embed detection, #tag extraction, heading-based chunking.
- Added `note_ingester.py` — vault walker with SHA-256 hash-based delta detection, TF-IDF keyword extraction (pure Python, no sklearn), and wikilink/embed tracking.
- Added `embedder.py` — batch embedding via mlx-embeddings (Qwen3-Embedding-0.6B, 1024-dim), sqlite-vec storage, model version tracking for automatic re-embed on model change, ANN similarity search.
- Added CLI commands: `rebalance ingest notes`, `rebalance ingest embed`, `rebalance query`, `rebalance search`.
- Added MCP tools: `query_notes` (semantic search), `search_vault` (keyword search).
- Fixed frontmatter serialization: `date` objects from YAML now serialize to ISO strings via custom JSON encoder.
- Fixed sqlite-vec KNN query: uses `e.k = ?` constraint required by vec0 virtual tables.
- Added `.venv/*` to default ingest exclude patterns to prevent indexing Python package metadata.
- Added `sqlite-vec` to core dependencies, `mlx-embeddings` as optional `[embeddings]` extra in pyproject.toml.

## [0.1.1] - 2026-03-28 — Onboarding MCP tools + schema fixes

- Added 4 onboarding MCP tools: `onboarding_status`, `setup_github_token`, `run_preflight`, `confirm_projects` — enables agent-driven onboarding through any MCP host.
- Refactored `preflight.py`: split monolithic `run_preflight()` into `discover_candidates()` (read-only) + `confirm_and_write()` (write + sync). CLI re-wired to call both.
- Added `validate_github_token()` in `github_scan.py` — validates PAT against GitHub `/user` endpoint and captures OAuth scopes.
- Fixed schema mismatch between MCP server and registry: server now queries `repos_json` column (not `repos`) and decodes as JSON (not YAML).
- Fixed registry `sync_db()` to write JSON (not YAML) into `_json` columns.
- Shipped `.vscode/mcp.json` for automatic MCP server registration on workspace open.
- Added `CLAUDE.md` with agent onboarding instructions so any MCP host can drive first-run setup.
- Updated PROJECT.md and MCP.md: aligned onboarding sequence to MCP-driven flow, standardized segment naming to match code (`*_projects` suffix), fixed `REBALANCE_DB` documentation, added refactor notes.

## 2026-03-28 (onboarding sequence)

- Expanded [PROJECT.md](PROJECT.md) with a reusable `Onboarding User Story Sequence` for first-run VS Code + AI agent setup.
- Defined first-run detection rules for missing/blank config, missing registry, and invalid stored GitHub PAT.
- Documented target onboarding bootstrap flow:
  - review README
  - start MCP server/services
  - detect new user
  - request GitHub PAT
  - validate PAT via live GitHub auth
  - pre-populate registry from GitHub activity into 7-day / 8-14 day / 15-30 day buckets
  - merge with vault-discovered candidates
  - write canonical registry and sync projections
- Added recommended follow-on onboarding steps: vault path confirmation, minimal metadata capture, optional calendar setup, resumable onboarding state, and startup smoke test.

## 2026-03-28 (activity segmentation)

- Implemented activity-based candidate segmentation in preflight generation:
  - Updated `run_preflight()` in `src/rebalance/ingest/preflight.py` to route curated projects into:
    - `most_likely_active_projects` (activity in last 14 days)
    - `semi_active_projects` (activity 15-30 days ago)
    - `dormant_projects` (activity 31+ days ago)
    - `potential_projects` (no activity signal available)
  - GitHub-derived candidates now persist `last_activity_at` from scanner output to support bucketing.
  - Added `_calculate_days_since_activity()` helper for ISO date parsing and resilient fallback behavior.
- Updated default registry section descriptions in `src/rebalance/ingest/registry.py` to document the new segmented buckets.

## 2026-03-29 (continued, part 2)

- **Tested GitHub & vault preflight discovery**:
  - GitHub PAT authentication working (verified with Kissplugins account).
  - GitHub activity scanner runs correctly; no recent activity in last 14 days (most recent events: Aug 2025).
  - Vault title scanner discovered **36 projects** from vault:
    1. Everyday, Temp, Finances, Ltvera, Love 2 Hug, 4. Acronyms, Wp Canary, Taxes For 2025, Welcome, Week Of Md Template, 0. Agents Ai Dtkk And Mcp Server, Marketing, 4x4clarity.com, Ai Dtkk, Wp Boxes, Sleuth, Bailiwik, 0. All Projects, Binoid, 3. Dumb Things, Hello World, Ucla Sacto, Wp Db Toolkit, 2. New Project Template Garl, Agents Scratchpad, Gitdashboard, Wp Page Builder V2, Macnerd, Project Templates.md, Project Dashboard, Mcp, Changelog, Project, Readme, Project Registry.template, License.
  - Registry file now properly formatted (newlines fixed in `_default_registry_markdown()` and `save_registry()` functions).
  - All 36 candidates stored in `potential_projects` section ready for curation.

## 2026-03-29 (continued)

- Preflight now includes **GitHub activity discovery** as a project intake signal:
  - `discover_repos_from_activity()` scans recent GitHub activity and returns repos sorted by activity score.
  - `rebalance ingest preflight --include-github` surfaces touched repos as potential project candidates (with commit counts and activity scores pre-populated).
  - Discovered via `github_token` parameter (from stored config) — gracefully degrades if GitHub scan fails.
- Config management system (`src/rebalance/ingest/config.py`):
  - Stored in `temp/rbos.config` (plaintext JSON, gitignored) for MVP simplicity.
  - `rebalance config set-github-token <PAT>` — stores PAT in config.
  - `rebalance config get-github-token` — check if token is configured (masked output for security).
  - `rebalance config show-config-path` — show config file location.
  - Future: upgrade to `keyring` library when multi-user or compliance required.
- Updated `rebalance ingest preflight` signature: now accepts `--include-github` and `--github-days` options.

## 2026-03-29

- Ported GitHub activity reader from `gitdaily` (TypeScript → Python):
  - `src/rebalance/ingest/github_scan.py` — PAT auth, events pagination (3-page cap), per-repo aggregation (commits/pushes/PRs/issues/reviews), SQLite persistence in `github_activity` table.
  - `rebalance github-scan` CLI command (accepts `--token`, `--days`, `--database`; `GITHUB_TOKEN` + `REBALANCE_DB` env vars).
  - `github_balance(since_days)` MCP tool in `mcp_server.py` — joins `project_registry.repos` with `github_activity` to surface idle vs active projects.
- Fixed regex bug in `src/rebalance/ingest/registry.py`: `YAML_BLOCK_PATTERN` had `\\s*` (string-escaped) in a raw string; corrected to `\s*`.
- `mcp_server.py`: added `json` import, `repos` column to project query (decoded from JSON string), `_project_repos_map()` helper.

## 2026-03-28

- Updated `PROJECT.md` to make in-vault Markdown registry canonical (`Projects/00-project-registry.md`) with sync modes: `pull`, `push`, `check`.
- Added preflight workflow spec: discover project candidates from vault page titles, curate keep/remove, collect 2-3 sentence summary, and capture quantitative/qualitative custom fields.
- Scaffolded Python package with CLI and ingest modules:
  - `rebalance ingest preflight`
  - `rebalance ingest sync --mode pull|push|check`
- Added registry and projection plumbing:
  - Markdown registry loader/saver
  - `projects.yaml` projection writer
  - SQLite `project_registry` upsert path
- Added initial MCP server scaffold with `list_projects(status="active")` tool.
- Added template file: `templates/project-registry.template.md`.
- Updated `README.md` with initial scaffold status and developer bootstrap commands.
