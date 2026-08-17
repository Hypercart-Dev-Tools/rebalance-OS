---
title: "Show incoming (not-yet-activated) XYZ HQ data in the architecture diagram"
owner: noel@neochro.me
gh_issue: 120
source: "https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/120"
status: "Completed 2026-07-16 via MARATHON-2026-07-16-B Lane A (PR #134, merged to development). Diagram/spec only — no collector activation."
created: 2026-07-06
updated: 2026-07-07
doc_type: project
goal: >
  Update ARCHITECTURE/system-diagram.json (and the inlined spec in system-diagram.html that renders it)
  to show the XYZ HQ cross-repo signal as a source that is arriving but NOT yet activated — so the
  architecture render distinguishes live sources from the staged XYZ feed gated behind GH-102's
  default-off toggle.
non_goals: >
  Not activating the collector or changing any ingest behavior. Diagram/spec only. Not adding the
  Seam #4 disposition collector to code — that is GH-102 Phase 5, toggle-gated and separate.
related:
  - PROJECT/2-WORKING/GH-102-XYZ-REBALANCE-INTEGRATION.md
effort: 1
complexity: 1
risk: 1
phases: 1
---

## Status

| What was just completed | What's next |
|---|---|
| **Captured 2026-07-06** from issue #120. Confirmed the render path: `system-diagram.html` inlines the spec via `renderDiagram({...})`, and `system-diagram.json` is the standalone spec — **both** must carry the new node to stay in sync. **Shipped 2026-07-16** via [MARATHON-2026-07-16-B](../2-WORKING/MARATHON-2026-07-16-B.md) Lane A (PR #134) — the original MARATHON-2026-07-07 Lane B queueing was superseded by the 2026-07-16 GH-issue triage sweep, which re-picked this issue up fresh. | **Done.** |

---

## Table of contents

- [Thesis](#thesis)
- [Phase 1 — Add the staged XYZ HQ node (marked not-active)](#phase-1--add-the-staged-xyz-hq-node-marked-not-active)
- [Anti-goals](#anti-goals)

---

## Thesis

The diagram currently shows five live sources (github, vault, calendar, sleuth, gmail) fanning into
collectors → SQLite. XYZ HQ is a sixth signal that's *staged but off* (GH-102 Seams #1/#4, toggle
`REBALANCE_XYZ_DISPOSITION` default-off). The diagram should show it as **incoming, not yet wired hot**
— visually distinct from the live sources — so the architecture render tells the truth about what's
active vs. planned. Spec-only, no code.

---

## Phase 1 — Add the staged XYZ HQ node (marked not-active)

**Observable checklist:**

- [x] **Add an `xyz_hq` external source node** ("XYZ HQ", description: cross-repo marathon/session state
      + per-issue disposition) to `ARCHITECTURE/system-diagram.json`.
- [x] **Add a staged collector/overlay node** feeding the signal plane (`xyz_disposition_collector`,
      matching the real GH-102 Seam #4 naming), so the fanout shape matches the other sources.
- [x] **Mark it not-yet-active.** Used the renderer's existing `async` edge `kind` (renders dashed) on
      all three new edges, plus `(planned)` appended to every new node/edge label.
- [x] **Mirror the change into `system-diagram.html`'s inlined `renderDiagram({...})` spec** — verified
      programmatically byte-identical to the standalone JSON, no drift.
- [x] **Render check:** confirmed the XYZ HQ node is visually distinguishable (dashed + "(planned)")
      from the five live sources.

### Phase 1 — QA checklist

- [x] **Litmus:** the rendered diagram shows XYZ HQ as incoming-but-staged, distinct from live sources.
- [x] **Sync:** `system-diagram.json` and the inlined spec in `system-diagram.html` carry the same node
      set (verified identical via JSON comparison, not eyeballed).
- [x] **Truthful:** the node is clearly marked not-active — it must not imply the collector is live
      (it isn't; GH-102 toggle is default-off).
- [x] **No code/behavior change:** only the two diagram files touched; `utils/pdda/pdda.sh run` clean.
      Landed via PR #134 (MARATHON-2026-07-16-B Lane A), merged to `development` 2026-07-16.

---

## Anti-goals

- **Not an activation.** The node is documentation of a *staged* source; no collector is registered, no
  ingest changes. Showing it live would be a lie until GH-102 Phase 5 lands and the toggle is flipped.
- **Not a diagram redesign.** One source + its collector node added in the existing style — no re-layout,
  no renderer changes beyond using an edge `kind` the renderer already supports.
