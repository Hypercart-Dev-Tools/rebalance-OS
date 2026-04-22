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

- [ ] Preserve raw pulse files as the canonical source-of-truth artifacts, with TSV reports as secondary verification inputs
- [ ] Build one canonical SQLite history layer over the synced data
- [ ] Support exact historical retrieval first with SQL + FTS
- [ ] Add semantic retrieval only where it improves recall over sparse commit subjects
- [ ] Keep the implementation in this repo under `experimental/git-pulse/`
- [ ] Use a configurable GitHub-backed sync folder with default root at `$HOME/Documents/rebalance-git-pulse`

## Data Source And Storage Decision

Chosen sync folder:

- Raw data root: `$HOME/Documents/rebalance-git-pulse`
- Config key: `GIT_PULSE_SYNC_ROOT`

Use that folder for:

- `pulse-*.md`
- `devices/*.yaml`
- `reports/*.tsv`
- `reports/*.md`

Recommended derived-data rule:

- Read raw inputs from the sync repo checkout
- Write the derived SQLite database under that same checkout in a dedicated derived path
- Do **not** commit the SQLite database to Git by default

Proposed derived path:

- `$HOME/Documents/rebalance-git-pulse/derived/git-pulse-history.sqlite`

Reasoning:

- This keeps all related code and data centered on the existing GitHub sync folder
- It avoids binary database churn and merge conflicts in the sync repo history
- It preserves raw synced artifacts as durable, inspectable, line-oriented source material

Default/fallback behavior:

- If `GIT_PULSE_SYNC_ROOT` is set, use it as the authoritative root
- If unset, use `$HOME/Documents/rebalance-git-pulse`
- If the selected root is unavailable or read-only, fail fast with a clear operator error and no partial ingest writes

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
  - canonical device id
  - display name
  - hostname
  - first_seen_utc
  - last_seen_utc
  - status

- `device_aliases`
  - alias device id
  - canonical device id
  - reason
  - first_seen_utc
  - last_seen_utc

- `commits`
  - canonical row id
  - device id
  - repo
  - branch
  - short sha
  - subject
  - epoch_utc
  - timestamp_utc
  - source_tz_offset_minutes
  - source_tz_name
  - local_day
  - local_time
  - source type
  - source file
  - source line
  - dedupe key

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

Canonical dedupe contract:

- Dedupe key formula: `sha1(device_id_norm + "|" + repo_norm + "|" + branch_norm + "|" + short_sha_norm + "|" + timestamp_utc_iso + "|" + subject_norm)`
- Normalization rules: trim, lowercase where appropriate for identifiers, collapse internal whitespace in subject, and normalize missing branch to `detached`
- Source precedence on collisions with same dedupe key: `pulse-*.md` first, then `reports/*.tsv` as reconciliation-only metadata
- Enforce with a unique index on `commits.dedupe_key`; collisions increment `duplicates_skipped` and are logged with source path

## Phase 0 Technical Spike

Timebox: 1-2 hours max

### Checklist

- [ ] Confirm SQLite writes cleanly from this repo against the chosen sync folder
- [ ] Confirm the derived DB path is writable and acceptable under the chosen sync folder
- [ ] Confirm `GIT_PULSE_SYNC_ROOT` override works and fallback to default root is deterministic
- [ ] Confirm current raw inputs can be parsed deterministically:
  - `pulse-*.md`
  - `devices/*.yaml`
  - `reports/*.tsv`
- [ ] Implement a tiny ingest prototype that loads current data and de-duplicates it
- [ ] Run 5 real historical queries against the prototype DB
- [ ] Measure import time and DB size on current data
- [ ] Validate blocking dependencies:
  - standard SQLite availability
  - FTS5 availability
  - `sqlite-vec` availability or install path
- [ ] Validate timezone correctness on at least one DST boundary sample and one cross-device timezone sample
- [ ] Stop and escalate if the chosen sync folder causes write friction or if vector dependencies are fragile

### What Phase 0 Must Prove

- The GitHub sync folder is a workable raw-data root for this workflow
- SQLite gives immediate value even before vectors
- Device alias cleanup can be modeled explicitly instead of hidden in ad hoc report logic
- Query quality is already materially better with SQL + FTS than with raw file grep alone

### Spike Deliverables

- [ ] A minimal ingest script under `experimental/git-pulse/`
- [ ] A scratch SQLite file at the proposed derived path
- [ ] A short result summary added back into this plan doc before Phase 1 starts

## Phase 1 Canonical SQLite Layer

Objective: build the durable historical database without vector search yet.

### Checklist

- [ ] Create a single ingest pipeline for all git-pulse historical data
- [ ] Parse raw pulse files into canonical commit rows
- [ ] Parse metadata files into canonical devices and aliases
- [ ] Optionally parse saved TSV reports for reconciliation and audit only
- [ ] Define one stable dedupe key per logical commit row
- [ ] Persist timezone provenance fields (`source_tz_offset_minutes`, `source_tz_name`) for trustworthy local-day rollups
- [ ] Create indexes for:
  - `timestamp_utc`
  - `device_id`
  - `repo`
  - `branch`
  - `short_sha`
  - `dedupe_key` (unique)
- [ ] Add structured ingest logging with row counts and duplicate counts
- [ ] Add at least one integration test for ingest over mixed raw sources
- [ ] Add a health-check style validation command for the DB

### Notes

- Raw pulse files should remain the primary historical source
- Saved TSV reports should be treated as secondary derived inputs, useful for verification and recap rebuilding
- Alias handling needs to be explicit because stale `noel-s-*` metadata already exists in the sync repo
- Local-day queries must derive from timezone-aware fields, not `timestamp_utc` alone

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
- **macOS protected folders**: the chosen sync folder is under `~/Documents`, so background sync remains a known write-risk; this does not block local SQLite use, but it remains an operational caveat
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
