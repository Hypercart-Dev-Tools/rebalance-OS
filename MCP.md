# rebalance OS — MCP.md

> Canonical reference for the rebalance MCP server: layer roles, live and planned tool surface, server configuration, and host adapter setup.

- For project execution decisions and onboarding sequence, see [PROJECT.md](./PROJECT.md).
- For marketing overview, see [README.md](./README.md).

---

## Layer Roles

```
Host / Client Adapter          Any MCP-enabled app that calls server tools
         ↕  JSON-RPC (stdio)
MCP Server (rebalance)         Tool interfaces + business logic over local data
         ↕
SQLite / filesystem / GitHub API / gcalcli
         ↕  (optional, future)
Local Inference Runtime        mlx-embeddings (Qwen3) for embed queries; Ollama/LM Studio for synthesis
```

| Layer | What it is | Examples |
|---|---|---|
| **MCP Server** | This project. Exposes named tools over JSON-RPC. No LLM logic inside. | `src/rebalance/mcp_server.py` |
| **Host / Client Adapter** | The app that brokers tool calls on behalf of the user's model session. Thin config — no custom code required. | Claude Desktop, Cursor, VS Code Copilot, Continue, Windsurf |
| **Local Inference Runtime** | On-device model runtime invoked by the server for embedding queries and optional synthesis. | mlx-embeddings (Qwen3-Embedding), Ollama, LM Studio |

The MCP server speaks standard JSON-RPC — no host-specific logic inside it. Any MCP-compatible client works without modification.

---

## Server Configuration

### Entry point

```bash
python -m rebalance.mcp_server
```

The server is launched by the host adapter as a subprocess — not run directly by the user during normal operation.

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `REBALANCE_DB` | `rebalance.db` (cwd) | Absolute path to the SQLite database. Always set this explicitly in adapter configs. |

### Transport

`stdio` (default via FastMCP). The host adapter launches the process and communicates over stdin/stdout.

---

## Live Tool Surface

### `list_projects`

Returns projects from the `project_registry` table.

| Param | Type | Default | Description |
|---|---|---|---|
| `status` | `str` | `"active"` | Filter by status: `active`, `potential`, `archived`, or `""` for all |

**Returns:** `list[{name, status, summary, value_level, priority_tier, risk_level, repos}]`

---

### `github_balance`

Shows GitHub commit/PR/issue activity per project over a rolling window.

**Prerequisite:** run `rebalance github-scan` via CLI first to populate the `github_activity` table. See [PROJECT.md — Step 6](./PROJECT.md) for setup.

| Param | Type | Default | Description |
|---|---|---|---|
| `since_days` | `int` | `30` | Rolling window in calendar days |

**Returns:** `list[{project_name, repos_linked, repos_touched, total_commits, prs_opened, prs_merged, issues_opened, last_active_at, is_idle}]`

---

### `ask`

General-purpose natural language query across all data sources. Gathers context from vault embeddings, GitHub activity, project registry, calendar events, and recent vault modifications. Optionally synthesizes a first-pass answer via a local Qwen3 LLM.

| Param | Type | Default | Description |
|---|---|---|---|
| `query` | `str` | *(required)* | Natural language question |
| `since_days` | `int` | `7` | Rolling window for GitHub and vault activity |
| `skip_synthesis` | `bool` | `false` | Return raw context only (faster, no model load) |

**Returns:** `{query, synthesis, vault_context, github_context, github_semantic_context, project_context, vault_activity, calendar_context, temporal_context, model_used, elapsed_seconds}`

---

### `query_notes`

Semantic search over chunked vault notes via sqlite-vec embeddings.

| Param | Type | Default | Description |
|---|---|---|---|
| `query` | `str` | *(required)* | Search query |
| `top_k` | `int` | `10` | Number of results |

**Returns:** List of matching chunks with similarity scores.

---

### `query_github_context`

Semantic search over the local GitHub artifact corpus after sync + embed.

| Param | Type | Default | Description |
|---|---|---|---|
| `query` | `str` | *(required)* | Search query |
| `repo_full_name` | `str` | `""` | Optional repo filter in `owner/name` form |
| `top_k` | `int` | `8` | Number of results |

**Returns:** List of matching GitHub issue / PR / comment / commit documents with similarity scores and structured metadata.

---

### `github_release_readiness`

Explicit current-state inference over the local GitHub corpus for a repo and optional milestone.

| Param | Type | Default | Description |
|---|---|---|---|
| `repo_full_name` | `str` | *(required)* | Repo in `owner/name` form |
| `milestone_title` | `str` | `""` | Optional milestone title. When blank, the tool picks the most urgent open milestone with work. |

**Returns:** `{repo_full_name, milestone_title, milestone_due_on, status, confidence, summary, blockers, evidence, counts, release_branch, release_branch_exists, promotion_pr, deployment_issue, recent_release, issue_states}`

---

### `github_close_candidates`

Suggests open issues that likely map to merged PRs and may be ready to close.

| Param | Type | Default | Description |
|---|---|---|---|
| `repo_full_name` | `str` | *(required)* | Repo in `owner/name` form |

**Returns:** `{repo_full_name, generated_at, summary, counts, high_confidence, medium_confidence, unmatched_open_issues}`

Each recommendation includes the candidate issue number, PR number, confidence, recommendation type, and evidence explaining why the pair was matched.

---

### `search_vault`

Exact keyword search over the indexed vault keywords table.

| Param | Type | Default | Description |
|---|---|---|---|
| `keyword` | `str` | *(required)* | Exact keyword to search |
| `limit` | `int` | `20` | Maximum number of ranked matches |

**Returns:** `list[{file_path, title, heading, body_preview, keyword_score, char_count, tags}]`

---

### `create_calendar_event`

Creates a Google Calendar event using the device-local OAuth token.

| Param | Type | Default | Description |
|---|---|---|---|
| `summary` | `str` | *(required)* | Event title |
| `start_time` | `str` | *(required)* | ISO datetime with timezone offset |
| `end_time` | `str` | *(required)* | ISO datetime with timezone offset |
| `description` | `str` | `""` | Optional body text |
| `location` | `str` | `""` | Optional location |
| `attendees` | `list[str] \| None` | `None` | Optional attendee email list |
| `calendar_id` | `str` | `config.calendar_id` when blank | Calendar to write into |
| `timezone_name` | `str` | `""` | Optional IANA timezone name for the payload |

**Returns:** `{event_id, html_link, calendar_id, summary, start_time, end_time, attendees_count, status}`

**Prerequisite:** authorize the device with write scope:

```bash
python scripts/setup_calendar_oauth.py --write-access --test
```

**Recommended operator path:** use the repo CLI for non-MCP clients:

```bash
rebalance calendar-create-event \
  --title "Planning review" \
  --date 2026-04-21 \
  --calendar-id primary \
  --dry-run
```

Duplicate/idempotency controls on the CLI:

- `--skip-if-exists` searches the target calendar for the same title + same start date and exits successfully without writing if found
- `--dedupe-key <key>` uses the local structured event log to short-circuit repeat runs from the same machine
- `--output json` returns machine-readable status values such as `created`, `skipped_existing`, `blocked_duplicate`, and `idempotency_hit`

Duplicate-guard limits:

- editing the title after the first create defeats the title + start-date lookup
- overlapping multi-day events are not treated as duplicates unless the same title also starts on the same date
- for repeated operator retries of the same logical event, prefer `--dedupe-key`

Structured operator log:

- `temp/logs/calendar-event-create.jsonl` records created IDs, duplicate blocks, and skip outcomes for reconciliation
- the log is local-only under `temp/`, gitignored, and can be rotated manually when it grows

For the full operator workflow, dry-run behavior, and a copy-paste worked example, see [GOOGLE_CALENDAR.md — Creating Events Programmatically](./GOOGLE_CALENDAR.md#creating-events-programmatically).

**Trade-off:** the MCP tool remains the canonical transport for registered MCP hosts, but the CLI is the cleaner path for local terminal sessions and external AI tools that do not have the rebalance server registered. The CLI calls the same underlying `create_calendar_event(...)` implementation and keeps the same write-scope guardrails while avoiding raw JSON-RPC boilerplate.

---

## Live Tool Surface — Calendar Review And Maintenance

### `review_timesheet`

Returns unclassified calendar events that need review for a given day.

| Param | Type | Default | Description |
|---|---|---|---|
| `date_str` | `str` | `""` | ISO date (`YYYY-MM-DD`). Blank means today. |

**Returns:** `{date, needs_review, available_projects}` where each `needs_review` item includes `{summary, start_time, end_time, duration_minutes}`.

---

### `classify_event`

Persists a classification decision for an unmatched calendar event so future reports stop asking the same question.

| Param | Type | Default | Description |
|---|---|---|---|
| `summary` | `str` | *(required)* | Exact event title from Google Calendar |
| `decision` | `str` | *(required)* | `include`, `exclude`, or `project:<Name>` |

**Returns:** `{summary, decision, status}` on success or `{error}` on invalid decisions.

---

### `snap_calendar_edges`

Detects and optionally fixes slight overlaps between adjacent timed calendar events by trimming Event 1's end to one minute before Event 2's start.

| Param | Type | Default | Description |
|---|---|---|---|
| `date_str` | `str` | `""` | Start date (`YYYY-MM-DD`). Blank means today in the calendar timezone. |
| `days` | `int` | `1` | Number of consecutive days to process |
| `calendar_id` | `str` | `""` | Override config calendar |
| `timezone_name` | `str` | `""` | Override config timezone |
| `apply` | `bool` | `false` | Dry-run by default. Set true to patch Google Calendar. |

**Returns:** `{days, total_snapped, total_skipped_clusters, applied, elapsed_seconds}`. Each day includes snapped pairs, skipped clusters, skipped all-day count, and total events examined.

---

### `sleuth_sync_reminders`

Pulls Slack reminders from the Sleuth Web API and mirrors them into SQLite.

| Param | Type | Default | Description |
|---|---|---|---|
| `active_only` | `bool` | `false` | When true, fetch only currently active reminders |

**Returns:** `{workspace_name, fetched_at, total_reminder_count, returned_reminder_count, inserted_count, updated_count, unchanged_count}`.

---

## Live Tool Surface — Onboarding

These tools move onboarding out of the CLI and into any MCP-capable host, so an agent can drive the setup flow conversationally. See [PROJECT.md — Onboarding User Story](./PROJECT.md) for the sequence and UX rationale.

| Tool | Description | Params | Returns | Depends on |
|---|---|---|---|---|
| `onboarding_status` | Returns completion state of each onboarding step | `vault_path: str` | `{steps: [{name, complete, detail}]}` | Config module, filesystem (checks registry/sync artifacts at vault_path), SQLite DB path resolved from `REBALANCE_DB` env var (same as all other server tools) |
| `setup_github_token` | Accepts a GitHub PAT, validates against `/user`, stores in config | `token: str` | `{valid, login, scopes}` | Config module, GitHub API |
| `run_preflight` | Discovers project candidates from vault titles + GitHub activity (read-only, no registry writes) | `vault_path: str` | `{most_likely_active_projects, semi_active_projects, dormant_projects, potential_projects}` — each a list of candidate objects | GitHub scanner, vault file scan |
| `confirm_projects` | Accepts curated project list with metadata, writes canonical registry, runs `pull` sync | `projects: list[{name, summary, repos, priority_tier, tags}]`, `vault_path: str` | `{registry_path, project_count, sync_ok}` | Registry sync |

Design principle: the MCP server stays stateless and host-agnostic. Onboarding logic lives in tools, not in host-specific code. Any MCP client — VS Code, Claude Desktop, Cursor, and others — drives the same sequence by calling these tools.

---

## Planned Tool Surface

| Tool | Description | Depends on |
|---|---|---|
| `weekly_rebalance` | Weekly verdict-first report across active projects with `verdict`, `evidence`, `next_move`, target share, actual share, and confidence | Attention ledger, project targets, calendar classification, git-pulse rollups, GitHub activity, reminders |
| `project_attention` | Single-project drilldown showing attention sources, target gap, pressure, progress, and recommended next move | Attention ledger, project registry, GitHub activity, calendar classification |
| `review_unattributed_attention` | Returns low-confidence or unattributed attention items that need human classification before the weekly report is trusted | Attention ledger, classification feedback store |
| `classify_attention_item` | Persists include, exclude, or reassign decisions for ambiguous attention items across all sources | Classification feedback store |
| `todays_agenda` | Today's calendar events (dedicated tool) | Google Calendar sync |
| `morning_brief` | Assembled daily briefing from all sources | All of the above |

The narrower operator path should be weekly-rebalance-first. Broad retrieval tools such as `ask`, `query_notes`, and `query_github_context` remain useful for exploration, but they should explain or drill into a verdict rather than act as the primary dashboard surface.

---

## Host Adapter Setup

Adapters are thin config files — no custom code. Each host reads the config and launches `python -m rebalance.mcp_server` as a subprocess over stdio.

> **Always set `REBALANCE_DB` to the absolute path of your SQLite database.** Relative paths will break when the host adapter launches the server from a different working directory.

---

### Claude Desktop

#### Step-by-step manual setup

1. **Open the config file.**
   Menu bar: **Claude → Settings → Developer → Edit Config**.
   This opens `~/Library/Application Support/Claude/claude_desktop_config.json`.
   If the file is empty or missing, start with `{}`.

2. **Add the rebalance server.** Paste the following into the file (adjust paths to match your machine):

   ```json
   {
     "mcpServers": {
       "rebalance": {
         "command": "/absolute/path/to/rebalance-OS/.venv/bin/python",
         "args": ["-m", "rebalance.mcp_server"],
         "env": {
           "REBALANCE_DB": "/absolute/path/to/rebalance-OS/rebalance.db"
         }
       }
     }
   }
   ```

   > **Important:** Use absolute paths for both `command` and `REBALANCE_DB`. Claude Desktop launches the server from its own working directory, so relative paths will not resolve.

   If you already have other MCP servers configured, add `"rebalance": { ... }` inside the existing `"mcpServers"` object — don't replace the whole file.

3. **Restart Claude Desktop.** Quit and reopen the app. The rebalance tools should appear in the tool picker (hammer icon) when starting a new conversation.

4. **Verify.** In a new conversation, ask:
   *"What should I work on today?"*
   Claude should call the `ask` tool and return your project context, GitHub activity, and calendar events.

#### Troubleshooting

| Symptom | Fix |
|---|---|
| Server not listed in tool picker | Check that the JSON is valid (no trailing commas). Restart Claude Desktop. |
| "command not found" or "No module named rebalance" | Ensure `command` points to the venv Python, not the system Python. Run the path in Terminal to verify. |
| Empty results from `ask` | Run `rebalance ingest notes` and `rebalance ingest embed` first to populate the database. |

---

### Cursor

Config file: `~/.cursor/mcp.json` (global) or `.cursor/mcp.json` (project-scoped, recommended)

```json
{
  "mcpServers": {
    "rebalance": {
      "command": "python",
      "args": ["-m", "rebalance.mcp_server"],
      "env": {
        "REBALANCE_DB": "/Users/you/path/to/rebalance.db"
      }
    }
  }
}
```

---

### VS Code (GitHub Copilot / MCP extension)

Config via workspace `.vscode/mcp.json` (recommended for beta) or user settings under `mcp.servers`:

```json
{
  "servers": {
    "rebalance": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "rebalance.mcp_server"],
      "env": {
        "REBALANCE_DB": "/Users/you/path/to/rebalance.db"
      }
    }
  }
}
```

**Beta plan:** a `.vscode/mcp.json` will be checked into the repo so beta users get the server registered automatically on workspace open. The config will use `${workspaceFolder}/rebalance.db` if VS Code supports variable expansion, otherwise the README will instruct users to set the absolute path.

---

### Continue (VS Code / JetBrains)

In `~/.continue/config.json` under `"mcpServers"`:

```json
{
  "mcpServers": [
    {
      "name": "rebalance",
      "command": "python",
      "args": ["-m", "rebalance.mcp_server"],
      "env": {
        "REBALANCE_DB": "/Users/you/path/to/rebalance.db"
      }
    }
  ]
}
```

---

## Server Registry

A human-readable reference for all running MCP servers on this machine. Store at `~/bin/servers.md` or equivalent. Useful when debugging which server is registered in which host adapter.

```
rebalance   python -m rebalance.mcp_server   REBALANCE_DB=/absolute/path/to/rebalance.db
```

Live tools: `ask`, `list_projects`, `github_balance`, `query_notes`, `query_github_context`, `github_release_readiness`, `github_close_candidates`, `search_vault`, `create_calendar_event`, `review_timesheet`, `classify_event`, `snap_calendar_edges`, `sleuth_sync_reminders`, `onboarding_status`, `setup_github_token`, `run_preflight`, `confirm_projects`
Planned: `weekly_rebalance`, `project_attention`, `review_unattributed_attention`, `classify_attention_item`, `todays_agenda`, `morning_brief`

---

## License

Copyright 2025 Hypercart DBA Neochrome, Inc.

Licensed under the **Apache License, Version 2.0**. See [APACHE-LICENSE-2.0.txt](./APACHE-LICENSE-2.0.txt) or https://www.apache.org/licenses/LICENSE-2.0.
