# rebalance OS

## Project Overview

This project builds a local RAG (Retrieval-Augmented Generation) pipeline that ingests your Obsidian Markdown vault into SQLite, adds Qwen embeddings for semantic search, and enables querying via a local Qwen LLM runtime. It extends to GitHub activity scanning via Personal Access Token (PAT) to detect over-investment in specific projects by comparing commit activity, PRs, and issues across repos. It also integrates Google Calendar via `gcalcli` to surface today's meetings as part of a unified morning briefing.

The goal is a unified "second brain" that surfaces notes, tracks progress, flags project imbalances, and delivers a structured daily briefing assembled automatically each morning and readable via any MCP-capable host.

Execution source of truth: this `PROJECT.md` file. `README.md` is marketing-facing and synced to execution reality on a weekly cadence.

## Assumptions

- **Obsidian Vault**: Local folder with clean MD files; frontmatter, headings, tags, and links are well-structured for parsing. Vault size <10k notes to keep embedding feasible on macOS hardware.
- **Local Setup**: macOS with `mlx-embeddings` (local fork at `WP-DB-Toolkit/mlx-embeddings`) for Qwen3 embeddings via Apple Silicon MLX; optional Ollama/LM Studio for local LLM synthesis; Python 3.12+ with sqlite-vec extension; GitHub PAT with repo:read scope.
- **GitHub Usage**: 5-6 active repos; PAT stored securely (e.g., keychain or env var); activity tracked via API (commits, PRs, issues last 30-90 days).
- **Google Calendar**: `gcalcli` installed and OAuth2-authenticated; today's agenda pulled via CLI subprocess call.
- **Project Registry Source**: A canonical Markdown registry file in the Obsidian vault (for example, `Projects/00-project-registry.md`) is human-editable source of truth for project metadata.
- **Project Projection**: `projects.yaml` and `project_registry` SQLite table are machine projections produced by ingest sync from the Markdown registry.
- **Data Quality**: "Garbage in, garbage out" — assumes curated notes with consistent tagging (e.g., `#project-ai-ddtk`) and a maintained `projects.yaml`.
- **Performance**: Single-user, offline-first; no multi-tenancy yet; embeddings batched to avoid OOM on M-series chips.
- **Scope**: MVP focuses on ingestion, embedding, basic query, GitHub delta analysis, calendar integration, and daily briefing output. No real-time sync initially.
- **Embedding Standardization**: If OpenAI embeddings are already in use for a parallel pgvector project (e.g., LTVera), strongly consider standardizing on one embedding model across both to avoid model drift and double overhead on the Mac Studio. Decide before building the embedder step.

## Architecture

```
Projects/00-project-registry.md (canonical, editable)
  ↓  ingest sync (pull/push/check)
projects.yaml + project_registry projection
  ↓
Obsidian Vault (.md files)    ← recursive scan/parse/chunk
    ↓
SQLite DB:
  - files, chunks, keywords, links, embeddings (sqlite-vec)
  - github_activity (commits, time_spent proxy via commit count/PR velocity)
  - project_registry (from canonical registry projection)
    ↓
morning_brief.py (scheduler, runs daily at set time)
  ├── gcalcli agenda today         → today's meetings + locations + attendees
  ├── github_scan.py               → repo balance, over-investment flags
  └── rebalance query              → relevant notes, project status
    ↓
Daily Briefing MD (written to vault/Daily Notes/YYYY-MM-DD.md)
    ↓
Any MCP host/agent (reads via local tool calls/filesystem access)
```

### Runtime Orchestration

```
Any IDE/agent workflow          -> builds rebalance package
Scheduler (macOS-first)         -> launchd on macOS, Task Scheduler on Windows, cron on Linux
Any MCP-capable host/agent      -> reads briefing + calls MCP tools conversationally
Local LLM runtime (optional)    -> Ollama or LM Studio for on-device inference
```

Build can happen in any IDE or coding agent. Daily use happens through any MCP-capable host that can call local tools. The briefing script runs on schedule regardless of whether an MCP host is open.

### MCP Layer Clarification

See **[MCP.md](./MCP.md)** — canonical SOT for layer roles, live and planned tool surface, server configuration, and all host adapter configs (Claude Desktop, Cursor, VS Code, Continue).

### Project Registry Model

- **Canonical file (human-editable)**: `Projects/00-project-registry.md` inside the vault.
- **Machine projections**: `projects.yaml` + `project_registry` table in SQLite.
- **Sync modes**:
  - `pull`: Markdown registry -> normalized projections (`projects.yaml`, SQLite)
  - `push`: projection updates -> Markdown registry (computed fields block only)
  - `check`: dry-run diff, no writes

Conflict policy:
- Descriptive fields (name, summary, tags, strategy notes): Markdown wins.
- Computed fields (weights, attention %, last activity): projection wins and is written into a dedicated computed block.

## Key Features

- **Project Registry**: Canonical in-vault Markdown registry for transparency and instant editability, synced into `projects.yaml` + SQLite projections.
- **Note Ingestion**: Recursive scan; chunk by headings; extract keywords/tags deterministically.
- **Semantic Query**: Embed queries; top-K retrieval; LLM synthesis.
- **GitHub Integration**: Daily scan via PAT; compute metrics (commits/repo, streak, velocity); flag if >40% activity in one repo — weighted by project priority tier from seed.
- **Calendar Integration**: `gcalcli agenda today tomorrow` pulled each morning; meeting titles, times, locations, and attendees included in briefing context.
- **Morning Briefing**: Single assembled MD file written to `vault/Daily Notes/YYYY-MM-DD.md`; includes calendar, GitHub balance, and RAG-surfaced project notes.
- **Alerts**: "Over-investing in AI-DDTK (Tier 3 exploratory): 65% of commits this week."
- **CLI Interface**: `rebalance query "WP vector plugin status"` or `rebalance github-balance`.
- **Registry Preflight**: Detect candidate projects from current vault page titles, let user remove false positives, then collect short summaries and custom fields before promotion into active projects.

## Preflight Candidate Workflow

Preflight mode is part of ingest and runs before first full seed sync.

1. Scan vault page titles and build a `Potential Projects` candidate list.
2. Present candidates for keep/remove review.
3. For each kept candidate, require:
   - 2-3 sentence summary
   - baseline custom fields (quantitative + qualitative)
4. Promote approved candidates to active projects in the canonical Markdown registry.
5. Run `pull` sync to materialize `projects.yaml` and SQLite `project_registry`.

Suggested custom fields:
- Quantitative: `priority_tier`, `value_score`, `risk_score`, `weekly_hours_target`, `confidence_score`
- Qualitative: `strategic_reason`, `failure_mode`, `momentum_state`, `stakeholder_context`, `notes_quality`

Store custom fields under `custom_fields.quantitative` and `custom_fields.qualitative` for extensibility.

## Project Registry Schema

`Projects/00-project-registry.md` in the vault is the canonical registry and prior-knowledge layer. `projects.yaml` is a projection used by pipelines and tooling.

Example canonical Markdown section:

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
potential_projects: []
archived_projects: []
```

`projects.yaml` projection shape:

```yaml
projects:
  - name: LTVera
    summary: 2-3 sentence summary in plain text
    status: active
    value_level: strategic          # revenue-generating | strategic | exploratory | maintenance
    priority_tier: 1                # 1-5, maps to your existing task prioritization framework
    risk_level: high                # low | medium | high
    repos:
      - ltv-era
    obsidian_folder: Projects/LTVera
    tags:
      - "#project-ltv-era"
    custom_fields:
      quantitative:
        value_score: 9
        weekly_hours_target: 8
      qualitative:
        momentum_state: warm

  - name: WP Canary
    description: WooCommerce health monitoring SaaS
    status: active
    value_level: revenue-generating
    priority_tier: 1
    risk_level: medium
    repos:
      - wp-canary
    obsidian_folder: Projects/WPCanary
    tags:
      - "#project-wp-canary"

  - name: AI-DDTK
    description: AI-driven developer toolkit
    status: active
    value_level: exploratory
    priority_tier: 3
    risk_level: low
    repos:
      - ai-ddtk
    obsidian_folder: Projects/AIDDTK
    tags:
      - "#project-ai-ddtk"

  # Add remaining projects following same schema
```

**Fields reference:**

| Field | Values | Purpose |
|-------|--------|---------|
| `value_level` | revenue-generating, strategic, exploratory, maintenance | Weights retrieval and alert severity |
| `priority_tier` | 1–5 (your existing framework) | GitHub imbalance context ("over-investing in Tier 3 vs Tier 1") |
| `risk_level` | low, medium, high | Surfaces in briefing when high-risk projects have low recent activity |
| `custom_fields.quantitative` | numeric and target metrics | Enables quantified seeding and scoring |
| `custom_fields.qualitative` | strategic and contextual text fields | Captures intent and judgment not inferable from metrics |

## Morning Briefing Script

`morning_brief.py` is a single Python script run by a scheduler each morning. It assembles a structured MD file in your vault's Daily Notes folder. Any MCP host can read this on demand via local filesystem access and/or tool calls.

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

**launchd plist** (preferred on macOS):
```xml
<!-- ~/Library/LaunchAgents/com.rebalance-os.morning-brief.plist -->
<key>StartCalendarInterval</key>
<dict>
  <key>Hour</key><integer>7</integer>
  <key>Minute</key><integer>0</integer>
</dict>
```

**Cross-platform fallback:**
- macOS: launchd (default)
- Windows: Task Scheduler
- Linux: cron

## Implementation Steps

Build order is sequenced for independent testability — each step works standalone before the next depends on it.

### Phase 1: Build (Any IDE / Coding Agent)

1. **Setup (1 day)**
  - Install deps: `sqlite-vec`, `ollama` + Qwen3-Embedding, `requests`, `keyring`, `gcalcli`, `pyyaml`, `typer`, `pydantic`, `questionary`
   - Create DB schema including `project_registry` table
   - Scaffold `rebalance/` package structure
   - Keep this file in repo root and treat it as execution source of truth

  - Implement `pull`, `push`, and `check` sync commands
  - Materialize `projects.yaml` projection
  - This table is referenced by the GitHub scanner and briefing assembler

3. **Project Registry Preflight (0.5 days)**
  - Scan vault page titles to build `Potential Projects`
  - Interactive keep/remove pass
  - Prompt for required summary and custom fields
  - Promote approved candidates into canonical Markdown registry

4. **Note Ingester (2 days)** — *Highest value, lowest risk — pure file I/O, no models needed.*
   - Python script to parse MD (frontmatter, wikilinks); chunk by headings
   - Keyword frequency via TF-IDF; insert to SQLite
   - Prototype: `python ingest.py /path/to/vault`

5. **Embedder (1 day)**
   - Batch Qwen3 embeddings; store in vector column
   - Hash-based delta updates to avoid re-embedding unchanged notes
   - ⚠️ Decide embedding model (Qwen3 vs. OpenAI) before this step

6. **GitHub Scanner (2 days)**
   - API calls for repos/activity; proxy "time spent" via commit count + PR velocity
   - Store in `github_activity` table; join with `project_registry` for weighted imbalance scores
   - PAT via `keyring`; rotate quarterly

7. **Calendar Integration (0.5 days)**
   - Install and OAuth2-authenticate `gcalcli`: `pip install gcalcli && gcalcli list`
   - Test: `gcalcli agenda today tomorrow --details all`
   - Wire subprocess call into `morning_brief.py`

8. **Querier (2 days)**
   - Embed input → ANN search → prompt Qwen LLM with context + GitHub metrics
   - CLI: `rebalance query "..."` and `rebalance github-balance`

9. **Morning Briefing Assembler (1 day)**
   - `morning_brief.py` pulls calendar + GitHub + RAG; writes Daily Notes MD
   - launchd plist for 7am daily run
   - Add manual trigger alias for on-demand runs: `alias brief='python -m rebalance.morning_brief'`

### Phase 2: Daily Use (Any MCP Host + Local Tools)

Once built, your MCP host becomes the conversational interface to the already-assembled output:

- **Morning**: Open MCP host → "Summarize my day" → reads today's briefing MD
- **Ad hoc queries**: "What did I decide about the LTVera embedding pipeline?"
- **Balance check**: "Am I over-investing anywhere this week?"
- **Meeting prep**: "What Obsidian notes are relevant to my 10am call?"

## Tech Stack

| Component | Tool/Library | Why |
|-----------|--------------|-----|
| MD Parsing | `frontmatter`, `markdown-it-py` | Handles Obsidian specifics (wikilinks, embeds) |
| Project Registry | `Projects/00-project-registry.md` + PyYAML | Human-editable canonical source + machine projection |
| CLI | `typer`, `questionary` | Interactive ingest, preflight review, and sync flows |
| DB | SQLite + `sqlite-vec` | Local, fast vector search, no server |
| Embeddings | `mlx-embeddings` (local fork, Qwen3-Embedding-4bit, Apple Silicon MLX) | Field-tested on WP-DB-Toolkit; same model already in use; avoids Ollama dependency for embeddings |
| LLM runtime | Ollama or LM Studio | Local model serving for on-device inference |
| GitHub API | `requests` + PAT | Simple activity aggregation |
| Calendar | `gcalcli` + Google Calendar API | Mature Python CLI; OAuth2; TSV output for easy parsing |
| Chunking/Keywords | NLTK/spaCy (light) | Deterministic pass for frequency analysis |
| PAT/Secret Storage | Plaintext JSON in `temp/rbos.config` (gitignored, MVP) | Local-only, low-risk scope (read-only repo). Upgrade to `keyring` when multi-user or sharing vault. See Secrets Strategy below. |
| Scheduler | launchd (macOS), Task Scheduler (Windows), cron (Linux) | macOS-first with practical cross-platform fallback |

## Secrets Strategy

**Phase 0 (MVP) — Plaintext in gitignored config file**

- Config stored at `temp/rbos.config` (JSON, plaintext)
- Directory (`temp/`) is listed in `.gitignore` — never committed
- Suitable for single-user, local-only use
- PAT scope: read-only repos (`repo:read`), so compromise impact is low
- CLI commands for management:
  - `rebalance config set-github-token <PAT>` — store PAT
  - `rebalance config get-github-token` — check config (masked output)
  - `rebalance config show-config-path` — show location

**Phase 1+ (if multi-user or compliance required)**

- Upgrade to `keyring` library (native OS credential storage)
- `config.py` already has the abstraction in place; just swap the backend
- `keyring` uses: Keychain (macOS), Credential Manager (Windows), Pass (Linux)

**Why not env vars?** They're visible in `ps` output and shell history. Plaintext file (gitignored) is safer for MVP because it's not in memory/history, and we upgrade later anyway.

**Why not encrypted?** Encryption key has to live somewhere — usually env var or keyring. Simpler to just use keyring directly for Phase 1.

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| `temp/rbos.config` exposure | Never commit (gitignored). Rotate PAT if exposed. Keyring upgrade in Phase 1. |
| Embed drift between model versions | Store model version in DB; re-embed on version change |
| Large vault OOM on embedding | Chunk aggressively; lazy/batched embedding |
| Over-investment false positives | Weight by `priority_tier` from canonical registry/projection |
| Dual embedding model overhead | Standardize on one model before building embedder |
| Registry drift between Markdown and projection | Enforce sync modes (`pull`, `push`, `check`) and run `check` in daily workflow |
| gcalcli OAuth token expiry | Token refresh is automatic; re-auth needed only after long gaps |
| Briefing runs while machine is asleep | launchd handles missed runs on wake; fallback schedulers may need explicit catch-up logic |

## License

Copyright 2025 Hypercart DBA Neochrome, Inc.

Licensed under the **Apache License, Version 2.0**. You may use, reproduce, modify, and distribute this software and its documentation under the terms of the Apache 2.0 License. Attribution is required — any redistribution must retain the above copyright notice. See [APACHE-LICENSE-2.0.txt](./APACHE-LICENSE-2.0.txt) or https://www.apache.org/licenses/LICENSE-2.0.

## Next Actions

- [ ] Create canonical registry `Projects/00-project-registry.md` in vault
- [x] Implement ingest sync modes: `pull`, `push`, `check`
- [x] Implement GitHub activity discovery + preflight integration (repo candidates, activity scores)
- [x] Config system for GitHub PAT (plaintext in gitignored temp/rbos.config, MVP)
- [ ] **Next:** Test GitHub preflight discovery with user PAT
- [ ] Run preflight to populate `Potential Projects` from vault titles + GitHub repos
- [ ] Promote curated candidates into active projects and materialize `projects.yaml`
- [x] Scaffold package structure in your IDE/agent workflow of choice
- [x] Implement `rebalance github-scan` CLI — PAT auth, events pagination, per-repo aggregation, SQLite persistence
- [x] Implement `github_balance(since_days)` MCP tool — joins `project_registry.repos` with `github_activity`
- [ ] Install and authenticate `gcalcli`: `pip install gcalcli && gcalcli list`
- [ ] Install deps and smoke test: `pip install -e .` → `rebalance ingest sync --mode check --vault ...`
- [ ] Prototype note ingester: `python ingest.py /path/to/vault`
- [ ] Decide: Qwen3-Embedding or OpenAI embeddings (align with LTVera if applicable)
- [ ] Wire `morning_brief.py` + launchd plist
- [ ] Wire MCP host of choice to vault and Daily Notes tooling/access
- [ ] Query examples:
  - `"Summarize my day"`
  - `"Am I over-investing in any Tier 3 projects this week?"`
  - `"What's the status of the WP vector plugin?"`
  - `"What Obsidian notes are relevant to my 10am call?"`
