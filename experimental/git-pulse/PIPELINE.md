# Git Pulse End-to-End ETL Pipeline

This doc describes the full data flow from raw git activity → executive-style recap markdown, across both the personal pipeline (local commits from your own machines) and the team pipeline (remote-repo activity from everyone).

It's a living reference. When the pipeline changes, update this doc.

## At a glance

```
                       PERSONAL PIPELINE                                           TEAM PIPELINE
                       (your local commits)                                    (everyone on a remote repo)

    launchd ─────▶ collect.sh ─▶ pulse-<device>.md         manual ────▶ team-collect.py ─▶ team-pulses/<owner>-<repo>.tsv
    (per machine)    reflog walker  │  (6-col TSV, UTC)                  GitHub API           │ (11-col TSV, local+UTC)
                                    │                                                         │
                                    ▼                                                         │
                              ┌─────────────┐                                                 │
                              │  sync repo  │  (GitHub-synced, shared across machines)        │
                              │  (checkout) │                                                 │
                              └──────┬──────┘                                                 │
                                     │                                                        │
    view.sh / view.py ───▶ reports/*.tsv    ◀────── merges multiple pulse-*.md files          │
    (range report)          (9-col TSV, adds local_day/time + device_name)                    │
                                     │                                                        │
                                     ▼                                                        ▼
    recap.py ────────────▶ reports/YYYY-MM-*.md                     team-recap.py ──▶ team-reports/YYYY-MM-*.md
    (per-month split,       (placeholder markers for agent prose)   (per-month split,   (placeholder markers)
     By Repo grouping)                                               By Contributor)
                                     │                                                        │
                                     ▼                                                        ▼
    ┌────────────────────────────────────────────────────────────────────────────────────────┐
    │  Agent layer (Claude Code / Codex / Copilot / Gemini):                                 │
    │  - Reads the recap file                                                                │
    │  - Follows AGENT INSTRUCTIONS at the top (points at EXEC-SUMMARY.md / TEAM-EXEC-…)     │
    │  - Replaces <!-- TLDR: --> / <!-- FOCUS: --> / <!-- OBSERVATIONS: --> with prose       │
    │  - Strips the AGENT INSTRUCTIONS block                                                 │
    └────────────────────────────────────────────────────────────────────────────────────────┘

    Planned (see PROJECT/1-INBOX/P1-SQLITE.md):
    ────────────────────────────────────────────
    pulse-*.md + reports/*.tsv + team-pulses/*.tsv ──▶ SQLite at ~/Library/Application Support/git-pulse/history.sqlite
                                                       (commit_observations table, FTS5, optional sqlite-vec)
                                                       └─▶ future MCP tools for historical retrieval
```

## Storage layout

All paths below are relative to `sync_repo_dir`, which comes from `~/.config/git-pulse/config.sh`. The sync repo is a **GitHub-synced folder** (not iCloud). As of writing, that resolves to `~/Documents/GH Repos/rebalance-git-pulse/`.

```
{sync_repo_dir}/
├── devices/
│   └── <device_id>.yaml                ← per-machine metadata (device_name, hostname, tz, pulse_file)
├── pulse-<device_id>.md                ← append-only per-machine commit log (6-col TSV, UTC)
├── reports/
│   ├── <name>.tsv                      ← range reports from view.sh (9-col TSV, adds local time + device_name)
│   └── YYYY-MM-*.md                    ← per-month exec recaps from recap.py
├── team-pulses/
│   └── <owner>-<repo>.tsv              ← team-collect.py output (11-col TSV, includes author + kind + pr_number)
└── team-reports/
    └── YYYY-MM-*.md                    ← per-month team exec recaps from team-recap.py

~/Library/Application Support/git-pulse/
└── history.sqlite                      ← planned: canonical SQLite history (local-only, per-machine, not synced)
```

## Personal pipeline

### 1. Extract — `collect.sh`

Invoked by launchd every N minutes (configured during `install.sh`). On each run:

- Walks `git reflog --date=iso-strict` for each repo in the `repos=(...)` array in `config.sh`
- Filters to commit/amend reflog entries (skips fetches, merges, rebases, cherry-picks)
- Writes one tab-separated row per new commit to `pulse-<device_id>.md`:
  ```
  epoch_utc \t timestamp_utc \t repo \t branch \t short_sha \t subject
  ```
- Appends, commits, and pushes to the GitHub sync repo

**Device identity** (two fields, two purposes):
- `device_id` — friendly slug derived from `scutil --get ComputerName`, lowercased, slug-normalized. Used for filenames (`pulse-<device_id>.md`) and display. Can change across renames and slug-rule updates.
- `hardware_uuid` — stable hardware-backed identifier (macOS `IOPlatformUUID` via `ioreg`, Linux `/etc/machine-id` fallback). Survives renames, slug changes, and OS reinstalls on the same hardware. Written to `devices/<device_id>.yaml` on every `collect.sh` run (`schema_version: 2`). The [Phase 1 SQLite layer](../../PROJECT/1-INBOX/P1-SQLITE.md) keys canonical dedup off `hardware_uuid`, with the slug as a display-only fallback for pre-UUID observations.

**Pulse file format:** UTC-only. Local time is computed downstream at render time — see the view/recap notes below for the actual (not ideal) timezone behavior.

### 2. Transform — `view.sh` (range reports)

Invoked manually. Reads pulse files from multiple machines (the sync repo merges them) and emits a merged 9-column TSV to `reports/<name>.tsv`:

```
local_day \t local_time \t utc_time \t device_id \t device_name \t repo \t branch \t short_sha \t subject
```

**Current timezone behavior (rough edge, not the ideal):** `local_day`/`local_time` are computed using the timezone of **the machine running `view.sh`** (via `date -r $epoch`), **not** the timezone of the device that originally authored the commit. That means running `view.sh` from Pacific time on commits authored in Eastern time re-stamps them with Pacific-local days. Cross-timezone rollups are viewer-dependent today; the Phase 1 SQLite layer persists per-observation timezone fields so queries can bypass this. Multiple range reports can coexist (e.g., `combined-14-day.tsv`, `combined-21-day.tsv`); `recap.py` handles the overlap via dedupe.

### 3. Load — `recap.py` (exec recap)

Invoked manually. Default: reads `reports/*.tsv`, dedupes, splits by calendar month, writes per-month files to `reports/YYYY-MM-*.md`.

**Filename rules** (shared with team pipeline via `pulse_common.month_auto_filename`):
- Full calendar month (first covered day = day 1, last = last of month): `YYYY-MM-MON.md` (e.g., `2026-02-FEB.md`)
- Partial month: `YYYY-MM-DD-PARTIAL.md` where `DD` is the last covered day in that month
- Multi-month windows split into one file per month, each standalone

**Structure of each recap:**
- Agent instructions block (strippable)
- `## Summary` with repos covered, commit counts, most active repo/machine
- `<!-- TLDR: -->` placeholder
- `## By Repo` — per-repo section, commits grouped by conventional-commit prefix
- `<!-- FOCUS: -->` placeholder per repo
- `## Observations` with `<!-- OBSERVATIONS: -->` placeholder
- `## Appendix` with the raw tables (Coverage, Machines, Repos, Cross-Machine Repos, Daily Activity, Recent Activity, Exceptions)

`--output PATH` bypasses month-splitting and writes a single combined recap for backward compatibility.

## Team pipeline

### 1. Extract — `team-collect.py`

Invoked manually. Queries the GitHub REST API for each `--repo owner/name`:

- Default-branch commits since `--since` (default 30 days ago)
- All PRs (any state) with `updated_at >= since`; recorded by `created_at`
- Extra branches via repeatable `--branch` flag

Auth: `--token` or `GITHUB_TOKEN` / `GH_TOKEN` env. Required scope: `repo:read` for public, `repo` for private.

Output: `{sync_repo_dir}/team-pulses/<owner>-<repo>.tsv` with 11 columns:

```
local_day \t local_time \t utc_time \t author_login \t author_name \t repo \t branch \t short_sha \t subject \t kind \t pr_number
```

`kind` is `commit` or `pr`. `short_sha` is empty for PRs; `pr_number` is empty for commits.

### 2. Transform + Load — `team-recap.py`

Same structure as `recap.py` but grouped by contributor instead of repo. Reads `team-pulses/*.tsv`, splits by month, writes to `team-reports/YYYY-MM-*.md`.

**Recap structure:**
- `## Summary` includes contributors list, commits + PRs counts, most active contributor
- `## By Contributor` — one `### @login` block per person, listing activity by repo (commits by conv-commit theme + PRs list)
- Observations target team patterns (bus factor, handoff flow, PR cadence)

## Agent layer

Each recap ships with an `AGENT INSTRUCTIONS` block pointing at a rulebook. An agent editing the file follows the skill, replaces the three placeholder types, and strips the instructions block.

| Recap type | Rulebook | Claude Code skill |
|---|---|---|
| Personal (`reports/YYYY-MM-*.md`) | [EXEC-SUMMARY.md](EXEC-SUMMARY.md) | `git-pulse-exec-recap` (via `.claude/skills/`) |
| Team (`team-reports/YYYY-MM-*.md`) | [TEAM-EXEC-SUMMARY.md](TEAM-EXEC-SUMMARY.md) | `git-pulse-team-recap` (via `.claude/skills/`) |

Placeholders:
- `<!-- TLDR: -->` — 1–2 sentences at the top
- `<!-- FOCUS: -->` — 2–3 sentences per repo (personal) or per contributor (team)
- `<!-- OBSERVATIONS: -->` — 3–5 bullets

The rulebooks enforce the executive-report tone (no SHAs, no commit subjects, themes over lists).

## Shared code

[pulse_common.py](pulse_common.py) holds utilities shared by `recap.py` and `team-recap.py`:

- `CONV_PREFIX_RE`, `GROUP_ORDER` — conventional-commit classification
- `classify_subject` — assigns a commit subject to a theme bucket
- `split_rows_by_month` — partitions rows by `(year, month)` using the `local_day` field (Protocol-typed, works with either row dataclass)
- `month_auto_filename` — applies the FULL vs. PARTIAL filename rules
- `load_sync_repo_dir` — resolves `sync_repo_dir` from the git-pulse config
- `markdown_cell`, `current_utc_iso` — small rendering helpers

## Scheduling

| Component | Trigger | Frequency |
|---|---|---|
| `collect.sh` | launchd plist `com.user.git-pulse.plist` | Per-machine, every N minutes (config-defined) |
| `view.sh` | Manual | As needed to produce a range report |
| `recap.py` | Manual (or ad-hoc cron) | As needed to rebuild monthly recaps |
| `team-collect.py` | Manual | On demand for team summaries |
| `team-recap.py` | Manual | After a fresh `team-collect.py` run |

The team pipeline is currently all-manual. A scheduled team scan is future work.

## Future: SQLite history layer

Planning doc: [P1-SQLITE.md](../../PROJECT/1-INBOX/P1-SQLITE.md).

The Phase 0 spike ([sqlite_spike.py](sqlite_spike.py)) proves ingest is trivially fast and FTS5 + `sqlite-vec` are both available. Phase 1 introduces a `commit_observations` table at `~/Library/Application Support/git-pulse/history.sqlite` that ingests `pulse-*.md`, `reports/*.tsv`, and `team-pulses/*.tsv` as first-class sources. Recap rendering and retrieval eventually read from this layer instead of re-parsing TSVs.

## Known rough edges

- **Metadata migration bug (mitigated, not fully resolved):** some `devices/<id>.yaml` files were renamed during an earlier ID normalization but their internal `device_id:` value still holds the legacy slug, which manifests as ghost rows in the Coverage table. `collect.sh` now rewrites the full YAML content on every run and adds `hardware_uuid` for forward-looking canonical dedup, so the ghost rows disappear as soon as each affected machine runs the updated collector. Machines that haven't pulled the new code and re-run will still show the stale content.
- **`view.sh` timezone is viewer-dependent, not commit-local:** described above. Until `view.sh` reads the source device's `timezone_name` from the devices YAML, cross-timezone `local_day`/`local_time` in `reports/*.tsv` reflect where `view.sh` ran, not where the commit happened. Phase 1 SQLite ingest stores per-observation timezone fields so queries can bypass this, but recaps rendered from TSVs still inherit the viewer's TZ until view.sh is fixed.
- **Short SHAs are not a safe canonical identity:** today's pulse and team TSVs store only 7-char short SHAs. Short SHAs are not unique within a repo over time. Phase 1 planning treats `full_sha` as the canonical commit identity; both `collect.sh` (pulse format) and `team-collect.py` (team TSV schema) need a small upgrade to emit the full SHA before the SQLite layer can fully rely on it.
- **Ingest source hierarchy is inverted in practice:** the original assumption was `pulse-*.md` = primary, `reports/*.tsv` = secondary. Phase 0 showed the opposite (TSVs carry most current history). The Phase 1 plan now treats them as co-equal first-class sources.
- **Pulse files under-populated** for at least one machine in the current dataset. Indicates the launchd collector isn't running everywhere. A Phase 1 consistency check will flag this automatically.
- **Team pipeline is append-overwrite** (each run replaces the TSV) rather than append-only. History beyond the current `--since` window is lost on re-run. Acceptable for v1; revisit if historical team recall becomes load-bearing.
