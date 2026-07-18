# Marathon Phase gh135-p2
STATUS: Open
NEXT: codex

<!-- marathon-drive: task=MARATHON-GH135-P2-TURN builder=codex reviewer=agy round-cap=7 -->

## Phase Brief

# Phase 2 — one shared row component

Part of GH-135. Full contract: `PROJECT/2-WORKING/GH-135-PULSE-DASHBOARD-CONSISTENCY.md`.
Depends on Phase 1 (`format_timestamp` in `src/rebalance/tz_utils.py`).

## ⛔ Hard invariant

Phase 1 added `format_timestamp()` to the **existing** `src/rebalance/tz_utils.py`
(from GH-130). Consume it. Do not add a second time helper, and do not re-implement
timestamp formatting inside the row component — the row calls `format_timestamp`.

## Context

There is no shared row abstraction today. `src/rebalance/web_components.py` provides a
shared *shell* (`RB_TOKENS_CSS:17`, `RB_BUTTON_CSS:37`, `RB_CHROME_CSS:111`,
`render_shell`, sidebar), but every list in the Today view hand-rolls its markup, and
each got its own CSS block inside one ~730-line `PAGE_CSS` literal
(`scripts/pulse_web.py:1411-2137`):

`.activity-row :1773` · `.email-row :1786` · `.figma-row :1891` · `.kv-list :2028` ·
`.strip :2044` · `.pr-row :2070`

Closest prior art to reuse/generalize: the sidebar row primitives
`.side-list / .side-row / .side-row-title / .side-row-meta` (`web_components.py:152-162`).

## Design decision (already made — do not re-litigate)

The shared row **lands in `src/rebalance/web_components.py`**, so the drift this issue
fixes cannot recur on the other surfaces. **But adopt it only on the Today view in this
pass.** The live-rendered Focus 5 / What's Next / Auth Log pages (`src/rebalance/web.py`,
`_page()` at `:380`) keep their current rendering and opt in later. Verify those pages
still render unchanged before finishing.

## Task

### 1. Extract the row renderer

Add a `data_row(...)` renderer to `web_components.py`, named to match this codebase's
existing `render_*` / `_render_*` / `badge_html` convention. Fixed anatomy, in this order:

1. **Leading marker**, fixed width — checkbox / type badge / rank / avatar-letter.
2. **Body** — **title first** (medium weight), then one meta line below (person · chips).
3. **Trailing** — right-aligned timestamp block, from `format_timestamp` (Phase 1),
   using the monospace/tabular/muted class Phase 1 declared.

### 2. Zebra striping

Alternate rows get a ~3% ink background tint. Driven by the shared component (CSS
`:nth-child` on the shared list container, or an index the renderer passes) — **not**
re-declared per module. This must work identically for every list that adopts the row.

### 3. Adopt it in the Today view

Replace the hand-rolled markup in:

| Module | Renderer | Location |
|---|---|---|
| Reminders sidebar | `build_nav_data` sleuth branch | `pulse_web.py:1294-1367` |
| Recent GitHub activity | `render_recent_activity` | `:713-776` |
| Recent Figma comments | `render_recent_figma` | `:1163-1252` |
| What's Next | `render_work_next` | `:777-836` |
| Recently Completed | `render_hero` undo block | `:656-680` (+ JS re-render `:2170-2190`) |
| Today's Goals — Goals | `_render_goal_rows` | `:556-576` |
| Today's Goals — Next Open Todos | `_render_goal_rows(compact=True)` | `:641-645` |
| Today's Goals — Apple Reminders | `_render_reminder_rows` | `:579-619` |

**The client-side JS re-render path must stay in sync.** `PULSE_JS` (`:2147-2661`)
re-renders Recently Completed at `:2170-2190` after an undo; that JS must emit the same
row markup the Python renderer does, or the row silently changes shape on interaction.

### 4. Retire what the component subsumes

Delete the per-module row CSS blocks listed above once nothing references them. Leave
`.card` / `.card-head` / `.card-foot` (`:1607-1611`) alone — that is the container, not
the row, and it is genuinely reused already.

## Constraints

- **Presentation only.** No data-source, collector, route, or API-handler changes.
- **Never hand-edit `web/pulse.html`** — build artifact, regenerated from `pulse_web.py`.
- The goal-complete / reminder-complete POST handlers are behaviorally unchanged.
- No JS framework. The page stays server-rendered strings + vanilla JS.

## Acceptance

- [ ] All eight lists above render through the shared row; no module hand-rolls row markup.
- [ ] Zebra striping is declared once and applies to every adopting list.
- [ ] The timestamp block comes from `format_timestamp`, right-aligned, in every row that has one.
- [ ] The JS undo re-render produces markup identical to the Python renderer's.
- [ ] Focus 5 / What's Next / Auth Log pages verified visually unchanged.
- [ ] `pytest tests/` green; page regenerated through `pulse_web.py`;
      `rebalance doctor` and `utils/pdda/pdda.sh run` clean.

---

▶ TAKE YOUR TURN (codex — BUILDER role)

You are the BUILDER for this phase. Read the phase brief above and implement it.
1. Implement the brief by creating/editing the artifact file(s): scripts/pulse_web.py,src/rebalance/web_components.py
2. Append a build block to this relay file: `### Round N · Builder · codex` summarizing what you did (files touched, key decisions).
3. Use this exact tick binary (run it from any directory): /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick claim MARATHON-GH135-P2-TURN --agent codex --paths "phases/gh-135-pulse-dashboard-consistency--gh135-p2/RELAY.md,scripts/pulse_web.py,src/rebalance/web_components.py"
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick ping MARATHON-GH135-P2-TURN --agent codex
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick release MARATHON-GH135-P2-TURN --agent codex --to agy
4. Edit ONLY these paths: phases/gh-135-pulse-dashboard-consistency--gh135-p2/RELAY.md and scripts/pulse_web.py,src/rebalance/web_components.py. Do NOT run git. Do NOT touch any other file — the harness commits for you.

---

▶ TAKE YOUR TURN (agy — REVIEWER role)

You are the REVIEWER for this phase. Read the latest builder block above AND review the artifact file(s) on disk: scripts/pulse_web.py,src/rebalance/web_components.py.
1. Append a review block: `### Round N · Reviewer · agy` followed by your assessment.
2. If changes needed: add `**Verdict:** Changes requested` then: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick release MARATHON-GH135-P2-TURN --agent agy --to codex
3. If satisfied: add `**Verdict:** Approved`, set `STATUS: Approved`, then: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick done MARATHON-GH135-P2-TURN --agent agy
4. Use this exact tick binary (run it from any directory) for all token operations: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick
   Edit ONLY phases/gh-135-pulse-dashboard-consistency--gh135-p2/RELAY.md (your review block + STATUS). Do NOT edit the artifact yourself — request changes instead. Do NOT run git.
