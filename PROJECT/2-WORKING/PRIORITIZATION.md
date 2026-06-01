# Project Prioritization — Signal-Agnostic Design

**Status:** Draft for review  
**Constraint:** Obsidian remains the write/configuration interface for user overrides.

---

## Problem

GitHub commit activity is a proxy for project priority, not priority itself. A client
receiving heavy email, calendar time, and Slack discussion — but no commits yet — is
high-priority by any reasonable measure. The old `_determine_verdict()` (removed in the
simplification audit) conflated "GitHub quiet" with "low priority," which was wrong
and is now gone.

The goal is to replace that single-signal heuristic with a transparent, multi-signal
count that the user can inspect, override, and trust.

---

## Design principles

1. **Counts before conclusions.** Surface raw per-project signal counts (calendar hours,
   email threads, Slack mentions, GitHub commits/PRs). Let the user — or a summariser —
   draw conclusions from those, not the system.

2. **Auditable over magical.** If a project is ranked high, the reason must be a
   one-line answer: "8 hours of calendar time + 3 email threads this week." Opaque
   ML-inferred priority scores erode trust the same way silent `repos_json` gating did.

3. **Obsidian as the override surface.** The system infers; the user corrects in Obsidian.
   DB is source of truth; the file is a regenerated view that also accepts `#tag` input
   and priority tier overrides. (See CLAUDE-ONBOARDING.md for the full annotation model.)

4. **Haiku as an attribution assistant, not a priority judge.** When name-matching is
   uncertain ("does this email thread belong to LTVera or BinoidCBD?"), Haiku helps
   classify. It does not emit a priority verdict — the counts do that.

5. **Graceful degradation at every layer.** A project with no email/Slack ingest still
   shows calendar + GitHub signals. A project with no repos still shows calendar signals.
   No signal combination should produce a blank row.

---

## Signal inventory

| Signal | Source table | Attributed how | Current state |
|---|---|---|---|
| Calendar time (hours) | `calendar_events` | Project classifier (name + alias match) | ✅ Working |
| GitHub commits / PRs | `github_activity` | Org-grouped (Phase 3 of simplification) | ✅ Working |
| Email threads | `gmail_messages` | Name-match against subject + sender (same classifier pattern) | ❌ Not attributed |
| Slack mentions | (not yet ingested) | Name-match against message text | ❌ Not ingested |
| Vault mentions | `vault_notes` | Name-match against note body | ⚠️ Partial (semantic index) |
| User priority override | `project_registry.priority_tier` | Obsidian write-back via `sync_registry(pull)` | ✅ Working |

---

## Target architecture

```
Raw signals                 Attribution layer           Payload
─────────────────           ──────────────────          ─────────────────────────
calendar_events   ──┐
gmail_messages    ──┤──→  project_classifier  ──→  per-project signal counts
vault_notes       ──┤      (name + alias match)      { calendar_hours,
github_activity   ──┤      + Haiku assist for         email_threads,
slack_messages    ──┘      low-confidence items        vault_mentions,
                                                       github_commits }
                                                           │
                                                           ▼
                                                  synthesize_dashboard_narrative()
                                                  (Gemini/Haiku narrates FROM counts)
                                                           │
                                                           ▼
                                                  Obsidian note + TUI + web
```

The attribution layer already exists for calendar events (`project_classifier.py`,
`annotate_events_with_projects()`). It needs to be applied to email and eventually
Slack using the same matchers.

---

## Obsidian write interface

Keeping CLAUDE-ONBOARDING.md recommendations. Three layers of grouping, all
zero-config, all reversible:

```
GitHub Repos.md (system-written, user-annotatable)
──────────────────────────────────────────────────
## BinoidCBD · 3 repos
  ### LTVera  (auto-detected from name prefix — add a #tag to override)
  - LTVera-Pandas    — 47 commits  · 2h calendar  · 1 email thread
  - LTVera-API       — 12 commits  · 0h calendar
  - storefront-theme — 3 commits   · 1h calendar

## Hypercart-Dev-Tools · 12 repos
  - invoice-gen    — 8 commits   ← add  #billing  to group
  - billing-cron   — 5 commits
```

Signal counts appear inline on repo lines — users can see *why* the system
thinks something is active without opening a separate view.

Priority tier overrides live in `project_registry.md` (existing surface),
not in `GitHub Repos.md`. Keep the two concerns separate: grouping annotation
goes in the repo file; priority decisions go in the project registry.

---

## Implementation sequence

### Step 0 — Foundation ✅ (done)
Simplification audit complete. Every repo visible, no silent gating,
`note_builder.py` at the read-only floor described in CLAUDE-ONBOARDING.md.

### Step 1 — Email attribution
Apply `project_classifier.py` matchers to `gmail_messages` (subject + sender).
Output: per-project email thread count added to `DashboardPayload`.
No new UI. No new DB tables. One new query + payload field.

> This is the highest-value next step because email is already ingested
> (`gmail_messages` table exists per GMAIL-INGEST.md) and the classifier
> is already written.

### Step 2 — Obsidian annotation surface (`GitHub Repos.md`)
New file, separate from `rebalanceOS Dashboard.md`. Written by a new
`write_repo_index()` function in `note_builder.py`.

- Floor: org-grouped repo list with inline signal counts (Step 1 counts appear here)
- Quick win: prefix-cluster auto-grouping within each org (`LTVera-*` → sub-group)
- Core: `#tag` parsing with SQLite write-back via existing `sync_registry(pull)`

Prefix clustering lives here, not as a standalone step.

### Step 3 — Multi-signal payload
Extend `build_dashboard_payload()` and `DashboardPayload` to carry per-project
signal counts from all attributed sources (calendar ✅, email after Step 1, vault).
Update `synthesize_dashboard_narrative()` prompt to include these counts.

At this point the narrative summary becomes genuinely multi-signal.

### Step 4 — Haiku attribution assist
For email/vault items where name-matching confidence is below a threshold,
batch them and ask Haiku to classify (project name → yes/no/unknown).
Cache results in the DB to avoid repeated calls.

This is the only step that requires an LLM call at attribution time (not just
summary time). Keep it optional and skippable — the system should degrade to
name-matching-only if no API key is present.

### Step 5 — Slack ingest + attribution
Slack ingest is not yet built. Once it exists, attribution follows the same
pattern as email (Step 1). Placeholder for now.

---

## Where prefix clustering fits

Step 2 — it is a display transform within the Obsidian annotation surface,
not a standalone phase. It is roughly the middle of the sequence, not the end.

The end is Step 3/4: a payload that aggregates real multi-signal counts per project
and a narrative that reflects all of them. Prefix clustering is the UX layer that
makes the *grouping* legible; the signal counts are what make the *priority* legible.

---

## Open questions for owner

1. **`GitHub Repos.md` — new file or replace `rebalanceOS Dashboard.md`?**
   Recommendation: new file. The dashboard note carries goals, highlights, and
   calendar context that don't belong in a repo index. Keep them separate.

2. **Haiku threshold for attribution assist (Step 4) — on by default or opt-in?**
   Recommendation: opt-in initially. A flag in `temp/rbos.config` (`haiku_attribution=true`).
   Name-matching alone handles the majority of cases correctly.

3. **Slack ingest priority.** Is Slack a material signal for you today? If yes, Step 5
   moves up. If the main communication surface is email + calendar, Step 5 can wait.

4. **Priority tier vs inferred rank — which wins in the sorted project list?**
   Current: `priority_tier` (user-set) is the primary sort key; signal counts are not
   yet in the sort. After Step 3, should signal counts influence sort order, or should
   manual tier always win?
   Recommendation: manual tier always wins. Signal counts appear as evidence; the
   human decides rank. Otherwise the system can silently re-rank a project the user
   intentionally deprioritised.
