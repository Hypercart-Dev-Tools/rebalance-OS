# Marathon Phase gh135-p4
STATUS: Open
NEXT: codex

<!-- marathon-drive: task=MARATHON-GH135-P4-TURN builder=codex reviewer=agy round-cap=5 -->

## Phase Brief

# Phase 4 — one section-header casing system

Part of GH-135. Full contract: `PROJECT/2-WORKING/GH-135-PULSE-DASHBOARD-CONSISTENCY.md`.
Depends on Phase 3. This is the smallest phase — a consistency sweep, not new structure.

## ⛔ Hard invariants

- **Presentation only.** No data-source, collector, route, or API-handler changes.
- **Never hand-edit `web/pulse.html`** — build artifact, regenerated from `pulse_web.py`.
- Do not add a new time helper or new row markup — Phases 1 and 2 own those.
- **No import workarounds** — no `sys.path` manipulation, no
  `importlib.util.spec_from_file_location` shims. Import normally. An import resolving to
  the wrong module copy is a worktree artifact, not a code defect; report it, don't code
  around it. Phase 1 did and it was reverted.

## Task

Apply one casing system across every card and sub-section on the Today view
(`scripts/pulse_web.py`; card container CSS at `:1607-1611`).

### Card titles — sentence case
`Today's goals` · `What's next` · `Recent GitHub activity` · `Recent Figma comments` ·
`Recently completed`

Sweep every `render_*` function that emits a `.card-head` — including the cards outside
the six refactored modules (`render_health_banner:410`, `render_org_activity:837`,
`render_repo_pie:900`, `render_open_prs:937`, `render_watched:1021`,
`render_index_health:1043`, `render_recent_emails:1085`) so the page has no leftovers.

### Sub-section labels — 11px uppercase, letter-spaced, with counts
`GOALS · 3` · `NEXT OPEN TODOS · 6` · `RECENTLY COMPLETED · 3`

Counts applied **consistently** — every sub-section label that has a meaningful count
shows one in the same `· N` form. Declare the label style once as a shared class; do not
repeat inline styles per module.

## Acceptance

- [ ] Every card title on the page is sentence case; no Title Case or ALL CAPS card titles remain.
- [ ] Every sub-section label uses the single shared 11px uppercase letter-spaced class.
- [ ] Counts are present and consistently formatted (`· N`) on every sub-section that has one.
- [ ] No inline per-module header styling remains.
- [ ] `pytest tests/` green; page regenerated through `pulse_web.py`;
      `rebalance doctor` and `utils/pdda/pdda.sh run` clean.
- [ ] Full-page before/after screenshot confirming one consistent header language.

---

▶ TAKE YOUR TURN (codex — BUILDER role)

You are the BUILDER for this phase. Read the phase brief above and implement it.
1. Implement the brief by creating/editing the artifact file(s): scripts/pulse_web.py
2. Append a build block to this relay file: `### Round N · Builder · codex` summarizing what you did (files touched, key decisions).
3. Use this exact tick binary (run it from any directory): /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick claim MARATHON-GH135-P4-TURN --agent codex --paths "phases/gh-135-pulse-dashboard-consistency--gh135-p4/RELAY.md,scripts/pulse_web.py"
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick ping MARATHON-GH135-P4-TURN --agent codex
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick release MARATHON-GH135-P4-TURN --agent codex --to agy
4. Edit ONLY these paths: phases/gh-135-pulse-dashboard-consistency--gh135-p4/RELAY.md and scripts/pulse_web.py. Do NOT run git. Do NOT touch any other file — the harness commits for you.

---

▶ TAKE YOUR TURN (agy — REVIEWER role)

You are the REVIEWER for this phase. Read the latest builder block above AND review the artifact file(s) on disk: scripts/pulse_web.py.
1. Append a review block: `### Round N · Reviewer · agy` followed by your assessment.
2. If changes needed: add `**Verdict:** Changes requested` then: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick release MARATHON-GH135-P4-TURN --agent agy --to codex
3. If satisfied: add `**Verdict:** Approved`, set `STATUS: Approved`, then: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick done MARATHON-GH135-P4-TURN --agent agy
4. Use this exact tick binary (run it from any directory) for all token operations: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick
   Edit ONLY phases/gh-135-pulse-dashboard-consistency--gh135-p4/RELAY.md (your review block + STATUS). Do NOT edit the artifact yourself — request changes instead. Do NOT run git.
