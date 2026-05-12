# P3 Coaching Signals Wedge

> Replace Goaly's mtime-based coaching proxies with rebalance's real activity signals, but stop there. This is the 80/20 path: one small MCP surface, no task/KPI import, no new schema, no runtime dependency in either direction.

## TOC

- Goals
- Assumptions
- Non-Goals
- Current State
- Architecture Direction
- Phase 0 — Match Quality Spike
- Phase 1 — `coaching_signals` Tool
- Deferred Work
- Contracts And Ownership
- Risks And Guardrails
- Success Criteria
- Open Questions

## Goals

- Replace Goaly's `_notion_edited` and file-mtime coaching proxies with real project activity from rebalance's local store.
- Ship the smallest useful surface first: one read-only MCP tool and one CLI mirror for manual smoke tests.
- Keep the systems independent. Rebalance remains useful with no Goaly repo present; Goaly remains useful when the MCP call is unavailable.
- Prove value in real coaching sessions before absorbing any goal, KPI, or task data model into rebalance.

## Assumptions

- The highest-value coaching question is still project-level: "did this client/project actually move?" That can be answered from existing `github_activity`, `github_items`, `calendar_events`, and `project_registry` tables.
- Goaly can continue to own task, KPI, goal, and coaching-session state. Rebalance only needs the project names Goaly already has in hand.
- Project-name matching can be made reliable enough by reusing rebalance's existing alias machinery in [../../src/rebalance/ingest/project_classifier.py](../../src/rebalance/ingest/project_classifier.py), plus a small number of operator-managed aliases when needed.
- Single-operator, local-first use means batch calls over a few dozen projects are fine. No network calls are required at tool runtime.

## Non-Goals

- No `goals`, `kpis`, or `tasks` tables in rebalance.
- No import of Goaly markdown into the rebalance vault.
- No KPI freshness or spear-sharpening logic in v1.
- No frog-eaten embedding matcher in v1.
- No composite `coaching_prep` bundle in v1.
- No port of Goaly skills into rebalance. Goaly stays the coaching UX; rebalance provides ground-truth signals.

## Current State

Rebalance already has the signal layer needed for this wedge. [../../src/rebalance/mcp_server.py](../../src/rebalance/mcp_server.py) exposes project, GitHub, and calendar surfaces over the local SQLite store. [../../src/rebalance/ingest/project_classifier.py](../../src/rebalance/ingest/project_classifier.py) already owns canonical project-name alias matching for calendar and attention surfaces.

What is missing is a coaching-shaped read model. Today Goaly's detectors mostly answer "was the markdown file touched," which is a weak proxy for whether work happened. Rebalance can answer the load-bearing question more directly: was there recent code movement, PR movement, issue movement, or client-touch movement for this project?

The previous full-port direction asked rebalance to absorb Goaly's entire goal layer. That is still possible later, but it is not the 80/20 move. The 80/20 move is a thin activity-truth seam that leaves all planning content in Goaly.

## Architecture Direction

```
GOALY (markdown + skills)                    REBALANCE (existing local store)
────────────────────────                    ────────────────────────────────
/goaly-coaching-prep  ────────┐
/mission                      │             project_registry
/goaly-triage                 ├── MCP ───▶ github_activity
                │             github_items
active project names ─────────┘             calendar_events
                      project_classifier aliases
                         │
                         ▼
                    coaching_signals(projects, since_days)
                         │
                         ▼
               [{requested_project, matched_project, match_status,
                 commits_count, prs_opened, prs_merged,
                 issues_opened, issues_closed, calendar_touches,
                 last_commit_at, last_calendar_at, verdict}]
```

Two design constraints keep this small:

- Goaly does the file walking. Rebalance does not parse Goaly markdown in v1.
- Rebalance reuses the existing project matcher path. No coaching-specific alias store, no second fuzzy matcher.

## Phase 0 — Match Quality Spike

Timebox: half-day. Read-only. This is the gating check.

### Checklist

- [ ] Pull the current active project/client names from Goaly's coaching surfaces, not the whole repo.
- [ ] Run those names through a spike that reuses [../../src/rebalance/ingest/project_classifier.py](../../src/rebalance/ingest/project_classifier.py) normalization and alias logic.
- [ ] Measure exact-match, alias-match, ambiguous, and unmatched rates against `project_registry`.
- [ ] Add only the minimum alias fixes needed via existing project metadata or local priority rules. Do not invent a new config surface for coaching.
- [ ] Hand-check 10 recent projects against GitHub and calendar truth to confirm the tool would say something materially better than mtime.

### What Phase 0 Must Prove

- At least 90% of the active Goaly project names resolve cleanly to one rebalance project after minimal alias cleanup.
- Ambiguous names fail cleanly enough that Goaly can ask the user instead of hallucinating a match.
- There are enough real project rows where rebalance meaningfully disagrees with mtime that the integration is worth carrying.

### Deliverables

- [ ] Findings block appended to this doc: match rates, alias additions required, unmatched names, ambiguous names.
- [ ] If match quality is poor, stop here. Do not slide into schema work to compensate for weak names.

## Phase 1 — `coaching_signals` Tool

Objective: ship one batch-oriented read-only tool plus a CLI mirror. No new tables, no writes, no daily sync changes.

### Tool shape

```python
coaching_signals(
  projects: list[str],
  since_days: int = 14,
) -> {
  "rows": [
    {
      "requested_project": str,
      "matched_project": str | None,
      "match_status": "exact" | "alias" | "ambiguous" | "unknown",
      "matched_alias": str | None,
      "commits_count": int,
      "prs_opened": int,
      "prs_merged": int,
      "issues_opened": int,
      "issues_closed": int,
      "calendar_touches": int,
      "last_commit_at": str | None,
      "last_calendar_at": str | None,
      "verdict": "active" | "stalled" | "killed_mammoth" | "unknown_project",
    }
  ]
}
```

The important contract choices are deliberate:

- `projects` is a batch input so Goaly can build one accountability table in one call.
- `match_status` replaces fake fuzzy-confidence decimals. The repo already has deterministic alias matching; the API should admit that shape instead of pretending to produce calibrated scores.
- `verdict` is the load-bearing field. Raw counts are evidence, not the main product.

### Verdict rules

- `unknown_project` when `match_status` is `unknown` or `ambiguous`
- `killed_mammoth` when there are zero commits, zero PR opens/merges, and zero calendar touches in the window for an active project
- `stalled` when there are zero commits and zero PR opens/merges but at least one calendar touch
- `active` when there is at least one commit or at least one PR open/merge in the window

### Checklist

- [ ] Add `src/rebalance/coaching/__init__.py` and `src/rebalance/coaching/signals.py`.
- [ ] Implement matching by reusing normalization and alias-building patterns from [../../src/rebalance/ingest/project_classifier.py](../../src/rebalance/ingest/project_classifier.py). If a helper extraction is needed, extract it once and reuse it.
- [ ] Gather GitHub counts from `github_activity` and `github_items`.
- [ ] Gather calendar touches from already-classified events when available, and otherwise reuse the canonical project matcher over recent event summaries. Do not add a coaching-only calendar classifier.
- [ ] Register `coaching_signals` in [../../src/rebalance/mcp_server.py](../../src/rebalance/mcp_server.py).
- [ ] Add CLI mirror: `rebalance coaching signals --project "Acme" --project "Client B" --since-days 14`.
- [ ] Add tests in `tests/test_coaching_signals.py`: exact match, alias match, ambiguous, unknown, and each verdict branch.
- [ ] Document the tool in [../../MCP.md](../../MCP.md) under a new Coaching section.

### Phase 1 Acceptance

- Goaly can rebuild its coaching-accountability table from one MCP call and stop consulting file mtimes for that surface.
- At least one real project is flagged `stalled` or `killed_mammoth` where the existing mtime proxy would have looked deceptively fresh.
- Runtime stays under 500ms for a normal coaching batch on the local DB.
- With no Goaly repo present, the tool still works as a generic project-activity summarizer for any caller that passes project names.

## Deferred Work

Everything below is explicitly out of scope until `coaching_signals` has been used in at least 3 to 4 real coaching sessions and proved worth the maintenance cost.

- Frog-eaten matcher over GitHub embeddings
- KPI ingest and spear-sharpening detector
- Goal/task/KPI schema inside rebalance
- Composite `coaching_prep` bundle
- Ikigai surfaces
- Triage-specific and CEO-review-specific tools

The bar for promoting any deferred item is simple: the user must be able to point to a repeated miss or friction that `coaching_signals` alone does not solve.

## Contracts And Ownership

- Goaly owns tasks, KPIs, goals, and coaching prompts.
- Rebalance owns activity truth over GitHub, calendar, and project matching.
- Project matching must reuse the existing matcher path. If names drift, fix aliases in the existing project metadata or local config, not in a coaching-only side table.
- `verdict` and `match_status` are public MCP contract fields once shipped. Any change to those enums requires a coordinated update in Goaly.
- The tool must degrade cleanly: unknown names return structured rows, not exceptions.

## Risks And Guardrails

- **Naming drift.** Free-form project names will drift. Mitigation: make ambiguity explicit with `match_status`, keep alias fixes in one existing place, and stop if Phase 0 match quality is weak.
- **Calendar attribution is fuzzy.** Event summaries are noisier than repo names. Mitigation: count calendar only as supporting evidence; never let calendar alone produce `active`.
- **Scope creep.** Once the tool exists, it will be tempting to pull in tasks and KPIs. Mitigation: require 3 to 4 real-session misses before adding another surface.
- **False precision.** A decimal confidence score would imply calibration the current matcher does not have. Mitigation: use categorical match outcomes instead.

## Success Criteria

- [ ] Goaly's coaching-accountability surface no longer depends on `_notion_edited` or file mtimes.
- [ ] One real coaching session uses the tool and the user judges the verdicts more useful than the old proxy.
- [ ] At least one real row exposes talking-without-shipping or no-activity-at-all that would have been missed by mtime.
- [ ] Rebalance users who do not use Goaly can still call the tool directly with project names and get a useful answer.
- [ ] No new schema, ingest scope, or markdown parser was required to get this value.

## Open Questions

- [ ] Should the tool accept one project or many? Batch input is the default here because the coaching table is inherently multi-project, but the implementation can still expose a convenience single-project CLI wrapper.
- [ ] Should issue activity ever influence `verdict`, or stay evidence-only? Start evidence-only; promote only if real cases show it changes decisions.
- [ ] If Goaly project names keep drifting, is the next step a lightweight `rebalance_project:` frontmatter hint in Goaly, or a fuller schema absorption? Defer until Phase 0 results say the alias path is insufficient.
