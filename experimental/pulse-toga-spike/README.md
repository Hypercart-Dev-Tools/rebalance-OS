# BeeWare/Toga pulse spike — findings

**Branch:** `spike/pulse-toga`
**Date:** 2026-05-08
**Time spent:** ~30 min (well under the 1-2 hour budget)
**Verdict:** 🟠 **ORANGE** (revised after iteration 1) — Toga renders the
layout and reuses the data layer cleanly, but the Cocoa native-bridge path
to rounded/shadowed cards is more constrained than the initial yellow
verdict assumed. See "Iteration 1" section below for the deeper finding.

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

## Iteration 1: Cocoa bridge for rounded corners + shadow

After the initial spike's yellow verdict, we tried the native-bridge path
to see if `CALayer.cornerRadius` + drop shadow on the hero card was the
small lift the verdict implied.

**Setup:** added a `style_as_card()` helper that uses Rubicon-ObjC to
reach `widget._impl.native` (the underlying NSView), sets
`wantsLayer = True`, and applies `cornerRadius`, `borderColor`,
`borderWidth`, and shadow properties on `view.layer`. Deferred the call
to `App.on_running()` so the layer was alive by then.

**What we observed (probed with a deliberately loud hot-pink fill +
4px red border to make changes obvious):**

- ✅ `layer.backgroundColor` — renders visibly. Card filled hot pink.
- ✅ `layer.borderColor` + `borderWidth` — renders visibly. 4px red
  border drew correctly around the card's rectangular bounds.
- ❌ **`layer.cornerRadius` is silently ignored** for visible drawing
  even though the property reads back as 12. Card stayed a sharp
  rectangle. The bridge stored the value; the drawing path didn't
  honor it.
- ❌ **`layer.shadow*` did not render.** Even with
  `masksToBounds = False` set, no shadow appeared.

**Diagnosis:** Toga's view class for `Box` is `TogaView`. It declares
`wantsUpdateLayer = YES`, meaning it goes through AppKit's "fast path"
where the view's `updateLayer:` method is the canonical place layer
state is set during display. TogaView's `updateLayer:` re-asserts a
specific layer configuration that doesn't include `cornerRadius`, and
TogaView's bounds-equal frame leaves no margin for shadows to escape
into. Setting custom CALayer state outside of `updateLayer:` is
effectively decorative — `backgroundColor` happens to survive the
re-assert path but `cornerRadius` and `shadow*` do not.

**Implication for the "go all-in" path:**

Getting rounded shadowed cards inside Toga requires one of:

1. Forking / patching `toga-cocoa` so `updateLayer:` exposes a hook
   that lets app code preserve `cornerRadius` / `shadow*`. Cleanest
   long-term but means maintaining a fork until the change lands
   upstream.
2. Subclassing `TogaView` via Rubicon-ObjC and overriding
   `updateLayer:` ourselves. Works without forking but is brittle
   across Toga version bumps; Toga's Box implementation is internal
   API and free to change between minor releases.
3. Embedding hand-rolled NSView subclasses outside Toga's widget
   system for every styled surface, then composing them via Pack.
   Most work, lowest reuse from existing widgets.

None of these is impossible — but the original "3-5 days" estimate
for the native-bridge path is optimistic. Realistic for option (2):
3-5 days for **just the styled cards**, plus ongoing maintenance
when Toga ships new versions.

## Recommendation

Two paths from here, decided by how much aesthetic fidelity to the HTML mockup
matters:

**A. "Default Mac styling is fine" → ship Toga in 1-2 days.**
   Add the missing cards using the same patterns as the hero, fix the bg-fill
   quirk (likely 5-min fix), wire `add_background_task` for auto-refresh,
   wrap with Briefcase. The result feels like Apple Notes/Reminders: clean,
   squarer, less shadowed, but still recognizably the same dashboard. No
   Cocoa bridge needed. **Still viable after iteration 1's findings —
   nothing in the cornerRadius/shadow gap blocks this path; you just don't
   get the rounded shadowed look.**

**B. "Match the Things-style HTML aesthetic" → revised cost: substantial.**
   Per iteration 1, this requires forking `toga-cocoa`, subclassing
   TogaView via Rubicon-ObjC, or embedding hand-rolled NSViews — all with
   real maintenance debt. **Not recommended as a near-term path.**

**Pragmatic order (unchanged after iteration 1):** ship the WKWebView
wrapper of the existing HTML pulse view first (~½ day) for a real Dock
icon today. Path A (Toga with default Mac styling) stays viable as a v2
if HTML-in-a-window starts feeling wrong. Path B is parked unless an
upstream change lands that makes custom layer state on TogaView clean.

## Cleanup

If we walk away from this experiment:

```
rm -rf .venv-toga experimental/pulse-toga-spike
git branch -D spike/pulse-toga
```
