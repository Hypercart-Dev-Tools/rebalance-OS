# rebalance OS — PROJECT.md

> Execution source of truth. `README.md` is marketing-facing and synced to this on a weekly cadence.

---

## Project Overview

rebalance is a local-first morning briefing engine and project intelligence layer. It ingests your Obsidian Markdown vault into SQLite, adds semantic embeddings for knowledge retrieval, scans GitHub activity to detect project over-investment, and pulls your Google Calendar to assemble a structured daily briefing — readable via any MCP-capable host or agent.

The goal: a unified workday OS that surfaces what matters, flags imbalances, and delivers a structured briefing each morning — all running locally, all on your data.

**MCP layer:** see [MCP.md](./MCP.md) — canonical SOT for tool surface, server config, and host adapter setup.

---

## User Tiers

### Beta (v1.0) — Technical users onboarding via IDE

The current onboarding sequence and all implementation steps below target **technical beta testers** entering through VS Code (or another MCP-capable IDE) with direct access to the codebase, CLI, and config files. The goal for this tier is to validate the onboarding flow, the project registry model, and the morning briefing pipeline with minimum friction and maximum signal.

Complexity that doesn't serve beta validation is explicitly deferred.

### General release (v1.1+) — Desktop app users

Future users entering through Claude Desktop, ChatGPT desktop, or other consumer MCP hosts will need a guided setup UI, installer, and simplified config experience. Onboarding for this tier is out of scope until the beta flow is proven.

All decisions that create divergence between tiers should be flagged explicitly in this document.

---

## Assumptions

- **Obsidian Vault**: Local folder with clean MD files; frontmatter, headings, tags, and links are well-structured for parsing. Vault size <10k notes to keep embedding feasible on macOS hardware.
- **Local Setup**: macOS with `mlx-embeddings` (local fork at `WP-DB-Toolkit/mlx-embeddings`) for Qwen3 embeddings via Apple Silicon MLX; optional Ollama/LM Studio for local LLM synthesis; Python 3.12+ with sqlite-vec extension; GitHub PAT with repo:read scope.
- **GitHub Usage**: 5-6 active repos; PAT stored securely in gitignored config (see Secrets Strategy); activity tracked via API (commits, PRs, issues last 30-90 days).
- **Google Calendar**: `gcalcli` installed and OAuth2-authenticated; today's agenda pulled via CLI subprocess call.
- **Project Registry Source**: `Projects/00-project-registry.md` in the Obsidian vault is the human-editable source of truth for project metadata.
- **Machine Projections**: `projects.yaml` and `project_registry` SQLite table are projections produced by ingest sync from the Markdown registry — never edited directly.
- **Data Quality**: "Garbage in, garbage out" — assumes curated notes with consistent tagging (e.g. `#project-ai-ddtk`) and a maintained registry.
- **Performance**: Single-user, offline-first; no multi-tenancy; embeddings batched to avoid OOM on M-series chips.
- **Scope**: MVP targets ingestion, embedding, GitHub delta analysis, calendar integration, and daily briefing output. No real-time sync.
- **Embedding Standardization**: If OpenAI embeddings are in use for a parallel pgvector project (e.g. LTVera), standardize on one embedding model before building the embedder to avoid model drift and double overhead on the Mac Studio.

---

## Architecture

```
Projects/00-project-registry.md  ← canonical, human-editable
  ↓  ingest sync (pull / push / check)
projects.yaml + project_registry SQLite table  ← machine projections

Obsidian Vault (.md files)  ← recursive scan / parse / chunk
  ↓
SQLite DB:
  - files, chunks, keywords, links, embeddings (sqlite-vec)
  - github_activity (commits, PRs, issues — structured)
  - github_embed_queue (PR/issue bodies >100 chars — embedded, phase 2)
  - project_registry (projected from canonical registry)
  ↓
morning_brief.py  (runs daily via scheduler)
  ├── gcalcli agenda today tomorrow   → meetings, locations, attendees
  ├── github_scan.py                  → repo balance, over-investment flags
  └── rebalance query                 → relevant notes, project status
  ↓
Daily Briefing MD → vault/Daily Notes/YYYY-MM-DD.md
  ↓
Any MCP host / agent  (reads via filesystem access + tool calls)
```

### Runtime Orchestration

```
VS Code + coding agent (beta)     →  builds rebalance package, runs CLI
Any MCP-capable host/agent        →  reads briefing + calls MCP tools
Scheduler (launchd / cron)        →  runs morning_brief.py daily at 7am
Local LLM runtime (optional)      →  Ollama or LM Studio for on-device synthesis
```

---

## GitHub Activity — Storage and Embedding Strategy

### What gets stored (SQLite, structured)

All GitHub activity is persisted to `github_activity` in normalized form: commit counts, PR metadata, issue metadata, velocity, repo-to-project joins. This structured layer is the primary signal source for balance analysis and briefing alerts.

### What gets embedded (phase 2, selective)

Raw commit messages are low-signal ("fix bug", "WIP", "update deps") and are **not** embedded. PR descriptions and issue bodies are semantically richer and worth embedding — but only selectively.

**Embedding criteria for `github_embed_queue`:**
- Body length > 100 characters
- Exclude automated messages (Dependabot, bots, merge commits)
- PR descriptions and issue bodies only — no commit messages

This keeps the vector space clean and avoids competing with high-quality Obsidian notes. Implement after the core embedder is validated — this is a phase 2 addition.

### Why not embed everything

Sparse, short GitHub text creates noisy embeddings that degrade retrieval quality for the questions rebalance actually answers. Structured counts + velocity metrics outperform embeddings for "am I over-investing?" The selective approach gives you semantic search on the meaningful GitHub content without poisoning the vault embeddings.

---

## Onboarding User Story — Beta (v1.0)

**Entry point:** VS Code with a MCP-capable coding assistant (Claude Code, Augment, Continue, or similar).

**Goal for beta:** validate the onboarding flow, project registry bootstrap, and morning briefing pipeline with minimum friction. Signal over noise at every step.

**Key design decision:** onboarding is driven by MCP tools, not by CLI prompts or host-specific logic. The MCP server exposes four onboarding tools — any agent (VS Code, desktop app, or future host) calls them in sequence. This keeps the server stateless and host-agnostic, and means the transition from VS Code to desktop apps requires zero server changes.

Tool specifications (params, return shapes, dependencies): see [MCP.md — Planned Tool Surface — Onboarding](./MCP.md).

### Onboarding sequence

The host agent (not the server) drives this flow by calling MCP tools:

1. **Check state** — Agent calls `onboarding_status`. If all steps complete, skip onboarding. If any step is incomplete, agent walks the user through remaining steps in order.

2. **GitHub PAT** (first because it's the fastest high-signal bootstrap):
   - Agent asks user for a PAT with `repo:read` scope.
   - Agent calls `setup_github_token` with the PAT.
   - Tool validates against GitHub `/user` endpoint, confirms minimum scope, stores in `temp/rbos.config` (gitignored, repo root — see Secrets Strategy).
   - If validation fails: tool returns error detail, agent prompts replacement.

3. **Project discovery:**
   - Agent calls `run_preflight` with the vault path.
   - Tool scans GitHub activity and vault note titles, returns candidates in four segments (names match `Registry` model in code):
     - `most_likely_active_projects`: GitHub activity in last 14 days
     - `semi_active_projects`: activity 15–30 days ago
     - `dormant_projects`: activity 31+ days ago
     - `potential_projects`: vault notes with no GitHub signal
   - Agent presents candidates conversationally with friendly labels. User removes false positives, merges duplicates.

4. **Metadata capture and registry write:**
   - For each retained candidate, agent collects: 2–3 sentence summary, repos, priority tier, tags. Full custom fields are optional — capture on a second pass. Keep this step fast: more fields = more abandonment.
   - Agent calls `confirm_projects` with the curated list.
   - Tool writes canonical registry to `Projects/00-project-registry.md`, runs `pull` sync to materialize `projects.yaml` and SQLite `project_registry`, creates missing vault folders (`Projects/`, `Daily Notes/`) if needed.

5. **Smoke test:**
   - Agent calls `list_projects` to confirm the registry round-tripped into SQLite.
   - Agent calls `onboarding_status` to display complete vs pending checklist.
   - Note: `github_balance` requires a separate `rebalance github-scan` run (it reads from `github_activity`, not the registry). The agent can prompt the user to run this after onboarding completes, but it is not part of the onboarding loop itself.

6. **Optional: Google Calendar setup:**
   - Offer gcalcli OAuth2 setup after registry bootstrap is confirmed working.
   - Not before — calendar is lower priority than project registry for beta validation.

**Resumability:** `onboarding_status(vault_path)` is the resumability mechanism. It checks: config file exists, GitHub token present and valid, registry file exists at vault_path, `projects.yaml` and SQLite projections are in sync (DB path resolved from `REBALANCE_DB` env var, same as all server tools). Each tool call advances state independently. If the user stops mid-flow, the next `onboarding_status` call tells the agent exactly where to resume.

**CLI escape hatch:** `rebalance ingest preflight` and `rebalance config set-github-token` remain available for power users who prefer terminal workflows.

**Refactor note:** the current `run_preflight()` function is monolithic — it discovers, prompts via `questionary`, writes the registry, and returns only counts. The MCP tools require a split: `run_preflight` (read-only, returns candidates) and `confirm_projects` (write-only, persists registry). Step 3 below includes this refactor. After the split, both CLI and MCP tools call the same discover/confirm functions.

**Beta scope note:** naming convention alignment (repo names → vault project names), full custom field capture, and UI polish are deferred to v1.1. Beta testers are technical enough to handle minor rough edges.

---

## Project Registry Model

### Canonical file (human-editable)
`Projects/00-project-registry.md` inside the vault. Descriptive fields (name, summary, tags, strategy notes) are always edited here. This file wins on conflict for all descriptive fields.

### Machine projections
`projects.yaml` and `project_registry` SQLite table. Computed fields (weights, attention %, last activity) are written back into a dedicated computed block in the Markdown file. Never edit projections directly.

### Sync modes
- `pull`: Markdown registry → normalized projections (`projects.yaml`, SQLite)
- `push`: computed fields → Markdown registry computed block only
- `check`: dry-run diff, no writes — run this in the daily workflow

---

## Project Registry Schema

Example canonical Markdown section (`Projects/00-project-registry.md`):

```yaml
active_projects:
  - name: LTVera
    status: active
    summary: >
      2-3 sentence project summary goes here.
    repos: [ltv-era]
    obsidian_folder: Projects/LTVera
    tags: ["#project-ltv-era"]
    custom_fields:
      quantitative:
        priority_tier: 1
        value_score: 9
        risk_score: 7
        weekly_hours_target: 8
        confidence_score: 6
      qualitative:
        strategic_reason: "Core revenue and retention upside"
        failure_mode: "Model quality under sparse order histories"
        momentum_state: "warm"
        stakeholder_context: "Used in client strategy updates"
        notes_quality: "high"
    computed:
      attention_percent_7d: 0
      last_activity_at: null

most_likely_active_projects: []
semi_active_projects: []
dormant_projects: []
potential_projects: []
archived_projects: []
```

Note: `most_likely_active_projects`, `semi_active_projects`, `dormant_projects`, and `potential_projects` are top-level registry sections — not nested inside individual project entries.

`projects.yaml` projection shape:

```yaml
projects:
  - name: LTVera
    summary: 2-3 sentence summary in plain text
    status: active
    value_level: strategic
    priority_tier: 1
    risk_level: high
    repos: [ltv-era]
    obsidian_folder: Projects/LTVera
    tags: ["#project-ltv-era"]
    custom_fields:
      quantitative:
        value_score: 9
        weekly_hours_target: 8
      qualitative:
        momentum_state: warm

  - name: WP Canary
    status: active
    value_level: revenue-generating
    priority_tier: 1
    risk_level: medium
    repos: [wp-canary]
    obsidian_folder: Projects/WPCanary
    tags: ["#project-wp-canary"]

  - name: AI-DDTK
    status: active
    value_level: exploratory
    priority_tier: 3
    risk_level: low
    repos: [ai-ddtk]
    obsidian_folder: Projects/AIDDTK
    tags: ["#project-ai-ddtk"]
```

**Fields reference:**

| Field | Values | Purpose |
|---|---|---|
| `value_level` | revenue-generating, strategic, exploratory, maintenance | Weights retrieval and alert severity |
| `priority_tier` | 1–5 | GitHub imbalance context ("over-investing in Tier 3 vs Tier 1") |
| `risk_level` | low, medium, high | Surfaces in briefing when high-risk projects have low recent activity |
| `custom_fields.quantitative` | numeric and target metrics | Quantified seeding and scoring |
| `custom_fields.qualitative` | strategic and contextual text | Captures intent not inferable from metrics |

---

## Morning Briefing Script

`morning_brief.py` runs on schedule and writes a structured MD file to `vault/Daily Notes/YYYY-MM-DD.md`. Any MCP host reads this on demand via filesystem access or tool calls.

```python
# morning_brief.py — simplified sketch
import subprocess
from datetime import date
from pathlib import Path

VAULT_PATH = Path("/path/to/your/vault")
BRIEFING_PATH = VAULT_PATH / "Daily Notes" / f"{date.today()}.md"

def get_calendar():
    result = subprocess.run(
        ["gcalcli", "agenda", "today", "tomorrow",
         "--details", "location", "--details", "attendees", "--tsv"],
        capture_output=True, text=True
    )
    return result.stdout

def get_github_balance():
    # calls github_scan.py, returns formatted string
    ...

def get_rag_summary():
    # queries SQLite via rebalance, returns top project notes
    ...

def write_briefing():
    content = f"""# Daily Briefing — {date.today()}

## Calendar
{get_calendar()}

## GitHub Balance
{get_github_balance()}

## Project Notes
{get_rag_summary()}
"""
    BRIEFING_PATH.write_text(content)

if __name__ == "__main__":
    write_briefing()
```

**Scheduler setup:**

```xml
<!-- ~/Library/LaunchAgents/com.rebalance-os.morning-brief.plist -->
<key>StartCalendarInterval</key>
<dict>
  <key>Hour</key><integer>7</integer>
  <key>Minute</key><integer>0</integer>
</dict>
```

Cross-platform fallback: launchd (macOS default), Task Scheduler (Windows), cron (Linux). launchd handles missed runs on wake — other schedulers may need explicit catch-up logic.

Manual trigger alias: `alias brief='python -m rebalance.morning_brief'`

---

## Implementation Steps

Build order is sequenced for independent testability — each step works standalone before the next depends on it. Steps are sized for a beta tester validating as they go.

### Phase 1: Build (VS Code + coding agent, beta)

**Step 1 — Environment setup (1 day)**
- Install deps: `sqlite-vec`, `mlx-embeddings`, `requests`, `keyring`, `gcalcli`, `pyyaml`, `typer`, `pydantic`, `questionary`
- Create DB schema including `project_registry`, `github_activity`, and `github_embed_queue` tables
- Scaffold `rebalance/` package structure
- Treat this file (`PROJECT.md`) as execution source of truth throughout

**Step 2 — Project Registry sync (1 day)**
- Implement `pull`, `push`, and `check` sync commands
- Materialize `projects.yaml` projection from canonical Markdown registry
- `project_registry` table is the join target for GitHub scanner and briefing assembler
- Smoke test: `rebalance ingest sync --mode check --vault /path/to/vault`

**Step 3 — Onboarding MCP tools (1.5 days)**
- **Refactor `run_preflight()`**: split the current monolithic function into two layers:
  - `discover_candidates(vault_path, registry_path, github_token?)` — pure, read-only, returns segmented candidates (`most_likely_active_projects`, `semi_active_projects`, `dormant_projects`, `potential_projects`)
  - `confirm_and_write(projects, vault_path, registry_path)` — write-only, persists registry and runs `pull` sync
  - CLI `rebalance ingest preflight` re-wired to call discover → questionary prompts → confirm
- Implement four MCP tools — see [MCP.md — Onboarding tools](./MCP.md) for param/return specs:
  - `onboarding_status(vault_path)` — checks config, token, registry, sync artifacts
  - `setup_github_token(token)` — validates against `/user`, stores in config
  - `run_preflight(vault_path)` — calls `discover_candidates`, returns structured candidates
  - `confirm_projects(projects, vault_path)` — calls `confirm_and_write`, returns sync result
- Ship `.vscode/mcp.json` in repo for beta workspace setup

**Step 4 — Note ingester (2 days)**
*Highest value, lowest risk — pure file I/O, no models needed.*
- Parse MD (frontmatter, wikilinks); chunk by headings
- Keyword frequency via TF-IDF; insert to SQLite
- Hash-based delta updates for re-ingest efficiency
- Prototype: `python ingest.py /path/to/vault`

**Step 5 — Embedder (1 day)**
- Batch Qwen3 embeddings via `mlx-embeddings`; store in sqlite-vec vector column
- Hash-based delta updates to skip unchanged notes
- ⚠️ Decide embedding model (Qwen3 vs OpenAI) before this step — align with LTVera if applicable

**Step 6 — GitHub scanner (2 days)**
- Paginated REST API calls for commits, PRs, issues
- Proxy "time spent" via commit count + PR velocity
- Store structured data in `github_activity` table
- Join with `project_registry.repos` for weighted imbalance scores
- PAT from `temp/rbos.config` via config module; rotate quarterly
- CLI: `rebalance github-scan`

**Step 7 — Calendar integration (0.5 days)**
- Install and OAuth2-authenticate gcalcli: `pip install gcalcli && gcalcli list`
- Smoke test: `gcalcli agenda today tomorrow --details all`
- Wire subprocess call into `morning_brief.py`

**Step 8 — Querier (2 days)**
- Embed input → ANN search via sqlite-vec → prompt local LLM with context + GitHub metrics
- CLI: `rebalance query "..."` and `rebalance github-balance`

**Step 9 — Morning briefing assembler (1 day)**
- `morning_brief.py` pulls calendar + GitHub balance + RAG summary
- Writes to `vault/Daily Notes/YYYY-MM-DD.md`
- launchd plist for 7am daily run
- Manual alias: `alias brief='python -m rebalance.morning_brief'`

**Step 10 — GitHub embed queue (phase 2, after core embedder validated)**
- Filter PR descriptions and issue bodies (>100 chars, no bots/automation)
- Embed and store in `github_embed_queue` table
- Merge into query retrieval pipeline alongside vault embeddings

### Phase 2: Daily use (any MCP host)

Once built, the MCP host becomes the conversational interface to the assembled output:

- **Morning**: "Summarize my day" → reads today's briefing MD
- **Ad hoc**: "What did I decide about the LTVera embedding pipeline?"
- **Balance check**: "Am I over-investing anywhere this week?"
- **Meeting prep**: "What Obsidian notes are relevant to my 10am call?"

---

## Tech Stack

| Component | Tool/Library | Why |
|---|---|---|
| MD Parsing | `frontmatter`, `markdown-it-py` | Handles Obsidian specifics (wikilinks, embeds) |
| Project Registry | `Projects/00-project-registry.md` + PyYAML | Human-editable canonical source + machine projection |
| CLI | `typer`, `questionary` | Interactive ingest, preflight review, and sync flows |
| DB | SQLite + `sqlite-vec` | Local, fast vector search, no server |
| Embeddings | `mlx-embeddings` (Qwen3-Embedding, Apple Silicon MLX) | Field-tested on WP-DB-Toolkit; avoids Ollama dependency for embeddings |
| LLM runtime | Ollama or LM Studio | Local model serving for on-device synthesis |
| GitHub API | `requests` + PAT | Simple activity aggregation |
| Calendar | `gcalcli` + Google Calendar API | Mature Python CLI; OAuth2; TSV output for easy parsing |
| Chunking/Keywords | NLTK/spaCy (light) | Deterministic keyword frequency pass |
| Secret storage | Plaintext JSON in `temp/rbos.config` (gitignored, repo root) | MVP: local-only, low-risk read-only PAT. Upgrade to `keyring` post-beta. |
| Scheduler | launchd (macOS), Task Scheduler (Windows), cron (Linux) | macOS-first with cross-platform fallback |

---

## Secrets Strategy

**Phase 0 (beta MVP) — Plaintext in gitignored config**

- Config stored at `temp/rbos.config` (JSON, plaintext) relative to **repo root** — not vault root. These are separate locations; do not conflate them.
- `temp/` is listed in `.gitignore` — never committed
- PAT scope is read-only (`repo:read`), so exposure impact is low
- CLI commands:
  - `rebalance config set-github-token <PAT>` — store PAT
  - `rebalance config get-github-token` — check config (masked output)
  - `rebalance config show-config-path` — show absolute path

**Phase 1+ (post-beta, if multi-user or compliance required)**
- Upgrade to `keyring` (native OS credential storage)
- `config.py` abstraction is already in place — swap the backend only
- Keychain (macOS), Credential Manager (Windows), Pass (Linux)

Why not env vars: visible in `ps` output and shell history. Why not encrypted: the encryption key has to live somewhere — usually keyring. Simpler to go straight to keyring in phase 1.

---

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| `temp/rbos.config` exposure | Gitignored. Rotate PAT if exposed. Keyring upgrade post-beta. |
| Embed drift between model versions | Store model version in DB; re-embed on version change |
| Large vault OOM on embedding | Chunk aggressively; lazy/batched embedding |
| Over-investment false positives | Weight imbalance scores by `priority_tier` from registry |
| Dual embedding model overhead | Standardize on one model before building embedder |
| Registry drift between Markdown and projection | Enforce sync modes; run `check` in daily workflow |
| GitHub embed noise degrading retrieval | Selective embedding via `github_embed_queue` filter (phase 2) |
| gcalcli OAuth token expiry | Token refresh is automatic; re-auth only after long gaps |
| Briefing runs while machine is asleep | launchd handles missed runs on wake; other schedulers may need catch-up logic |

---

## License

Copyright 2025 Hypercart DBA Neochrome, Inc.

Licensed under the **Apache License, Version 2.0**. You may use, reproduce, modify, and distribute this software and its documentation under the terms of the Apache 2.0 License. Attribution is required — any redistribution must retain the above copyright notice. See [APACHE-LICENSE-2.0.txt](./APACHE-LICENSE-2.0.txt) or https://www.apache.org/licenses/LICENSE-2.0.

---

## Next Actions

### Done
- [x] Scaffold `rebalance/` package structure
- [x] Implement ingest sync modes: `pull`, `push`, `check`
- [x] Config system for GitHub PAT (`temp/rbos.config`, gitignored, repo root)
- [x] Implement GitHub activity discovery + preflight integration (repo candidates, activity segments)
- [x] Implement `rebalance github-scan` CLI
- [x] Implement `github_balance` MCP tool

### Up next — Onboarding MCP tools (Step 3)
- [ ] Implement `onboarding_status` MCP tool (per-step completion state)
- [ ] Implement `setup_github_token` MCP tool (validate + store PAT)
- [ ] Implement `run_preflight` MCP tool (vault + GitHub discovery, returns candidates)
- [ ] Implement `confirm_projects` MCP tool (write registry, run sync)
- [ ] Ship `.vscode/mcp.json` in repo for beta workspace setup
- [ ] Test full onboarding loop via MCP tools (VS Code agent-driven)

### Remaining — Build phase
- [ ] Create canonical registry `Projects/00-project-registry.md` in vault
- [ ] Smoke test: `pip install -e .` → `rebalance ingest sync --mode check --vault /path/to/vault`
- [ ] Prototype note ingester: `python ingest.py /path/to/vault`
- [ ] Decide: Qwen3-Embedding or OpenAI embeddings (align with LTVera if applicable)
- [ ] Install and authenticate gcalcli: `pip install gcalcli && gcalcli list`
- [ ] Wire `morning_brief.py` + launchd plist
- [ ] Phase 2: implement `github_embed_queue` selective embedding pipeline