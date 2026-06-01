# Decouple Obsidian as Source of Truth for GitHub Activity

**Status:** In Review  
**Author:** Claude Code  
**Owner:** Noel  
**Created:** 2026-05-31

---

## The Problem We Found

`BinoidCBD/LTVera-Pandas` has 573 commits in the last 14 days and ranks #2 by recency in `github_activity`. It shows up in every sync log. But the "Recent GitHub Activity" dashboard showed zero activity for LTVera because `project_registry.repos_json` for LTVera is `[]` — nobody ever added the repo to the project entry in Obsidian.

This is a silent filter. The data is there. The sync is working. But a forgotten manual step in Obsidian causes the entire project's activity to disappear from dashboards. The user has no idea why.

This is the wrong architecture for a tool that is supposed to surface what's actually happening.

---

## Current Architecture (What Gates Activity Today)

```
GitHub Events API
      ↓
github_activity table  ← all repos, all events, correct data
      ↓
project_registry.repos_json  ← MANUAL, Obsidian-sourced, GATES DISPLAY
      ↓
Dashboard / "Recent GitHub Activity" widget
```

The `project_registry` table has a `repos_json` column that lists which repos belong to each project. This list is populated from Obsidian project entries. If a repo isn't in that list, it is invisible to every project-level view — even if it's the most-active repo on the account.

### What is Obsidian's current role:
1. **Project definition** — project names, clients, priority tiers (`LTVera`, `Binoid`, etc.)
2. **Repo registration** — `repos_json` links repos to projects (the broken gate)
3. **Note content** — vault notes are vectorized for semantic search (working, keep this)
4. **Dashboard output** — `rebalanceOS Dashboard.md` is written into the vault (stale, last generated May 12)

Problems 1 and 2 are the ones we are fixing. Problems 3 and 4 are kept.

---

## Proposed Architecture

```
GitHub Events API
      ↓
github_activity table  ← all repos, all events (unchanged)
      ↓
Group by GitHub org (auto-discovery, zero config)
      ↓
Dashboard / activity feed  ← all repos visible immediately
      ↑↓  (optional, additive)
GitHub Repos.md in Obsidian vault  ← enrichment, never a gate
```

**Core principle: every repo you push to is visible by default. Obsidian annotations are enrichment, not admission control.**

---

## What Changes

### 1. Remove the `repos_json` filter from all queries

The immediate fix is to comment out the filter that joins `github_activity` to `project_registry.repos_json`. Every repo in `github_activity` becomes visible. No data changes — just a query change.

This is the "see what happens" phase. Risk is low: the data was already there, we're just surfacing it.

### 2. Group by GitHub org instead of project name

Instead of "LTVera: 0 repos linked, 0 commits" — show "BinoidCBD: 7 repos, 641 commits."

The org is the natural default grouping signal because it is:
- Already in the repo name (`BinoidCBD/LTVera-Pandas`)
- Always present without any configuration
- Meaningful (orgs map roughly to clients or teams)

**Known limitation:** `Hypercart-Dev-Tools` is a noisy org containing unrelated projects. This is fine for the default view. The bi-directional Obsidian page (Phase 2) is how power users sub-divide noisy orgs — but it never gates anything.

### 3. Auto-populate a bi-directional Obsidian page

After each sync, write (or update) `GitHub Repos.md` in the vault:

```markdown
# GitHub Repos (auto-discovered)
_Last updated: 2026-05-31 20:00 UTC — edit annotations freely, deletions are ignored_

## BinoidCBD
- [ ] BinoidCBD/LTVera-Pandas — 573 commits · last active 2026-06-01
- [ ] BinoidCBD/LTVera — 20 commits · last active 2026-05-28
- [ ] BinoidCBD/universal-child-theme-oct-2024 — 2 commits · last active 2026-05-31

## Hypercart-Dev-Tools
- [ ] Hypercart-Dev-Tools/ask-self — 97 commits · last active 2026-06-01
- [ ] Hypercart-Dev-Tools/rebalance-OS — 60 commits · last active 2026-06-01
...

## BinoidCBD — custom project labels (optional)
<!-- Add a project: label to override the org grouping for any repo -->
- BinoidCBD/LTVera-Pandas — project: LTVera
- BinoidCBD/LTVera-wp-theme — project: LTVera
```

**Read direction:** sync writes the full repo list here on each run.  
**Write direction:** user can add `project: X` annotations to any repo line. On next sync, those annotations are read and used for sub-grouping within the org. A repo without an annotation just stays under its org — it is never hidden.

### 4. Obsidian notes remain fully vectorized

All Obsidian vault content continues to be ingested into the vector index. This is unchanged. The only thing being removed is the role of Obsidian project entries as a *filter* on GitHub activity. Obsidian content as *context* is unaffected.

---

## What Stays the Same

- `github_activity` table schema and sync logic — no changes
- `github_sync.sh` and all ingest scripts — no changes
- Obsidian vault vectorization — no changes
- `project_registry` table exists, but stops gating the activity feed; it becomes an optional enrichment layer
- Calendar-based project inference — no changes

---

## What Could Fall Apart

This is the section to read if something breaks after the decouple.

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Dashboard gets noisy — too many repos visible at once | High | Medium | Add a "min commits in window" threshold (e.g. only show repos with ≥1 commit in 14d); this is a display filter, not a gate |
| `Hypercart-Dev-Tools` org becomes a wall of unrelated items | High | Low | Phase 2 bi-directional page lets user add `project:` labels; no urgency |
| Something downstream joins `project_registry.repos_json` we haven't found | Medium | High | Audit before shipping Phase 1 — grep codebase for `repos_json` to find all consumers |
| Auto-generated `GitHub Repos.md` overwrites user edits | Medium | High | Write to a temp page first; only replace repo list lines (keyed by `repo_full_name`), preserve user annotation lines |
| `project_registry` is still read by a scheduled report we forgot about | Low | Medium | Phase 1 is "comment out, observe" — run for 1 week before deleting anything |
| Obsidian vault path changes across devices | Low | Low | Already handled by `REBALANCE_SECRETS_DIR` resolver |

---

## Phased Plan

### Phase 1 — Comment out, observe (immediate, low risk)

- [ ] Grep codebase for all consumers of `project_registry.repos_json` — list every query and report that uses it
- [ ] Comment out (do not delete) the `repos_json` filter in those queries; replace with "show all repos in `github_activity`"
- [ ] Add org-based grouping to the activity feed query (`SUBSTR(repo_full_name, 1, INSTR(repo_full_name, '/') - 1) AS org`)
- [ ] Run for 1 week; observe what appears, check for noise
- [ ] Note anything that breaks or looks wrong

### Phase 2 — Bi-directional Obsidian page

- [ ] Add `github_repos_page` step to `github_sync.sh` — writes `GitHub Repos.md` to vault after each sync
- [ ] Write logic is additive: update existing repo lines (commit count, last active), never delete user-added annotation lines
- [ ] Add sync read step: scan `GitHub Repos.md` for `project: X` annotations; load into an in-memory enrichment dict; apply as display-only labels (not stored back into `project_registry`)
- [ ] Confirm new repos pushed to any org appear in the next sync cycle without any Obsidian action

### Phase 3 — Clean up (after 2–4 weeks of Phase 1 observation)

- [ ] Delete `repos_json` column from `project_registry` if nothing broke
- [ ] Regenerate the rebalance dashboard with org-based grouping
- [ ] Update `ARCHITECTURE.md` and `CHANGELOG.md` to reflect the new model
- [ ] Archive this doc to `3-DONE`

---

## Obsidian Onboarding Design — Research Prompt for Claude Opus

Use this prompt to explore onboarding design options before implementing Phase 2.

---

**Prompt:**

```
You are designing the onboarding experience for a personal developer dashboard called rebalanceOS.

rebalanceOS syncs GitHub activity, calendar events, and Obsidian vault notes into a SQLite 
database, then surfaces them as project-level dashboards, activity feeds, and semantic search.

CURRENT PROBLEM:
The system previously required users to manually register GitHub repos to named projects inside 
Obsidian (e.g. "link BinoidCBD/LTVera-Pandas to the LTVera project"). This was a silent gate — 
if a user forgot to register a new repo, it disappeared from all dashboards with no warning. 
This caused real confusion and eroded trust in the tool.

NEW DEFAULT BEHAVIOR (already decided):
- Every repo the user pushes to is visible by default, grouped by GitHub org
- No manual registration required for a repo to appear
- Obsidian vault content is still vectorized for semantic search
- A file called GitHub Repos.md is auto-written to the vault after each sync, listing all 
  discovered repos with their recent commit counts
- Users CAN add "project: X" annotations to repo lines in that file to sub-group repos 
  within a noisy org (e.g. Hypercart-Dev-Tools contains 12 unrelated projects), but failing 
  to annotate NEVER hides a repo

YOUR TASK:
Design the ideal onboarding experience for this system, with the constraint that 
**zero configuration is the default state** — the tool works fully without any setup. 
Configuration is only for *reclassification* (overriding the default org grouping) 
and *enrichment* (adding client names, priority tiers, notes to a project).

Consider:
1. What does the GitHub Repos.md file look like on first open? What makes a new user 
   understand what it is and what (if anything) they should do with it?
2. Is there a smarter auto-grouping signal than GitHub org that requires zero config? 
   (e.g. calendar event text matching repo names, repo topics, commit message patterns)
3. If a user WANTS to add project labels, what is the lowest-friction way to do that 
   inside Obsidian without learning a new syntax?
4. Should the file be read-only (system writes, user reads) or editable (bi-directional)?
   What are the failure modes of each?
5. Is Obsidian even the right place for optional enrichment, or is there a better surface 
   (e.g. a simple CLI prompt on first run: "BinoidCBD looks like a client org — what should 
   we call it?")?

Constraints:
- The user is a solo developer or small team (1-4 people)
- They often forget to update configuration
- They use Obsidian daily but not as a structured database — more as a scratchpad
- The system must degrade gracefully: if Obsidian isn't open, if the vault moves, 
  if the user ignores GitHub Repos.md entirely — everything still works
- Prefer solutions that create value on day 0 without any user action

Output: a ranked list of onboarding approaches with trade-offs, followed by your 
recommended approach with a concrete example of what the user sees on first run.
```

---

## Open Questions (Resolve Before Phase 2)

1. **What is the `Hypercart-Dev-Tools` grouping strategy?** Org grouping flattens it. Do we want a default sub-group by repo name prefix (`WP-*`, `KISS-*`, `rebalance-*`) as a heuristic within noisy orgs?
2. **Who writes `project_registry` today?** Is it only populated from Obsidian, or does `rebalance ingest` have its own logic? Audit before commenting anything out.
3. **Does the stale dashboard (`rebalanceOS Dashboard.md`, last generated May 12) need to be regenerated as part of Phase 1, or left as-is until Phase 3?**
4. **Cross-org projects:** LTVera spans `BinoidCBD/LTVera-Pandas`, `BinoidCBD/LTVera`, and `BinoidCBD/LTVera-wp-theme` — all in the same org, so org grouping handles this naturally. But what if a project ever spans two orgs? Punt to Phase 2 annotations.
