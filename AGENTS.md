## Working with the rebalance MCP server (Codex, Gemini, Claude, others)

This repo **is** an MCP server. Every refresh and query path is exposed through MCP tools — do not scan the codebase for `rebalance ...` CLI commands or write ad-hoc shell pipelines. Reach for the tools first.

**"Find my recent work" queries.** When the user asks to find, summarize, or locate recent work/activity (what they've been doing, which project touched X recently, etc.), use `ask()`, `get_next_actions()`, `github_balance()`, `peek_source()`, or `publish_pulse()` — not Spotlight (`mdfind`) or ad-hoc filesystem search. The MCP's SQLite index is purpose-built for this and stays current via `refresh_index`. Reserve Spotlight/`find` for pure disk-location questions the registry doesn't track (e.g. "where did this repo get moved to on disk").

> ### 🧭 Start here — the central orchestrator (the data-plane spine)
>
> Every data source — `vault`, `github`, `calendar`, `sleuth`, `email`, `semantic` — is registered as a `Collector` in **[src/rebalance/ingest/index_ops.py](src/rebalance/ingest/index_ops.py)** (`register_collector` / `COLLECTORS`). That registry **is** the central orchestrator of the system: `refresh_index`, `index_status`, and the daily-sync cron all dispatch through it, and adding a source is one `register_collector(...)` call — no edits to the dispatch chain. **To understand or extend this system, read `index_ops.py` first.**
>
> - **Setup / health / "why is X empty?"** → run `rebalance doctor` (it names the exact remediation, e.g. a missing calendar OAuth token → `scripts/setup_calendar_oauth.py`). Don't grep for setup scripts.
> - **Orientation** → [ARCHITECTURE.md](ARCHITECTURE.md) (Signal Sources table, Source→Table fanout, "Adding a New Source"). Read it at session start.
> - **`querier.py`** is the read-side orchestrator (retrieval + synthesis); `index_ops.py` is the source/refresh orchestrator. Both consume the same source set — the direction to make `doctor`, the morning brief, and `querier` all iterate the one registry is in [PROJECT/2-WORKING/P1-MODULE-REGISTRY.md](PROJECT/2-WORKING/P1-MODULE-REGISTRY.md).

**Connection.** The repo ships two equivalent configs: [.vscode/mcp.json](.vscode/mcp.json) for VS Code agents and [.mcp.json](.mcp.json) at the repo root for tools that look there. Both launch `.venv/bin/python -m rebalance.mcp_server` over stdio with `REBALANCE_DB` set to the repo's `rebalance.db`.

**Single entry points (use these first):**

| Tool | When to call |
|---|---|
| `index_status()` | "Is the data fresh?" / "What's in the DB right now?" — read-only snapshot of every source + the unified semantic index, with drift indicators |
| `refresh_index(scope=[...], dry_run=?)` | "Refresh the local DB." `scope` accepts `vault` / `github` / `calendar` / `sleuth` / `semantic` / `all`. Always preview with `dry_run=True` first if scope includes `github` — that hits the GitHub API for every active project repo and can take minutes |
| `semantic_query(query, sources=[...], top_k=?)` | Cross-source vector search across the unified `semantic_documents` table |
| `list_watched_repos(since_days=?)` | Show the merged set of GitHub repos being monitored — project registry ∪ recent `github_activity` − ignored. Same set `refresh_index(scope=["github"])` syncs. Use this to debug coverage gaps |
| `publish_pulse(dry_run=?, push=?)` | Render today's + yesterday's activity into a markdown status page and publish it to a private pulse repo. Each row tagged by source (`claude-cloud` / `codex-cloud` / `lovable` / `local-vscode` / `human`) via `src/rebalance/ingest/agent_tags.py`. Reusable: every per-user value (`github_login`, `slack_user_id`, `pulse_target_path`, `pulse_filename`, `pulse_timezone`) lives in `temp/rbos.config` |

**On first interaction:** call `onboarding_status(vault_path)` to check setup state. If any steps are incomplete, walk the user through them in order. If you don't know the vault path, ask: "Where is your Obsidian vault? (absolute path)"

**Onboarding flow:**

1. **Check state:** `onboarding_status(vault_path)` — shows which steps are done/pending.
2. **GitHub PAT:** If `github_token_set` is false, ask the user for a PAT with `repo:read` scope. Call `setup_github_token(token)`. If it returns `valid: false`, ask for a corrected token.
3. **Discover projects:** Call `run_preflight(vault_path)`. Present results using friendly labels: "Most active" = `most_likely_active_projects` (last 14 days), "Semi-active" = `semi_active_projects` (15–30 days), "Dormant" = `dormant_projects` (31+ days), "Vault only" = `potential_projects`. If `github_error` is set, inform the user that GitHub discovery failed. Ask which to keep, remove, or merge. For each kept project, collect: short summary (2–3 sentences) and priority tier (1–5).
4. **Confirm:** Call `confirm_projects(projects, vault_path)`. Each project dict **must** include `status: "active"`. Minimum shape: `{name, status: "active", summary, repos: [], priority_tier: int, tags: []}`.
5. **Verify:** Call `list_projects()` to confirm projects are queryable.
6. **Initial refresh:** Call `refresh_index(scope=["all"])` to populate the SQLite knowledge base. Use `dry_run=True` first for a preview. After it completes, `github_balance()` will return per-project commit/PR/issue counts.

**Onboarding & project tools:**

| Tool | Purpose |
|---|---|
| `onboarding_status(vault_path)` | Check which setup steps are complete |
| `setup_github_token(token)` | Validate and store a GitHub PAT |
| `run_preflight(vault_path)` | Discover project candidates (read-only) |
| `confirm_projects(projects, vault_path)` | Write registry and sync to DB |
| `list_projects(status?)` | Query projects (default: active) |
| `github_balance(since_days?)` | GitHub activity per project (requires prior refresh) |

**Targeted retrieval (older, per-source — still valid):**

| Tool | Purpose |
|---|---|
| `query_notes(query, top_k?)` | Vault-only vector search (legacy `embeddings` table) |
| `search_vault(keyword, limit?)` | Full-text/keyword search over vault |
| `query_github_context(query, repo?, top_k?)` | GitHub-only vector search (legacy `github_embeddings`) |
| `ask(query, since_days?, skip_synthesis?)` | Combined context + optional local LLM synthesis |
| `github_release_readiness(repo, milestone?)` | Milestone readiness inferred from local corpus |
| `github_close_candidates(repo)` | Issues likely closed by merged PRs |

**Key paths:**
- Registry: `{vault_path}/Projects/00-project-registry.md`
- Config: `temp/rbos.config` (gitignored, repo root)
- Database: resolved from `REBALANCE_DB` env var (set in `.vscode/mcp.json`)
- Architecture docs: `ARCHITECTURE.md`, `MCP.md`, `PROJECT/PDDA.md`

**Background refresh.** A launchd job (`com.rebalance-os.daily-sync`) runs [scripts/daily_sync.sh](scripts/daily_sync.sh) at 6:30 AM daily and on boot. The script invokes the same `refresh_index(scope=["all"])` orchestration, so the cron and the MCP tool share one code path. If the index looks stale, check `temp/logs/daily_sync_YYYY-MM-DD.log` before manually re-running.

**Hourly pulse publish.** A second launchd job (`com.rebalance-os.pulse-sync`) runs [scripts/pulse_sync.sh](scripts/pulse_sync.sh) on the hour, every hour from 6 AM to 11 PM local. It calls the same `publish_pulse()` orchestration the MCP tool exposes — render markdown, commit + push to the configured private pulse repo only when content actually changed. Logs in `temp/logs/pulse_sync_YYYY-MM-DD.log`. Install via `bash scripts/install_pulse_scheduler.sh`. Public users wanting to reuse this only need to populate the pulse keys in their own `temp/rbos.config` and point at their own private clone.

**Source of truth for the orchestration:** [src/rebalance/ingest/index_ops.py](src/rebalance/ingest/index_ops.py). Only edit there if you need to change refresh behavior — the MCP wrappers in `src/rebalance/mcp/` (25 tools across 7 domain modules; `mcp_server.py` is a 5-line backward-compat shim) and `daily_sync.sh` are thin and should stay that way.

**Repo coverage.** `refresh_index(scope=["github"])` no longer requires every monitored repo to be in the active project registry. It auto-merges `project_repos ∪ activity_repos` (from `github_activity`, last 14 days) and skips `github_ignored_repos`. Use `list_watched_repos()` for the canonical view. The `refresh_index` orchestration and the `pulse` renderer both consume the same set, so a repo only has to appear once for everything downstream to see it.

**Auto-promotion (GH-124).** `refresh_index(scope=["github"])` also auto-promotes a watched-but-unconfirmed repo into `project_registry` (as a `machine_owned` row, never overwriting a curated one) once the operator has authored `auto_promote_commit_threshold` commits to it (default 3; config in `config.py::get_auto_promote_config()`). So `list_projects()` can grow entries you never explicitly confirmed — check `custom_fields.provenance == "auto_promoted"` before assuming a project was hand-curated. Each promotion is surfaced non-silently: a `project_auto_promoted` event on `/auth-log` and a "New repo added" banner on the pulse dashboard's repo-activity chart.

## Communication & Documentation

- Precise, concise chat replies/updates: Short as possible, detailed enough.
- Reduce redundancy/duplication unless critical.
- New docs: High-level TOC at top; checklist + phased format; actionable items visible. Suggest Phase 0 technical spike (1-2h max) to validate assumptions/critical paths first.
- Do not create new MD/text files unless instructed or it is a new audit. Append to existing project docs.
- Add things to remember to MEMORY.md
- General workflow: 1-2 step ad-hoc requests to direct implementation. If 4-5 steps with multiple phases, write project MD file first.
- Slight pushback OK if security/maintainability/destructive risk ahead.

## UI Design

- Layout follows the user's decision sequence, not the system's data structure.
- Label roles at the point of action — if the user must scroll or remember context to understand what a control does, the label is missing.
- Every repeated component (card, row, panel) must be self-describing without surrounding context.
- Design for how the user reads, not how the data is stored or fetched.
- Default to the most common action. If 80% of users will pick the same option, pre-select it — don't make the majority click what the system already knows.

## Code & Architecture

> For the *why* behind these rules, see [GUIDING-PRINCIPLES.md](./GUIDING-PRINCIPLES.md).

- Code: DRY, SOLID; balance maintainability, performance, secure. Comply with framework security best practices.
- **Pre-flight Search Rule**: Before writing any new utility function or system layer, you MUST use `grep_search` or MCP `search_graph` to check if a similar function exists (e.g., date parsing, JSON handling). If it exists, import it. Do not duplicate it.
- **Centralization Rule**: All standard data formatting and OS-level operations (like datetime parsing, json dumping, git calls) must use `src/rebalance/lib/*` modules instead of creating local helper methods in the collector.
- **State Management**: Introduce FSM (Finite State Machine) if state transitions exceed 4 distinct states or more than one conditional branch per state. Document the state diagram in code comments, or in the owning `PROJECT/**` doc.
- **Contracts**: Designate single writer per contract/schema (API response shape, DB record structure, queue message format). Changes require review from contract owner; broadcast breaking changes immediately.
- **Pipelines**: One logical pipeline per data flow whenever possible. Avoid forking/rejoining; use filters, transforms, and side effects in sequence. If pipeline needs multiple paths, use conditional routing within single pipeline, not separate pipelines.
- **Collectors, sources & write paths** (see `PROJECT/2-WORKING/COLLECTOR-PATH-AND-PORTABILITY-AUDIT.md`):
  - **Classify before you register.** Every scope is exactly one of: raw source / derived scan / projection / export. Only raw sources are `all`-eligible; derived/projection/export attach as named stages, never as peers in the registry.
  - **One writer per table.** Only the `semantic` stage writes `semantic_documents`/`semantic_embeddings`; a source writes only its own raw tables. (This is the Contracts rule above, applied to the semantic tables.)
  - **Route user-facing writes through the orchestrator.** CLI, MCP, scheduler, and web write surfaces call `refresh_index` or one source-owned helper — never a leaf ingest function (`sync_*`, `ingest_*`, `embed_*`, `backfill_*`) directly.
  - **Use the shared resolvers** for any new runtime path (DB, secrets, auth/token, operator config). No `Path.home()` token paths, no `parents[N]` repo-root walks, no sibling-checkout assumptions.
  - **Obsidian/vault is optional output, not a control-plane dependency** — a refresh must succeed with no vault present.
  - **Name settings by what they are**, not the first feature that used them (e.g. `ask_self_scan_roots` → `repo_scan_roots`).
  - These are the **target contract**: the route-through-orchestrator and stage-owned-semantic rules bind *new* code; the audit owns migrating existing call sites. Enforce mechanically, not by prose — drift slipped past these same principles once already. Ship the contract tests (single-writer on the semantic tables, `all`-expansion, "no user-facing surface imports a leaf ingest fn") so a violation fails CI instead of accreting.
  - **Current scope taxonomy (Phase 1, 2026-06-10)** — canonical home until `ARCHITECTURE.md` is re-segmented (it's regenerated by ask-self ingest, so not durable yet):
    - **raw sources** (the `all` token): `vault`, `github`, `calendar`, `sleuth`, `email`. `figma` is a raw source but **opt-in** (needs PAT + file-key allowlist).
    - **derived scans:** `code`, `focus5`, `ask_self`.  **projection:** `semantic`.  **export:** `sync`.
    - **`all`** = raw sources only. **Default recipe** (no-scope `rebalance refresh` / `refresh_index(scope=None)`) = `all` + `code` + `semantic` + `sync`. Opt-in scopes (`figma`/`focus5`/`ask_self`) must be requested by name.

## Anti-Patterns to Avoid

- N+1 queries (e.g., loop API/DB calls; batch/paginate instead).
- Unpaginated API/DB calls (always use `per_page=100`, `page` iteration).
- Unbound DB queries (add `LIMIT 1000`, timeouts).
- Infinite loops/recursion without bounds.
- High-rate API bursts (respect GitHub 5000/hr PAT limits; sleep/retry).
- Hardcoding credentials or secrets in code or config files.
- Destructive operations without explicit confirmation or dry-run support.

## Security & Credentials

- Do not store credentials, personal/project/client names, most emails in repo unless in confirmed gitignored `/temp/` or config folder. Double-check for leaks.
- Use environment variables or `.env` files (always gitignore `.env`). Never hardcode credentials.
- For production integrations, reference Vault, AWS Secrets Manager, or equivalent secret storage.
- Log credential usage (masked) to audit trail; log actual credential values only to secure, non-repository logs.
- Mask sensitive data in logs (credentials, tokens, email addresses).

## Destructive Operations

- Log all DELETE/DROP/TRUNCATE operations with timestamp, user, and target to `/logs/agent-audit.json`.
- Require explicit confirmation flag (e.g., `--confirm` or env var `CONFIRM_DESTRUCTIVE=true`) before executing.
- Support `--dry-run` mode when applicable; output what _would_ be deleted without executing.
- If operation affects >1000 rows/records, require additional confirmation or escalation.
- Pause and escalate if operation is blocked or validation fails; do not retry silently.

## Observability & Tests From Day One

- Every new service, plugin, or pipeline ships with structured logging, health checks, and at least one integration test before merging to main.
- Instrument first, optimize later. Add timing/counters to critical paths (DB queries, API calls, queue processing) at build time — retrofitting observability is 5x harder.
- Log with context: every log line should include enough to trace a request end-to-end (request ID, tenant/user ID, operation name). Avoid generic messages like "error occurred."
- Health check endpoints (`/healthz`, `wp-admin` heartbeat, cron verification) are not optional — they are part of the definition of done.
- Write the smoke test that proves the happy path works before writing any feature code. If you can't test it, you can't ship it.
- Alerts should be actionable. If a threshold fires, the runbook or next step should be obvious. No alert without a documented response.
- For WordPress/WooCommerce: hook into `query_monitor` data, log slow queries (>500ms), and monitor Action Scheduler queue depth from the start.
- Dashboards and log queries are deliverables, not afterthoughts. Include them in the PR or project doc alongside the code.

## Testing & Mock Harnesses

- Write tests _before_ integrating with external APIs. Use mock harnesses to simulate responses.
- Mock harnesses should cover: happy path, rate limits (429), timeouts (504), malformed responses, and auth failures (401/403).
- Store mock response fixtures in `/fixtures/` (JSON, YAML, or plaintext). Keep them realistic and versioned.
- Use conditional logic or env vars (`MOCK_MODE=true`) to toggle between real and mock backends without code changes.
- For external integrations (Shopify, WooCommerce, Meta Ads, GA4), create a mock server or HTTP interceptor (e.g., `nock` in Node, `responses` in Python, `http-mock` in Go).
- Test both sync and async paths separately; async errors (timeouts, retries) are common blindspots.
- Assert on side effects (logs, DB writes, queue messages) not just return values. Mock should verify agent behavior, not just response parsing.

## Versioning & Changelog

- There is no concept of "Unreleased." Every fix or feature gets a version bump at time of commit/merge.
- Use semver: MAJOR for breaking changes, MINOR for features, PATCH for fixes.
- Documentation-only changes do not increment version unless explicitly instructed.
- Changelog entries describe _what changed and why_ in plain language. Do not include project names, filenames, or folder paths in changelog entries — those belong in `4X4.md` or project docs, not the changelog.
- Format: `## [x.y.z] - YYYY-MM-DD` followed by `### Added`, `### Changed`, `### Fixed`, `### Removed` as applicable.

## Monitoring & Safety

- Audit deps weekly (`safety check`, Dependabot).
- Rate limit APIs; exponential backoff on 429s.

### 3-Eyes — the local job supervisor (read this before touching scheduled jobs)

**3-Eyes is the sentinel system for this machine's scheduled jobs.** It supersedes the earlier
Cactus-Needle sentinel, which was disabled on 2026-07-27 (its four `com.neochro.*` launchd agents
are parked in `~/Library/LaunchAgents/.disabled-cactus-sentinel-2026-07-27/`). Do not reintroduce a
second supervisor — one machine, one sentinel.

- **Code:** `utils/3-eyes/` · **Plan:** [PROJECT/2-WORKING/GH-195-UNIFIED-SENTINEL.md](PROJECT/2-WORKING/GH-195-UNIFIED-SENTINEL.md)
- **Status / inventory:** `cd utils/3-eyes && PYTHONPATH=$PWD python3 -m three_eyes status`
- **Skill:** `/3-eyes` for job health; `/launchd-triage` for raw launchd triage beneath it
- **Inert by default.** A clone without a gitignored `config/runtime.env` is a clean no-op —
  "3-Eyes says nothing" on a fresh machine means *not activated*, not *nothing wrong*.

**Known gap (2026-07-27): the registry does not match reality.** `registry/jobs.d/` lists
`collector-health` and `selfcheck`, but `3eyes.skill-sync` is loaded in launchd and firing every
120 s without a registry entry. A supervisor that doesn't know about one of its own jobs is the
condition 3-Eyes exists to prevent — reconcile before trusting its inventory.

## Phase 0 Technical Spikes

- When proposing phased work, include Phase 0 spike (1–2h max) to validate critical assumptions.
- Phase 0 should test: API availability, DB connectivity, performance baseline, and blocking dependencies.
- If Phase 0 surfaces blockers or contradicts assumptions, pause and escalate; do not proceed to Phase 1.
- Document Phase 0 findings in spike report before committing to later phases.

---

## Known MCP tool gaps (as of 2026-06-02)

Observed in a real session where the MCP surface was unavailable and CLI/SQLite fallbacks were used. Record here so future agents know what to work around or fix.

| # | Gap | Impact | Owner action |
|---|-----|--------|--------------|
| 1 | **Runtime/docs sync** — AGENTS.md says "use MCP tools first" but the MCP server may not be callable at session start | Agent wastes time on MCP calls before falling back to CLI | Add a session-start connectivity check; verify tool list is live before instructing agents to prefer it |
| 2 | **`semantic_query()` has no time filter** — no `since_days`, `updated_after`, or `updated_before` | Date-bounded investigations require raw SQL fallback | Add time filter to `semantic_query` MCP tool and underlying query in `src/rebalance/ingest/db/semantic.py` |
| 3 | **`semantic_query()` weak filtering** — no `repo`, exact/keyword mode, or source metadata filter | Noisy recall for short/ambiguous terms | Add `repo`, `mode` (semantic/keyword), and `source` filter params |
| 4 | **CLI `semantic-query` hides `updated_at`** — returned by query, stripped from output | Slows triage; requires raw SQL to see timestamps | Expose `updated_at` in the CLI table output |
| 5 | ⚠️ **SECURITY: live API key surfaced in semantic results** — a vault note containing a live credential was indexed and returned by `semantic_query` | Key exposure via any agent that can call the tool | Add pre-embed redaction (strip key-shaped patterns) in `note_ingester.py` and/or a vault note exclusion mechanism (frontmatter `index: false` or path exclusion). **Fix before next vault ingest.** |

---

## Agent rulebooks (read before editing generated docs)

Some generated artifacts in this repo ship with placeholder prose that any agent
(Claude Code, Codex, Copilot, Gemini) is expected to fill in. Each has an
authoritative rulebook that should be read first.

| Artifact | Rulebook | Notes |
|---|---|---|
| Git Pulse Executive Recap (`reports/YYYY-MM-*.md`) | [experimental/git-pulse/EXEC-SUMMARY.md](experimental/git-pulse/EXEC-SUMMARY.md) | Claude Code skill `git-pulse-exec-recap` via `.claude/skills/` |
| Git Pulse Team Recap (`team-reports/YYYY-MM-*.md`) | [experimental/git-pulse/TEAM-EXEC-SUMMARY.md](experimental/git-pulse/TEAM-EXEC-SUMMARY.md) | Claude Code skill `git-pulse-team-recap` via `.claude/skills/` |

The generated recap itself carries the same pointer in its top-of-file instructions block, so agents that open the file directly will also find the rulebook without needing this index.