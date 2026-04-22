# Git Pulse Historical Retrieval Plan

## TOC
- Current State
- Goals
- Data Source And Storage Decision
- Architecture Direction
- Phase 0 Technical Spike
- Phase 1 Canonical SQLite Layer
- Phase 2 Exact Retrieval And Operator Reports
- Phase 3 Semantic Retrieval
- Phase 4 MCP And Workflow Integration
- Contracts And Ownership
- Risks And Guardrails
- Success Criteria
- Open Questions

## Current State

Git Pulse already has the passive collection layer:

- Per-machine raw commit logs in the sync repo as `pulse-<device_id>.md`
- Per-machine metadata in `devices/<device_id>.yaml`
- Flat TSV range reports from `git-pulse-view`
- A Markdown recap layer from `git-pulse-recap`

What it does not yet have is a canonical historical query layer. Right now, historical reconstruction depends on reading markdown and TSV exports directly. That is workable for recent manual review, but it is weak for:

- Cross-machine historical search
- Stable dedupe across overlapping saved reports
- Device-id migration and alias cleanup
- Time-window rollups over months instead of days
- Higher-quality retrieval for local agents

## Goals

- [ ] Treat raw pulse files and `reports/*.tsv` as **co-equal first-class** ingest sources (distinguished by `source_type`). The Phase 0 spike showed that `reports/*.tsv` currently carries most of the usable history because the launchd collector isn't running on every machine, so elevating TSVs is a present-day correctness requirement, not an optional reconciliation hook.
- [ ] Build one canonical SQLite history layer over the synced data
- [ ] Support exact historical retrieval first with SQL + FTS
- [ ] Add semantic retrieval only where it improves recall over sparse commit subjects
- [ ] Keep the implementation in this repo under `experimental/git-pulse/`
- [ ] Resolve the GitHub-backed sync folder strictly from `sync_repo_dir` in `~/.config/git-pulse/config.sh` (same contract as `collect.sh`, `view.sh`, `recap.py`, and the team pipeline). No hardcoded default path; fail fast if the config is missing.

## Data Source And Storage Decision

Raw (shared) data root:

- Resolved from the existing git-pulse config contract: `sync_repo_dir` in `~/.config/git-pulse/config.sh` (the same path `collect.sh`, `view.sh`, `recap.py`, and the team pipeline already use)
- This is the GitHub-synced folder, not an iCloud-synced folder
- **iCloud Drive must not sync this folder.** SQLite's WAL/journal files are incompatible with iCloud's opportunistic file sync and corrupt over time. If `~/Documents` is iCloud-synced on the host machine, either disable Desktop & Documents for that folder or keep the raw folder outside `~/Documents` entirely.

Use that folder for (unchanged from today):

- `pulse-*.md`
- `devices/*.yaml`
- `reports/*.tsv`
- `reports/*.md`
- `team-pulses/*.tsv` (team pipeline, added in the team-collect work)
- `team-reports/*.md`

Derived data (SQLite history layer):

- Path: `~/Library/Application Support/git-pulse/history.sqlite`
- Per-machine, local-only. Not synced through GitHub. Not synced through iCloud.
- Override via `GIT_PULSE_DB_PATH` env var for operator convenience (e.g. testing, scratch DBs)
- Lives outside the sync repo entirely, so no `.gitignore` entry is needed

Reasoning for the split:

- Raw artifacts stay in the shared folder so every machine converges on the same source of truth
- The derived DB is a computed artifact — cheaper to rebuild than to replicate, and replicating it across machines via GitHub or iCloud invites corruption
- Each machine's local DB reflects that machine's latest sync state; no cross-machine SQLite writes

Default/fallback behavior:

- Raw root resolved strictly from `sync_repo_dir` in `config.sh`. If config is missing, fail fast — do not invent a default path
- If the derived DB path is unavailable or read-only, fail fast with a clear operator error and no partial ingest writes

## Architecture Direction

Target layers:

1. Raw sync artifacts
   - `pulse-*.md`
   - `devices/*.yaml`
   - saved TSV reports

2. Canonical SQLite history layer
   - normalized commits table
   - device alias table
   - ingest runs table
   - source file inventory
   - optional report row cache

3. Exact retrieval layer
   - SQL filters
   - FTS5 over commit subjects and grouped summaries

4. Semantic retrieval layer
   - embeddings for grouped summaries, not raw rows
   - `sqlite-vec` only after the exact layer proves insufficient

Recommended schema direction:

- `devices`
  - hardware_uuid (canonical primary key — stable across renames, reinstalls, slug changes)
  - device_id (friendly slug used for filenames and display only; not a dedup key)
  - display name
  - hostname
  - timezone_name
  - utc_offset
  - pulse_file
  - first_seen_utc
  - last_seen_utc
  - status

- `device_aliases`
  - alias device_id (the old slug)
  - canonical hardware_uuid (what it resolves to)
  - reason
  - first_seen_utc
  - last_seen_utc

- `commit_observations` (renamed from `commits` — each row is a device-specific observation of a commit, not a globally-canonical commit row; this is deliberate so we can answer "which machines have seen commit X")
  - row id
  - hardware_uuid (FK to `devices.hardware_uuid`; nullable for team-sourced rows and for legacy pulse rows ingested before the UUID field existed)
  - device_id (slug at the time of ingest — kept for display and for backfilling observations from pre-UUID pulse files)
  - author_login (nullable; populated for team-sourced rows)
  - repo
  - branch
  - full_sha (canonical commit identity — full 40-char SHA; nullable until the upstream collectors are upgraded to emit it, see "Upstream data-source changes" below)
  - short_sha (display-only; derived from `full_sha` when available, preserved verbatim for legacy rows)
  - subject
  - epoch_utc
  - timestamp_utc
  - source_tz_offset_minutes
  - source_tz_name
  - local_day
  - local_time
  - source_type (`pulse`, `reports_tsv`, or `team_pulse`)
  - source_file
  - source_line
  - kind (`commit` or `pr`)
  - pr_number (nullable)
  - dedupe key

Canonical commit view: a deduplicated `commits` view (or materialized table) over `commit_observations` grouped by `(repo, full_sha)` — **not** `(repo, short_sha)`. Short SHAs are not unique within a repo over time (Git itself uses variable-length prefixes and expands them on collision), so keying canonical identity off a 7-char prefix risks silently merging distinct commits in the exact layer meant to be historically trustworthy. For rows where `full_sha` is null (pre-upgrade legacy data), the view falls back to `(repo, short_sha, timestamp_utc)` as a best-effort proxy and flags the row as "unpromoted" so consumers can tell the difference.

### Upstream data-source changes required for `full_sha`

`collect.sh` and `team-collect.py` currently emit only the 7-char `short_sha`. To make `full_sha` the canonical key, we need a small schema upgrade on both producers:

- `pulse-*.md`: add a 7th column `full_sha` (or replace the existing `short_sha` column with `full_sha` and compute `short_sha` downstream). Backward compat: parser treats 6-col rows as legacy (short-only).
- `team-pulses/*.tsv`: the GitHub API already returns full SHAs (`item["sha"]`); `team-collect.py` just needs to stop truncating. Add a `full_sha` column to the 11-column TSV header.

This is not done yet. Phase 1 ingest begins against current-schema inputs, with `full_sha` nullable and the fallback dedupe key described above. Promoting `full_sha` to `NOT NULL` waits until both producers have shipped and every active machine has re-run.

- `ingest_runs`
  - started_at_utc
  - completed_at_utc
  - source_root
  - rows_read
  - rows_inserted
  - duplicates_skipped
  - malformed_skipped

- `summary_chunks`
  - chunk id
  - chunk type
  - date range
  - repo scope
  - device scope
  - summary text
  - embedding status

Canonical dedupe contract (per-observation):

- Identity segment precedence: `hardware_uuid` if present → `device_id` slug fallback → literal `team:<source_type>` for team rows. This keeps pre-UUID pulse rows ingestable and lets slug-only observations coexist until a subsequent collect.sh run backfills the UUID.
- SHA segment precedence: `full_sha` if present → `short_sha + timestamp_utc_iso` compound fallback for legacy rows. Once all producers emit `full_sha`, this fallback retires.
- Dedupe key formula: `sha1(identity_segment_norm + "|" + repo_norm + "|" + sha_segment_norm + "|" + kind + "|" + pr_number_norm)`
- `subject` is intentionally excluded — an amended commit or a subject typo correction should not produce a phantom duplicate observation. Full SHA uniquely identifies the commit.
- Normalization rules: trim, lowercase identifiers, normalize missing branch to `detached`, normalize empty `pr_number` to `-`
- Source precedence on collisions with same dedupe key: `pulse-*.md` beats `reports_tsv`; `team_pulse` never collides with personal rows because its identity segment differs
- Enforce with a unique index on `commit_observations.dedupe_key`; collisions increment `duplicates_skipped` and are logged with source path
- Migration path: once all active devices emit YAMLs with `hardware_uuid`, a one-time backfill links legacy `device_id`-keyed observations to the matching `hardware_uuid` via `device_aliases`. The unique index stays on `dedupe_key`, not on the identity segment — so a subsequent ingest with the UUID will simply add richer rows alongside the legacy ones rather than displacing them.

## Phase 0 Technical Spike

Timebox: half-day (the prior 1–2 hour target was unrealistic given the checklist).

### Checklist (must-have to inform Phase 1)

- [ ] Confirm the derived DB path (`~/Library/Application Support/git-pulse/history.sqlite`) is writable
- [ ] Parse current `pulse-*.md` deterministically into normalized rows
- [ ] Parse current `devices/*.yaml` into `devices` + `device_aliases`
- [ ] Implement a minimal ingest that loads the real sync folder and de-duplicates
- [ ] Run 2–3 representative queries from Python (e.g., "last commit per repo," "observations per device," "cross-device duplicates")
- [ ] Measure import time and DB size on current data
- [ ] Confirm FTS5 availability in the Python `sqlite3` build (simple `CREATE VIRTUAL TABLE ... USING fts5`)
- [ ] Confirm `sqlite-vec` can load as a dynamic extension (already a hard dep in `pyproject.toml` — just verifying `enable_load_extension` is available)

### Deferred to Phase 1 (not blocking the decision to proceed)

- Comprehensive DST-boundary + cross-timezone validation — belongs in a proper test fixture set, not a spike
- `reports/*.tsv` ingest path — only needed for reconciliation, not Phase 1 correctness
- Polished CLI query surface — Phase 2 concern
- Deep device-alias reconciliation heuristics — Phase 1 can start with a manual alias seed

### What Phase 0 Must Prove

- The GitHub sync folder is a workable raw-data root for this workflow
- SQLite gives immediate value even before vectors
- Device alias cleanup can be modeled explicitly instead of hidden in ad hoc report logic
- Query quality is already materially better with SQL + FTS than with raw file grep alone

### Spike Deliverables

- [x] A minimal ingest script at [experimental/git-pulse/sqlite_spike.py](../../experimental/git-pulse/sqlite_spike.py)
- [x] A scratch SQLite file at `~/Library/Application Support/git-pulse/history.sqlite`
- [x] A result summary added back into this plan doc (below)

### Spike Findings (run 2026-04-22)

Measured against the real sync folder (`/Users/noelsaw/Documents/GH Repos/rebalance-git-pulse/`):

**Dependencies — no blockers:**

- SQLite writes cleanly to `~/Library/Application Support/git-pulse/history.sqlite`.
- FTS5 virtual tables create successfully in the Python `sqlite3` build.
- `sqlite-vec` loads via `enable_load_extension` (version `v0.1.9`). Already pinned in `pyproject.toml`; no separate install dance needed.

**Data shape — the surprise:**

- `pulse-*.md` files are *under-populated* for this user. MacBook Pro 14" pulse has **0** rows despite the device showing 66 observations in the combined TSV reports. Mac Studio pulse has 23 rows. MBP 16" M1 Pro has 3.
- Combined TSVs in `reports/` carry the bulk of the data (82 rows across two files; ~20% overlap between windows).
- **This inverts the plan's assumption.** The plan treats `pulse-*.md` as canonical and `reports/*.tsv` as "secondary verification." For this dataset, that is wrong — TSVs are load-bearing. Either (a) the launchd collector has not been running on every machine, or (b) the recap pipeline is the only thing keeping history alive. Phase 1 needs to treat `reports/*.tsv` as a first-class ingest source, not a fallback.

**Dedupe — working:**

- 108 rows read, 92 inserted, 16 duplicates skipped — all duplicates come from the 14-day vs. 21-day TSV window overlap.
- Zero cross-source (pulse ↔ TSV) SHA collisions. This is a *signal, not a feature* — the pulse and TSV sources aren't covering the same commits right now. Phase 1 ingest will need to reconcile the two once collector coverage improves.

**Scale — trivially cheap:**

- Ingest: 1.4ms for 108 rows. DB size: 86 KB. Linear extrapolation: ~100k rows ≈ 100 MB and sub-second ingest. No performance concerns even at orders of magnitude more data.

**Device hygiene — clean for now:**

- Three device YAMLs on disk, three device IDs seen in data, no pulse-file/device-id mismatches detected by the "alias candidate" query. The legacy `noel-s-*` slugs the plan mentions have already been migrated out of live data.

### Phase 1 Adjustments Informed by the Spike

1. Promote `reports/*.tsv` to a first-class ingest source alongside `pulse-*.md`. The spike's `source_type` column already distinguishes them.
2. Add a post-ingest consistency check: flag devices where `pulse-*.md` row count is dramatically lower than `reports/*.tsv` row count for the same device_id. This is the signal for "collector is not running."
3. Keep the `commit_observations` per-observation model. It is what made the pulse-vs-TSV coverage gap visible in the spike; a globally-deduped table would have hidden it.
4. Defer alias reconciliation heuristics — current data doesn't need them. Phase 1 can ship with an empty `device_aliases` table and add seed rows only when drift re-emerges.
5. FTS5 is ready to light up in Phase 2 without additional validation.

## Phase 1 Canonical SQLite Layer

Objective: build the durable historical database without vector search yet.

### Checklist

- [ ] Create a single ingest pipeline for all git-pulse historical data
- [ ] Parse raw pulse files into `commit_observations` with `source_type = 'pulse'`
- [ ] Parse saved TSV reports into `commit_observations` with `source_type = 'reports_tsv'` — first-class, not fallback
- [ ] Parse metadata files into canonical devices and aliases
- [ ] Define one stable dedupe key per logical commit row
- [ ] Persist timezone provenance fields (`source_tz_offset_minutes`, `source_tz_name`) for trustworthy local-day rollups
- [ ] Create indexes for:
  - `timestamp_utc`
  - `hardware_uuid`
  - `device_id`
  - `repo`
  - `full_sha` (primary commit identity)
  - `short_sha` (display fallback only)
  - `dedupe_key` (unique)
- [ ] Add structured ingest logging with row counts and duplicate counts
- [ ] Add at least one integration test for ingest over mixed raw sources
- [ ] Add a health-check style validation command for the DB, including the collector-coverage check (pulse vs. reports_tsv row counts per device)

### Notes

- Raw pulse files AND `reports/*.tsv` are both first-class ingest sources. The spike showed the TSVs currently carry most usable history; promoting pulse files back to "primary" only becomes accurate once collector coverage is fixed on every machine.
- Alias handling needs to be explicit because legacy slug YAMLs still exist on machines that haven't re-run the updated collector
- Local-day queries must derive from the commit's own timezone (stored as `source_tz_offset_minutes` / `source_tz_name`), not from the machine that ran `view.sh` or the machine running ingest

## Phase 2 Exact Retrieval And Operator Reports

Objective: make historical retrieval useful before any semantic layer exists.

### Checklist

- [ ] Add FTS5 over commit subjects and grouped summary text
- [ ] Add CLI queries such as:
  - `history-search --text "calendar edge snapping"`
  - `history-search --repo rebalance-OS --days 30`
  - `history-day --date 2026-04-20`
  - `history-device --device noels-mac-studio`
- [ ] Add deterministic grouped summaries:
  - daily rollups
  - per-repo rollups
  - cross-machine overlap windows
- [ ] Rebuild the all-machines recap from SQLite instead of directly from TSV once parity is proven
- [ ] Add fixtures for duplicate rows, stale metadata, and detached branches

### Success Condition For Phase 2

An operator should be able to answer questions like these without manually grepping raw files:

- What did I work on across all machines last Tuesday?
- When did I last touch repo X?
- Which machine was active on project Y this month?
- What stale device ids still exist in the sync history?

## Phase 3 Semantic Retrieval

Objective: add vectors only where they improve retrieval quality.

### Checklist

- [ ] Keep raw commit rows out of the first embedding pass
- [ ] Generate grouped chunks for embedding:
  - per-day summaries
  - per-repo weekly summaries
  - cross-machine recap chunks
  - notable activity windows
- [ ] Store embeddings in SQLite via `sqlite-vec` only after Phase 2 is stable
- [ ] Compare FTS-only vs vector-backed retrieval on at least 10 real prompts
- [ ] Keep semantic retrieval inspectable by showing the exact matched chunks
- [ ] Do not make vector search the only retrieval path

### Guardrail

If sparse commit subjects do not benefit materially from embeddings, stop here and keep FTS as the primary search surface.

## Phase 4 MCP And Workflow Integration

Objective: expose the history layer to agents without requiring direct file parsing.

### Checklist

- [ ] Add a local CLI command family for historical retrieval
- [ ] Add at least one MCP tool over the SQLite history layer
- [ ] Reuse the same canonical query functions for CLI and MCP
- [ ] Add integration tests for the happy-path retrieval flow
- [ ] Document the operator workflow for:
  - re-ingest
  - recap rebuild
  - search
  - health check

### Likely MCP Tool Shape

- `git_pulse_history_search`
- `git_pulse_day_recap`
- `git_pulse_repo_timeline`

## Contracts And Ownership

Single-writer rule:

- One ingest pipeline owns the SQLite schema and write path
- Recap generation should read from the canonical layer once SQLite parity is proven
- Breaking schema changes must be treated as contract changes and called out explicitly

Canonical writer responsibilities:

- dedupe rules
- alias resolution
- ingest logging
- summary chunk generation
- retrieval query contracts

## Risks And Guardrails

- **Binary DB in a Git sync repo**: acceptable only if the DB is gitignored or otherwise excluded from normal sync commits
- **Stale alias drift**: existing `noel-s-*` vs `noels-*` mismatches must be modeled, not silently dropped
- **Duplicate ingestion**: overlapping TSV windows and repeated recap runs can create duplicates if the dedupe key is weak
- **Low-signal embeddings**: raw commit subjects may be too sparse for vectors to help
- **iCloud Drive and SQLite are incompatible**: if the raw folder ends up under an iCloud-synced path (e.g., `~/Documents` with Desktop & Documents enabled), SQLite's WAL/journal files will corrupt over time. This is not a caveat — it's a hard rule. The raw folder must live on the GitHub sync path only; the derived DB lives in `~/Library/Application Support/git-pulse/` precisely to avoid this class of failure.
- **macOS Full Disk Access**: if the raw folder sits under `~/Documents`, terminal processes may need Full Disk Access permission to read it. Worth documenting in the operator setup.
- **Schema sprawl**: keep one logical pipeline instead of separate pulse/tsv/vector side stores

## Success Criteria

- [ ] SQLite ingest works reliably against the chosen sync folder
- [ ] FTS-based retrieval answers real historical questions better than raw-file grep
- [ ] Alias drift is visible and repairable
- [ ] The all-machines recap can be regenerated from canonical history data
- [ ] Vector search proves meaningfully better on real prompts before it becomes part of the default workflow

## Open Questions

- [ ] Should saved TSV reports remain first-class ingest inputs long-term, or become verification-only artifacts?
- [ ] Should grouped summary chunks be persisted as tables, markdown artifacts, or both?
- [ ] At what data volume does semantic retrieval start outperforming FTS for this commit-history domain?
- [ ] Team-pulse PRs: keep them in the same `commit_observations` table with `kind = 'pr'`, or split into a sibling `pull_requests` table? This spike's tentative answer is "same table" for Phase 1 simplicity; revisit if PR-specific fields (reviewers, labels, states) become load-bearing.
