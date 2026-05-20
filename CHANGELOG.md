# Changelog

## [0.31.0] - 2026-05-19

### Added

- `Collector` dataclass and `COLLECTORS` source registry in `src/rebalance/ingest/index_ops.py`. `refresh_index` now routes `scope=[...]` through the registry instead of a hard-coded dispatch chain. External integrators can call `register_collector()` to add new data sources without editing the dispatcher. `included_in_all=False` marks opt-in collectors that are skipped by `scope=["all"]`.
- Shared GitHub HTTP client (`src/rebalance/ingest/_http.py`) extracted from the duplicated `urlopen` + retry + pagination logic in `github_scan.py` and `github_knowledge.py`. Single entry point with 30 s timeout, exponential backoff on 429/5xx, and `per_page=100` automatic pagination.
- `[project.optional-dependencies] server` group in `pyproject.toml` — `pip install -e '.[server]'` installs `fastapi>=0.110.0` and `uvicorn[standard]>=0.29.0` so the pulse-server venv is reproducible from a fresh clone without manual installs.

### Changed

- Logging bootstrap consolidated: `ingest/` modules now use `logging.getLogger(__name__)` via a shared setup path; the 24 duplicate `Path("rebalance.db"), envvar="REBALANCE_DB"` option declarations across the CLI were deduplicated through the shared `DBOption`.

### Fixed

- `scripts/dashboard.py` data-fetch functions (`fetch_recent_github`, `fetch_repo_activity_counts`, `fetch_vault_recent`, `fetch_recent_emails`, `fetch_watched_summary`) now return empty lists instead of raising when the DB is absent or has no tables yet. Prevents `pulse_web.py` and the terminal dashboard from crashing on a fresh checkout before the first sync.

## [0.30.0] - 2026-05-14

### Added

- The goals panel now shows a second column with the next six uppermost open todos from the same goals source, while keeping the primary three goals on the left.

## [0.29.2] - 2026-05-14

### Fixed

- Calendar viewer upcoming-event lists now compare event starts by absolute time instead of raw ISO text, so offset-stamped morning events no longer disappear while they are still upcoming.

## [0.29.1] - 2026-05-14

### Fixed

- The pulse-server launchd job is now template-managed like the other five jobs. Previously `com.rebalance-os.pulse-server.plist` lived only in `~/Library/LaunchAgents/` with four hardcoded `/Users/<name>/...` paths and no checked-in template or installer — the one launchd job PR #18 didn't reach. Added [scripts/com.rebalance-os.pulse-server.plist.template](scripts/com.rebalance-os.pulse-server.plist.template) with `{{REBALANCE_DIR}}` placeholders and [scripts/install_pulse_server_scheduler.sh](scripts/install_pulse_server_scheduler.sh) to render + load it. `pulse_server.sh` itself already derived `REBALANCE_DIR` from script location (0.29.0).
- `install_pulse_server_scheduler.sh` always attempts an `launchctl unload` before `load`, rather than gating the unload behind a `launchctl list | grep` check. The grep check can miss a job that is loaded but momentarily absent from `launchctl list`, in which case `launchctl load` fails with an opaque `Input/output error` (observed reinstalling pulse-sync and github-sync). The other five installers still use the older gated pattern — a uniform fix across all six is a follow-up.

## [0.29.0] - 2026-05-13

### Changed

- **Operator-breaking**: the ask-self wrappers ([scripts/ask-self-ingest.sh](scripts/ask-self-ingest.sh), [scripts/ask-self-query.sh](scripts/ask-self-query.sh)) now require `ASK_SELF_PATH` to be set in the environment and fail with an actionable error message when it isn't. Previously they fell back to a hardcoded `/Users/noelsaw/...` path that didn't exist on any other operator's machine — a missing env var manifested as a confusing "ask-self repo not found at <someone-else's-path>". Add `export ASK_SELF_PATH="$HOME/Documents/GitHub/ask-self"` (adjust to your checkout) to your shell rc to keep using these wrappers.

### Fixed

- The launchd installers no longer ship with one developer's home directory baked in. All five sync shell scripts (`daily_sync.sh`, `vault_sync.sh`, `pulse_sync.sh`, `pulse_web_sync.sh`, `github_sync.sh`) now derive `REBALANCE_DIR` from their own location, and their five plists became `.plist.template` files with a `{{REBALANCE_DIR}}` placeholder that each `install_*_scheduler.sh` substitutes with the local checkout path before writing into `~/Library/LaunchAgents/`. The rendered plists are gitignored, so a fresh clone on any machine installs cleanly with no per-user editing.
- The author-fallback in `PROJECT/cleanup.sh` no longer hardcodes a single operator's username — it falls back to `os.environ.get('USER', 'unknown')` when neither the existing frontmatter nor git provides an author.
- The `Degraded Mac` test fixture in [tests/test_git_pulse_health_check.py](tests/test_git_pulse_health_check.py) no longer embeds a real operator path in its `scan_failure_examples` example; it uses a generic `/Users/operator/...` placeholder instead.
- The project's `.claude/settings.json` permission allowlist had a few stale `Bash(...)` entries pointing at paths from another machine (`/Users/noelsaw/Documents/GitHub-Repos/...` and `/Users/noelsaw/Documents/rebalance-OS/...`) along with a corresponding `additionalDirectories` entry — all removed since they were dead-ends on this checkout.

### Action required on existing machines

If you already had launchd jobs or ask-self wrappers set up against the previous code, the changes above don't take effect until you do the following on each affected machine:

1. **Re-install the launchd jobs** so the rendered plists in `~/Library/LaunchAgents/` are regenerated from the new templates with your local checkout path. The install scripts unload any existing job before re-rendering, so this is safe to re-run:

   ```bash
   bash scripts/install_scheduler.sh             # daily sync (06:30)
   bash scripts/install_vault_scheduler.sh       # hourly vault refresh
   bash scripts/install_pulse_scheduler.sh       # hourly pulse publish
   bash scripts/install_pulse_web_scheduler.sh   # 30-min pulse-web refresh
   bash scripts/install_github_scheduler.sh      # hourly github-only sync
   ```

   Skip any installer for a job you don't currently have loaded (`launchctl list | grep rebalance-os` shows what's running).

2. **Set `ASK_SELF_PATH` in your shell** if you use the ask-self wrappers — there is no longer a built-in default. Add to `~/.zshrc` / `~/.bashrc`:

   ```bash
   export ASK_SELF_PATH="$HOME/Documents/GitHub/ask-self"   # adjust to your checkout
   ```

No DB or vault migration is required — only the install paths above change behavior.

## [0.28.3] - 2026-05-13

### Added

- Single-command triage wrapper [experimental/triage/run_triage.py](experimental/triage/run_triage.py). Wraps the multi-step triage flow (github-sync, sleuth-sync, `spike.py`) into one invocation with flags for `--sync`, `--publish`, and `--dry-run`. Existing direct `spike.py` workflows are unchanged.
- Two new triage buckets in [experimental/triage/spike.py](experimental/triage/spike.py): **close candidates** (scores open issues against merged PRs to surface issues likely already fixed) and **stale issues** (uses last-comment dates instead of `updated_at`, since the latter is bumped by edits/labels/assignee changes that don't indicate progress). A notes-section counter also surfaces orphaned remote branches whose `head_sha` matches a merged PR.

### Changed

- `load_project_matchers(db, config=None, *, priority_rules=None)` and `_build_matchers_from_priority_rules(rules=None)` now accept an explicit `priority_rules` override. `None` (default) preserves production behavior — read operator-local `project_priority_rules` from `temp/rbos.config`. `[]` skips operator rules entirely; a list of rule dicts injects test fixtures. Previously, any test exercising the classifier (directly or via `generate_daily_report` / `generate_weekly_report`) inherited whatever brand rules happened to be on the host machine, making test outcomes depend on the operator's local config. `tests/test_calendar_reports.py` drops its `setUpModule`/`tearDownModule` pair as a result; `tests/test_calendar_aggregator.py` shrinks similarly.

### Fixed

- The triage spike's **PRs unblocked** bucket now filters out merged PRs, requires CI-green status, excludes drafts, and adds a staleness warning when activity stalls. Previously merged PRs could appear because the filter relied on `state` alone.
- The triage spike's **release blockers** bucket now joins `github_milestones` to surface due dates and flags overdue items. Previously the rendered table had no time signal.
- The triage spike's **perf concrete** bucket now reads `labels_json` and warns on close-intent labels (`wontfix`, `duplicate`, etc.), reducing false-positive recommendations.
- `bucket_client_visible` in [experimental/triage/spike.py](experimental/triage/spike.py) now handles a missing `sleuth_reminders` table gracefully — catches `sqlite3.OperationalError` and returns an empty bucket instead of crashing the whole triage run when Sleuth hasn't been synced on this checkout.
- Eight test-suite failures carried over from pre-0.28 main are now resolved, restoring a fully green `pytest tests/` from a fresh clone.
- Real client/org names were scrubbed from 15 test fixture files (`Binoid` → `AcmeCorp`, `Bloomz` → `Mainline`, `CreditRegistry` → `AcmeReg`, etc., with longest-match-first to preserve substring relationships). Test fixtures no longer advertise real client relationships, and the suite is portable to anyone running it without the operator's `temp/rbos.config` priority rules.

## [0.28.2] - 2026-05-13

### Changed

- Timezone handling centralized into `src/rebalance/tz_utils.py` (single source of truth). `local_tz()` resolves device timezone via `REBALANCE_TZ` env var → `/etc/localtime` symlink → UTC fallback. Stored timestamps remain UTC ISO 8601; conversion happens only at display.
- **Behavior change:** operator-facing timestamps in the terminal dashboard, pulse, and calendar reports now default to the **OS-detected local timezone** instead of hardcoded fallbacks (`America/Los_Angeles` for `scripts/dashboard.py`, `America/New_York` for `CalendarConfig`). Set `REBALANCE_TZ` or pin a `timezone` value in `temp/calendar_config.json` to keep a specific zone regardless of host.
- `src/rebalance/ingest/calendar_config.py` default `timezone` value changed from `"America/New_York"` to `""` — empty resolves to the device-local zone at load time via `local_tz().key`.
- `src/rebalance/ingest/pulse.py` and `scripts/dashboard.py` drop their inline `_parse_iso()` / `ZoneInfo("America/Los_Angeles")` duplicates and route through `tz_utils`.
- `src/rebalance/ingest/dashboard.py::_format_generated_at()` now renders in local zone with `%Z` suffix instead of forced UTC.

## [0.28.1] - 2026-05-13

### Fixed

- Pulse web now labels the main feed as `Recent GitHub activity` and shows one additional GitHub history row in that card.
- The pulse web/dashboard data layer now treats missing optional SQLite tables such as `calendar_events` and `sleuth_reminders` as empty-state sources instead of aborting the whole page render.

## [0.28.0] - 2026-05-12

### Changed

- Canonical `rebalance.db` location moved from the project tree (`~/Documents/rebalance-OS/rebalance.db`) to `~/Library/Application Support/rebalance-os/rebalance.db` on macOS (or `$XDG_DATA_HOME/rebalance-os/` / `~/.local/share/rebalance-os/` on Linux). The new path is not TCC-protected, so the SwiftUI dashboard (and any other GUI consumer) can read it without an Allow-prompt dance on first launch.
- `src/rebalance/paths.py::resolve_database_path()` gained a third resolution layer for the canonical path, inserted between the `REBALANCE_DB` env var and the user-config `database_path` field. Existing env-var and explicit-path overrides continue to win; stale paths simply fall through to the canonical location.
- `scripts/dashboard.py` now resolves the DB via `rebalance.paths.resolve_database_path()` instead of reading `REBALANCE_DB` directly with a `"rebalance.db"` relative fallback. Survives running outside the project tree.
- `.vscode/mcp.json` updated to point `REBALANCE_DB` at the canonical app-data location.

### Added

- `src/rebalance/paths.py::migrate_database_to_canonical()` — idempotent migration that moves `rebalance.db` plus its `-wal` and `-shm` sidecars to the canonical location, and clears the user-config `database_path` field when it was pointing at the just-migrated source. Run via `python -m rebalance.paths --migrate` (add `--dry-run` to preview).
- Phase 0 of the Mac SwiftUI Dashboard port landed under `experimental/mac-dashboard/` — Xcode app project (xcodegen-generated) consuming `HypercartMacOSDashboard` and GRDB. Renders 23 GitHub-balance rows from the live SQLite in ~69 ms on the canonical path. See [PROJECT/2-WORKING/MAC-DASHBOARD-PORT.md](PROJECT/2-WORKING/MAC-DASHBOARD-PORT.md) for findings.

## [0.27.1] - 2026-05-12

### Fixed

- Gmail 403 handling is now conservative: only true insufficient-scope responses are rewritten into the `gcloud auth application-default login` remediation message. Other 403s, such as a disabled Gmail API, surface their original upstream error instead of being mislabeled as a scope problem.

## [0.27.0] - 2026-05-12

### Added

- Gmail inbox ingest via `refresh_index(scope=["email"])`. Phase 1 syncs the newest 100 inbox messages, stores message metadata plus Gmail-provided snippets in SQLite, and backfills them into the unified semantic index so email participates in default `semantic_query()` results.
- New `gmail_query_filter` config key in `temp/rbos.config` to narrow the Gmail fetch scope without code changes. Defaults to `in:inbox`.
- `index_status()` now reports an `email` source block with message count, last sync time, and newest received timestamp.

### Fixed

- Gmail auth failures caused by missing `gmail.readonly` scope now return an explicit remediation message with the exact `gcloud auth application-default login` command to rerun.

## [0.26.0] - 2026-05-12

### Added

- Pulse FastAPI server autostart at login. New LaunchAgent `com.rebalance-os.pulse-server` (managed at `~/Library/LaunchAgents/com.rebalance-os.pulse-server.plist`) runs `scripts/pulse_server.sh` with `RunAtLoad=true` + `KeepAlive=true` + `ThrottleInterval=30s`. Previously the server was on-demand only — the 30-minute `pulse-web-sync` job kept the static `web/pulse.html` fresh but the interactive Refresh/filter layer at `http://127.0.0.1:8767` only ran when a terminal was open. Logs to `temp/logs/pulse_server_stdout.log` and `pulse_server_stderr.log`.
- Per-repo activity doughnut on the pulse page. New `fetch_repo_activity_counts(days=7, limit=12)` in `scripts/dashboard.py` returns a UNION-of-three-tables count (items + commits + comments) grouped by `repo_full_name` for the last N days, honoring the existing `github_ignored_repos` blocklist. `scripts/pulse_web.py` renders this as a Chart.js 4.4 doughnut (loaded from `cdn.jsdelivr.net` with `defer`) with per-slice colors from a 12-entry palette, an embedded JSON payload (`<script type="application/json" id="repo-pie-data">`) that the existing `PULSE_JS` IIFE reads on `load`, and tooltips showing count + percentage. The chart sits in the right column of the body grid (where Index Health used to live); Watched repos now stacks above it. Falls back to a friendly empty-state when no activity exists in the window.
- Pulse page layout restructured to put Index Health on a full-width row beneath the two-column grid. The grid is now Recent Activity (left col, 2fr) / Watched + Repo Activity doughnut (right col, 1fr), with `<div class="full-row">` holding Index Health below. New CSS: `.full-row { margin-top: 16px }`, `.repo-pie .card-head { display: flex; justify-content: space-between }`, `.repo-pie-wrap { padding: 8px 14px 16px }`.
- Slack deep links on Sleuth reminder rows in the pulse sidebar. New `build_slack_url(reminder)` helper in `scripts/pulse_web.py` constructs `https://<workspace>.slack.com/archives/<channel_id>/p<ts-no-dot>` from the reminder's own `workspace_name` + `original_channel_id` (falling back to `target_channel_id`) + `original_message_id` (falling back to `original_thread_ts`). macOS Slack registers `slack.com` as a Universal Link and opens these URLs directly in the desktop app when installed. Each sleuth row that resolves a URL now renders as `<li class="side-row has-link"><a class="side-row-link" target="_blank" rel="noopener noreferrer">…</a></li>`; rows without a usable channel degrade gracefully to the plain non-link form. New CSS rules: `.side-row.has-link { padding: 0 }`, `.side-row-link { display: block; padding: 7px 8px; color: inherit; text-decoration: none }`, `.side-row-link:hover { background: rgba(124,196,255,.10) }`, `.side-row-link:hover .side-row-title { color: var(--info) }`. `fetch_sleuth_due` in `scripts/dashboard.py` now selects `workspace_name`, `original_channel_id`, `target_channel_id`, `original_message_id`, `original_thread_ts` so the renderer has everything it needs.
- Sleuth workspace blocklist. New `sleuth_ignored_workspaces` array key in `temp/rbos.config` (the same gitignored config file that holds `github_ignored_repos` and `calendar_ignored_summaries`) suppresses reminders from listed Slack workspaces. `get_pulse_config()` in `src/rebalance/ingest/config.py` now whitelists this key — previously the explicit-keys return dict silently dropped any unknown config keys, which caused the first iteration of the filter to no-op. `fetch_sleuth_due` reads the list and appends `AND LOWER(workspace_name) NOT IN (?, ?, …)` to both SQL branches (the `slack_user_id` one and the unauthenticated one). Edits take effect on the next render or refresh — no restart needed. Example:

    ```json
    {
      "sleuth_ignored_workspaces": ["neochrome-dev"]
    }
    ```

- Production Sleuth Web API support. `_load_sleuth_env(which="production")` in `src/rebalance/cli.py` now looks up `~/secrets/sleuth-web-api-{which}.env` first (default: production), falling back to the legacy `sleuth-web-api-development.env` if the requested file doesn't exist. Existing dev-only setups continue working without modification. Operator-side setup is unchanged: create the new env file (mode 600) with `SLEUTH_WEB_API_BASE_URL` / `SLEUTH_WEB_API_TOKEN` / `SLEUTH_WORKSPACE_NAME`. Because the prod Sleuth Web API typically only listens on the host's loopback (port 2020 firewalled from the public internet), `SLEUTH_WEB_API_BASE_URL` is usually a local port-forward target (e.g. `http://127.0.0.1:12020` with a separate SSH tunnel managed by a `com.rebalance-os.sleuth-tunnel` LaunchAgent).

### Changed

- `get_pulse_config()` whitelist now exposes `sleuth_ignored_workspaces` (defaults to `[]`). All other keys are unchanged. The new key documentation in the docstring explicitly mentions the `["neochrome-dev"]` blocklist pattern as the canonical example.

## [0.25.0] - 2026-05-07

### Added

- Centralized path resolution via new module `src/rebalance/paths.py`. Single source of truth for "where is the database?" and "where are the secrets?". Layered resolver chain: (1) explicit `--database` flag, (2) `REBALANCE_DB` env var, (3) walk up from cwd for a project marker (`.git` / `pyproject.toml`) and look for `rebalance.db` next to it, (4) `database_path` field in `~/.config/rebalance-os/config.json`. When no layer resolves, raises `DatabaseNotFoundError` whose message names every candidate it tried and the four routes to fix it. Same chain for secrets: `REBALANCE_SECRETS_DIR` env var → `secrets_dir` user-config field → `~/secrets/` legacy default. Migrates the previously-hardcoded operator paths (`/Users/noelsaw/secrets/google-calendar.env`, `/Users/noelsaw/secrets/sleuth-web-api-development.env`) onto the resolver, closing the AGENTS.md portability TODO. All 24 `Path("rebalance.db"), envvar="REBALANCE_DB"` defaults across the CLI plus the MCP server's `main()` now route through the resolver. New CLI subcommands `rebalance config set-default-database <path>`, `rebalance config set-secrets-dir <path>`, and `rebalance config show-defaults` (debug helper that prints what every layer of the resolver currently sees).
- 30-minute web pulse refresh. New launchd job `com.rebalance-os.pulse-web-sync` runs `scripts/pulse_web_sync.sh` every 30 minutes from 06:00 to 23:30, regenerating `web/pulse.html` from the same SQLite the TUI reads. The page itself uses `<meta refresh content="30">` so any browser tab pointed at `file://` reloads on a cadence; pair the two and the local mirror stays within ~30 min of the SQLite truth. Atomic via tmp+replace (a crashed run leaves the previous HTML intact). No network, no git push — separate from the hourly markdown→private-repo pulse-sync job. Install with `bash scripts/install_pulse_web_scheduler.sh`.
- Repository hygiene audit (`scripts/audit_modules.py`). Verifies that ingest collectors and render modules are documented in ARCHITECTURE.md + CHANGELOG.md, and that recent commits' file changes appear in the latest CHANGELOG version section. Three checks: ARCHITECTURE.md mention, CHANGELOG.md historical mention, and recent-commit coverage (last N commits since the live version's date, default 20). A baseline lockfile (`scripts/audit_modules.lock`) silences pre-existing gaps so the audit fails only on NEW drift; `--init` re-snapshots the baseline after a deliberate doc backfill. `--include-uncommitted` adds a pre-commit preview that flags working-tree changes (modified/untracked audit-worthy `.py`/`.sh`/`.plist` files) not yet in the latest CHANGELOG section. `--json` emits a stable schema (`audit_version: 1`) with `passed`, `summary`, structured `checks`, and an actionable `next_steps` array suitable for orchestrating agents.
- `audit_modules` MCP tool (registered in `src/rebalance/mcp_server.py`). Wraps `scripts/audit_modules.py --json` for host agents (Claude Code / Claude Desktop). Parameters mirror the CLI: `init`, `commits_window`, `include_uncommitted`. Returns the same stable JSON schema as the CLI, with subprocess-launch errors surfaced as `passed: False, exit_code: 2` and diagnostic fields rather than raised exceptions.
- Audit script scope expansion. `scripts/audit_modules.py` now also scans top-level `src/rebalance/*.py` files (cli.py, mcp_server.py, paths.py) — previously the discovery was limited to `src/rebalance/ingest/*.py` + `scripts/*.py`, which silently let new top-level modules slip past. `__main__.py` was added to IGNORED_FILES alongside the existing `__init__.py` since both are package shims. The substring mention check is now case-insensitive so docs can talk about a module using capitalized prose ("the CLI", "the MCP server") and still satisfy the audit; trades a small false-positive risk (English word matching a stem) for catching the previously-silent false-negative class.
- `rebalance raw` calibration command. Shows GitHub events from the last N minutes (default 30) and classifies each against local pipeline state: ✓ captured (`last_active_at >= event_time` for that repo), ⏳ pending (repo watched but pipeline hasn't caught up yet), ✗ unwatched (repo not in `github_repo_meta` — silently missing from the pipeline). The output now includes a second **team activity** table that fetches per-repo events for the top N most-active watched repos (default 10, tunable with `--top`) and filters out the current user's own actions — surfaces teammate activity that `/users/{login}/events` alone cannot see (the same gap that motivated the "use PAT + per-repo branch queries" calibration practice). A third **unwatched repos with recent pushes** section uses `/user/repos?sort=pushed` to compare your accessible repos against `github_repo_meta` independent of the events feed — surfaces freshly-created or low-event repos (default 7-day push threshold) that the time-bounded event sections can't see, so a new repo you push to once and forget no longer slips past calibration. Honors the configured ignored-repos list and skips archived/disabled repos. Total cost: 1 + N + 1 GH API requests per invocation. `--watch N` re-runs every N seconds (recommended floor 30s due to GH events API ~30s eventual consistency); `--json` emits a structured snapshot for orchestration with `events` (your activity), `team_activity.events`, and `unwatched_active_repos.repos` arrays. Used to verify that recent commits/PRs/issues — yours and your team's — are making it into rebalanceOS, and that no accessible repo is silently missing from the watch list.
- Project plan doc [PROJECT/1-INBOX/P3-MODULE-REGISTRY.md](PROJECT/1-INBOX/P3-MODULE-REGISTRY.md) covering three approaches to drift control (post-hoc audit / proactive registry / SOP-only), with empirical findings from the Approach A prototype and an explicit recommendation to revisit a declarative registry only if drift recurs after this round.
- Static web mirror of the terminal pulse dashboard. `scripts/pulse_web.py` renders a self-contained `web/pulse.html` from the same SQLite knowledge base the TUI reads, with an "Open in Obsidian" link in the hero, a left sidebar that surfaces the next 6 calendar events and 6 Sleuth reminders, and meta-refresh-driven auto-reload. Run one-shot via `./.venv/bin/python scripts/pulse_web.py`, or in `--watch` mode for continuous regeneration. Goals are pulled from `{vault_path}/0. Goals.md` by default; override with `--goals` or `PULSE_GOALS`.
- Calendar ignore list. Add a `calendar_ignored_summaries` array to `temp/rbos.config` (the same gitignored config file that holds `github_ignored_repos`) to suppress recurring events from both the web mirror and the terminal dashboard. Patterns are matched case-insensitively as substrings against `calendar_events.summary` — no glob or regex syntax. Example:

    ```json
    {
      "calendar_ignored_summaries": ["Daily Standup", "Lunch Break"]
    }
    ```

  Edits take effect on the next render or refresh — no restart needed.

### Fixed

- Background HTTP calls to the GitHub API now have a 30-second timeout (`urlopen(req, timeout=30)`) in `github_scan.py`, `github_knowledge.py`, and `diagnose.py`. Without this, a stalled HTTPS connection (commonly after macOS sleep/wake) could leave a long-running terminal dashboard blocked inside `urlopen` indefinitely, holding a SQLite writer connection across the hang.
- SQLite connections now set `PRAGMA busy_timeout=30000`, so brief writer contention waits up to 30 seconds for a slot instead of erroring instantly. Together with the HTTP timeouts, this prevents the cascade where one stalled request silently broke the daily sync, every hourly vault sync, and the TUI auto-refresh with "database is locked" until the holder process was manually killed.

## [0.23.9] - 2026-05-05

### Added

- Local project/client priority rules can now assign dashboard priority tiers, value scores, client labels, value levels, and risk levels without committing private account metadata.
- The dashboard now ranks projects by local priority score before activity, shows the priority metadata in each project block, and can surface configured priority projects even before they exist in the active registry.
- Calendar/project classification now uses the same local priority aliases, so important client or project nicknames route to the right dashboard row.
- The config CLI can set, list, and remove local project priority rules stored in the ignored operator config.

## [0.23.8] - 2026-05-05

### Changed

- Full index refreshes now update the Obsidian dashboard note after successful ingest and immediately re-ingest/embed that note so the local SQLite index sees the refreshed operating dashboard.
- The generated dashboard note now shows a visible "Last generated" timestamp directly under the title, making freshness/staleness obvious without inspecting frontmatter.

## [0.23.7] - 2026-05-05

### Changed

- Pulse Sleuth reminder sections now include tasks assigned by the operator to other people, not only tasks assigned to the operator, so delegated follow-ups remain visible in the daily operating view.

## [0.23.6] - 2026-05-05

### Added

- GitHub triage reports can now include configured related/affiliate project repos, showing open external issues and PRs alongside whether each one is already linked from a central tracker issue.
- Local config now supports per-tracker related GitHub repo lists so implementation repos can stay separate while project tracking remains centralized.

## [0.23.5] - 2026-05-05

### Fixed

- The terminal pulse dashboard now skips GitHub semantic embedding during its background refresh, preventing the terminal process from loading the local embedding model and consuming excessive memory. Daily sync and explicit refresh calls still run semantic work by default.

## [0.23.4] - 2026-05-04

### Added

- Dashboard-triggered GitHub refreshes now append profile records to local logs, and `rebalance profile-sync` can read those logs to show the slowest repos from the latest live refresh instead of only the daily sync job.

## [0.23.3] - 2026-05-04

### Fixed

- Starred or watched GitHub repos no longer become automatically monitored. Auto-discovered watched repos now require at least one real work signal such as a push, commit, issue, PR, comment, or review.

## [0.23.2] - 2026-05-04

### Fixed

- The terminal pulse dashboard now filters its recent GitHub feed through the configured GitHub ignore list, so ignored repos stay hidden even when older rows are still present in the local database.

## [0.23.1] - 2026-05-04

### Fixed

- The terminal pulse dashboard now uses explicit dark and light palettes instead of ANSI reverse-video styling, preventing low-contrast text on light terminal backgrounds while preserving the inverse visual mode.
- Rich is now declared as a runtime dependency so the terminal dashboard and profiling tables are available after a normal package install.

## [0.23.0] - 2026-05-03

### Added

- A new `rebalance pulse` terminal dashboard (`scripts/dashboard.py`) — a Rich Live four-pane monitor of watched repos, recent GitHub activity, vault/calendar/sleuth signals, and index health. Polls the local SQLite every 2 seconds and runs `refresh_index(scope=["github"])` in a background thread every 10 minutes so the underlying data actually changes. Themed with the "Refined Dark" palette (single amber accent, low-contrast borders) and toggleable to inverse-video via `PULSE_INVERSE=1` for a brain-hack visual modality.
- A new `diagnose_repo` MCP tool that walks the watched-repos and sync funnel for a single repo and explains why it is or isn't being monitored. Supports per-commit and per-PR diagnoses (`sha=`, `pr=`) and an opt-in `live=True` that probes GitHub directly so callers can distinguish "we never synced" from "PAT can't see it."
- A new hourly vault refresh job (`scripts/com.rebalance-os.vault-sync.plist` + `vault_sync.sh` + `install_vault_scheduler.sh`) that calls `refresh_index(scope=["vault"])` at HH:15 from 06:15 to 23:15, so notes edited mid-day surface within the hour instead of waiting for the daily 06:30 sync.
- A new `rebalance profile-sync` subcommand that parses the most recent `daily_sync_*.log`, extracts per-repo GitHub timings, and prints a sorted Rich table with semantic colour bands for outliers and a `--top N` flag. The log parser walks the file with `JSONDecoder.raw_decode` for the last valid object, so it survives shell-prefixed lines, `tqdm` progress bars on the JSON line, and even multi-run logs.
- A new Slack user lookup (`src/rebalance/ingest/slack_users.py` + user-editable, gitignored `temp/slack_users.json`) that rewrites `<@U…>` mentions to friendly names across the dashboard sleuth panel and the published pulse markdown. Cached against the file's mtime so edits land on the next read without a restart.

### Changed

- The `rebalance` CLI now launches the live dashboard when invoked with no arguments. All existing subcommands continue to work and `rebalance --help` lists the full surface; `rebalance dashboard` is exposed explicitly so the launcher is discoverable. The CLI defaults `REBALANCE_DB` to the repo's `rebalance.db` so the dashboard works from any cwd.
- The vault note ingester now refreshes `vault_files.last_modified` when the on-disk mtime moves but content bytes don't, so a no-op save in Obsidian still registers as a "touch" in the dashboard. A new `touched_files` counter is reported alongside `new_files` / `updated_files` in the `refresh_index` JSON.
- The pulse markdown publisher now runs reminder messages through the same Slack mention rewrite, so reminders rendered into the daily pulse use friendly names instead of raw user IDs.

## [0.22.0] - 2026-04-28

### Added

- A new dashboard rendering command that synthesizes one Obsidian-ready operating note from recent local project, calendar, and GitHub signals.
- Structured dashboard output that pulls recent release highlights and current weekly goals into the same generated note so the operating surface stays anchored in recent shipped work and current intent.
- Focused tests covering dashboard note write-back plus the optional Gemini summary path.

### Changed

- Dashboard generation now supports an optional Gemini narrative layer for the operator summary while keeping project verdicts and evidence deterministic from local data.
- The dashboard flow now supports an optional cleanup mode that tightens the Gemini-written summary without changing the underlying structured evidence.

## [0.21.0] - 2026-04-28

### Added

- A new inferred project-registry pipeline that builds `project_registry` rows from existing GitHub and Calendar activity already stored in local SQLite, instead of requiring a hand-written registry to exist first.
- A `rebalance ingest infer-project-registry` command with a dry-run mode so inferred project rows can be previewed before they are written into the canonical SQLite registry.
- Focused tests covering repo-plus-calendar project merging, calendar-only project inference, ignored-repo exclusion, and stale inferred-row cleanup on resync.

### Changed

- Organization-style owners such as `NeochromeTeam` and `BinoidCBD` now collapse into cleaner umbrella project names when their repos are inferred from GitHub activity.
- Project inference now ignores repos with zero activity in the latest GitHub scan and filters out several recurring non-project calendar labels, producing a more usable first-pass registry.

## [0.20.0] - 2026-04-28

### Added

- A first-class local GitHub ingest ignore list stored in gitignored operator config, with CLI commands to add, remove, and list exact skipped repos.
- A destructive-but-audited GitHub repo purge path that can preview row counts with `--dry-run`, requires `--confirm` for execution, and records purge activity in the local audit log.
- Targeted tests covering ignored-repo config normalization, CLI management flows, GitHub scan filtering, artifact-sync rejection, purge cleanup, and semantic backfill exclusion.

### Changed

- GitHub activity scans now filter ignored repos before persistence and report how many repos were skipped.
- GitHub artifact sync and unified GitHub semantic backfill now enforce the same ignored-repo contract so skipped repos cannot be reintroduced through later ingest runs.

## [0.19.0] - 2026-04-24

### Added

- A new unified semantic index layer with `semantic_documents`, `semantic_embeddings`, and `semantic_embedding_meta` so vault chunks and GitHub artifact documents can be embedded and queried through one shared contract instead of separate per-source vector tables.
- New `rebalance semantic-backfill`, `rebalance semantic-embed`, and `rebalance semantic-query` CLI commands for populating, embedding, and querying the unified semantic layer directly from the existing local SQLite database.
- Focused semantic-index tests covering cross-source backfill, shared embedding/query behavior, and incremental re-embed behavior when only one source row changes.

### Changed

- Vault ingest now dual-writes into the unified semantic document layer after chunk updates, keeping the derived semantic index aligned with the canonical `chunks` table.
- GitHub artifact sync now dual-writes into the unified semantic document layer after rebuilding `github_documents`, so the new cross-source semantic index stays current without a separate post-sync job.
- GitHub artifact sync tests now assert that semantic write-through is happening, not just the legacy `github_documents` population.

## [0.18.4] - 2026-04-23

### Fixed

- `collect.sh` now treats watched-repo access failures as degraded scans instead of silently collapsing them into "no commits yet." When a repo scan fails, the collector still syncs metadata and any successfully scanned repos, but it records `repo_scan_failures`, `scan_status`, and `scan_failure_examples` in `devices/<device_id>.yaml` so the failure is visible.
- The collector no longer advances `~/.config/git-pulse/last-run` after a partial scan. That preserves the broken window for later re-collection once repo access is restored instead of making those commits invisible.
- `git-pulse-health` now reports recent-but-partial scans as `DEGRADED` rather than `ALIVE`, so the new heartbeat does not mask blocked watched repos.
- `install.sh` and `config.example.sh` now default repo discovery to non-protected roots (`~/code`, `~/src`, `~/Projects`) instead of `~/Documents`, aligning the installer with the launchd/TCC recovery guidance.

## [0.18.3] - 2026-04-23

### Fixed

- `git-pulse-health` no longer treats a quiet but healthy machine as stale just because its `pulse-<device_id>.md` file has not changed recently. The collector now publishes a sync-visible heartbeat in each device metadata record, and health checks prefer that heartbeat before falling back to pulse-file git history on older installs.
- Health output now reports the last scan timestamp instead of only the last pulse-file commit timestamp, and adds notes that surface the age of the last pulse update and last local commit when that context is available.

## [0.18.2] - 2026-04-22

### Fixed

- Hourly launchd-triggered git-pulse runs were silently failing on every machine because the sync repo and the watched repos lived under `~/Documents`, a macOS TCC-protected location. Launchd-spawned shells inherit no Full Disk Access, so `git` exited with `fatal: Unable to read current working directory: Operation not permitted` on every fire (`launchctl list` showed exit 128). The Phase 0 SQLite spike documented this risk only for the future SQLite layer; it should have been flagged for the existing collector too.
- Discovered as a follow-on issue: `~/.config/git-pulse/last-run` gets bumped to the scan-start epoch even when the watched-repo reflog walk fails inside the loop, so commits authored during the broken window become invisible to subsequent runs unless the operator rolls `last-run` back manually. Worth a future hardening pass on `collect.sh` so `last-run` only advances after a scan that actually iterated the watched repos successfully.

### Per-machine recovery instructions

The same recovery applies to every machine where launchd-triggered git-pulse hasn't been pushing on its expected hourly cadence (check with `git-pulse-health` — STALE for hours = likely affected).

```bash
# 1. Stop the launchd agent so we can reconfigure cleanly
launchctl unload ~/Library/LaunchAgents/com.user.git-pulse.plist

# 2. Move the sync repo out of ~/Documents (TCC-protected)
#    Adjust the source path to match this machine's current sync_repo_dir.
mv "$HOME/Documents/GH Repos/rebalance-git-pulse" "$HOME/git-pulse-sync"

# 3. Update sync_repo_dir in the config to the new location
sed -i '' "s|/Users/$USER/Documents/GH Repos/rebalance-git-pulse|/Users/$USER/git-pulse-sync|" \
  ~/.config/git-pulse/config.sh

# 4. Reload the launchd agent
launchctl load ~/Library/LaunchAgents/com.user.git-pulse.plist
```

If your watched repos in `~/.config/git-pulse/config.sh` (`repos=(...)`) still live under `~/Documents`, you also need **one** of the following so launchd-spawned `bash` can reach them:

- **Recommended for personal Macs:** add `/bin/bash` to System Settings → Privacy & Security → Full Disk Access. Open the pane with `open "x-apple.systempreferences:com.apple.preference.security?Privacy_AllFiles"`, click `+`, press `⌘⇧G`, paste `/bin/bash`, Add, and ensure the toggle is on. macOS TCC tracks the responsible parent process; granting FDA on `git` alone does not propagate when invoked from a non-FDA shell.
- **Alternative:** move each watched repo out of `~/Documents` (mirrors the sync-repo fix). More disruptive — re-points editor workspaces and IDE bookmarks.

Then optionally roll back `last-run` so commits authored during the broken window get re-collected on the next fire:

```bash
# Use this machine's pulse file. Replace <device-id> with the slug from `git-pulse-health`.
tail -1 ~/git-pulse-sync/pulse-<device-id>.md | cut -f1 > ~/.config/git-pulse/last-run
```

Verify:

```bash
launchctl kickstart -k gui/$(id -u)/com.user.git-pulse
sleep 5
launchctl list | grep git-pulse        # exit code should be 0, not 128
git-pulse-health                       # this machine should flip to ALIVE
```

### Known quirk surfaced during recovery

`collect.sh` filters reflog entries down to `commit:` / `commit (initial):` / `commit (amend):` prefixes. Commits produced by `git rebase` are recorded in the reflog with different prefixes (`rebase:` family) and are therefore not captured into pulse files. The reachable orphan commits from before a rebase still get captured; the rebased target commits do not. Worth tracking; not blocking for this release.

## [0.18.1] - 2026-04-22

### Fixed

- Git pulse copied Python launchers now install their shared support files beside `~/bin/git-pulse-recap` and `~/bin/git-pulse-health`, including `pulse_common.py` and the recap summary rulebooks, so the new commands work on machines using copy mode from protected folders like `~/Documents`.
- The Python git-pulse entrypoints now resolve imports from their real script directory, which keeps shared-helper imports working in both copied and symlinked launcher modes.

## [0.18.0] - 2026-04-22

### Added

- New `git-pulse-health` command that reads the sync repo's git log for each `pulse-<device_id>.md` file and reports time-since-last-push per machine. Flags devices as ALIVE / STALE / ALERT / NO PUSHES with configurable thresholds (`--warn-hours`, `--alert-hours`). Exit codes: 0 all alive, 1 at least one stale, 2 any alert or missing pushes — suitable for shell chaining.
- Recap Daily Activity tables (both personal `recap.py` and team `team-recap.py`) now surface quiet days explicitly. Consecutive zero-activity days inside the coverage window collapse into a single `_<start> to <end> — no activity (N days)_` row so the reader can see gaps at a glance instead of inferring them from missing rows.

### Changed

- `pulse_common.py` gains `daily_activity_with_gaps(day_rows)` to compute the gap-aware reverse-chronological timeline; both recap scripts and any future SQLite-backed renderers share it.
- `install.sh` now installs a fourth launcher, `~/bin/git-pulse-health`, alongside the collector, view, and recap commands.

### Per-machine re-install instructions

Each machine already running git-pulse needs to pull the updated scripts and refresh its `~/bin/` launchers so launchd picks up the new `collect.sh` (from the earlier `hardware_uuid` work) and gains the new `git-pulse-health` command:

```bash
# On every machine running git-pulse:
cd /path/to/rebalance-OS
git pull
bash experimental/git-pulse/install.sh
```

`install.sh` is idempotent — it re-copies the launcher scripts, rewrites the launchd plist, and reloads the agent. No config changes required. After re-install, verify with:

```bash
git-pulse-health           # prints per-machine health table
git-pulse --dry-run        # quick smoke test of the collector
```

Running the collector once post-install (manually or by waiting for the next hourly launchd fire) will also rewrite that machine's `devices/<id>.yaml` with `schema_version: 2` and its `hardware_uuid`, completing the legacy metadata migration.

## [0.17.1] - 2026-04-22

### Fixed

- Git pulse collector migration now stages both renamed files and removed legacy files so duplicate machine pulse entries are actually deleted from the sync repo on push.
- Collector integration coverage now matches the real `git add -A -- ...` staging path used during legacy device-id cleanup.

## [0.17.0] - 2026-04-21

### Added

- A new `git-pulse-recap` command that merges overlapping saved TSV reports and renders an all-machines Markdown recap with summary metrics, coverage, repo rollups, daily activity, recent activity, and exception flags.
- Integration coverage for the recap flow, including default discovery from `sync_repo_dir/reports` and writing the rendered Markdown to disk.

### Changed

- The git-pulse installer now exposes a third launcher, `~/bin/git-pulse-recap`, alongside the collector and unified view commands.
- The git-pulse README now documents the saved-report recap workflow and the new recap artifact path under the sync repo's `reports/` directory.

## [0.16.3] - 2026-04-20

### Added

- Collector self-healing for old git pulse ids: a normal non-dry-run collection now migrates older UUID-based ids and older apostrophe-split slugs to the current human-friendly slug for that machine.
- Integration coverage for collector-driven device-id migration so the self-heal path is exercised without manual cleanup steps.

## [0.16.2] - 2026-04-20

### Changed

- Git pulse slug generation now drops apostrophes instead of turning them into extra separators, so names like `Noel's` become `noels` rather than `noel-s`.

## [0.16.1] - 2026-04-20

### Changed

- Git pulse device ids now default to human-friendly computer-name slugs instead of generated UUIDs when `device_id` is left blank.
- Git pulse hostname sanitization now trims leading and trailing dashes so device ids and host tags do not pick up quote-induced trailing separators.

## [0.16.0] - 2026-04-20

### Added

- A new `--include-local-unsynced` mode for the git pulse viewer so a saved report can combine synced cross-device pulse files with this Mac's current unsynced local reflog activity.
- Integration coverage for combined git pulse report generation, including writing a reusable TSV report to disk via `--output`.

### Changed

- The git pulse viewer can now generate a real reusable combined range report with `--days N --include-local-unsynced --output ...` instead of requiring ad-hoc terminal merges.

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

- Google Calendar docs now include a "Creating Events Programmatically" section with write-scope validation, dry-run workflow, and a copy-paste project reminder example.
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
  - GitHub PAT authentication working with a non-production operator account.
  - GitHub activity scanner runs correctly; no recent activity in last 14 days (most recent events: Aug 2025).
  - Vault title scanner discovered **36 project candidates** spanning active work, templates, scratchpads, and admin notes.
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
