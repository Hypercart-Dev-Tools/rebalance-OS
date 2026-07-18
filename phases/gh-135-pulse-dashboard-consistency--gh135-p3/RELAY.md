# Marathon Phase gh135-p3
STATUS: Open
NEXT: codex

<!-- marathon-drive: task=MARATHON-GH135-P3-TURN builder=codex reviewer=agy round-cap=7 -->

## Phase Brief

# Phase 3 — per-module presentation fixes

Part of GH-135. Full contract: `PROJECT/2-WORKING/GH-135-PULSE-DASHBOARD-CONSISTENCY.md`.
Depends on Phase 1 (`format_timestamp` in `tz_utils.py`) and Phase 2 (shared row component).

## ⛔ Hard invariants

- Timestamps come from `format_timestamp()` in the **existing** `src/rebalance/tz_utils.py`.
  No new time helper, no per-module time formatting.
- Rows come from the Phase 2 shared row component. No new per-module row markup or CSS.
- **Presentation only** — no data-source, collector, route, or API-handler changes. If a
  fix appears to require one, stop and flag it rather than widening scope.
- **Never hand-edit `web/pulse.html`** — build artifact, regenerated from `pulse_web.py`.
- **No import workarounds.** Import normally (`from rebalance.tz_utils import ...`);
  `scripts/pulse_web.py` already imports `_bootstrap`, which puts `src/` on `sys.path`.
  An import that seems to resolve to the wrong copy of a module is an artifact of the
  throwaway git worktree, not a code defect. Do not add `sys.path` manipulation or
  `importlib.util.spec_from_file_location` shims — Phase 1 did and it was reverted.
  Report it in your relay block instead.

## Fixes

### Reminders (sidebar) — `pulse_web.py:1294-1367`
- Order: title first, then `person`, then `due <timestamp>`.
- Replace `A.)`-style text prefixes with a compact letter-keycap badge in the row's
  leading-marker slot.
- **Remove the age string from the title.** `pulse_web.py:1314-1315` currently builds
  `f" ({age_days}d old)"` and concatenates it into the title — this corrupts a data field
  with presentation. Render age as a structured chip on the meta line instead; the title
  string must come through clean.

### Recent GitHub activity — `render_recent_activity`, `:713-776`
- Replace the unlabeled glyphs (`+`, `○`, `↑`, `●`) with small labeled type badges —
  Issue / PR / Comment / Commit — in distinct colors. Reuse `badge_html`
  (`web_components.py:52`) rather than inventing a badge.
- Strip the org prefix from repo names:
  `Claude-AI-Tools-Ventura-County/xyz-3-agents-swarm` → `xyz-3-agents-swarm`.
  Keep the full path in the `title` attribute for hover.

### Recent Figma comments — `render_recent_figma`, `:1163-1252`
- Layout: author top-left, timestamp top-right, comment body below, file link last.
- **Remove raw thread IDs** (e.g. `VoQWc0fh0020JoxOyqeE1P`) from the rendered output.
- Sort strictly newest-first.

### What's Next — `render_work_next`, `:777-836`
- Fix the rank-circle vertical alignment: center it against the **first text line**, not
  the full row box.
- Show the top **3** ranked items, not 1.
- Move the count into the link: `Open What's Next → 21 ranked`.

### Today's Goals — three columns, `render_hero` board `:695-707`
- All three columns (`_render_goal_rows` `:556-576`, `_render_goal_rows(compact=True)`
  `:641-645`, `_render_reminder_rows` `:579-619`) use **identical** row styling — same
  checkbox, same padding, same zebra — via the Phase 2 component.
- Remove the divider rules that exist only in column 1.
- **Every** Apple Reminder with a date gets the shared right-aligned timestamp — currently
  only the first one does.

### Recently Completed — `render_hero` undo block `:656-680`
- Use the shared row: check-glyph leading marker, struck-through title, timestamp, and
  Undo as a quiet outline button (`button_link`, `web_components.py:65`). Replace the
  current bordered-card pattern.
- Keep the client-side JS re-render (`PULSE_JS`, `:2170-2190`) emitting identical markup.

### Progress header — `render_hero` header markup `:681-694`
- `0 done · 9 in progress` next to a `0%` bar is self-contradictory. Compute the bar width
  from `done / total` and **drop the redundant `0%` label**.

## Acceptance

- [ ] No raw IDs, org path prefixes, or age strings inside titles remain in the rendered DOM.
- [ ] All three Goals columns are visually identical in row treatment; every dated Apple
      Reminder shows a timestamp.
- [ ] What's Next shows 3 items with an aligned rank circle and the count in the link.
- [ ] GitHub activity rows show labeled, colored type badges — no bare glyphs.
- [ ] Figma rows are newest-first with no thread IDs.
- [ ] The progress bar is computed from done/total and no longer contradicts its label.
- [ ] Before/after screenshots captured for each of the six modules, confirming identical
      row anatomy across all of them.
- [ ] `pytest tests/` green — especially `test_pulse_web_goals.py`,
      `test_pulse_web_worknext.py`, `test_pulse_server_figma.py`,
      `test_pulse_server_apple_reminders.py`.
- [ ] Page regenerated through `pulse_web.py`; `rebalance doctor` and
      `utils/pdda/pdda.sh run` clean.

---

▶ TAKE YOUR TURN (codex — BUILDER role)

You are the BUILDER for this phase. Read the phase brief above and implement it.
1. Implement the brief by creating/editing the artifact file(s): scripts/pulse_web.py
2. Append a build block to this relay file: `### Round N · Builder · codex` summarizing what you did (files touched, key decisions).
3. Use this exact tick binary (run it from any directory): /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick claim MARATHON-GH135-P3-TURN --agent codex --paths "phases/gh-135-pulse-dashboard-consistency--gh135-p3/RELAY.md,scripts/pulse_web.py"
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick ping MARATHON-GH135-P3-TURN --agent codex
   - /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick release MARATHON-GH135-P3-TURN --agent codex --to agy
4. Edit ONLY these paths: phases/gh-135-pulse-dashboard-consistency--gh135-p3/RELAY.md and scripts/pulse_web.py. Do NOT run git. Do NOT touch any other file — the harness commits for you.

---

▶ TAKE YOUR TURN (agy — REVIEWER role)

You are the REVIEWER for this phase. Read the latest builder block above AND review the artifact file(s) on disk: scripts/pulse_web.py.
1. Append a review block: `### Round N · Reviewer · agy` followed by your assessment.
2. If changes needed: add `**Verdict:** Changes requested` then: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick release MARATHON-GH135-P3-TURN --agent agy --to codex
3. If satisfied: add `**Verdict:** Approved`, set `STATUS: Approved`, then: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick done MARATHON-GH135-P3-TURN --agent agy
4. Use this exact tick binary (run it from any directory) for all token operations: /Users/noelsaw/Documents/rebalance-OS/.xyz/bin/tick
   Edit ONLY phases/gh-135-pulse-dashboard-consistency--gh135-p3/RELAY.md (your review block + STATUS). Do NOT edit the artifact yourself — request changes instead. Do NOT run git.
