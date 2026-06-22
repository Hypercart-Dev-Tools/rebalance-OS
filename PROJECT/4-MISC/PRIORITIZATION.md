---
title: Project Prioritization — Signal-Agnostic Design
status: active
created: 2026-05-31
constraint: Obsidian remains the write/configuration interface for user overrides
---

# Project Prioritization — Signal-Agnostic Design

## Current Status

| Last completed phase | What's next |
|---|---|
| Foundation ✅ — simplification audit done, every repo visible, no silent gating | Phase 1 — email attribution (apply project classifier to `gmail_messages`) |

---

## Table of Contents

- [Problem](#problem)
- [Design Principles](#design-principles)
- [Signal Inventory](#signal-inventory)
- [Target Architecture](#target-architecture)
- [Obsidian Write Interface](#obsidian-write-interface)
- [Phase 0 — Foundation](#phase-0--foundation-)
- [Phase 1 — Email Attribution](#phase-1--email-attribution)
- [Phase 2 — Obsidian Annotation Surface](#phase-2--obsidian-annotation-surface)
- [Phase 3 — Multi-Signal Payload](#phase-3--multi-signal-payload)
- [Phase 4 — Haiku Attribution Assist](#phase-4--haiku-attribution-assist)
- [Phase 5 — Slack Ingest and Attribution](#phase-5--slack-ingest-and-attribution)
- [Open Questions](#open-questions)

---

## Problem

GitHub commit activity is a proxy for project priority, not priority itself. A client
receiving heavy email, calendar time, and Slack discussion — but no commits yet — is
high-priority by any reasonable measure. The old `_determine_verdict()` conflated
"GitHub quiet" with "low priority," which was wrong and is now gone.

The goal is to replace that single-signal heuristic with a transparent, multi-signal
count that the user can inspect, override, and trust.

---

## Design Principles

1. **Counts before conclusions.** Surface raw per-project signal counts (calendar hours,
   email threads, Slack mentions, GitHub commits/PRs). Let the user — or a summariser —
   draw conclusions from those, not the system.

2. **Auditable over magical.** If a project is ranked high, the reason must be a
   one-line answer: "8 hours of calendar time + 3 email threads this week." Opaque
   inferred priority scores erode trust the same way silent `repos_json` gating did.

3. **Obsidian as the override surface.** The system infers; the user corrects in Obsidian.
   SQLite is source of truth; the file is a regenerated view that also accepts `#tag`
   input and priority tier overrides.

4. **Haiku as an attribution assistant, not a priority judge.** When name-matching is
   uncertain ("does this email thread belong to LTVera or BinoidCBD?"), Haiku helps
   classify. It does not emit a priority verdict — the counts do that.

5. **Graceful degradation at every layer.** A project with no email/Slack ingest still
   shows calendar + GitHub signals. A project with no repos still shows calendar. No
   signal combination produces a blank row.

6. **Manual tier always wins.** Signal counts appear as evidence; the human decides rank.
   The system must never silently re-rank a project the user intentionally deprioritised.

---

## Signal Inventory

| Signal | Source table | Attributed how | Status |
|---|---|---|---|
| Calendar time (hours) | `calendar_events` | Project classifier (name + alias match) | ✅ Working |
| GitHub commits / PRs | `github_activity` | Org-grouped | ✅ Working |
| Email threads | `gmail_messages` | Name-match on subject + sender (same classifier) | ❌ Not yet attributed |
| Vault mentions | `vault_notes` | Name-match on note body (semantic index) | ⚠️ Partial |
| Slack mentions | _(not ingested)_ | Name-match on message text | ❌ Not ingested |
| User priority override | `project_registry.priority_tier` | Obsidian write-back via `sync_registry(pull)` | ✅ Working |

---

## Target Architecture

```
Raw signals                 Attribution layer           Payload
─────────────────           ──────────────────          ──────────────────────────
calendar_events   ──┐
gmail_messages    ──┤──→  project_classifier  ──→  per-project signal counts
vault_notes       ──┤      (name + alias match)      { calendar_hours,
github_activity   ──┤      + Haiku assist for          email_threads,
slack_messages    ──┘      low-confidence items         vault_mentions,
                                                        github_commits }
                                                            │
                                                            ▼
                                                   synthesize_dashboard_narrative()
                                                   (narrates FROM counts, not from vibes)
                                                            │
                                                            ▼
                                                   Obsidian note + TUI + web
```

The attribution layer already exists for calendar events (`project_classifier.py`,
`annotate_events_with_projects()`). Extending it to email uses the same matchers —
no new infrastructure.

---

## Obsidian Write Interface

Keeping CLAUDE-ONBOARDING.md recommendations. Three grouping layers, all zero-config,
all reversible. Signal counts appear inline so users can see *why* something is active:

```
GitHub Repos.md  (system-written · user-annotatable)
─────────────────────────────────────────────────────
## BinoidCBD · 3 repos
  ### LTVera  (auto-detected from name prefix — add a #tag to override)
  - LTVera-Pandas      — 47 commits · 2h calendar · 1 email thread
  - LTVera-API         — 12 commits · 0h calendar
  - storefront-theme   — 3 commits  · 1h calendar

## Hypercart-Dev-Tools · 12 repos
  - invoice-gen    — 8 commits   ← add  #billing  to group
  - billing-cron   — 5 commits
```

Priority tier overrides live in `project_registry.md` (existing surface), not here.
Grouping annotation (`#tags`) goes in the repo file; priority decisions go in the
project registry. Keep the two concerns separate.

---

## Phase 0 — Foundation ✅

_No code changes. Decisions only._

- [x] Simplification audit complete — all 4 phases shipped, audit in `PROJECT/3-DONE/`
- [x] Every repo now visible regardless of `repos_json` registration (no silent gating)
- [x] `note_builder.py` at read-only floor — correct starting point for annotation layer
- [x] `sync_registry(pull)` preserved — load-bearing for future Obsidian write-back
- [x] `github_balance` MCP kept as-is — per-project names needed for agent queries

---

## Phase 1 — Email Attribution

_Apply the existing project classifier to `gmail_messages`. No new tables, no new UI._

- [ ] Read `gmail_messages` schema — confirm `subject` and `sender` fields available
- [ ] Add `attribute_gmail_to_projects(database_path, matchers)` function in `project_classifier.py` — same pattern as `annotate_events_with_projects()`, matching on `subject` + sender domain
- [ ] Add `fetch_project_email_counts(database_path, since_days)` query — returns `{project_name: thread_count}` grouped by attributed project
- [ ] Extend `DashboardPayload` with `email_counts: dict[str, int]` field
- [ ] Populate `email_counts` in `build_dashboard_payload()`
- [ ] Update `synthesize_dashboard_narrative()` prompt to include email thread counts alongside calendar + GitHub
- [ ] Run existing tests green; add one test asserting `email_counts` is a dict

---

## Phase 2 — Obsidian Annotation Surface

_New file `GitHub Repos.md`. Separate from the dashboard note. Three sub-steps._

**2A — Read-only floor (ship first)**

- [ ] Add `write_repo_index(database_path, vault_path, since_days)` to `note_builder.py`
- [ ] Floor content: org-grouped repo list with inline signal counts (commits, calendar hours, email threads from Phase 1)
- [ ] Self-explaining header per CLAUDE-ONBOARDING.md ("You don't need to do anything…")
- [ ] Wire into `refresh_index` MCP tool so it writes after each sync
- [ ] Confirm file survives vault move (path resolved from `vault_path`, not hardcoded)

**2B — Prefix-cluster auto-grouping**

- [ ] Add `_cluster_by_prefix(repos) -> dict[str, list]` — scan for shared leading tokens (min 2 repos sharing a prefix of ≥ 4 chars), return `{cluster_name: [repos], None: [ungrouped]}`
- [ ] Apply inside `write_repo_index()` within each org section
- [ ] Label auto-detected clusters with `(auto-detected from name — add a #tag to override)`
- [ ] No storage — pure display transform at render time

**2C — `#tag` parsing and write-back**

- [ ] Parse trailing `#tag` on repo lines in the written file (regex, read before each rewrite)
- [ ] Store confirmed tags in `project_registry` `custom_fields.repo_groups` via `sync_registry(pull)`
- [ ] Atomic rewrite: temp-file-then-rename; read current disk state before each write so open edits are not lost
- [ ] Skip rewrite entirely if vault path is gone (DB stays; no data loss)

---

## Phase 3 — Multi-Signal Payload

_Extend payload and synthesis with all attributed signals._

- [ ] Add `vault_mention_counts: dict[str, int]` to `DashboardPayload` — query semantic index for project name mentions in vault notes
- [ ] Update `build_dashboard_payload()` to populate both `email_counts` (Phase 1) and `vault_mention_counts`
- [ ] Update `synthesize_dashboard_narrative()` prompt — include full signal table per project: `calendar_hours | email_threads | vault_mentions | github_commits`
- [ ] Update `render_dashboard_markdown()` project section — add a signal summary line per project replacing the current bare tier/client/risk block
- [ ] Run full test suite; update fixtures to include multi-signal counts

---

## Phase 4 — Haiku Attribution Assist

_Optional. For email/vault items where name-matching confidence is below threshold._

- [ ] Define confidence threshold — items below get batched for Haiku review (e.g. no exact name match, only partial alias match)
- [ ] Add `classify_uncertain_items(items, matchers, api_key) -> dict[str, str]` — batch call to Haiku with project name list and item text; returns `{item_id: project_name | "unknown"}`
- [ ] Cache results in `project_classifier_cache` table (schema: `item_id, source, project_name, classified_at`) — avoid repeated calls on re-sync
- [ ] Gate behind `haiku_attribution=true` in `temp/rbos.config` — system degrades to name-matching-only if absent or no API key
- [ ] Log cache hit rate to `index_status()` output so user can see value

---

## Phase 5 — Slack Ingest and Attribution

_Placeholder. Not yet ingested. Sequence mirrors Phase 1 once ingest exists._

- [ ] **Owner decision first:** is Slack a material signal today? If yes, this phase moves above Phase 3.
- [ ] Ingest `slack_messages` (see any existing SLACK-INGEST working doc if present)
- [ ] Apply `project_classifier` matchers to message text — same pattern as email
- [ ] Add `slack_mention_counts: dict[str, int]` to `DashboardPayload`
- [ ] Include in synthesis prompt

---

## Open Questions

1. **`GitHub Repos.md` vs replace `rebalanceOS Dashboard.md`?**
   Recommendation: new file. The dashboard note carries goals, highlights, and calendar
   context that don't belong in a repo index. Keep concerns separate.

2. **Haiku threshold for attribution assist — on by default or opt-in?**
   Recommendation: opt-in via `haiku_attribution=true` in `rbos.config`. Name-matching
   handles the majority of cases; Haiku is for the tail.

3. **Is Slack a material signal today?** If yes, Phase 5 moves above Phase 3.

4. **Manual tier vs signal-inferred rank.** Recommendation recorded in Design Principle 6:
   manual tier always wins. Signal counts are evidence, not the sort key.
