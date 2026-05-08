# BeeWare/Toga pulse spike — findings

**Branch:** `spike/pulse-toga`
**Date:** 2026-05-08
**Time spent:** ~30 min (well under the 1-2 hour budget)
**Verdict:** 🟡 **YELLOW** — Toga can do this, but matching the HTML aesthetic
needs Cocoa native-bridge work. "Capable, with a known styling tax."

## Goal

Answer four questions cheaply before committing to a full Toga port:

1. **Layout** — can Pack do sidebar + main with a card inside?
2. **Card styling** — rounded corners, shadow, custom backgrounds: how close
   without Cocoa escape hatches?
3. **Multi-line list rows** — title-on-top + meta-below, real DB data.
4. **Data-layer reuse** — import `fetch_*` and `parse_goals` from scripts/
   without friction.

## Setup

- Dedicated venv at `.venv-toga/` (gitignored)
- `pip install toga toga-cocoa -e .` (Toga 0.5.4, toga-cocoa 0.5.4)
- Single file: [app.py](app.py)
- Run: `.venv-toga/bin/python experimental/pulse-toga-spike/app.py`

## What worked

- ✅ **Layout (Pack)** — sidebar + main split via `Pack(direction=ROW, flex=1)`
  rendered as expected. No fight, no surprises.
- ✅ **Multi-line list rows** — each calendar entry is a stacked
  `toga.Box(direction=COLUMN)` with two Labels (title + meta line). Reads
  cleanly, looks right, no need for `DetailedList` for read-only data.
- ✅ **Data-layer reuse** — `from dashboard import fetch_calendar_upcoming` and
  `from pulse_web import parse_goals, load_vault_path` worked 1:1. No port,
  no SQL duplication. This was the biggest open question and it's a clean win.
- ✅ **Native chrome** — traffic lights, title bar, scroll behavior, system
  font, antialiasing all "just work" and feel Mac-native.
- ✅ **Real data** — same 6 calendar events and same 3 goals as the HTML view,
  driven by the same `temp/rbos.config` and `0. Goals.md`.

## Gaps observed (with severity)

1. 🔴 **No rounded corners or shadows on widgets.** Pack offers no
   `border-radius` or `box-shadow`. The hero card renders as a sharp white
   rectangle vs. the soft shadowed card in HTML. **Cost to fix:** drop into
   Cocoa via Rubicon-ObjC, set `CALayer.cornerRadius`/`shadowOpacity` on the
   underlying NSView (~50-100 LoC plus a small style helper). This is the
   single biggest aesthetic gap.

2. 🟡 **Main column background doesn't fill empty vertical space.** The hero
   card paints white where it sits, but the main column below it shows the
   default dark window background instead of the warm BG color set on the
   main `Box`. Likely a Pack quirk where bg only renders inside the
   content-area frame. **Cost to fix:** probably trivial — add a `flex=1`
   spacer Box at the bottom, or set bg on `MainWindow` directly. Not tried in
   spike.

3. 🟡 **Calendar event titles clip mid-word.** "Neochrome Daily Check-in
   (Zoom or Slac…" got truncated by the sidebar width. `toga.Label` doesn't
   wrap automatically. **Cost to fix:** investigate `MultilineTextInput`
   (read-only mode) or compute width-aware truncation. Not a blocker but
   visible.

4. 🟡 **No gradient sidebar.** HTML uses `linear-gradient(180deg, #f8f4ec,
   #f3efe7)`. Toga: solid colors only without escape hatches. Could use a
   stack of boxes with stepped colors as a fake, or live with solid.

5. 🟢 **`Pack.padding` is deprecated** in Toga 0.5.x in favor of `Pack.margin`.
   Trivial mechanical rename across the file. Cosmetic warning, no behavior
   change.

6. 🟢 **List rows are stacked Boxes, not NSTableView-backed.** Fine for
   read-only display. If we later want hover/select/click affordances, switch
   to `DetailedList` or `Table`.

## What I deliberately didn't validate

- Briefcase packaging (well-trodden path, doesn't gate the decision)
- Auto-refresh loop (Toga's `add_background_task` is documented; standard)
- Goals checkbox write-back (separate axis, single-process Python so feasible)
- Activity / Watched / Index health cards (same patterns as hero + sidebar)

## Recommendation

Two paths from here, decided by how much aesthetic fidelity to the HTML mockup
matters:

**A. "Default Mac styling is fine" → ship Toga in 1-2 days.**
   Add the missing cards using the same patterns as the hero, fix the bg-fill
   quirk (likely 5-min fix), wire `add_background_task` for auto-refresh,
   wrap with Briefcase. The result feels like Apple Notes/Reminders: clean,
   squarer, less shadowed, but still recognizably the same dashboard. No
   Cocoa bridge needed.

**B. "Match the Things-style HTML aesthetic" → 3-5 days.**
   Layer in Rubicon-ObjC native bridge calls to set CALayer corner radius +
   shadow on cards, fix label wrapping, fake the gradient sidebar with a box
   stack. Briefcase packaging same as A.

**Pragmatic order:** still ship Path A (WKWebView wrapper of the HTML, ~half a
day) first as the lowest-risk way to get a Mac app icon in your Dock today.
Toga path A above stays viable as a v2 if you want to drop the HTML
dependency entirely later.

## Cleanup

If we walk away from this experiment:

```
rm -rf .venv-toga experimental/pulse-toga-spike
git branch -D spike/pulse-toga
```
