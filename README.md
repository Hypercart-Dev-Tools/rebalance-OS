> Your workday "OS"

---

## Who this is for

- **Dev and design agency owners** juggling 5+ client repos, scattered notes, and back-to-back meetings with no time to connect the dots
- **Solopreneurs and indie hackers** who live in Obsidian but lose hours tracking where their attention actually goes
- **Technical founders** who want AI-assisted clarity on their own work — without sending their notes, commits, or calendar to a cloud service

If you've ever opened your laptop in the morning and genuinely not known where to start, this is for you.

---

## The problem

Your work lives in multiple places that never talk to each other: your notes, your code repos, your recent git activity, your calendar, and the reminder systems wrapped around them. You context-switch constantly, lose track of which projects are getting too much attention (and which aren't getting enough), and spend the first 30 minutes of every day reconstructing what you were doing yesterday.

AI assistants could help — but they can't see your Obsidian vault, your GitHub activity, or your Google Calendar. And sending all of that to a cloud LLM isn't an option for client work.

<img width="1882" height="1516" alt="rebalance" src="https://github.com/user-attachments/assets/eb60a254-d452-4839-a900-0ffedd72758f" />

---

## What it does

**rebalance OS** is a local-first work operating system that ingests your Obsidian vault, GitHub activity and artifacts, recent git history, calendar, and email into a queryable SQLite database — then lets any MCP-capable host or agent (ChatGPT, Gemini, Claude, Copilot, Cursor, Continue, and others where MCP is supported) answer questions about your own work, surface where your attention is actually going across projects, and trigger self-repairing background collectors when something goes wrong — all from your local machine, without sending private data to a cloud service.

---

## Use cases

**Morning briefing**
Ask "What's my day look like?" and get today's meetings, yesterday's commit activity, and a summary of relevant notes — in one shot, from your local machine.

**Project balance check**
"Am I over-investing in client X?" surfaces commit velocity, PR activity, and note density per project. Flags when one repo is consuming >40% of your attention.

**Knowledge retrieval**
"What did I decide about the Project Alpha embedding pipeline?" Semantic search across your vault and synced GitHub corpus, ranked by relevance and answered from the local SQLite evidence layer.

**Handoff prep**
"Summarize everything I know about Project Y" pulls notes, recent commits, and open issues into a coherent brief — useful for client updates, team handoffs, or just getting back up to speed after a break.

**Weekly rebalance**
"Where did my attention actually go this week?" — calendar hours, email threads, Slack mentions, and GitHub activity are all indexed per project. The signal-agnostic prioritization layer (in progress) will aggregate these into a transparent per-project count, narrated by AI summary rather than hard-coded verdict labels.

**Self-repairing background jobs**
Background collectors (pulse sync, GitHub scan) now use a finite-state-machine repair loop (`src/rebalance/repair.py`). When a job fails with a recoverable error — e.g., a push conflict on the pulse repo — it retries automatically with `pull --rebase`. If deterministic repair is exhausted, Haiku is consulted to pick from a bounded action menu before the job files a GitHub issue and stops. Destructive actions require explicit operator authorization and are never selected autonomously.

---

## High-level architecture

```
Data sources
  Google Calendar   ──┐
  GitHub activity   ──┤
  GitHub artifacts  ──┤
  Git pulse history ──┤──▶  scheduler / on-demand sync ──▶ SQLite + sqlite-vec
  Obsidian vault    ──┤      (launchd on macOS,           (vault chunks,
  Sleuth reminders  ──┤       Task Scheduler on            github_activity,
  Gmail inbox       ──┤       Windows, cron on Linux)      github_artifacts,
  Slack [planned]   ──┘                                     calendar_events,
                                                              email_messages,
                                                              git-pulse reports,
                                                              semantic_documents)
                                     │
                                     ▼
                           MCP server — src/rebalance/mcp/
                           25 tools across 7 domains:
                             Projects  list_projects · github_balance
                             Onboarding  onboarding_status · setup_github_token
                                         run_preflight · confirm_projects
                                         ingest_gmail_messages
                             Retrieval  ask · query_notes · search_vault
                                        query_github_context
                                        github_release_readiness
                                        github_close_candidates
                             Calendar  create_calendar_event · review_timesheet
                                       classify_event · snap_calendar_edges
                             Index  index_status · refresh_index · diagnose_repo
                                    list_watched_repos · publish_pulse
                                    semantic_query
                             Hygiene  audit_modules
                             Sleuth   sleuth_sync_reminders
                                     │
             ┌───────────────────────┼────────────────────────┐
             ▼                       ▼                        ▼
      ChatGPT/Gemini           Claude/Copilot          Cursor/Continue
      (where MCP works)       (MCP clients)             (MCP clients)
```

The MCP server speaks standard JSON-RPC — no LLM-specific logic inside it. Any MCP-compatible client works without modification.

The scheduled side of the diagram (the launchd fleet: daily/hourly syncs, pulse publishing, health checks) is governed by the policy table in [SCHEDULER.md](SCHEDULER.md) — job cadences, scopes, prerequisites, and the runbook live there.

For layer roles, tool surface, server configuration, and host adapter setup (Claude Desktop, Cursor, VS Code, Continue), see **[MCP.md](./MCP.md)**.

---

## Why Markdown files and local LLMs make this possible

Obsidian stores everything as plain `.md` files. No proprietary database, no sync lock-in, no API needed — just a folder on your disk. That makes ingestion a simple recursive file scan: parse frontmatter, chunk by headings, extract tags and wikilinks, embed, and index. Recent work extends that same pattern beyond the vault: embeddable GitHub artifacts now flow into the same unified semantic document layer instead of living in a separate vector silo.

Local LLMs — such as Qwen3 via Ollama or LM Studio-compatible models — close the loop. Your vault content can stay local and be queried without sending note content to a hosted LLM by default. GitHub and Google Calendar data are pulled from their APIs, then cached and queried locally. The model runs on-device (optimized for Apple Silicon via MLX), retrieves context from the local vector store, and answers in seconds.

The result is an AI assistant that actually knows your work — because it's reading the same files and synced local history you are.

---

## Tech stack

| Layer | Tool |
|---|---|
| Notes | Obsidian (plain `.md`) |
| Local activity history | `git-pulse` sync repo + recap/report layer |
| Vector DB | SQLite + `sqlite-vec` |
| Embeddings | Qwen3-Embedding-0.6B via `mlx-embeddings` (Apple Silicon MLX) |
| LLM synthesis | Qwen3-0.6B via `mlx-lm` (on-device, Layer 1) |
| Calendar | Google Calendar API (direct client, OAuth2) |
| GitHub | GitHub REST API + PAT |
| Reminders | Sleuth Web API (structured sync) |
| MCP server | Python `mcp` SDK (FastMCP, stdio) — decomposed into `src/rebalance/mcp/` (7 domain modules, 25 tools) |
| Repair loop | `src/rebalance/repair.py` — `RepairFSM` (PENDING → REPAIRED \| ESCALATED → REPAIRED \| DEAD) with Haiku escalation and bounded action menu |
| LLM clients | Any MCP host (Claude Code, Copilot, Cursor, Continue, Claude Desktop, and others) |

---

## Roadmap

- [x] Architecture and design
- [x] Project registry + MCP onboarding tools
- [x] GitHub activity scanner + 30-day A/B/C band classification
- [x] GitHub artifact sync + local semantic query (issues, PRs, comments, reviews, commits)
- [x] Unified semantic index across vault and GitHub (`semantic_documents`, `semantic_embeddings`)
- [x] GitHub readiness inference from local repo signals (milestones, linked PRs, branches, releases)
- [x] GitHub issue <-> PR close-candidate reconciliation with high/medium-confidence recommendations
- [x] Obsidian vault ingester (parse, chunk, keywords, links)
- [x] Qwen3 embedding pipeline (sqlite-vec, semantic search)
- [x] Google Calendar integration (OAuth2, 1-year retention)
- [x] Git-pulse local repo discovery, recap layer, health checks, and sync hardening
- [x] Sleuth reminder sync (structured ingest)
- [x] `ask` tool — multi-source natural language query with local LLM synthesis
- [x] Temporal context (day-of-week, work/off/vacation awareness)
- [x] Daily scheduler scripts (launchd plist, install helper)
- [x] Calendar daily/weekly reports with project aggregation and time totals
- [x] Configurable hours format (decimal or h:m) for calendar reports
- [x] Agent review layer for calendar events (`review_timesheet`, `classify_event` MCP tools)
- [x] DRY calendar helpers (shared datetime parsing, duration calc, connection setup)
- [x] CI test suite (GitHub Actions, Python 3.12/3.13)
- [x] Gmail inbox integration (newest 100 inbox messages, semantic index via subject + snippet)
- [x] MCP server decomposed — `src/rebalance/mcp/` package with 7 domain modules, 25 tools, 5-line backward-compat shim
- [x] Display-layer simplification — dead code removed, registry-gated path eliminated, `ingest/dashboard.py` renamed `note_builder.py`, ignored-repos filter added to org-activity query
- [x] `RepairFSM` (`src/rebalance/repair.py`) — deterministic repair loop with bounded Haiku escalation, circuit breakers, and unrecoverable-error short-circuiting; pulse self-repair is the first consumer
- [ ] Signal-agnostic project prioritization — multi-source attribution (calendar + email + Slack + GitHub) feeding transparent per-project counts; `GitHub Repos.md` annotation surface with `#tag` write-back
- [ ] Weekly rebalance note generation grounded in multi-signal counts rather than hard-coded verdict labels
- [ ] Slack integration beyond reminder/task signals
- [ ] Email → project auto-correlation (classifier already applied to calendar; extending to `gmail_messages`)

## Documentation

| Guide | What's in it |
|-------|--------------|
| [GMAIL.md](./GMAIL.md) | Gmail inbox ingest — `oauth` (keyring) vs `mcp` methods, durable Internal tokens, query filters, troubleshooting |
| [GOOGLE_CALENDAR.md](./GOOGLE_CALENDAR.md) | Google Calendar timesheets — setup, team config, event creation, project aggregation |
| [MCP.md](./MCP.md) | MCP layer — tool surface, server config, host adapters (Claude Desktop, Cursor, VS Code, Continue) |
| [UPGRADE.md](./UPGRADE.md) | Keyring credential model + multi-device upgrade steps |
| [DASHBOARD.md](./DASHBOARD.md) | Local web/activity dashboard |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | System architecture and data flow |
| [PROJECT.md](./PROJECT.md) · [PROJECT/](./PROJECT/README.md) | Execution source-of-truth and the plan-doc index |
| [AGENTS.md](./AGENTS.md) | Conventions for AI agents working in this repo |
| [macOS/Apps/Focus5Float/README.md](./macOS/Apps/Focus5Float/README.md) | Focus 5 Float macOS app — build, install, binary path setup (`pipx`), self-checks |

---

## Getting Started

### Fastest path — `/welcome`

After cloning and installing (Step 1 below), open the repo in Claude Code and type `/welcome`. The welcome agent walks you from zero to your first rendered pulse: it checks where you are (`onboarding_status` — resumable any time, even days later), runs each step itself (GitHub PAT validation, optional Google Calendar/Gmail OAuth, project discovery), asks you which discovered repos to promote to monitored, then installs the scheduled sync fleet and opens your first pulse. You only click OAuth consent screens and answer promote/skip questions — secrets never appear in the chat.

Prefer no agent? `rebalance onboard` is the same guided journey as a CLI wizard, and `rebalance onboard --status` shows the stage map ("where am I / what's next") at any time. To start over: `rebalance reset` (dry-run by default; your vault is never touched).

The manual steps below remain for reference and for environments without an MCP host.

### Prerequisites

- macOS with Apple Silicon (M1+) for the **full** local stack (embeddings + on-device LLM) — the core runs cross-platform; see [Supported platform & first-run network](#supported-platform--first-run-network) just below
- Python 3.12+ (3.13 recommended for the local MLX embeddings stack)
- An Obsidian vault (local folder with `.md` files)
- A GitHub Personal Access Token ([create one here](https://github.com/settings/tokens)) — either:
  - **classic token** with the `repo` scope (GitHub offers no read-only private scope on classic tokens; `public_repo` alone makes your private work invisible to discovery), or
  - **fine-grained token** — change *Repository access* from the default **"Public repositories"** to *All repositories* (or the ones you work in), with read-only **Contents** and **Metadata** permissions.
- Claude Code (CLI or VS Code extension)

### Supported platform & first-run network

**Full experience: macOS with Apple Silicon (M1+).** On-device embeddings
(`mlx-embeddings`) and LLM synthesis run on Apple's MLX, which is Apple-Silicon-only.

**Cross-platform subset.** The core is pure-Python and runs on Linux, Windows,
and Intel Macs — only the `embeddings` extra is platform-gated:

| Install | What it adds | Platform |
|---|---|---|
| `pip install -e .` | CLI, MCP server, SQLite + `sqlite-vec`, vault ingest (parse/chunk/keywords/links), GitHub scan/sync, `doctor` | any (Python 3.12+) |
| `+ [calendar]` | Google Calendar + Gmail OAuth ingest | any |
| `+ [server]` | local web/activity dashboard | any |
| `+ [embeddings]` | semantic search + embeddings (`semantic-*`, and the retrieval behind `ask`) | **Apple Silicon only** |

So semantic search needs Apple Silicon; everything else — ingest, GitHub,
calendar, the full MCP tool surface — works anywhere Python 3.12+ runs.

**First-run network egress** (matters behind an egress allowlist / agent sandbox):

- First `semantic-embed` / `ingest embed` downloads **Qwen3-Embedding-0.6B** from
  **huggingface.co** — one-time, several hundred MB, then cached under `~/.cache/huggingface`.
- `github-*` commands call **api.github.com** with your PAT.
- Calendar / Gmail call **accounts.google.com** and **\*.googleapis.com** for OAuth and sync.

Allow those hosts before first run if you operate behind an allowlist; the model
download is the only large transfer and happens once.

### Step 1 — Clone and install

```bash
git clone https://github.com/Hypercart-Dev-Tools/rebalance-OS.git
cd rebalance-OS
/opt/homebrew/bin/python3.13 -m venv .venv
.venv/bin/pip install -e ".[embeddings,calendar]"
```

> On Linux / Windows / Intel Mac, drop the `embeddings` extra:
> `pip install -e ".[calendar]"` (semantic search will be unavailable; everything else works).

### Step 2 — Ingest your vault

```bash
# Parse all .md files, chunk by headings, extract keywords and links
.venv/bin/rebalance ingest notes --vault /path/to/your/vault --database rebalance.db

# Generate vault embeddings
.venv/bin/rebalance ingest embed --database rebalance.db
```

> **Embedding runs under a memory guard (GH-172).** Embedding is the heaviest
> local job in this project — it loads a Qwen model and holds vectors resident.
> Every embedding pass therefore takes a **single-instance lock** and runs under a
> **memory ceiling** (default: 35% of physical RAM), so a second run cannot stack
> on a first and exhaust the machine. This is on by default with nothing to
> install.
>
> If a run exits with "job 'rebalance-embed' is already running", that is the
> guard working — another embed (often a scheduled `daily-sync`) holds the lock.
> Wait, or re-run with `REBALANCE_JOB_GUARD_ON_CONFLICT=replace` to take over.
>
> Verify it is active, and tune it per machine:
>
> ```bash
> .venv/bin/python -c "from rebalance.ingest import _job_guard as g; print(g.available(), g.enabled())"
> # -> True True
> ```
>
> Every guarded run also appends its peak memory to `temp/logs/job_rss.jsonl`,
> so if a job ever does exhaust the machine you can tell **which** one it was —
> the incident that motivated this (GH-172) was hard to attribute precisely
> because macOS records only the process name `Python`.
>
> Full reference, tuning variables, and the non-editable-install caveat:
> [UPGRADE.md § Embedding job guard](./UPGRADE.md#embedding-job-guard-gh-172--verify-on-every-device).
> On a machine with substantially less than 64 GB RAM, set
> `REBALANCE_JOB_GUARD_MAX_RSS_GB` explicitly rather than relying on the fraction.

> **If you install the scheduled jobs**, note that the plist templates in
> `scripts/` set `Nice=5` on batch jobs and use a deliberately de-collided
> schedule — no two jobs fire in the same minute. `pulse-web-sync` in particular
> must not share a slot with `pulse-sync`: it is a derived read-only stage over
> what `pulse-sync` writes, so a shared minute risks reading half-written state.
> Install via the per-job `scripts/install_*_scheduler.sh` scripts; there is no
> single install-everything script. Details:
> [UPGRADE.md § Re-render your launchd plists](./UPGRADE.md#re-render-your-launchd-plists-gh-175--required-on-existing-devices).

### Step 3 — Connect GitHub

```bash
# Store your PAT
.venv/bin/rebalance config set-github-token <github-pat>

# Scan recent activity (commits, PRs, issues across all your repos)
.venv/bin/rebalance github-scan --token <github-pat> --database rebalance.db

# Sync detailed GitHub artifacts into the local SQLite corpus
.venv/bin/rebalance github-sync-artifacts \
  --repo owner/repo \
  --database rebalance.db

# Backfill the unified semantic layer from vault + GitHub
.venv/bin/rebalance semantic-backfill --source vault --source github --database rebalance.db

# Embed the unified semantic layer (downloads Qwen3-Embedding-0.6B on first run)
.venv/bin/rebalance semantic-embed --source vault --source github --database rebalance.db

# Query the unified semantic corpus without re-reading GitHub live
.venv/bin/rebalance semantic-query "What is close to deploy?" --source vault --source github --database rebalance.db
```

You can still use the source-specific commands:

```bash
.venv/bin/rebalance github-embed --database rebalance.db
.venv/bin/rebalance github-query "What changed in release readiness?" --database rebalance.db
```

### Step 4 — Connect Google Calendar (optional)

OAuth Desktop app credentials are already bundled in the repo. You do **not** need to create a Google Cloud project or download a `client_secret.json`.

**4a. Install with calendar support**

```bash
.venv/bin/pip install -e ".[calendar]"
```

**4b. Authorize this device**

```bash
.venv/bin/python scripts/setup_calendar_oauth.py --test
```

A browser window opens — log in with your Google account and click **Allow**. The script prints your available calendars and their IDs. Your token is saved in your OS keyring, with a launchd-reachable JSON fallback in the out-of-repo secret store at `~/.config/rebalance-os/secrets/google-calendar-oauth` (never in the repo).

If you want MCP agents to create events, re-run auth with write access:

```bash
.venv/bin/python scripts/setup_calendar_oauth.py --write-access --test
```

> **Joining a team?** If a teammate sent you a pre-filled `calendar_config.json`, place it at `temp/calendar_config.json` and skip to step 4d.

**4c. Create your config**

```bash
mkdir -p temp
cp calendar_config.example.json temp/calendar_config.json
```

Edit `temp/calendar_config.json` with your preferences:

| Field | What to put here |
|-------|-----------------|
| `calendar_id` | Calendar ID from step 4b, or `"primary"` for your main calendar |
| `exclude_titles` | Exact event titles to hide from reports (e.g., `"Lunch"`, `"Check Slack"`) |
| `aggregator_skip_words` | Broad terms skipped in project grouping labels only (e.g., `"wrap"`, `"setup"`) |
| `timezone` | Your local timezone (e.g., `"America/Los_Angeles"`) |
| `hours_format` | `"decimal"` (default, e.g. `4.50h`) or `"hm"` (e.g. `4h 30m`) |

**4d. Sync and run reports**

```bash
# Pull events (use --days-back 365 for initial backfill)
.venv/bin/rebalance calendar-sync --days-back 30

# Generate reports
.venv/bin/rebalance calendar-daily-report
.venv/bin/rebalance calendar-weekly-report
.venv/bin/rebalance calendar-weekly-report --vault /path/to/vault --write-week-note
```

For the full guide — including team setup, Claude Code prompts, and project definitions — see [GOOGLE_CALENDAR.md](./GOOGLE_CALENDAR.md).

### Step 5 — Connect Gmail (optional)

The Gmail ingest stores message metadata plus Gmail-provided snippets only —
it does not parse full message bodies. There are two ways to feed it, and you
pick one with `rebalance config set-gmail-method`:

| Method | When to use | Credential |
|---|---|---|
| `oauth` *(default)* | Autonomous / scheduled sync (launchd, cron) | Desktop OAuth token in keyring |
| `mcp` | You drive rebalance from an MCP host (e.g. Claude) | None — an agent calls `ingest_gmail_messages` |

**Option A — `oauth` (self-contained, works under launchd)**

A one-time browser consent stores a read-only Gmail token in your OS keyring,
with a launchd-reachable JSON fallback in the out-of-repo secret store
(`~/.config/rebalance-os/secrets/`) — the same model as Calendar:

```bash
python scripts/setup_gmail_oauth.py        # browser consent; writes keyring + JSON fallback directly
rebalance config set-gmail-method oauth
```

> `gmail.readonly` is a Google-*restricted* scope. This flow uses **your own**
> Desktop OAuth client with the consent screen in **Testing** mode (add your
> account as a test user), which can request it **without** formal app
> verification. That is why this path works where
> `gcloud auth application-default login --scopes=…gmail.readonly` does not —
> the shared gcloud ADC client is generally not authorized for restricted Gmail
> scopes, so ADC tokens 403 with "insufficient authentication scopes."

**Option B — `mcp` (no local credential)**

```bash
rebalance config set-gmail-method mcp
```

`email_messages` is then populated by an agent (e.g. Claude) using the Gmail
MCP connector, which calls the `ingest_gmail_messages` tool. A scheduled job
cannot trigger this — an agent has to. No local Gmail credential is needed.

> **Trade-off:** `mcp` routes your email through the host's cloud (e.g.
> claude.ai), while `oauth` (Option A) keeps it on this machine. It requires a
> host that ships a Gmail connector with your Google account already connected
> there — otherwise use `oauth`.

**5c. Optional: narrow the inbox query**

Add a `gmail_query_filter` key to `temp/rbos.config`. Example:

```json
{
  "gmail_query_filter": "in:inbox -category:promotions -category:social"
}
```

If unset, rebalance defaults to `in:inbox`.

**5d. Sync and verify**

Run `rebalance refresh` (the full pipeline syncs email in `oauth` mode), or from
an MCP host call `refresh_index(scope=["email"])`. Confirm the `email` block
appears in `index_status()`, email hits show up in `semantic_query()`, and
`rebalance doctor` reports `gmail — OK`.

For the full guide — both ingest methods, durable (Internal) tokens, query
filters, troubleshooting, and Claude Code prompts — see [GMAIL.md](./GMAIL.md).

### Step 6 — Start using with Claude Code

The `.mcp.json` at the project root auto-registers the MCP server. Open the project in Claude Code:

```bash
cd rebalance-OS
claude
```

Then ask:

```
"What should I focus on today?"
"Am I over-investing in any projects this week?"
"What meetings do I have tomorrow and what should I prep?"
"What did I decide about the embedding pipeline?"
```

Claude Code calls the `ask` tool behind the scenes — it gathers your project registry, GitHub activity, vault notes, and calendar events, synthesizes a first-pass answer via a local Qwen3 model, then Claude reviews and presents a refined answer.

### Claude Desktop App

#### Manual config (recommended for now)

1. Open **Claude → Settings → Developer → Edit Config** to open `~/Library/Application Support/Claude/claude_desktop_config.json`.
2. Add the rebalance server (use absolute paths):

   ```json
   {
     "mcpServers": {
       "rebalance": {
         "command": "/absolute/path/to/rebalance-OS/.venv/bin/python",
         "args": ["-m", "rebalance.mcp_server"],
         "env": {
           "REBALANCE_DB": "/Users/<you>/Library/Application Support/rebalance-os/rebalance.db"
         }
       }
     }
   }
   ```

   `REBALANCE_DB` is **optional** as of 0.28.0 — `src/rebalance/paths.py` defaults to the canonical app-data path (`~/Library/Application Support/rebalance-os/rebalance.db` on macOS, `$XDG_DATA_HOME/rebalance-os/rebalance.db` on Linux). Set it explicitly only when you want to override that default. Stale env-var values silently fall through to the canonical path, so updating `REBALANCE_DB` here is never urgent. To move an existing DB into the canonical location, run `python -m rebalance.paths --migrate` (idempotent; also moves the `-wal` and `-shm` sidecars). Launchd jobs in `scripts/com.rebalance-os.*.plist` don't set `REBALANCE_DB` at all — they rely on the same resolver fallback, so no plist edits are needed when the canonical path moves or new sync jobs are added.

3. Quit and reopen Claude Desktop. The rebalance tools appear in the tool picker (hammer icon).
4. Ask *"What should I work on today?"* to verify.

For detailed setup, troubleshooting, and other MCP hosts, see [MCP.md — Claude Desktop](./MCP.md#claude-desktop).

#### Extension (`.mcpb`) — coming soon

rebalance OS will also ship as a Claude Desktop Extension. The extension packaging step (`mcpb pack`) requires bundling all Python dependencies into the archive. This is not yet automated — use the manual config above for daily use. See [manifest.json](./manifest.json) for the extension spec.

### Other MCP hosts

The server works with any MCP-compatible client. Config files are provided for:

- **Claude Code** — `.mcp.json` (auto-loaded on `cd rebalance-OS && claude`)
- **VS Code (Copilot/Continue)** — `.vscode/mcp.json` (auto-loaded on workspace open)
- **Claude Desktop** — manual config (see above) or extension (`.mcpb`, coming soon)
- **Cursor** — see [MCP.md](./MCP.md) for config snippet

### Focus 5 Float (optional macOS menu-bar app)

Focus 5 Float renders your live Focus 5 roster as an always-on-top floating
card stack, with offline cache and a one-click "Start server" button.

**Build and install:**

```bash
cd macOS/Apps/Focus5Float
./make-app.sh          # release build → ad-hoc signed → /Applications/Focus 5 Float.app
```

**Binary path requirement.** The app starts `rebalance serve` on demand, but
macOS GUI apps don't inherit your shell `PATH`. Install `rebalance` at a
system-accessible path once per device so the app can find it:

```bash
brew install pipx
pipx install -e /path/to/rebalance-OS   # → ~/.local/bin/rebalance
```

The app checks `~/.local/bin/rebalance` directly — no shell needed. Without
this step the app shows _"Couldn't find the `rebalance` binary"_ when trying
to start the server. See [macOS/Apps/Focus5Float/README.md](./macOS/Apps/Focus5Float/README.md)
for the full resolution order and troubleshooting.

---

## Code Intelligence

`ask-self` is an external RAG-based code and docs scanner that builds a local queryable index for this repository without vendoring its code here.

This repo runs ask-self in **portable mode** with **fully-local Qwen embeddings** — the SQLite index is committed at [ask_self/index/rebalance-OS.sqlite](ask_self/index/rebalance-OS.sqlite), so a fresh clone can query immediately with no ingest and no API keys.

> Last ingested: 2026-05-28 on `fix/28-dev-install-fixes` after the hardened portable `qwen-local` refresh

### Query this repo (no setup required)

```bash
./scripts/ask-self-query.sh "How does dashboard rendering work?"
```

The query wrapper pins `--db-path` to the committed portable DB, so it works on a fresh clone.

### Refresh the index (maintainers only)

```bash
./scripts/ask-self-ingest.sh --mode all --no-architecture-md
```

Notes:
- The wrapper now defaults to `--mode all` if you omit `--mode`, but keeping it explicit in maintainer docs is still clearer.
- `--no-architecture-md` is intentional: the curated [ARCHITECTURE.md](ARCHITECTURE.md) is hand-edited and should not be regenerated.
- Embedding is **Gemini** (`gemini-embedding-001`, dim 768), set in [ask_self/ask_self_harness.json](ask_self/ask_self_harness.json) since commit `4ef8c39`. `GOOGLE_API_KEY` is required for **both** ingest and query — query-time embedding needs it too, not just synthesis.
- The wrapper no longer auto-applies `qwen-local` tuning (`TOKENIZERS_PARALLELISM`, `ASK_SELF_QWEN_BATCH_SIZE`, `ASK_SELF_QWEN_MAX_TOKENS`, `--concurrency 1`); that path was dead under the Gemini harness and was removed. If you switch the harness back to a local Qwen provider, set those explicitly — the defaults are not memory-safe on this machine (see #172).
- Switching provider changes the embedding dimension, which forces a **full index rebuild**. That is the heaviest local job in the repo; do not flip it casually.
- PR ingestion now fails loudly if neither `GITHUB_TOKEN` / `SLEUTH_RAG_GITHUB_PAT` nor a healthy `gh auth login` is available. Pass `--no-prs` only if you intentionally want a files-only refresh.
- Synthesis (the answer step) still defaults to Gemini unless you pass `--retrieval-only` or configure a local synthesis provider in [ask_self/ask_self_harness.json](ask_self/ask_self_harness.json).

The wrappers require `ASK_SELF_PATH` to point at your local `ask-self` checkout (no default — the scripts fail loudly if it isn't set):

```bash
export ASK_SELF_PATH="$HOME/Documents/GitHub/ask-self"
```

### CLI reference

All tools are also available as CLI commands:

```bash
rebalance ask "What should I work on today?" --database rebalance.db
rebalance ask "What should I work on today?" --database rebalance.db --no-llm  # raw context only
rebalance query "embedding pipeline" --database rebalance.db                   # semantic search
rebalance search "project alpha" --database rebalance.db                       # keyword search
rebalance ingest notes --vault /path/to/vault --database rebalance.db          # re-ingest (delta)
rebalance ingest embed --database rebalance.db                                 # embed new chunks
rebalance github-scan --token <github-pat> --database rebalance.db             # refresh GitHub data
rebalance github-close-candidates --repo owner/name --database rebalance.db    # open issues likely fixed by merged PRs
rebalance calendar-sync --database rebalance.db                                # refresh calendar
rebalance calendar-daily-report                                                # today's events + project breakdown
rebalance calendar-weekly-report                                               # this week's summary + aggregator
rebalance calendar-weekly-report --vault /path/to/vault --write-week-note     # write week-of-YYYY-MM-DD.md and re-index it
rebalance calendar-daily-totals                                                # daily event count + duration stats
```

---

## License

Copyright 2025-2026 Hypercart DBA Neochrome, Inc.

Licensed under the **Apache License, Version 2.0**.

You may use, reproduce, modify, and distribute this software and its documentation under the terms of the Apache 2.0 License. Attribution is required — any redistribution must retain the above copyright notice.

See [APACHE-LICENSE-2.0.txt](./APACHE-LICENSE-2.0.txt) for the full license text, or visit https://www.apache.org/licenses/LICENSE-2.0.

---

## Contributing

Not open to contributions yet — getting the core right first. Watch the repo and come back when the first milestone lands.

---

*Built by [Hypercart](https://hypercart.com) — tools for agencies and solopreneurs who build on WordPress.*
