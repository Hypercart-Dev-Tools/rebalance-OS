# Changelog

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
