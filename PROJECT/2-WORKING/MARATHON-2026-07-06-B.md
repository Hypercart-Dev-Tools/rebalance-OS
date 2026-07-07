---
title: MARATHON — 2026-07-06-B (HELD — GH-102 Phase 5 seam #4 disposition overlay)
status: Held (un-fired — awaiting operator go + XYZ-side export confirmation)
created: 2026-07-06
updated: 2026-07-06
owner: noel@neochro.me
branch: marathon/2026-07-06-b
roadmap_exempt: true
goal: >
  Preflighted, DELIBERATELY-HELD lane for GH-102's newly-added Phase 5 (seam #4 — XYZ per-issue
  disposition overlay onto github_items). Lane A is the Phase 5.0 contract-lock spike (doc-only,
  discovery); the Reb-side collector build is a gated follow-on that does NOT run until 5.0 locks
  the emit contract. Not seeded, not fired — this file exists to hold the ready analysis, not to
  drive it. roadmap_exempt: coordination artifact; the tracked deliverable is GH-102 Phase 5.
---

# MARATHON — 2026-07-06-B (HELD)

## Status

| What was just completed | What's next |
|---|---|
| **Nothing driven — this marathon is HELD by design.** GH-102 extended with Phase 5 (seam #4) + a 5.0 contract-lock spike (2026-07-06). This doc preflights the work into lanes and stops. Today's *other* marathon ([MARATHON-2026-07-06.md](MARATHON-2026-07-06.md)) is already Completed/closed; this is a separate held file so a closed marathon is not reopened. | **Operator decision:** (a) confirm whether the XYZ harness can emit a *deterministic* per-issue disposition export (not the `agy`/Gemini render), then (b) release **Lane A** (the 5.0 spike, doc-only) to run. Lane B (Reb collector) stays gated behind 5.0's locked contract. Nothing is seeded until you say go. |

## Why this is HELD, not fired

Two honest blockers make firing premature (both are exactly what the 5.0 spike exists to resolve):

1. **The XYZ-side emit may not exist yet.** Today XYZ ships session-health `XYZ.json` (GH-75) and a
   *Gemini-rendered* Obsidian rollup. Neither is a deterministic per-issue disposition export. Lane B
   (the Reb collector) has nothing real to read until that emit is confirmed or built XYZ-side.
2. **Lane A is a discovery/authoring spike, not a headless code lane.** Like GH-102's own Phase 0, it
   is read-and-decide with a written-back findings contract — judgment work, not a bounded code-to-spec
   `relay-xyz` build. It should be run deliberately, not swept into an auto-driven wave.

## Preflight — freshness / bounded-path / disjointness

Same manual analysis MARATHON-2026-07-06 applied to its lanes.

| Lane | Source | Ready? | Kind |
|---|---|---|---|
| A | [GH-102](GH-102-XYZ-REBALANCE-INTEGRATION.md) Phase 5.0 | **Ready to hold.** Fully spec'd discovery checklist + exit criteria + QA gate already written in GH-102. Doc-only, no code. | Discovery spike (manual / authoring) |
| B | [GH-102](GH-102-XYZ-REBALANCE-INTEGRATION.md) Phase 5 build | **Gated — not ready.** Needs 5.0 to lock the emit schema + confirm the XYZ export exists. Build against fixture only after that. | Reb-side code lane (future) |

**Disjointness (tick literal-prefix rule):**

| Lane | Paths |
|---|---|
| A | `PROJECT/2-WORKING/GH-102-XYZ-REBALANCE-INTEGRATION.md` (write-back only) |
| B (future) | `src/rebalance/ingest/index_ops.py`, `src/rebalance/ingest/xyz_disposition.py` (new), `tests/test_xyz_disposition.py` (new), `ARCHITECTURE/system-diagram.html`, `PROJECT/2-WORKING/GH-102-XYZ-REBALANCE-INTEGRATION.md` |

Lane A and Lane B **share** `GH-102-...md`, so they can never run concurrently — B is sequenced strictly
after A by design (A writes the contract B builds against). No concurrency claim is made here.

## Lane A — GH-102 Phase 5.0 contract-lock spike (HELD)

- **Paths:** `PROJECT/2-WORKING/GH-102-XYZ-REBALANCE-INTEGRATION.md` (findings write-back)
- **Contract:** Execute GH-102 Phase 5.0's observable checklist — confirm/deny the XYZ deterministic
  disposition export, lock the emit schema (`repo`, `gh_issue`, `disposition`, `reason`, `updatedAt`),
  fix consume-source = deterministic ROADMAP parse (never the Gemini render), lock the
  `(repo, issue_number)` join key onto `github_items`, confirm the `xyz_disposition` projection
  collector seam. Write findings back per the PDDA discovery contract.
- **Acceptance:** GH-102 Phase 5.0 exit criteria met + its QA checklist ticked; `utils/pdda/pdda.sh run`
  clean. No Rebalance code changed.

## Lane B — GH-102 Phase 5 Reb collector (GATED, not in this held wave)

- **Gate:** do not start until Lane A has locked the contract and the XYZ export is confirmed to exist.
- **Contract (preview):** `register_collector("xyz_disposition", …)` projection joining disposition +
  reason onto `github_items`; decision-gated → `get_next_actions`; disagreement detector; observe-only
  priority inference; add the `xyz` node to `ARCHITECTURE/system-diagram.html`. Build against a fixture
  export first (mirrors GH-102 Phase 2's fixture approach).
- **Acceptance:** GH-102 Phase 5 QA checklist — fixture litmus (decision-gated surfaces, disagreement
  flags, absent = no-op), `pytest tests/` green, `rebalance doctor` clean, `pdda run` clean, self-mergeable PR.

## Seed (coordinator — DO NOT RUN until released)

```bash
# HELD — intentionally not executed. Uncomment only after the operator releases Lane A.
# tick log task.created MARATHON0706B-GH102-P50 --agent dispatcher --priority 20 \
#   --paths "PROJECT/2-WORKING/GH-102-XYZ-REBALANCE-INTEGRATION.md" \
#   --note "GH-102 Phase 5.0 contract-lock spike: lock the XYZ per-issue disposition emit + join. Doc-only, findings write-back. See GH-102 Phase 5.0."
```

## Hard invariants (carry into the session prompt when released)

- [ ] Lane A writes only to `GH-102-...md` — no Rebalance code, no XYZ tree writes.
- [ ] Consume-source decision is the deterministic ROADMAP parse, **never** the Gemini/`agy` render.
- [ ] The priority-tier inference (Lane B) is observe-only — it must never write `project_registry`.
- [ ] Absence (no XYZ export) is a normal state, never an error (GH-102 invariant 3).
- [ ] On finish, update GH-102's Status table + `updated:`, and this file's Status table.
