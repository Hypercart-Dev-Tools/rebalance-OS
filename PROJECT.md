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

## Signals — Data Sources & Ingest

Tracks all integration sources, their priority, and what data is ingested from each.

| Priority | Source | Status | Vectorized | Why / Why Not |
|---|---|---|---|---|
| P1 | GitHub | ✅ Active | ❌ No (Phase 2) | Structured counts/timestamps — exact matching outperforms semantic search. PR descriptions & issue bodies >100 chars queued for selective embedding in Phase 2. |
| P1 | Obsidian Vault | ✅ Active | ✅ Yes | Long-form prose with implicit meaning — semantic search is the only way to surface relevant context across hundreds of notes. |
| P2 | Google Calendar | ✅ Active | ❌ No | Short structured fields (title, time, attendees). Exact filters on date range and keywords are sufficient; embedding a meeting title adds no retrieval value. |
| P3 | Slack / Sleuth Tasks | 🔜 Planned | TBD | Thread bodies may warrant embedding if long enough; task metadata (status, assignee) is structured. Decision deferred until data shape is known. |
| P4 | Email | 🔜 Planned | TBD | High noise — most emails are not project-relevant. If implemented, would need aggressive filtering *before* embedding to avoid polluting the vector space. |

### Temporal Context — Day-of-Week & Work Schedule

Not a data source but a contextual signal injected into every query. Shapes recommendations: what you *should* work on depends on what kind of day it is.

- **Work days** — Monday through Friday. Default: full project availability, prioritize by tier.
- **Off days** — Saturday and Sunday. Default: no project recommendations unless user explicitly asks.
- **Vacation days** — detected from Google Calendar events with title containing "vacation", "PTO", "OOO", "time off", or "holiday" (case-insensitive). Treated like off days: suppress work recommendations, surface only urgent flags (e.g. Tier 1 neglect).
- **Day-before context** — if tomorrow is a work day, "what should I work on tomorrow?" pulls tomorrow's calendar for meeting prep signals. If tomorrow is an off day or vacation, say so.

Implementation: computed at query time in `querier.py` `_gather_temporal_context()`. No storage — derived from system clock + `calendar_events` table. Injected into prompt as a `## Today` section with day name, work/off/vacation status, and any relevant schedule notes.

### P1 — GitHub

Primary signal for project investment tracking and balance analysis.

- **Issues** — creation events and comments; stored in `github_activity`; bodies >100 chars queued for embedding (phase 2)
- **Commits** — counts and timestamps per repo; velocity proxy for time-spent; commit messages not embedded (low signal)
- **Pull Requests** — open/merge events, PR descriptions; descriptions >100 chars queued for selective embedding (phase 2)

Implementation: `github_scan.py` → `github_activity` SQLite table → joined with `project_registry.repos` for weighted balance scores.
Activity classified into 30-day bands: A (0–7d), B (8–14d), C (15–30d).
**Vectorized:** No — structured counts only. PR descriptions and issue bodies >100 chars queued for selective embedding in phase 2 (`github_embed_queue`).

### P1 — Obsidian Vault

Primary knowledge source for project context, retrieval, and briefing synthesis.

- **Existing files — edit dates** — file modification timestamps used for project activity signals and delta ingest (skip unchanged files)
- **Existing files — contents** — parsed for frontmatter, headings, wikilinks, and tags; chunked and embedded into sqlite-vec for RAG retrieval
- **New files** — picked up on next ingest run via hash-based delta check; no continuous watching required for MVP

Implementation: `note_ingester.py` + `embedder.py` → `vault_files`, `chunks`, `keywords`, `links`, `embeddings` SQLite tables.
**Vectorized:** Yes — chunks embedded via Qwen3-Embedding-0.6B (1024-dim) into sqlite-vec.

### P2 — Google Calendar — ✅ Active

Meeting load, scheduling patterns, and daily briefing context.

- **Events** — title, time, location, attendees, description; fetched via Google Calendar API (direct client, not gcalcli)
- **Retention** — 1 year of historical events persisted in `calendar_events` table for meeting-load analysis and project-meeting correlation
- **Sync window** — configurable: `rebalance calendar-sync --days-back 365 --days-forward 14`
- **Calendar selection** — sync from any readable calendar (primary, shared, team calendars): `rebalance calendar-sync --calendar-id <email_or_id>`
- **Daily totals** — aggregate daily event metrics (count + duration): `rebalance calendar-daily-totals --days-back 30`
- **Context delivery** — upcoming events (next 2 days) + recent events (last 7 days) fed into `ask` tool prompt

Implementation: `calendar.py` → `calendar_events` SQLite table → `querier.py` `_gather_calendar_context()`.
**Vectorized:** No — structured event data only. Calendar events are high-signal for scheduling context but low-signal for semantic search.

**Access setup:**

1. **Google Cloud project** — create a project at https://console.cloud.google.com/
2. **Enable the Google Calendar API** — APIs & Services → Library → search "Google Calendar API" → Enable
3. **OAuth consent screen** — APIs & Services → OAuth consent screen → User type: External (or Internal if using Google Workspace) → fill in app name ("rebalance OS"), user support email, and developer email.
4. **Create OAuth 2.0 credentials** — APIs & Services → Credentials → Create Credentials → OAuth client ID → Application type: **Desktop app** → name it "rebalance-calendar" → Download the JSON file.
5. **Authenticate via rebalance** — run `python scripts/setup_calendar_oauth.py --client-secret /path/to/client_secret.json`. This opens a browser for Google OAuth consent. Grant read-only calendar access. Token is saved to `~/.config/gcalcli/oauth`.
6. **Sync calendar** — run `rebalance calendar-sync --days-back 365` (for initial backfill, then use `--days-back 30` in daily cron/scheduler)
7. **View daily totals** — `rebalance calendar-daily-totals --days-back 30` shows event count and duration per day

**Required OAuth scopes**:
- `https://www.googleapis.com/auth/calendar.readonly` — read-only access to calendar events

**Token storage:** OAuth2 refresh token is stored in `~/.config/gcalcli/oauth` (pickle format). This file is outside the repo — not gitignored here, but never committed. The refresh token auto-renews; re-auth is only needed after long gaps or token revocation.

**Security notes:**
- The OAuth client ID/secret are not sensitive in the same way as API keys — they identify the app, not the user. However, do not commit them to the repo. Store in `temp/rbos.config` alongside the GitHub PAT.
- rebalance only reads calendar data — it never creates, modifies, or deletes events.
- To revoke access: https://myaccount.google.com/permissions → find "rebalance-gcalcli" → Remove.

### P3 — Slack / Sleuth Tasks

Task and communication signal across projects. Deferred until P1/P2 are validated.

- Slack: channel messages, @mentions, threads linked to project tags
- Sleuth: task creation, status changes, comments

Implementation: TBD — likely webhook or API polling into a `tasks` SQLite table.

### P4 — Email

Stakeholder communication signal — surfaces external commitments, blocked-on-response patterns, and "human pressure" behind projects that GitHub/Vault/Calendar don't capture. Deferred until P1–P3 are stable.

**Core constraint: keep it as light as possible.**

#### Pre-filter — what gets collected

Only threads matching **both** conditions:

1. **Gmail label:** `IMPORTANT` or `STARRED` (user's existing curation — no new rules to learn)
2. **Date:** forward-only from onboarding date. **No backfill** — historical email is unbounded noise.

Everything else is ignored. This means rebalance never sees the bulk of a user's inbox.

#### Data shape — thread-level metadata only

No message bodies. No content parsing. No embedding. One row per thread:

| Field | Source | Notes |
|---|---|---|
| `thread_id` | Gmail API | Dedupe key |
| `subject` | First message | For project-keyword matching |
| `label` | Gmail | `IMPORTANT`, `STARRED`, or both |
| `last_activity_at` | Latest message timestamp | Recency signal |
| `message_count` | Thread length | Conversation depth |
| `user_replied` | Boolean | Did the authenticated user send a reply? |
| `user_reply_count` | Integer | How many times the user replied |
| `first_seen_at` | Ingest timestamp | When rebalance first saw this thread |

~8 fields per thread. No bodies, no attachments, no sender PII stored.

#### Weighting

- **Replied-to threads** get higher weight — replying is the strongest signal of time investment.
- **Reply count** scales weight — 5 replies > 1 reply (sustained engagement, not a quick ack).
- **Starred + Important** outweighs either label alone (user double-signaled).
- **Recency** — threads with activity in the last 7 days weighted higher than stale threads.

Weight formula (computed at briefing time, stored in project's `computed:` block):

```
email_pressure = starred_replied_threads × 3
               + important_replied_threads × 2
               + starred_unreplied_threads × 1
               + important_unreplied_threads × 0.5
```

Threads are linked to projects via subject-line keyword matching against `project_registry.name` and `project_registry.tags`. Unmatched threads are counted in an "unlinked" bucket (visible in briefing but not attributed to any project).

#### Sync strategy

- **API:** Gmail API (REST) with `users.threads.list` + label filter. Not IMAP — Gmail API supports label-based queries natively and avoids IMAP connection overhead.
- **Frequency:** Daily batch (cron/launchd alongside morning briefing). Email is not real-time actionable in this context.
- **Pagination:** `maxResults=100`, iterate pages. Expect low volume since pre-filter is aggressive.
- **Delta:** Only fetch threads with `internalDate` after last sync timestamp. No full re-scan.
- **Rate limits:** Gmail API allows 250 quota units/second per user. `threads.list` = 1 unit, `threads.get` = 1 unit. Daily batch of ~50 threads is negligible.

#### What this does NOT do

- No message body storage or parsing
- No sender/recipient PII beyond what Gmail labels provide
- No attachment handling
- No embedding or vectorization (structured metadata only)
- No backfill of historical email
- No real-time sync or push notifications
- No email sending or modification

#### Implementation

`email_sync.py` → `email_threads` SQLite table → `querier.py` `_gather_email_context()`.

**Required OAuth scopes:**
- `https://www.googleapis.com/auth/gmail.readonly` — read-only access to Gmail

**Vectorized:** No — structured thread metadata only. Subject lines are too short for meaningful embeddings; the signal is in the counts and patterns, not the prose.

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
      neglect_score: 0
      momentum_decay: 0.0
      avoidance_ratio: 0.0

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

## Project Weights — Nudge System (Planned)

> Status: **Planned** — not yet implemented. All inputs already exist in the data model (`priority_tier`, GitHub activity bands, `last_activity_at`). No new signals required — only arithmetic in the query/briefing layer.

Three computed weights that surface healthy-but-uncomfortable truths about where the user is spending time vs where they said they would.

### 1. Neglect Score

`days_since_last_touch × priority_tier_inverse`

A Tier 1 project untouched for 10 days scores higher than a Tier 3 project untouched for 10 days. Surfaces the pattern of avoiding high-stakes work by staying busy with low-stakes comfort projects.

- **Input:** `last_activity_at` (GitHub or vault), `priority_tier`
- **Delivery:** Morning briefing line — *"Sleuth App (Tier 1) — no activity in 12 days"*

### 2. Momentum Decay

Rolling activity trend: this week vs trailing 2-week average.

Not "are you working on it" but "are you working on it *less than you were*." A project dropping from 15 commits/week to 3 is a stronger signal than one that's always been at 3. Detects the slow fade-out before the user consciously notices.

- **Input:** GitHub activity bands (A/B/C), commit counts per scan window
- **Delivery:** Briefing flag — *"rebalance OS: activity down 70% vs 2-week average"*

### 3. Avoidance Ratio

`time_on_low_tier / time_on_high_tier`

If you spent 80% of your week on Tier 3–5 projects and 20% on Tier 1–2, that ratio is the nudge. No judgment — just a mirror showing allocation vs stated priorities. The user set the tiers, so the cognitive dissonance does the motivational work.

- **Input:** GitHub activity (commits + PRs) per project, `priority_tier`
- **Delivery:** Briefing summary — *"This week: 82% of activity on Tier 3+ projects"*

### Storage

All three weights are written to the `computed:` block of each project in the canonical registry (`Projects/00-project-registry.md`) via `push` sync. This keeps them:

- **Transparent** — visible in the same file the user already reads and edits
- **Auditable** — diffs show how scores change over time
- **Co-located** — next to `priority_tier`, `attention_percent_7d`, and `last_activity_at`

The `computed:` block is machine-written only (never hand-edited). The briefing assembler reads these values from the registry rather than recomputing from scratch.

Not the primary value proposition of rebalance — a hidden bonus that emerges from data already being ingested.

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

## Post-v1.0 Roadmap

Items explicitly deferred to reduce scope. Prerequisites: P1–P3 signals stable, nudge weights shipping, morning briefing validated.

### Email → Project Auto-Correlation

**Problem:** Keyword matching (`subject LIKE '%LTVera%'`) catches obvious hits but misses threads like "Re: Q3 renewal pricing" that are clearly project-related. Unmatched threads pile up in the "unlinked" bucket.

**Approach (phased):**

1. **Alias map (semi-automatic)** — When a user replies to an unlinked thread during the same week they commit to a specific repo, the system *proposes* a link: "Link 'Q3 renewal pricing' → LTVera?" User confirms or rejects. Confirmed aliases persist and auto-apply to future threads with similar subjects.
2. **Correspondent → Project mapping** — Co-occurrence inference: if emails from a specific sender spike when a project's GitHub activity spikes, propose the association. Structured correlation query — no vectors needed.
3. **Subject embedding (evaluate last)** — Embed subject lines + project names into the same vector space for fuzzy matching. Only worth it if alias map coverage plateaus below ~80%. Short-text embeddings are noisy; may not outperform the alias approach.

**What this does NOT include:** storing sender PII, parsing message bodies, or real-time sync. The correlation layer works on the same thread-level metadata already collected.

### GitHub Selective Embedding (Phase 2)

PR descriptions and issue bodies >100 chars embedded into sqlite-vec via `github_embed_queue` filter. Adds semantic search over long-form GitHub content without polluting the vector space with short commit messages.

### Cross-Source Activity Correlation

Unified timeline view across GitHub + Vault + Calendar + Email — detect patterns like "meetings spike → commits drop" or "email pressure on Project X but no vault notes updated." Requires all four sources active and at least 30 days of data.

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