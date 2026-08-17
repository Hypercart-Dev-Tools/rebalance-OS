# Claude Code prompt — Pulse dashboard consistency cleanup

Paste the following into Claude Code at the repo root of the Pulse dashboard:

---

The Pulse dashboard ("Today" view) has drifted: every module formats rows, timestamps, and metadata differently. Refactor for consistency. Do NOT change functionality, data sources, or routes — this is presentation + formatting only.

## 1. One shared timestamp utility

Create a single `formatTimestamp(date, { relative })` helper and replace ALL ad-hoc time formatting with it:

- Absolute format everywhere: `YYYY-MM-DD h:mm AM/PM` (e.g. `2026-07-17 8:02 PM`), rendered in monospace (`ui-monospace` stack), tabular, muted color.
- Relative time is allowed only as a SUFFIX to the absolute: `2026-07-17 8:02 PM · 2h ago`. Never a bare "28m ago" / "19d ago" / "sat 12:00 pm" / "fri 9:16 pm" on its own.
- Kill every other format currently in use: weekday-lowercase times in Reminders and Calendar, bare relatives in GitHub activity / Recently Completed / collector chip / "computed 13h ago", and "(3d old)" / "(42d old)" strings embedded inside Reminder titles — move age into a structured `age` field rendered as a small chip.

## 2. One shared row component

Extract a `<DataRow>` used by Reminders, GitHub activity, Figma comments, What's Next, Recently Completed, and the three checklist columns. Anatomy, in order:

1. Leading marker (fixed width): checkbox / type badge / rank / avatar-letter.
2. Body: **title first** (medium weight), then one meta line below (person · chips).
3. Trailing: right-aligned timestamp block (the `formatTimestamp` output).

Zebra striping: alternate rows get a faint background tint (~3% ink). Applies to every list in the app, driven by the shared component, not per-module CSS.

## 3. Per-module fixes

- **Reminders (sidebar):** title first, then `person`, then `due <timestamp>`. Replace `A.)`-style text prefixes with a compact letter keycap badge. Remove age from the title string.
- **Recent GitHub activity:** replace the unlabeled glyphs (+, ○, ↑, ●) with small labeled type badges (Issue / PR / Comment / Commit) with distinct colors. Strip the org prefix from repo names (`Claude-AI-Tools-Ventura-County/xyz-3-agents-swarm` → `xyz-3-agents-swarm`; full path on hover/title attr).
- **Recent Figma comments:** author on top-left, timestamp top-right, comment body below, file link last. Remove raw thread IDs (`VoQWc0fh0020JoxOyqeE1P`) from the UI. Sort strictly newest-first.
- **What's Next:** fix the rank-circle vertical alignment (center it against the first text line). Show the top 3 ranked items, not 1; move the count into the link: "Open What's Next → 21 ranked".
- **Today's Goals:** the three columns (Goals / Next Open Todos / Apple Reminders) must use identical row styling — same checkbox, padding, and zebra. Remove the divider rules that exist only in column 1. Every Apple Reminder with a date gets the shared timestamp treatment (right-aligned), not just the first one.
- **Recently Completed:** use the shared row (check-glyph marker, struck-through title, timestamp, Undo as a quiet outline button) instead of the current bordered-card pattern.
- **Progress header:** "0 done · 9 in progress" next to a 0% bar is contradictory — compute the bar from done/total and drop the redundant "0%" label.

## 4. Section headers

One casing system: card titles in sentence case ("Today's goals", "What's next", "Recent GitHub activity"); sub-section labels in 11px uppercase letter-spaced ("GOALS · 3", "NEXT OPEN TODOS · 6", "RECENTLY COMPLETED · 3"). Include counts in sub-section labels consistently.

## 5. Acceptance checklist

- `grep` finds zero remaining call sites of old time-formatting code; all rows go through `formatTimestamp`.
- No relative time appears without an adjacent absolute timestamp.
- Every list in the view renders through `<DataRow>` with zebra striping.
- No raw IDs, org path prefixes, or age strings inside titles remain in the DOM.
- Take before/after screenshots of each module and confirm identical row anatomy across all six.
