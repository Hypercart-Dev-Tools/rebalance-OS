---
title: "Show incoming (not-yet-activated) XYZ HQ data in the architecture diagram"
owner: noel@neochro.me
gh_issue: 120
source: "https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/120"
status: "Active (2-WORKING) — promoted 2026-07-07; queued in MARATHON-2026-07-07 Lane B, ready to fire (not yet fired). Diagram/spec only — no collector activation."
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
| **Captured 2026-07-06** from issue #120. Confirmed the render path: `system-diagram.html` inlines the spec via `renderDiagram({...})`, and `system-diagram.json` is the standalone spec — **both** must carry the new node to stay in sync. | **Phase 1** — add an `xyz_hq` source + staged-collector node, marked not-yet-active (dashed/"planned" edge convention), to both files. Queued in [MARATHON-2026-07-07.md](MARATHON-2026-07-07.md) Lane B. |

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

- [ ] **Add an `xyz_hq` external source node** ("XYZ HQ", description: cross-repo marathon/session state
      + per-issue disposition) to `ARCHITECTURE/system-diagram.json`.
- [ ] **Add a staged collector/overlay node** feeding the signal plane (`github_items` overlay per
      GH-102 Seam #4), so the fanout shape matches the other sources.
- [ ] **Mark it not-yet-active.** Use a visible convention the renderer already supports — e.g. a
      `kind` on its edges that renders dashed (the renderer has `async`/`data` dashes), plus a label
      like "planned / toggle-off" — so it reads as staged, not live.
- [ ] **Mirror the change into `system-diagram.html`'s inlined `renderDiagram({...})` spec** so the
      rendered page and the standalone JSON stay identical (they drift otherwise).
- [ ] **Render check:** open `system-diagram.html`, confirm the XYZ HQ node appears and is visually
      distinguishable from the five live sources.

### Phase 1 — QA checklist

- [ ] **Litmus:** the rendered diagram shows XYZ HQ as incoming-but-staged, distinct from live sources.
- [ ] **Sync:** `system-diagram.json` and the inlined spec in `system-diagram.html` carry the same node
      set (no drift between the two).
- [ ] **Truthful:** the node is clearly marked not-active — it must not imply the collector is live
      (it isn't; GH-102 toggle is default-off).
- [ ] **No code/behavior change:** only the two diagram files touched; `utils/pdda/pdda.sh run` clean.
      Lands via self-mergeable PR (main is protected).

---

## Anti-goals

- **Not an activation.** The node is documentation of a *staged* source; no collector is registered, no
  ingest changes. Showing it live would be a lie until GH-102 Phase 5 lands and the toggle is flipped.
- **Not a diagram redesign.** One source + its collector node added in the existing style — no re-layout,
  no renderer changes beyond using an edge `kind` the renderer already supports.
