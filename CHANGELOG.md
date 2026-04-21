# Changelog

## [0.15.0] - 2026-04-20

### Added

- A new 14-day style window filter for the git pulse viewer so recent activity can be read as a bounded local-time slice instead of only single-day views.
- An integration test that exercises the git pulse viewer with a deterministic clock stub and verifies the flat row output contract.

### Changed

- The git pulse viewer now emits one canonical tab-separated schema with explicit local day and local time columns, replacing the previous comment-heavy preamble format.

## [0.14.0] - 2026-04-20

### Added

- Experimental Phase 0 plan for a deterministic GitHub Action that scans open issues against merged PRs and produces close-candidate recommendations every 2-3 days.
- Experimental standalone Action helper script in `/experimental` that reads open issues and merged PRs directly from the GitHub REST API, scores deterministic issue <-> PR matches, and emits JSON plus Markdown reports.
- Focused tests for the experimental Action helper covering explicit auto-close and strong inferred close recommendations.

### Changed

- Product memory now explicitly captures the intended split between deterministic GitHub hygiene in Actions and weekly higher-context local agent review.

## [0.13.0] - 2026-04-18

### Added

- New GitHub issue <-> PR reconciliation pass that suggests open issues likely fixed by merged PRs, grouped into high-confidence and medium-confidence recommendations with evidence.
- New `github-close-candidates` CLI command for reviewing explicit auto-close candidates and inferred close recommendations from the local GitHub corpus.
- New `github_close_candidates` MCP tool so hosts can ask for likely closeable issues before release or deployment planning.
- Unit tests covering explicit auto-close detection, strong inferred issue/PR matches, and medium-confidence review candidates.

### Changed

- GitHub planning can now distinguish between issues with explicit closing links and issues that only have strong inferred evidence from branch names, cross-mentions, commit messages, and title overlap.

## [0.12.0] - 2026-04-17

### Added

- Weekly report write-back path for the Obsidian vault: `calendar-weekly-report --vault ... --write-week-note` now creates `Weekly Notes/week-of-YYYY-MM-DD.md`.
- Weekly notes now include a deterministic `End of Week Summary` block with week window, total retained hours, working-day count, busiest day, review-needed count, and top project buckets so that next-week retrieval has a compact searchable recap.
- CLI tests covering weekly note write-back, required vault validation, and the automatic re-ingest/re-embed path.
- Weekly notes are now formatted as vault-native review artifacts with frontmatter and a stable `week-of-YYYY-MM-DD.md` naming contract for downstream retrieval.

### Changed

- Weekly report generation now supports turning the report into a vault-native note with frontmatter for downstream ingestion and retrieval.
- Writing a weekly vault note can immediately re-ingest and embed the updated vault so the generated summary becomes part of the local knowledge base without a separate operator step.
- The weekly review flow now closes the loop between calendar reporting and second-brain retrieval instead of leaving weekly output as a disconnected export.

## [0.11.0] - 2026-04-17

### Added

- New explicit GitHub readiness inference over the local corpus, including milestone selection, blockers, evidence, release-branch detection, deployment-issue parsing, and confidence scoring.
- New `github-release-readiness` CLI command for current-state inspection from locally synced GitHub signals.
- New `github_release_readiness` MCP tool so hosts can ask for review, merge, release-candidate, and deploy-ready state without live GitHub scanning.
- Unit tests covering repo metadata and branch sync plus a focused readiness-inference scenario with review blockers and a missing release branch.

### Changed

- GitHub artifact sync now stores repo metadata and branches so readiness inference can reason about default branches, release branches, and promotion paths locally.
- The public tool surface now treats GitHub readiness inference as live functionality instead of planned-only work.

## [0.10.0] - 2026-04-17

### Added

- Local-first GitHub knowledge sync for detailed artifacts: issues, pull requests, labels, milestones, releases, comments, reviews, review comments, commits, and check runs are now stored in SQLite instead of being read live at answer time.
- A new local GitHub document corpus built from issue bodies, PR bodies, comments, reviews, review comments, and commit messages, ready for semantic retrieval with local embeddings.
- New CLI commands for the GitHub corpus workflow: `github-sync-artifacts`, `github-embed`, and `github-query`.
- New `query_github_context` MCP tool for semantic retrieval over the local GitHub corpus.
- Linked-issue extraction from pull request text using closing keywords such as `fixes #123`, so the local store can preserve issue-to-PR relationships for readiness inference.
- Two focused GitHub unit tests covering artifact sync, document creation, embedding, and semantic query against mocked GitHub responses.

### Changed

- The main `ask` flow now includes relevant semantic GitHub artifacts alongside structured GitHub activity when local GitHub context is available.
- Version metadata is now aligned again across the package, manifest, and changelog.

## [0.9.0] - 2026-04-15

### Added

- New `rebalance calendar-snap-edges` CLI command — detects slightly overlapping calendar events and trims Event 1's end to 1 minute before Event 2's start, producing clean adjacent boundaries. Dry-run by default; pass `--apply` to patch Google Calendar.
- Batch mode via `--days` flag (1-7 consecutive days per run) with per-day overlap reporting.
- New `snap_calendar_edges` MCP tool with the same capabilities for agent-driven workflows.
- First `events().patch()` integration — the project can now update existing Google Calendar events (previously only read and create).
- 18 unit tests covering overlap detection (2-event pairs, 3+ cluster skips, contained events, adjacent non-overlaps, UTC Z-suffix), patch call verification, dry-run vs apply behaviour, timezone preservation, and batch validation.

### Changed

- All-day events and clusters of 3+ overlapping events are intentionally skipped — not enough context for automated resolution. Skipped clusters are reported so operators can resolve them manually.

## [0.8.0] - 2026-04-14

### Added

- New `rebalance calendar-create-event` CLI command for creating Google Calendar events from plain terminal sessions without needing the rebalance MCP server to be registered in the calling client.
- Dry-run support for calendar event creation. Operators can preview the normalized payload, including all-day date expansion into timezone-aware midnight boundaries, with no network calls or calendar writes.
- CLI tests covering the dry-run payload shape and the required write-scope guard.
- Duplicate guard for calendar event creation: before writing, the CLI now searches the target calendar for an existing event with the same title and start date.
- Idempotency controls for calendar creation: `--skip-if-exists`, optional `--dedupe-key`, and local structured JSONL logging for created, skipped, and blocked attempts.
- Machine-readable CLI output via `--output json`, including distinct statuses for `created`, `skipped_existing`, `blocked_duplicate`, and `idempotency_hit`.

### Changed

- Google Calendar docs now include a "Creating Events Programmatically" section with write-scope validation, dry-run workflow, and a copy-paste Binoid reminder example.
- MCP docs now recommend the CLI path for non-MCP clients and clarify why the project bypasses raw JSON-RPC for local operator workflows.
- Calendar event docs now call out duplicate-guard blind spots (title edits, overlapping multi-day events), recommend when to use `--dedupe-key`, and document local log rotation expectations.

## [0.7.0] - 2026-04-14

### Added

- Write-capable Google Calendar MCP tool: `create_calendar_event`. Agents can now create events with summary, start/end time, optional description, location, attendees, calendar override, and timezone payload.
- Calendar write-path tests covering OAuth scope enforcement, timezone-aware validation, and event insertion payload generation.

### Changed

- `scripts/setup_calendar_oauth.py` now supports `--write-access` so a device can be reauthorized with Google Calendar write scope instead of the previous read-only scope.
- Version metadata is now aligned across the Python package, manifest, and changelog at `0.7.0`.

## [0.6.2] - 2026-04-07

### Fixed

- Aggregator skip words no longer tokenize `exclude_titles`. Previously, a title like "Post Daily Timesheet" leaked "post", "daily", and "timesheet" into the aggregator, silently suppressing legitimate project keywords. `exclude_titles` and `aggregator_skip_words` now serve separate purposes with no cross-contamination.
- Preflight activity date parsing now uses the canonical `parse_calendar_dt` helper instead of inline Z-replace, preventing a CI grep check failure.
- Added `# raw-ok` annotations to `calendar.py` connection calls that can't use the helper due to circular imports.

### Added

- 16 unit tests for the canonical calendar helpers: datetime parsing (Z-suffix, offset-aware, date-only, invalid), duration calculation (normal, all-day, mixed naive/aware, negative, empty), and connection context manager (open/close lifecycle). 68 tests total.

## [0.6.1] - 2026-04-07

### Changed

- Extracted shared calendar helpers into a single canonical module: datetime parsing (`parse_calendar_dt`), duration calculation (`event_duration_minutes`), and database connection setup (`calendar_connection`). Eliminates duplicated patterns across the daily report, calendar sync, and MCP server modules.
- `calendar-daily-totals` now applies the same `calendar_id`, `exclude_titles`, and `hours_format` filters as the daily and weekly report commands. Previously showed unfiltered counts that didn't match the other reports. Resolves Hypercart-Dev-Tools/rebalance-OS#5.

### Fixed

- All-day events (date-only strings from Google Calendar) no longer crash the daily report duration calculation. They appear in the event list with 0 duration instead. Resolves Hypercart-Dev-Tools/rebalance-OS#4.

### Added

- CI grep checks that fail the build if raw datetime parsing or duration calculation patterns appear outside the canonical helpers without a `# raw-ok` escape hatch.

## [0.6.0] - 2026-04-07

### Added

- **Agent review layer for calendar reports.** Events that pass the exclude filter but don't match any configured project now appear in a "Needs Review" section at the bottom of daily reports. Agents or users can classify these via the new `review_timesheet` and `classify_event` MCP tools.
- Two new MCP tools: `review_timesheet(date)` returns unclassified events for a given date with available project names; `classify_event(summary, decision)` persists a classification ("include", "exclude", or "project:Name") so the same event pattern is handled automatically in future reports.
- Review decisions persist to `temp/review_decisions.json` (gitignored) so they survive across sessions.
- New config field `aggregator_skip_words` — broad terms (e.g. "wrap", "setup", "test") that are skipped during project aggregator grouping but do **not** filter events from the report.

### Changed

- **Breaking (config):** `exclude_keywords` replaced by `exclude_titles` for event filtering. Filtering now uses **exact title matching** (case-insensitive) instead of substring matching. This prevents real work events like "Wrap up Countdown Timer" and "Setup rebalance app" from being silently dropped when "wrap" or "setup" appear in the exclude list. Legacy `exclude_keywords` in existing config files is automatically migrated to `exclude_titles`.

### Fixed

- Resolves Hypercart-Dev-Tools/rebalance-OS#2 — exclude keywords no longer filter out legitimate work events containing common verbs.

## [0.5.8] - 2026-04-07

### Added

- CI test suite for Google Calendar functionality: config loading and validation, duration formatting (decimal and hm), daily reports (filtering, timezone, empty days), weekly reports (summary totals, project aggregator, both formats), calendar-sync config resolution, and calendar_id filtering. 36 tests total.
- GitHub Actions CI workflow running tests on Python 3.12 and 3.13 for every push and pull request to main (10-minute hard timeout).
- Google Calendar API dependencies declared as `[calendar]` optional dependency group in pyproject.toml (`pip install -e ".[calendar]"`).

### Fixed

- Report output now uses correct grammar: "1 event" instead of "1 events" in daily totals and project aggregator lines.

## [0.5.7] - 2026-04-07

### Added

- Configurable hours format for calendar reports: set `"hours_format": "decimal"` (default, e.g. `4.50h`) or `"hm"` (e.g. `4h 30m`) in the calendar config. Applies to daily reports, weekly summaries, and project aggregator tables.

## [0.5.6] - 2026-04-07

### Fixed

- `rebalance calendar-sync` now reads `calendar_id` from the calendar config instead of defaulting to `"primary"`. Previously, syncing always pulled from the user's personal calendar unless `--calendar-id` was passed explicitly, even when the config pointed to a shared team calendar. The `--calendar-id` CLI flag still overrides when provided.

### Changed

- Rewrote Google Calendar documentation with Prerequisites, Team Quick Setup, and Claude Code Setup sections for smoother developer onboarding.
- Updated README Step 4 to reflect embedded OAuth credentials — developers no longer need to create a Google Cloud project or download a separate client secret file.

## [0.5.5] - 2026-04-07

### Added

- Calendar report project matching now supports a non-Obsidian fallback: if no synced project registry exists in SQLite, reports load canonical project names and aliases from the calendar config.

### Changed

- Calendar config now supports a `projects` list for lightweight local project definitions when a developer only needs calendar timesheet grouping without the full Obsidian registry workflow.

## [0.5.4] - 2026-04-07

### Changed

- Calendar report project aggregation now treats the synced project registry as the canonical source of truth for project names and aliases, falling back to keyword grouping only for unmatched events.

### Fixed

- Daily and weekly calendar reports now preserve canonical project casing from the registry instead of reformatting matched names through heuristic title-casing.

## [0.5.3] - 2026-04-07

### Fixed

- Weekly and daily project aggregators now skip low-signal verb labels such as "can", "change", and similar filler terms, so grouped work is easier to scan.
- Project aggregation now reuses the same calendar exclude keywords as event filtering, so one keyword source drives report cleanup across the calendar reporting flow.

## [0.5.2] - 2026-04-07

### Added

- Example calendar config template at repo root for new users.
- Calendar config setup guide (4 steps: create temp folder, copy example, edit config, verify).

### Changed

- Replaced inline config template with repo-root example file.
- Clarified README calendar config instructions with code examples.

## [0.5.1] - 2026-04-07

### Added

- Portability audit confirming zero hardcoded user data across calendar setup and configuration.
- Step-by-step new user setup guide for OAuth, config, testing, and scheduling.

### Changed

- OAuth setup script now lists all available calendars with IDs and provides next-step instructions.

## [0.5.0] - 2026-04-07

### Added

- Daily and weekly calendar report CLI commands (`calendar-daily-report`, `calendar-weekly-report`) with event filtering, project aggregator grouping, and time totals.
- Per-device calendar config for calendar selection, exclude keywords, and timezone (gitignored).
- Project aggregator groups similar events by keyword, counts, and sums durations.
- Exclude keywords filter events from reports while keeping them in the database.
- Timezone-aware report times (configurable, defaults to America/Los_Angeles).
- All reports generated in clean markdown format suitable for Obsidian, email, or archival.

### Fixed

- Database layer now gracefully handles systems without sqlite-vec extension support.

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
