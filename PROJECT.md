# rebalance OS

## Project Overview

This project builds a local RAG (Retrieval-Augmented Generation) pipeline that ingests your Obsidian Markdown vault into SQLite, adds Qwen embeddings for semantic search, and enables querying via a local Qwen LLM. It extends to GitHub activity scanning via Personal Access Token (PAT) to detect over-investment in specific projects by comparing commit activity, PRs, and issues across repos. It also integrates Google Calendar via `gcalcli` to surface today's meetings as part of a unified morning briefing.

The goal is a unified "second brain" that surfaces notes, tracks progress, flags project imbalances, and delivers a structured daily briefing — assembled automatically each morning and readable via Claude Desktop.

## Assumptions

- **Obsidian Vault**: Local folder with clean MD files; frontmatter, headings, tags, and links are well-structured for parsing. Vault size <10k notes to keep embedding feasible on macOS hardware.
- **Local Setup**: macOS with MLX/Ollama for Qwen3-Embedding and Qwen LLM (e.g., Qwen3-7B); Python 3.12+ with sqlite-vec extension; GitHub PAT with repo:read scope.
- **GitHub Usage**: 5-6 active repos; PAT stored securely (e.g., keychain or env var); activity tracked via API (commits, PRs, issues last 30-90 days).
- **Google Calendar**: `gcalcli` installed and OAuth2-authenticated; today's agenda pulled via CLI subprocess call.
- **Project Seed**: A `projects.yaml` in the vault root defines all active projects with name, value level, priority tier, risk level, related repos, and Obsidian folder paths. This is the first thing ingested and carries highest retrieval weight.
- **Data Quality**: "Garbage in, garbage out" — assumes curated notes with consistent tagging (e.g., `#project-ai-ddtk`) and a maintained `projects.yaml`.
- **Performance**: Single-user, offline-first; no multi-tenancy yet; embeddings batched to avoid OOM on M-series chips.
- **Scope**: MVP focuses on ingestion, embedding, basic query, GitHub delta analysis, calendar integration, and daily briefing output. No real-time sync initially.
- **Embedding Standardization**: If OpenAI embeddings are already in use for a parallel pgvector project (e.g., LTVera), strongly consider standardizing on one embedding model across both to avoid model drift and double overhead on the Mac Studio. Decide before building the embedder step.

## Architecture

```
projects.yaml (seed)          ← ingested first, highest retrieval weight
Obsidian Vault (.md files)    ← recursive scan/parse/chunk
    ↓
SQLite DB:
  - files, chunks, keywords, links, embeddings (sqlite-vec)
  - github_activity (commits, time_spent proxy via commit count/PR velocity)
  - project_registry (from projects.yaml seed)
    ↓
morning_brief.py (launchd, runs daily at set time)
  ├── gcalcli agenda today         → today's meetings + locations + attendees
  ├── github_scan.py               → repo balance, over-investment flags
  └── obsidian_rag query           → relevant notes, project status
    ↓
Daily Briefing MD (written to vault/Daily Notes/YYYY-MM-DD.md)
    ↓
Claude Desktop (reads via filesystem MCP, on demand)
```

### Runtime Orchestration

```
Claude Code (VS Code)     →  builds obsidian_rag/ package
launchd (macOS, daily)    →  runs morning_brief.py at set time
Claude Desktop + MCP      →  reads briefing MD and answers queries conversationally
```

Claude Code in VS Code handles **building**. Claude Desktop handles **daily use** — it reads the already-assembled briefing and answers queries against the SQLite DB via filesystem MCP. It does not run the briefing script itself; the script runs on schedule whether Claude Desktop is open or not.

## Key Features

- **Project Registry**: Seed file (`projects.yaml`) defines all projects with value, priority, risk, and repo mappings. Ingested first; used to weight retrieval and contextualize GitHub imbalance alerts.
- **Note Ingestion**: Recursive scan; chunk by headings; extract keywords/tags deterministically.
- **Semantic Query**: Embed queries; top-K retrieval; LLM synthesis.
- **GitHub Integration**: Daily scan via PAT; compute metrics (commits/repo, streak, velocity); flag if >40% activity in one repo — weighted by project priority tier from seed.
- **Calendar Integration**: `gcalcli agenda today tomorrow` pulled each morning; meeting titles, times, locations, and attendees included in briefing context.
- **Morning Briefing**: Single assembled MD file written to `vault/Daily Notes/YYYY-MM-DD.md`; includes calendar, GitHub balance, and RAG-surfaced project notes.
- **Alerts**: "Over-investing in AI-DDTK (Tier 3 exploratory): 65% of commits this week."
- **CLI Interface**: `rebalance OS query "WP vector plugin status"` or `rebalance OS github-balance`.

## Project Seed Schema

`projects.yaml` lives in the vault root and is the first file ingested. It is the prior knowledge layer — without it, the system cannot weight retrieval or interpret GitHub imbalance meaningfully.

```yaml
projects:
  - name: LTVera
    description: Post-purchase decision engine using WooCommerce behavioral priors
    status: active
    value_level: strategic          # revenue-generating | strategic | exploratory | maintenance
    priority_tier: 1                # 1-5, maps to your existing task prioritization framework
    risk_level: high                # low | medium | high
    repos:
      - ltv-era
    obsidian_folder: Projects/LTVera
    tags:
      - "#project-ltv-era"

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

## Morning Briefing Script

`morning_brief.py` is a single Python script run by launchd each morning. It assembles a structured MD file in your vault's Daily Notes folder. Claude Desktop reads this on demand via filesystem MCP — no real-time dependency on Claude Desktop being open.

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
    # queries SQLite via obsidian_rag, returns top project notes
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

**launchd plist** (preferred over cron on macOS):
```xml
<!-- ~/Library/LaunchAgents/com.rebalance OS.morning-brief.plist -->
<key>StartCalendarInterval</key>
<dict>
  <key>Hour</key><integer>7</integer>
  <key>Minute</key><integer>0</integer>
</dict>
```

## Implementation Steps

Build order is sequenced for independent testability — each step works standalone before the next depends on it.

### Phase 1: Build (Claude Code / VS Code Agent)

1. **Setup (1 day)**
   - Install deps: `sqlite-vec`, `ollama` + Qwen3-Embedding, `requests`, `keyring`, `gcalcli`, `pyyaml`
   - Create DB schema including `project_registry` table
   - Scaffold `obsidian_rag/` package structure
   - Copy this file to repo root as `AGENTS.md` so Claude Code uses it as ground truth

2. **Project Seed Ingester (0.5 days)** — *Do this before any other ingestion.*
   - Parse `projects.yaml`; populate `project_registry` table
   - Draft `projects.yaml` with all active projects before writing any code
   - This table is referenced by the GitHub scanner and briefing assembler

3. **Note Ingester (2 days)** — *Highest value, lowest risk — pure file I/O, no models needed.*
   - Python script to parse MD (frontmatter, wikilinks); chunk by headings
   - Keyword frequency via TF-IDF; insert to SQLite
   - Prototype: `python ingest.py /path/to/vault`

4. **Embedder (1 day)**
   - Batch Qwen3 embeddings; store in vector column
   - Hash-based delta updates to avoid re-embedding unchanged notes
   - ⚠️ Decide embedding model (Qwen3 vs. OpenAI) before this step

5. **GitHub Scanner (2 days)**
   - API calls for repos/activity; proxy "time spent" via commit count + PR velocity
   - Store in `github_activity` table; join with `project_registry` for weighted imbalance scores
   - PAT via `keyring`; rotate quarterly

6. **Calendar Integration (0.5 days)**
   - Install and OAuth2-authenticate `gcalcli`: `pip install gcalcli && gcalcli list`
   - Test: `gcalcli agenda today tomorrow --details all`
   - Wire subprocess call into `morning_brief.py`

7. **Querier (2 days)**
   - Embed input → ANN search → prompt Qwen LLM with context + GitHub metrics
   - CLI: `rebalance OS query "..."` and `rebalance OS github-balance`

8. **Morning Briefing Assembler (1 day)**
   - `morning_brief.py` pulls calendar + GitHub + RAG; writes Daily Notes MD
   - launchd plist for 7am daily run
   - Add manual trigger alias for on-demand runs: `alias brief='python ~/obsidian_rag/morning_brief.py'`
   - Wire Claude Desktop filesystem MCP to vault and Daily Notes folder

### Phase 2: Daily Use (Claude Desktop + MCP)

Once built, Claude Desktop becomes the conversational interface to the already-assembled output:

- **Morning**: Open Claude Desktop → "Summarize my day" → reads today's briefing MD
- **Ad hoc queries**: "What did I decide about the LTVera embedding pipeline?"
- **Balance check**: "Am I over-investing anywhere this week?"
- **Meeting prep**: "What Obsidian notes are relevant to my 10am call?"

## Tech Stack

| Component | Tool/Library | Why |
|-----------|--------------|-----|
| MD Parsing | `frontmatter`, `markdown-it-py` | Handles Obsidian specifics (wikilinks, embeds) |
| Project Seed | `projects.yaml` + PyYAML | Structured prior knowledge; human-editable |
| DB | SQLite + `sqlite-vec` | Local, fast vector search, no server |
| Embeddings | Qwen3-Embedding (Ollama/MLX) | High-quality, local, macOS-optimized |
| LLM | Qwen3-7B (Ollama) | Matches embedding model; strong reasoning |
| GitHub API | `requests` + PAT | Simple activity aggregation |
| Calendar | `gcalcli` + Google Calendar API | Mature Python CLI; OAuth2; TSV output for easy parsing |
| Chunking/Keywords | NLTK/spaCy (light) | Deterministic pass for frequency analysis |
| PAT/Secret Storage | `keyring` | Secure; avoids env var exposure |
| Scheduler | launchd (macOS) | Preferred over cron on macOS; reliable wake/missed-run handling |

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Embed drift between model versions | Store model version in DB; re-embed on version change |
| Large vault OOM on embedding | Chunk aggressively; lazy/batched embedding |
| PAT exposure | Use `keyring`; rotate quarterly |
| Over-investment false positives | Weight by `priority_tier` from `projects.yaml` seed |
| Dual embedding model overhead | Standardize on one model before building embedder |
| Stale project seed | Review `projects.yaml` monthly; treat as a living document |
| gcalcli OAuth token expiry | Token refresh is automatic; re-auth needed only after long gaps |
| Briefing runs while machine is asleep | launchd handles missed runs on wake; manual alias as fallback |

## License

Copyright 2025 Hypercart DBA Neochrome, Inc.

Licensed under the **Apache License, Version 2.0**. You may use, reproduce, modify, and distribute this software and its documentation under the terms of the Apache 2.0 License. Attribution is required — any redistribution must retain the above copyright notice. See [LICENSE](./LICENSE) or https://www.apache.org/licenses/LICENSE-2.0.

## Next Actions

- [ ] Draft `projects.yaml` with all active projects (name, value, priority, risk, repos) — **do this first**
- [ ] Create `obsidian_rag/` repo; copy this file to root as `AGENTS.md`
- [ ] Scaffold package structure with Claude Code
- [ ] Install and authenticate `gcalcli`: `pip install gcalcli && gcalcli list`
- [ ] Prototype seed ingester: `python ingest_seed.py projects.yaml`
- [ ] Prototype note ingester: `python ingest.py /path/to/vault`
- [ ] Decide: Qwen3-Embedding or OpenAI embeddings (align with LTVera if applicable)
- [ ] Test GitHub scan on active repos (AI-DDTK, etc.)
- [ ] Wire `morning_brief.py` + launchd plist
- [ ] Wire Claude Desktop filesystem MCP to vault and Daily Notes folder
- [ ] Query examples:
  - `"Summarize my day"`
  - `"Am I over-investing in any Tier 3 projects this week?"`
  - `"What's the status of the WP vector plugin?"`
  - `"What Obsidian notes are relevant to my 10am call?"`
