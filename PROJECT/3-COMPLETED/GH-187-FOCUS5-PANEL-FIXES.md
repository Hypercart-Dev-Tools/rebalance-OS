---
gh_issue: 187
source: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/187
title: "GH-187 Focus 5 Float: Dock reopen and panel resizing fixed"
status: "Complete — Dock reopen and native panel resizing shipped; top visual gap removed; regression coverage added"
created: 2026-07-21
updated: 2026-07-21
doc_type: bugfix
branch: development
roadmap_exempt: false
---

# GH-187 — Focus 5 Float: Dock reopen + panel resize

## Status

| What was just completed | What's next |
|---|---|
| Dock/Launch-Services reopen is verified live. The operator confirmed native horizontal and vertical resizing after the artificial height cap was removed. The remaining visual gap was eliminated at the AppKit/SwiftUI boundary: the hosting view now suppresses the hidden titlebar's 28pt safe area and the root shell has no top gutter. A real-panel regression test failed at 28pt before the fix and passes at 0pt after it; the packaged app screenshot is flush and all 53 Swift tests pass. | None. Monitor the geometry log if a future macOS/AppKit change alters resize or safe-area behavior. |

## Original ask

Two bugs in the Focus 5 Float menu-bar app (`macOS/Apps/Focus5Float`):
1. Hiding the panel (the in-panel "x" button, `panel.orderOut(nil)`) and then clicking the app's Dock tile did nothing — the panel never came back.
2. The panel can't be resized taller to fill the space between it and the menu bar — dragging the top edge doesn't work.

## Fix 1 — Dock/reopen (DONE, shipped)

`AppDelegate` never implemented `applicationShouldHandleReopen(_:hasVisibleWindows:)`, so AppKit's default reopen handling had nothing to unhide — the panel is an `NSPanel` we manually `orderOut()`, not a standard hidden window.

**Fix:** added `applicationShouldHandleReopen` to call `showPanel()` when the panel isn't visible. Verified live via unified log (`panel hidden` → `panel shown` after a simulated Dock reopen) and by the operator directly ("1 is good now"). Commit `c75a5f0`.

## Fix 2 — Panel resizing and top gap (DONE, shipped)

### Investigation log (chronological, debug-mantra breadcrumbs)

1. **Hypothesis: `panel.maxSize.height` hardcoded to 1200 is the cap.**
   `git log` showed `panel.maxSize` was introduced in commit `2e59ff1` ("feat: refresh Focus5Float panel UI") — before that commit there was **no** `maxSize` at all (unbounded resize). Changed `maxSize.height` to `NSScreen.main?.visibleFrame.height` so the cap tracks the actual screen instead of a flat constant. Commit `c75a5f0`.
   **Verified via Accessibility-forced resize:** the live cap did increase (1200 → ~1415 on the connected 2560×1440 display) and the OS-level ceiling is not the current display's visible height.
   **Disproved as the fix:** operator reported still unable to drag taller — "It seems like something is locking it to a max height."

2. **Hypothesis: `isMovableByWindowBackground = true` wins hit-testing over the native resize border in the top strip**, since this is a hidden-titlebar (`titlebarAppearsTransparent` + `fullSizeContentView` + hidden title/buttons) `NSPanel`.
   Confirmed via synthetic-click sweep (Accessibility position of the hide button + `CGEventPost`) that a drag starting a bit lower in the header (not the exact top few px) triggers a **window move**, and — when dragged far enough toward the screen's top edge — triggers **macOS's native window-tiling snap-to-fullscreen**, not a resize.
   Added a custom `TopEdgeResizeHandle` (an 8pt-tall `NSView` overlay pinned to the top edge, manually computing frame growth on `mouseDragged`) to bypass the native path entirely. Commit `bd6fd1b`.
   **Verification limits hit:** `CGEventPost`-simulated held-button drags proved unreliable in this headless environment — the *same* script that once reproduced the native tiling-snap stopped reproducing anything on a retry. Confirmed via logging that the handle's frame is computed correctly and that a plain synthetic click does reach it (`mouseDown` fires), but could not get a synthetic `mouseDragged` sequence to reliably fire at all, on either the handle or the native background-move path. Treated as an environment limitation, not evidence against the fix — asked the operator to test with a real mouse instead.

3. **Operator's real-mouse test surfaced a new, more specific symptom:** dragging the panel up shows macOS's full-screen tiling outline preview, but on release the panel **snaps to center** instead of filling the screen — and separately, plain top-edge drag to grow taller still didn't work with the handle in place.

4. **Isolation test app (`ResizeTestBar`, disposable, not part of the repo):** built a minimal AppKit-only panel mirroring Focus5Float's exact window-chrome settings (same `styleMask`, `isMovableByWindowBackground`, `isOpaque`/`backgroundColor` transparency flip, and a `maxSize.width` capped at 420 like Focus5Float) but with **no** custom drag handling and **no** SwiftUI content.
   **Result:** the test app resized and moved freely ("can be resized and moved much more freely... can drag it edge to edge"). It also showed the same width-capped centering during the OS full-tile gesture ("won't exceed a certain width and it centers itself") — but that specific behavior is now understood to be an **expected, shared side effect** of intentionally capping `maxSize.width` at 420 on both apps, not the core bug.
   **Disproves:** "`maxSize.width` blocking OS tiling → center fallback" as the *sole* cause, since the isolated test app has the identical constraint and still resizes/moves normally outside of the full-tile gesture.

5. **Follow-up isolation: reverted Focus5Float to the pre-handle state** (`git checkout c75a5f0 -- Focus5FloatApp.swift`, i.e. keep the `maxSize` dynamic fix, drop `TopEdgeResizeHandle`), rebuilt, reinstalled, operator retested on the **real** app:
   - Can drag slightly wider, but still maxes out at a set width (expected — `maxSize.width` = 420).
   - Triggering the full-screen snap only widens it slightly (doesn't grow taller) — consistent with the width-capped-centering behavior seen on the test app.
   - **Can now drag edge to edge, unlike the version with the custom handle.**

   **Conclusion:** the custom `TopEdgeResizeHandle` (step 2) was actively regressing normal native resize/drag behavior rather than fixing it. It was reverted in `fbf5f58`.

6. **Live-frame inspection isolated the remaining height blocker.** With the installed app running:
   - Accessibility reported the live panel at position `(-341, 30)`, size `(341, 1415)`.
   - `NSScreen.main.visibleFrame.height` was `1415`, exactly the value assigned to `panel.maxSize.height`.
   - The panel was actually on the other 2560×1440 display, whose visible height was `1440`, and its top remained about 30pt below that display's top.
   - The saved `.v5` frame was also 1415pt tall.

   **Conclusion:** AppKit was honoring the app's explicit maximum. The panel had already reached the 1415pt cap, and `NSScreen.main` described the wrong display for a panel restored/moved onto another screen. Even on one screen, an autosaved frame offset a few points below the visible origin cannot grow its top edge back to the menu bar when maximum height equals the full visible height.

   **Fix:** preserve the intentional 420pt width maximum but restore AppKit's default unbounded frame height (`Float.greatestFiniteMagnitude`). Runtime geometry logging confirms `max={420, 3.402823e+38}` and `contentMax={420, 3.402823e+38}`. The operator then verified both horizontal and vertical native resizing.

7. **Operator verified both horizontal and vertical resizing, but reported the panel still could not visually reach the top.** Post-gesture inspection showed the window at Accessibility `y=25`, exactly the bottom of the main display's 25pt menu bar. The window itself was therefore correctly placed. A cropped screenshot showed the visible glass shell beginning about 34pt inside the window: AppKit's hidden-titlebar safe area was 28pt and the root SwiftUI view added another 6pt on every edge.

   **Final fix:** `FirstMouseHostingView` now reports zero safe-area insets, enforcing the full-size-titlebar contract at the AppKit/SwiftUI boundary, while the root view retains padding only on the horizontal and bottom edges. This lets the visible shell reach the legal menu-bar boundary without placing the actual window underneath system UI. A regression test mounts the real hosting view in the real panel chrome: it failed with the prior 28pt inset, then passed at 0pt after the fix. The installed build and a post-install screenshot confirm the gap is gone.

### Current code state

- Dock reopen fix — committed in `c75a5f0`.
- `TopEdgeResizeHandle` — reverted and committed in `fbf5f58` (the earlier note that this was uncommitted was stale).
- Final code replaces the screen-derived height maximum with AppKit's default maximum while preserving the 420pt width cap, logs frame/constraint geometry, suppresses the hidden-titlebar safe area in the hosting view, and leaves no top shell gutter.
- Regression coverage asserts both the unbounded-height/width-cap sizing contract and the real hosting view's zero safe-area inset inside a hidden-titlebar panel.
- Installed `/Applications/Focus 5 Float.app` contains the fixes. Runtime logging verifies the old height cap is absent, and a screenshot verifies the shell draws to the top window boundary.
- Disposable isolation app lives at `/private/tmp/.../scratchpad/ResizeTestBar` (session-scoped temp dir, not part of this repo, safe to ignore/lose).

### Root cause: isolated and fixed

The screen-derived maximum is the direct blocker in the observed live state. `panel.maxSize.height` was 1415 and the live panel height was already 1415, so no user drag could make it taller. Because the cap came from `NSScreen.main` before/independently of the panel's eventual screen, it was also 25pt shorter than the visible height of the display holding the panel. SwiftUI intrinsic size and autosave may influence layout/placement, but neither is required to explain this failure.

### Next steps

1. No further implementation work is required.
2. If a future macOS release recreates the gap, inspect the `panel shown` / `panel live resize ended` geometry logs before changing hit-testing.
3. Do not reintroduce a custom resize-handle view; it already regressed native resize and move behavior.

## Consult — Codex + agy second opinion (2026-07-21, historical)

Ran `/consult` (both models read this doc + `Focus5FloatApp.swift` directly). Full raw transcripts:
`relay-system/2026-07-21/gh187-panel-resize-124307/gh187-panel-resize.{codex,agy}.md`.

**Reconciled call:** both independently suspect the SwiftUI `NSHostingView` content as the real
differentiator from the isolated test app — but Codex adds a sharper, more important catch: this
doc's own "can drag edge to edge" conclusion never explicitly re-confirmed *height* growth via the
native top edge post-handle-revert; "edge to edge" almost certainly described *width*. That's a gap
in our own methodology, not just a new theory, and should be closed before trusting any other
hypothesis below.

**Where they disagreed:**
- Codex flagged `[Blocker]`: post-revert testing never explicitly confirmed a successful (or failed)
  *height-only* native top-edge resize — only width ("edge to edge") and the full-tile-snap were
  confirmed. The earlier custom handle had also regressed normal resize, which may have contaminated
  what we thought we'd already ruled out. Agy did not raise this; it accepted the log at face value
  and went straight to a sizing hypothesis.
- Mechanism specificity differs: agy's theory is that `NSHostingView`'s intrinsic SwiftUI layout can
  override `panel.maxSize` outright. Codex doesn't make that literal claim but independently surfaced
  that `contentMinSize`/`contentMaxSize` are **distinct `NSWindow` properties from `minSize`/`maxSize`**
  and take precedence — a more precise, directly-checkable mechanism neither of us had inspected
  before. Not truly contradictory — same suspect (SwiftUI content constraining the window), Codex's
  framing is the more actionable one.

**Where they agreed:**
- SwiftUI/`NSHostingView` content (vs. the isolation app's plain `NSView`) is the top suspect.
- `panel.isMovableByWindowBackground = false` is a good *diagnostic* (not a permanent fix) to test
  whether background-move is swallowing the resize attempt.
- The tile-to-center-at-420 behavior is expected given `maxSize.width`, not a separate bug.
- Frame-autosave state is low-priority, unlikely to actively fight a live resize.

**Advisory list at the time:**
- **Blocking (do first):** re-verify with a human, cursor-watching test whether *height-only*
  top-edge resize actually works or fails now that the handle is reverted — our "fixed" read may
  rest on an untested assumption (Codex).
- **Worth doing, optional:** inspect runtime `contentMinSize`/`contentMaxSize`/`aspectRatio`/resize
  increments and `panel.screen?.visibleFrame` vs `NSScreen.main` (can differ on multi-monitor)
  (Codex); run an A/B ladder — plain `NSView` → `FirstMouseView` → empty `NSHostingView` → real
  `ContentView`, same panel subclass/bundle/agent policy throughout — to isolate which exact layer
  changes drag behavior (Codex); temporarily flip `isMovableByWindowBackground = false` as a
  diagnostic (both); add `.frame(maxWidth: .infinity, maxHeight: .infinity)` to `ContentView` as a
  quick sizing-conflict probe (agy).
- **Skip / out of scope:** autosave-state clearing — low confidence from both, test once but don't
  treat as a likely culprit.

The resumed investigation tested the useful parts of this advice. Runtime inspection disproved an
active `contentMaxSize` constraint in the final build, confirmed the screen-derived `maxSize` was the
original hard stop, and isolated the remaining visible gap to the hosting view's titlebar safe area.
The background-move diagnostic and custom-handle path were unnecessary.

## Verification

- Operator verified Dock/Launch-Services reopen.
- Operator verified both horizontal and vertical native resizing after the height cap was removed.
- Runtime log: panel and content maximum heights both equal AppKit's default `Float.greatestFiniteMagnitude`; width remains capped at 420pt.
- Regression test red/green proof: real hosting view mounted in real hidden-titlebar panel reported 28pt before the boundary fix and 0pt after it.
- Packaged app rebuilt, ad-hoc signature verified, installed, relaunched, and screenshot-checked at the menu-bar boundary.
- `swift test`: 53 tests passed, 0 failures.

## Lessons Learned (For Future Agents)

- A window can be correctly positioned while its visible SwiftUI shell is inset; inspect both the AppKit frame and hosting-view safe area before changing resize hit-testing.
- `NSScreen.main` is not a stable sizing authority for a movable, autosaved multi-display panel. Cap the dimension that is intentionally bounded (width) and leave height at AppKit's default maximum.
- `.fullSizeContentView` does not make `NSHostingView.safeAreaInsets.top` zero. Enforce that invariant at the hosting boundary and test the real panel chrome.
- Synthetic held-button drags were unreliable here. Runtime geometry plus one human gesture produced better evidence than a custom event-handling workaround.
- Custom resize handles are high-risk on native resizable panels because they can intercept the same edge region AppKit uses for move/resize behavior.
