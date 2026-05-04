Please follow instructions from AGENTS.md

## MCP Onboarding — Agent Instructions

This project is an MCP server. When a user opens this workspace, you have access to rebalance MCP tools via `.vscode/mcp.json`.

**Do not scan the repo for `rebalance ...` CLI scripts.** Every refresh and query path is exposed through MCP tools below — reach for those first.

### Single-entry-point tools (use these first)

For "what data is available?" or "is the index fresh?" call `index_status()`. For "refresh the local DB" call `refresh_index(scope=[...], dry_run=True)` to preview the plan, then re-call without `dry_run` to execute. For "search across vault + GitHub in one ranked list" call `semantic_query(query, sources=["vault","github"])`.

### On first interaction

Call `onboarding_status` with the user's vault path to check setup state. If any steps are incomplete, walk the user through them in order (see flow below).

If you don't know the vault path, ask: "Where is your Obsidian vault? (absolute path)"

### Onboarding flow

Drive this sequence using MCP tool calls:

1. **Check state:** `onboarding_status(vault_path)` — shows which steps are done/pending.

2. **GitHub PAT:** If `github_token_set` is false, ask the user for a GitHub Personal Access Token with `repo:read` scope. Then call `setup_github_token(token)`. If it returns `valid: false`, ask for a corrected token.

3. **Discover projects:** Call `run_preflight(vault_path)`. Present the results conversationally using friendly labels:
   - "Most active" = `most_likely_active_projects` (GitHub activity last 14 days)
   - "Semi-active" = `semi_active_projects` (15-30 days)
   - "Dormant" = `dormant_projects` (31+ days)
   - "Vault only" = `potential_projects` (notes with no GitHub signal)
   - If `github_error` is set, inform the user that GitHub discovery failed and only vault candidates are shown.
   - Ask the user which to keep, remove, or merge. For each kept project, collect: short summary (2-3 sentences) and priority tier (1-5). Tags and repos are optional.

4. **Confirm:** Call `confirm_projects(projects, vault_path)` with the curated list. Each project dict **must** include `status: "active"` so it lands in `active_projects` and syncs to SQLite (projects without this status are routed to activity-based segments which are not yet projected to the DB). Full minimum shape: `{name, status: "active", summary, repos: [], priority_tier: int, tags: []}`.

5. **Verify:** Call `list_projects()` to confirm projects are queryable. Show the user a summary.

6. **Initial data refresh:** Call `refresh_index(scope=["all"])` to populate the SQLite knowledge base. Use `dry_run=True` first if you want a preview. After it completes, `index_status()` will show the resulting freshness, and `github_balance()` will return per-project commit/PR/issue counts.

### Available MCP tools

**Single entry points (prefer these):**

| Tool | Purpose |
|------|---------|
| `index_status()` | Snapshot of all sources + unified semantic index, with drift indicators |
| `refresh_index(scope, vault_path?, since_days?, repos?, dry_run?)` | Orchestrated refresh: vault / github / calendar / sleuth / semantic / all |
| `semantic_query(query, sources?, top_k?)` | Vector search across the unified semantic index (vault + github) |
| `list_watched_repos(since_days?)` | Show which repos are being monitored (project registry ∪ recent activity − ignored). Use this to debug "is X being synced?" |
| `publish_pulse(dry_run?, push?)` | Render today's + yesterday's activity to markdown and push to a private pulse repo. Each row is tagged by source (`claude-cloud` / `codex-cloud` / `lovable` / `local-vscode` / `human`) via `agent_tags.classify`. Uses `temp/rbos.config` keys: `github_login`, `slack_user_id`, `pulse_target_path`, `pulse_filename`, `pulse_timezone` |

**Onboarding & projects:**

| Tool | Purpose |
|------|---------|
| `onboarding_status(vault_path)` | Check which setup steps are complete |
| `setup_github_token(token)` | Validate and store a GitHub PAT |
| `run_preflight(vault_path)` | Discover project candidates (read-only) |
| `confirm_projects(projects, vault_path)` | Write registry and sync to DB |
| `list_projects(status?)` | Query projects (default: active) |
| `github_balance(since_days?)` | GitHub activity per project (requires prior refresh) |

**Targeted retrieval (older, per-source):**

| Tool | Purpose |
|------|---------|
| `query_notes(query, top_k?)` | Vault-only vector search (legacy `embeddings` table) |
| `search_vault(keyword, limit?)` | Full-text/keyword search over vault |
| `query_github_context(query, repo?, top_k?)` | GitHub-only vector search (legacy `github_embeddings`) |
| `ask(query, since_days?, skip_synthesis?)` | Combined context + optional local LLM synthesis |
| `github_release_readiness(repo, milestone?)` | Milestone readiness inferred from local corpus |
| `github_close_candidates(repo)` | Issues likely closed by merged PRs |

### Key paths

- Registry: `{vault_path}/Projects/00-project-registry.md`
- Config: `temp/rbos.config` (gitignored, repo root)
- Database: resolved from `REBALANCE_DB` env var (set in `.vscode/mcp.json`)
- Architecture docs: `PROJECT.md`, `MCP.md`

## Agent rulebooks (read before editing generated docs)

Some generated artifacts in this repo ship with placeholder prose that any agent
(Claude Code, Codex, Copilot, Gemini) is expected to fill in. Each has an
authoritative rulebook that should be read first.

| Artifact | Rulebook | Notes |
|---|---|---|
| Git Pulse Executive Recap (`reports/YYYY-MM-*.md`) | [experimental/git-pulse/EXEC-SUMMARY.md](experimental/git-pulse/EXEC-SUMMARY.md) | Claude Code skill `git-pulse-exec-recap` via `.claude/skills/` |
| Git Pulse Team Recap (`team-reports/YYYY-MM-*.md`) | [experimental/git-pulse/TEAM-EXEC-SUMMARY.md](experimental/git-pulse/TEAM-EXEC-SUMMARY.md) | Claude Code skill `git-pulse-team-recap` via `.claude/skills/` |

The generated recap itself carries the same pointer in its top-of-file
instructions block, so agents that open the file directly will also find the
rulebook without needing this index.
