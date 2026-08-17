# Scheduler Policy

This table is the single source of truth for the launchd fleet. Every plist
template in `scripts/`, every wrapper script, and every installer must agree
with it — a divergence is a bug. `tests/test_scheduler_policy.py` enforces the
machine-checkable columns (label, cadence, wrapper, entry call/scope) against
the actual templates and scripts, and checks that this file documents every
job.

## Job table

| Job (label suffix) | Cadence | Wrapper | Work | Prerequisites | Outputs |
|---|---|---|---|---|---|
| `daily-sync` | daily 06:30 + RunAtLoad (boot/login catch-up) | `scripts/daily_sync.sh` | `refresh_index(db_path)` — default recipe: all raw sources + code/semantic/sync | vault path, GitHub token, calendar/sleuth auth as configured | SQLite knowledge base fully refreshed; dashboard note write-back |
| `vault-sync` | hourly at :15, 06:15–23:15 | `scripts/vault_sync.sh` | `refresh_index(db_path, scope=["vault", "semantic"])` | `vault_path` in temp/rbos.config | vault raw tables + semantic index fresh within the hour |
| `github-sync` | hourly at :45, 06:45–23:45 | `scripts/github_sync.sh` | `refresh_index(db_path, scope=["github", "focus5"])` | GitHub token (keyring/config) for github; Focus 5 needs none | github raw tables fresh (semantic backfill deferred to daily-sync); Focus 5 roster recomputed hourly |
| `pulse-sync` | hourly at :00, 06:00–23:00 | `scripts/pulse_sync.sh` | `publish_pulse(db_path, dry_run=False, push=True)` | pulse_* keys in temp/rbos.config; local clone at pulse_target_path | markdown status page pushed to private repo (only when changed) |
| `pulse-web-sync` | every 30 min at :08/:38, 06:00–23:38 | `scripts/pulse_web_sync.sh` | `scripts/pulse_web.py` | `vault_path` in temp/rbos.config (locates "0. Goals.md") | `web/pulse.html` regenerated atomically (local only, no network) |
| `pulse-server` | daemon: RunAtLoad + KeepAlive, ThrottleInterval 30s | `scripts/pulse_server.sh` | `scripts/pulse_server.py --port 8767` | port 8767 free | FastAPI server on 127.0.0.1:8767 (loopback only) |
| `pulse-warning-watch` | every 15 min at :07/:22/:37/:52, around the clock + RunAtLoad | — (python direct) | `scripts/pulse_warning_watch.py --url http://127.0.0.1:8767/` | pulse-server running on 8767 | `temp/pulse-warning-watch.jsonl` (one record per check) |
| `health-check` | hourly at :10, around the clock | — (python direct) | `scripts/health_issue_reporter.py --close` (FAIL-only, no LLM) | GitHub token for issue filing | GitHub issues opened/closed on failing doctor checks |
| `health-check-triage` | 3×/day at 08:25, 14:25, 20:25 | — (python direct) | `scripts/health_issue_reporter.py --warn --close --llm-triage --llm-daily-limit 8 --llm-max-per-run 5` | ANTHROPIC_API_KEY in rendered plist or keyring | LLM-triaged GitHub issues; quota circuit breakers CB-1/2/3 |
| `obsidian-rollover` | daily 00:40 (or next wake); RunAtLoad must stay **false** | `utils/obsidian_rollover.sh` | `utils/obsidian_daily_rollover.py` | Full Disk Access via bash wrapper (TCC) | daily note rolled over; log in `~/Library/Logs/rebalance-os/` |
| `obsidian-daily-sync` | daily 18:20 (or next wake); RunAtLoad **false**; a post-midnight catch-up skips itself | `utils/obsidian_daily_sync.sh` | `utils/obsidian_daily_sync.py` — Gemini daily-activity summary from the structured pulse snapshot | rebalance venv + Gemini API key; Full Disk Access via bash wrapper (TCC) | idempotent AI summary block appended to `0. Today's Notes.md`; log in `~/Library/Logs/rebalance-os/` |
| `git-pulse-daily-synthesis` | daily 18:30 (or next wake); RunAtLoad **false**; a post-midnight catch-up skips itself; **must stay after `obsidian-daily-sync`** | `utils/git_pulse_daily_synthesis.sh` | `utils/git_pulse_daily_synthesis.py` — Gemini synthesis of `view.sh --today` multi-device git activity (GH-114) | rebalance venv + Gemini API key; Full Disk Access via bash wrapper (TCC) for the optional vault write | idempotent Git Pulse summary block appended to `0. Today's Notes.md` (if vault configured) AND/OR upserted into `<pulse_target_path>/CLIO/git-pulse-daily-log.md` (if `git_pulse_clio_enabled`, git-committed+pushed); log in `~/Library/Logs/rebalance-os/` |

All labels are prefixed `com.rebalance-os.`. Experimental/utility agents
(`com.user.git-pulse`, `com.user.stickies2obsidian`) live in `experimental/`
and `utils/stickies-to-obsidian/` with their own installers and are out of
scope for this table.

## Freshness model (intentional, not accidental)

The hourly stagger is deliberate — readers trail writers inside each hour, and
since GH-175 **no two jobs share a minute**:

```
:00 pulse-sync (reads)
:07 pulse-warning-watch      :22      :37      :52
:08 pulse-web-sync (reads)   :38
:10 health-check
:15 vault-sync (writes vault + semantic)
:25 health-check-triage (08/14/20 only)
:45 github-sync (writes github raw only)
06:30 daily-sync (writes everything, incl. github → semantic backfill)
00:40 obsidian-rollover      18:20 obsidian-daily-sync      18:30 git-pulse-daily-synthesis
```

- **`obsidian-daily-sync` → `git-pulse-daily-synthesis` is an ORDERING
  DEPENDENCY, not just a stagger.** When both destinations are configured, the
  Git Pulse block must land *after* the GH-112 AI Daily Summary block. Both were
  moved together in GH-175 (18:00→18:20 and 18:05→18:30); moving one without the
  other inverts the order and puts the Git Pulse block above the AI summary.

- **pulse-web-sync moved off :00 for correctness, not tidiness** (GH-175). It is
  a derived read-only stage over what `pulse-sync` writes at :00; sharing that
  minute risked rendering from half-written state. :08 puts it clearly after.
- **pulse-warning-watch moved off the quarter hours** — on :00/:15/:30/:45 it
  collided with `pulse-sync`, `vault-sync`, `pulse-web-sync` and `github-sync` in
  turn. Same 15-minute cadence, no shared minute.
- This is *same-minute* de-confliction only. It does **not** address run-window
  overlap: `daily-sync` runs ~25–30 min from 06:30 and still spans `github-sync`
  at :45. That overlap is handled by GH-131's bounded SQLite retry.

- **vault-sync includes the `semantic` scope intentionally** — vault ingest
  alone only updates raw tables; the semantic backfill+embed is what makes a
  note edited at 10:05 searchable by 10:16.
- **github-sync intentionally excludes `semantic`** — hourly embedding of
  github docs is not worth the cost; the 06:30 daily-sync closes the gap. The
  lag is observable as the `github_documents_missing_from_semantic` drift
  metric (`index_status` MCP tool / `refresh_index` summary).
- **github-sync also carries `focus5`** — the Focus 5 collector is opt-in
  (`included_in_all=False`) and would otherwise never run unattended, leaving
  the roster frozen until a manual ↻ Refresh. It piggybacks the hourly github
  cadence rather than running its own launchd job: a device-local git scan
  (~30s, no network, no GitHub token) that recomputes `focus5_roster`. The web
  page stays non-blocking (PR #72) — this job is the background writer it reads.
- **pulse-sync and pulse-web-sync are read-only derived stages** — they render
  whatever the ingest jobs last wrote and never refresh sources themselves.
- **pulse-warning-watch depends on pulse-server** being up on 127.0.0.1:8767;
  a down server is itself a finding the watcher records.

## Shared mechanics

- Wrapper scripts source `scripts/lib/scheduler_common.sh`: env bootstrap
  (repo root, venv python, `PYTHONPATH=src`), per-day logs in `temp/logs/`
  (`<job_name>_YYYY-MM-DD.log`, dashes→underscores), job-lifecycle events
  (`job_started`/`job_completed`/`job_failed`) appended to
  `temp/logs/auth_activity.jsonl`, and retention trimming (30 days for
  daily-sync, 14 for the rest).
- Installers source `scripts/lib/install_common.sh`: chmod the wrapper,
  always-unload, render the template (`{{REBALANCE_DIR}}`, `{{PYTHON}}`,
  `{{HOME}}`), `plutil -lint`, load, poll-verify registration. Rendered plists
  live in `~/Library/LaunchAgents/` (gitignored).
- Python-direct jobs (no wrapper) log via launchd `StandardOutPath`/
  `StandardErrorPath` into `temp/logs/` instead of the dated wrapper logs;
  obsidian-rollover logs to `~/Library/Logs/rebalance-os/` because
  `~/Documents` is TCC-protected.

## Runbook

| Task | Command |
|---|---|
| Install / reinstall a job | `bash scripts/install_<job>_scheduler.sh` (daily-sync: `install_scheduler.sh`) |
| Check fleet status | `launchctl list \| grep rebalance` (also surfaced by `rebalance doctor`) |
| Run a job now | `bash scripts/<job>.sh` |
| Tail a job log | `cat temp/logs/<job_name>_$(date +%Y-%m-%d).log` |
| Job lifecycle history | `temp/logs/auth_activity.jsonl` (also `rebalance serve` → /auth-log) |
| Uninstall a job | `launchctl unload ~/Library/LaunchAgents/com.rebalance-os.<job>.plist && rm` same path |
| Verify templates match installed plists | render with the installer substitutions and `diff` against `~/Library/LaunchAgents/` |

Secrets: never put API keys in templates (tracked in git). The
health-check-triage job reads `ANTHROPIC_API_KEY` from the rendered plist or
keyring; reinstalling overwrites a hand-added key (the installer warns).
