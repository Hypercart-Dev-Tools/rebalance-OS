# P1 Signal

## TOC
- Refined Direction Read
- Product Surface Decision
- Scoring Model
- Attention Ledger Schema And Derived Views
- MCP Signal Audit
- Phased Delivery

## Refined Direction Read

This read is based on the local commit history in this checkout through April 22, plus the stated direction in [PROJECT.md](../../PROJECT.md), [4X4.md](../../4X4.md), [experimental/git-pulse/PIPELINE.md](../../experimental/git-pulse/PIPELINE.md), and [P1-SQLITE.md](./P1-SQLITE.md).

### What is working

The current direction is stronger than a typical second-brain repo because the recent commits are not collapsing into generic AI summarization. The center of gravity is clearly git-pulse: capture reliability, install hardening, repo discovery, device identity cleanup, recap guardrails, and the SQLite history plan. That is the right backbone. A system like this only becomes trustworthy if capture, normalization, and exact retrieval are solid before any additional synthesis layer starts speaking with confidence.

### What is still risky

The main risk is scope spread. In a short window the repo touched personal history capture, team recap tooling, SQLite history design, reminders, calendar ingest, and GitHub sync behavior. That is productive exploration, but it can still produce a smart archive without producing a strong operator signal.

The repo does not need more raw capability right now. It needs a tighter loop that answers three questions reliably:

1. Where did my attention actually go?
2. Where should it have gone?
3. What needs rebalancing next?

### Refined recommendation

The next high-leverage move is not another ingest surface. It is one weekly rebalance loop backed by one canonical attention ledger in SQLite and rendered into one operator-facing dashboard in Obsidian. That keeps the intelligence local, reduces agent rabbit holes, and gives the repo a clear center of product gravity.

## Product Surface Decision

### Obsidian should be the dashboard

There is no pushback on making Obsidian and the vault more of the dashboard where updates are read and notes are entered. That is probably the right move if the product is meant to be a second brain instead of another engineering console.

Using Obsidian as the daily and weekly operating surface has three advantages:

1. It matches the product promise. The system should meet the user where planning and reflection already happen.
2. It reduces agent-induced rabbit holes. A generated markdown dashboard is more likely to steer toward decisions than an open-ended chat surface.
3. It creates a clean writeback loop. Daily briefs, weekly rebalance notes, and project updates become durable artifacts inside the same corpus the system later retrieves from.

### Mild pushback

Obsidian should be the operator surface, not the computation layer.

That means:

1. Do not make critical workflows depend on a fragile plugin stack or live-query dashboard widgets.
2. Do not let agents write freely across hand-maintained notes.
3. Do not move heavy inference, ETL, or reconciliation logic into vault-side scripts.

The better split is:

1. Obsidian for briefing, triage, note entry, weekly review, and project snapshots.
2. SQLite plus the MCP or CLI layer for scoring, normalization, retrieval, and recomputation.
3. VS Code agents for deep implementation work, audits, schema changes, and one-off investigations.

### Recommended vault contract

Generated markdown should become the dashboard. Human notes should remain human-owned.

Suggested shape:

1. `Daily Notes/YYYY-MM-DD.md` for the daily brief.
2. `Reviews/week-of-YYYY-MM-DD.md` for the weekly rebalance report.
3. `Dashboards/Projects/<project>.md` for project snapshots.
4. `Inbox/rebalance-needs-review.md` for unattributed or low-confidence items.
5. `Projects/00-project-registry.md` remains the canonical source for project metadata and target intent.

Use a single-writer contract inside generated notes:

1. rebalance owns explicit generated sections or fully generated files.
2. Freeform reflections, decisions, and overrides live in clearly separate human sections.
3. Any agent writeback should preserve human-authored content byte-for-byte outside generated sections.

## Scoring Model

### Goal

Score a small set of operator states directly rather than producing a vague summary. The first four are enough:

1. `overweight` — too much attention relative to target share.
2. `neglected` — too little attention relative to target share and recency needs.
3. `thrashing` — lots of touches and switches with weak outcome signal.
4. `blocked` — pressure is accumulating faster than progress.

### Inputs to score

Use source-normalized shares instead of one giant raw formula. Each source contributes signal on its own scale, then the sources are combined.

Per project, per week:

1. `calendar_share` from classified work minutes only. Exclude recurring filler, pure admin, and explicitly excluded events.
2. `git_share` from meaningful git-pulse activity. Down-weight tiny housekeeping commits and dependency churn.
3. `github_flow_share` from merged PRs, opened PRs, review load, issue pressure, and release events.
4. `note_share` from substantive vault activity and weekly review writebacks, not trivial metadata edits.
5. `reminder_share` from active and overdue reminders or other explicit pressure signals.

Initial combined attention share:

```text
actual_attention_share =
		0.45 * calendar_share
	+ 0.25 * git_share
	+ 0.10 * github_flow_share
	+ 0.10 * note_share
	+ 0.10 * reminder_share
```

These weights are deliberately opinionated. Calendar time should dominate because it is the closest proxy for real attention. Git and GitHub are secondary evidence. Notes and reminders are context enrichers, not primary proof of investment.

### Target share

Target share should not be inferred from recent behavior. It should come from explicit project intent.

Start with:

```text
tier_weight = 6 - priority_tier
target_weight = tier_weight * manual_focus_multiplier
target_share = target_weight / SUM(target_weight across active projects)
```

Where:

1. `priority_tier=1` is highest priority.
2. `manual_focus_multiplier` defaults to `1.0` and is the explicit override when a week needs deliberate imbalance.

### State scores

Use simple bounded formulas first.

```text
gap = actual_attention_share - target_share

overweight_score = clamp((gap - 0.10) / 0.15, 0, 1) * confidence_score
neglect_score    = clamp(((-gap) - 0.08) / 0.12, 0, 1) * staleness_factor * confidence_score
thrash_score     = clamp((switch_rate * (1 - outcome_rate)), 0, 1) * confidence_score
blocked_score    = clamp((pressure_rate - progress_rate), 0, 1) * confidence_score
```

Definitions:

1. `switch_rate` is high when a project is touched in many short bursts across many days with low completion evidence.
2. `outcome_rate` is driven by merged PRs, completed reminders, releases, or explicit milestone movement.
3. `pressure_rate` is driven by overdue reminders, unresolved issue load, review backlog, and meeting load.
4. `progress_rate` is the normalized outcome signal over the same window.

### Confidence score

Never emit a strong verdict without a coverage score.

```text
confidence_score = attributed_signal_units / total_signal_units
```

Then reduce confidence further when:

1. a large share of calendar minutes is unattributed,
2. a project has repos linked but no reliable activity source for the week,
3. a large share of git activity is still classed as low-signal churn,
4. a project relies on only one weak source.

### Output contract

Every dashboard row should use the same operator format:

1. `verdict`
2. `evidence`
3. `next_move`

If a surface cannot answer in that shape, it is probably too noisy for the dashboard.

## Attention Ledger Schema And Derived Views

### Design principle

Do not create another competing raw history system. The repo already has raw per-source tables. Add one normalized derived layer that references those sources and turns them into comparable project-level attention units.

### Proposed tables

#### `project_targets`

Explicit weekly or date-effective target intent.

```text
project_name           TEXT NOT NULL
effective_from         TEXT NOT NULL
priority_tier          INTEGER NOT NULL
manual_focus_multiplier REAL NOT NULL DEFAULT 1.0
min_share              REAL
max_share              REAL
notes                  TEXT
PRIMARY KEY (project_name, effective_from)
```

#### `attention_events`

One normalized attributable unit of attention or pressure, regardless of source.

```text
event_id               TEXT PRIMARY KEY
source_type            TEXT NOT NULL          -- calendar, git_pulse, github, vault_note, reminder
source_key             TEXT NOT NULL
project_name           TEXT                   -- nullable until classified
signal_kind            TEXT NOT NULL          -- focus, delivery, pressure, planning, support, admin
event_start_utc        TEXT
event_end_utc          TEXT
local_day              TEXT NOT NULL
local_week             TEXT NOT NULL
raw_value              REAL NOT NULL
normalized_units       REAL NOT NULL
attribution_method     TEXT NOT NULL          -- explicit, rule, inferred, manual
attribution_confidence REAL NOT NULL
noise_flag             INTEGER NOT NULL DEFAULT 0
noise_reason           TEXT NOT NULL DEFAULT ''
outcome_flag           INTEGER NOT NULL DEFAULT 0
metadata_json          TEXT NOT NULL DEFAULT '{}'
UNIQUE (source_type, source_key)
```

#### `attention_feedback`

Persistent user corrections so the system gets better instead of repeatedly asking the same question.

```text
feedback_id            INTEGER PRIMARY KEY
source_type            TEXT NOT NULL
source_key             TEXT NOT NULL
decision               TEXT NOT NULL          -- include, exclude, reassign
project_name           TEXT
decided_at             TEXT NOT NULL
decided_by             TEXT NOT NULL DEFAULT 'user'
UNIQUE (source_type, source_key)
```

#### `project_balance_snapshots`

Historical weekly output for auditability and dashboard writeback.

```text
week_start             TEXT NOT NULL
project_name           TEXT NOT NULL
actual_attention_share REAL NOT NULL
target_share           REAL NOT NULL
confidence_score       REAL NOT NULL
overweight_score       REAL NOT NULL
neglect_score          REAL NOT NULL
thrash_score           REAL NOT NULL
blocked_score          REAL NOT NULL
primary_state          TEXT NOT NULL
evidence_json          TEXT NOT NULL
next_move              TEXT NOT NULL
generated_at           TEXT NOT NULL
PRIMARY KEY (week_start, project_name)
```

### Derived views

#### `v_attention_events_clean`

`attention_events` filtered to `noise_flag = 0`. This becomes the default source for all rollups.

#### `v_unattributed_attention`

Everything with `project_name IS NULL` or low attribution confidence. This should drive a review queue in Obsidian and MCP.

#### `v_project_attention_daily`

Per project, per day rollup of focus units, pressure units, delivery units, and confidence.

#### `v_project_attention_weekly`

Per project, per week rollup with source shares and target shares. This is the core operator dataset.

#### `v_project_balance_current`

Current-week or latest-week verdict view that exposes:

1. primary state,
2. actual share,
3. target share,
4. gap,
5. confidence,
6. next move.

This is the view the dashboard should read first.

#### `v_project_context_switches`

Per project fragmentation view based on short bursts, day count, and repeated re-entry without outcome. This isolates thrash logic instead of hiding it inside a big score.

#### `v_dashboard_feed`

Presentation-ready row shape for markdown rendering into Obsidian:

1. project name,
2. verdict,
3. evidence,
4. next move,
5. confidence,
6. linked source counts.

### Important contract

Embeddings should not participate in the scoring path. They can support explanation and retrieval after a verdict exists, but they should not decide the verdict.

## MCP Signal Audit

This audit is against the live server surface in [src/rebalance/mcp_server.py](../../src/rebalance/mcp_server.py), not just the docs.

### High-signal tools already aligned with the product

1. `review_timesheet` and `classify_event` are the best current pattern in the repo. They reduce ambiguity at the source, they create reusable feedback, and they improve future reports instead of merely answering one question.
2. `github_release_readiness` is high-signal because it is narrow, verdict-oriented, and evidence-backed.
3. `github_close_candidates` is directionally strong because it produces explicit recommendations rather than broad chat synthesis.

### Useful ingredients, but not yet strong dashboard tools

1. `github_balance` is useful as a raw ingredient, but it is still only GitHub-shaped activity. It does not know target share, calendar load, note activity, or pressure. It is not yet a rebalance verdict.
2. `query_notes` and `query_github_context` are supporting evidence tools. They help explain a verdict. They should not be the front door of the product.
3. `sleuth_sync_reminders` is an ingest tool, not an operator dashboard tool.

### Current noise sources

1. `ask` is too broad for the primary dashboard loop. The current prompt assembly mixes project registry, GitHub activity, GitHub semantic hits, recent note edits, upcoming calendar events, and semantic vault hits in one response path. That is good for exploration, but it is structurally prone to rabbit holes and verbose answers.
2. `search_vault` is documented as full-text search, but the live implementation is an exact keyword lookup over the `keywords` table. That mismatch creates false expectations and weakens trust in the surface.
3. `github_balance` is documented in [MCP.md](../../MCP.md) with a default 14-day window, while the live server default is 30 days.
4. [MCP.md](../../MCP.md) omits live tools that materially affect the real surface: `review_timesheet`, `classify_event`, `snap_calendar_edges`, and `sleuth_sync_reminders`.
5. The docs describe `search_vault(query)` while the server exposes `search_vault(keyword, limit)`. Again, the issue is not just docs drift. It is signal drift.

### Recommendation for the MCP surface

The repo should keep broad retrieval tools, but the primary dashboard path should move toward dedicated verdict-oriented tools, for example:

1. `weekly_rebalance(week_start?)`
2. `project_attention(project_name, since_days?)`
3. `review_unattributed_attention(limit?)`
4. `classify_attention_item(source_type, source_key, decision)`

Those tools would align the MCP layer with the product promise: answer the rebalance question directly, then expose supporting evidence only as a second step.

## Phased Delivery

### Phase 0 spike: Obsidian-first weekly dashboard

Timebox: 1 to 2 hours.

Checklist:

1. Generate one weekly markdown report into the vault from the current data you already have.
2. Force the output into `verdict`, `evidence`, `next move` per project.
3. Include an explicit `unattributed / low-confidence` section.
4. Read that note in Obsidian for a few days instead of relying on VS Code chat.
5. Record what decisions it actually changed.

If that report is not useful, do not widen the ingest surface yet.

### Phase 1: build the attention ledger

1. Implement `project_targets`, `attention_events`, `attention_feedback`, and the weekly rollup views.
2. Reuse existing classification patterns from calendar review for any unattributed source.
3. Make confidence visible in every balance output.

### Phase 2: narrow the operator surface

1. Add dedicated rebalance MCP tools.
2. Relegate `ask` to exploratory use, not primary dashboard use.
3. Bring [MCP.md](../../MCP.md) back into sync with the live server.

### Phase 3: render into Obsidian by default

1. Daily brief note.
2. Weekly rebalance note.
3. Project snapshot note.
4. Needs-review note for unattributed items.

## Bottom line

The repo is pointed in the right direction, but it is still one layer too close to raw capability. The right product move is to make Obsidian the calm dashboard and note-entry surface, keep SQLite as the canonical attention ledger underneath it, and reserve VS Code agent chats for deep implementation or investigative work.