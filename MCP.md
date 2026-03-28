# rebalance MCP — Source of Truth

This file is the canonical reference for the rebalance MCP server: layer roles, live tool surface, planned tools, server configuration, and host adapter setup.

- For project execution decisions, see [PROJECT.md](./PROJECT.md).
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

Or if installed via `pip install -e .`:

```bash
# server is invoked by the host adapter; not run directly by the user
```

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `REBALANCE_DB` | `rebalance.db` (cwd) | Absolute or relative path to the SQLite database |

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

Shows GitHub commit/PR/issue activity per project over a rolling window. Requires a prior `rebalance github-scan` run to populate the `github_activity` table.

| Param | Type | Default | Description |
|---|---|---|---|
| `since_days` | `int` | `14` | Rolling window in calendar days |

**Returns:** `list[{project_name, repos_linked, repos_touched, total_commits, prs_opened, prs_merged, issues_opened, last_active_at, is_idle}]`

---

## Planned Tool Surface

| Tool | Description | Depends on |
|---|---|---|
| `query_notes` | Semantic search over chunked vault notes via sqlite-vec | Note ingester + embedder |
| `search_vault` | Full-text keyword search over vault files | Note ingester |
| `todays_agenda` | Today's calendar events via `gcalcli` | gcalcli integration |
| `morning_brief` | Assembled daily briefing from all sources | All of the above |

---

## Host Adapter Setup

Adapters are thin config files — no custom code. Each host reads the config and launches `python -m rebalance.mcp_server` as a subprocess over stdio.

> Set `REBALANCE_DB` to the **absolute path** of your SQLite database in every adapter config below.

---

### Claude Desktop

Config file: `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "rebalance": {
      "command": "python",
      "args": ["-m", "rebalance.mcp_server"],
      "env": {
        "REBALANCE_DB": "/Users/noelsaw/Documents/Obsidian Vault/rebalance.db"
      }
    }
  }
}
```

If using a virtualenv, replace `"python"` with the full path to the venv interpreter, e.g. `"/Users/noelsaw/.venv/rebalance/bin/python"`.

---

### Cursor

Config file: `~/.cursor/mcp.json` (global) or `.cursor/mcp.json` (project-scoped)

```json
{
  "mcpServers": {
    "rebalance": {
      "command": "python",
      "args": ["-m", "rebalance.mcp_server"],
      "env": {
        "REBALANCE_DB": "/Users/noelsaw/Documents/Obsidian Vault/rebalance.db"
      }
    }
  }
}
```

---

### VS Code (GitHub Copilot / MCP extension)

Config via workspace `.vscode/mcp.json` or user settings under `mcp.servers`:

```json
{
  "servers": {
    "rebalance": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "rebalance.mcp_server"],
      "env": {
        "REBALANCE_DB": "/Users/noelsaw/Documents/Obsidian Vault/rebalance.db"
      }
    }
  }
}
```

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
        "REBALANCE_DB": "/Users/noelsaw/Documents/Obsidian Vault/rebalance.db"
      }
    }
  ]
}
```

---

## Server Registry

Entry in `~/bin/servers.md`:

```
rebalance   python -m rebalance.mcp_server   REBALANCE_DB=/path/to/rebalance.db
```

Tools: `list_projects`, `github_balance` (live) · `query_notes`, `search_vault`, `todays_agenda`, `morning_brief` (planned)
