Please follow instructions from AGENTS.md

## MCP Onboarding — Agent Instructions

This project is an MCP server. When a user opens this workspace, you have access to rebalance MCP tools via `.vscode/mcp.json`.

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

4. **Confirm:** Call `confirm_projects(projects, vault_path)` with the curated list. Each project dict should include at minimum: `name`, `summary`, `repos` (list of strings), `priority_tier` (int), `tags` (list of strings).

5. **Verify:** Call `list_projects()` to confirm projects are queryable. Show the user a summary.

6. **Optional — GitHub activity scan:** Suggest the user run this in the terminal:
   ```
   rebalance github-scan --token <PAT> --database <path-to-rebalance.db>
   ```
   After that, `github_balance()` will show per-project commit/PR/issue counts.

### Available MCP tools

| Tool | Purpose |
|------|---------|
| `onboarding_status(vault_path)` | Check which setup steps are complete |
| `setup_github_token(token)` | Validate and store a GitHub PAT |
| `run_preflight(vault_path)` | Discover project candidates (read-only) |
| `confirm_projects(projects, vault_path)` | Write registry and sync to DB |
| `list_projects(status?)` | Query projects (default: active) |
| `github_balance(since_days?)` | GitHub activity per project (requires prior `github-scan`) |

### Key paths

- Registry: `{vault_path}/Projects/00-project-registry.md`
- Config: `temp/rbos.config` (gitignored, repo root)
- Database: resolved from `REBALANCE_DB` env var (set in `.vscode/mcp.json`)
- Architecture docs: `PROJECT.md`, `MCP.md`
