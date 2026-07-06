# RELAY · GH-104 desktop parity — Focus5Float off-roster reason
<!--
  Single source of truth for this two-agent relay. Read the ENTIRE file before acting.
  Scaffolded by relay-automation/new-relay.sh on 2026-07-05.
-->

NEXT: Reviewer
STATUS: Open
ROUND: 1 / 4

## ▶ TAKE YOUR TURN — read this first (works for ANY agent: Claude, Codex, agy)
1. **Read this whole file** (header, Setup, Ground rules, every block in the Log).
2. **Check it's your turn:** `NEXT` (top) names the role to act. Confirm you are bound to it and the
   last Log block isn't already yours. If not → STOP and reply "wrong window — nudge the <other> window."
3. **Do your role's work** on the artifact named in Setup:
   - **Reviewer:** review vs the Definition of Done → graded findings
     (`[Blocker]`/`[Should]`/`[Nit]`/`[Pass]`), each with a concrete fix → set a **Verdict**
     (Approved | Changes requested | Blocked). Do **not** edit the artifact; only append findings here.
   - **Producer:** log a disposition for every open finding (Implemented / Modified / Declined + why),
     make the change, then add new work.
4. **Append ONE block** at the very bottom, directly **above** the marker line. Never edit earlier turns.
5. **Update the header:** flip `NEXT`; set `STATUS` (`Approved` closes — Reviewer only; else `Open`);
   the Producer bumps `ROUND` when opening a new cycle. If the max `ROUND` ends without `Approved`,
   set `STATUS: Escalated`.
6. **Commit only the relay file** (`relay(gh104-desktop-parity): <role> r<N>`); no push. **Stop** and report one line.

## Setup
- Paths this lane may touch: `macOS/Apps/Focus5Float/Sources/Focus5Float/Models.swift`, `.../ContentView.swift` (only the `OffRosterFooter` view), `.../Focus5Model.swift` if needed
- Producer: codex   ·   Reviewer: agy
- Handoff: cli-driven (relay-xyz — codex builds, agy reviews; single-session headless), running against an isolated worktree/branch `marathon/2026-07-06`
- Started: 2026-07-05
- Definition of Done: per [GH-104-FOCUS5-OFFROSTER-REASON.md](../../PROJECT/2-WORKING/GH-104-FOCUS5-OFFROSTER-REASON.md) — the off-roster strip in the Focus5Float macOS app shows the specific reason per repo (not generic "needs attention"/counts-only), matching the web slice's `off_roster_reason()` output. No change to top-5 ranking eligibility. `swift build` green.

## Task brief (for the Producer's first turn)
Part of the 2026-07-06 marathon, Lane C (see [MARATHON-2026-07-06.md](../../PROJECT/2-WORKING/MARATHON-2026-07-06.md#lane-c--gh-104-desktop-parity-focus5float-off-roster-reason)). Implements the desktop half of [GH-104-FOCUS5-OFFROSTER-REASON.md](../../PROJECT/2-WORKING/GH-104-FOCUS5-OFFROSTER-REASON.md) (web half already shipped 2026-07-03).

**Important finding — do NOT re-derive the reason logic in Swift.** `src/rebalance/ingest/focus5_scan.py:1103` already computes `wd["warning_reason"] = off_roster_reason(wd)` server-side, and `web.py:533` already reads `w.get("warning_reason")` for the web HTML strip — meaning the reason string is already computed Python-side and (very likely) already flows into the JSON payload the Swift app fetches (`/focus-5.json`). **First confirm** whether `warning_reason` is actually present in the live JSON response for an off-roster row (curl the endpoint or read the JSON-building code path in `web.py`/`focus5_scan.py` that serializes `offRosterWarnings`). If it's already on the wire:
- Add `let warningReason: String?` to the `OffRosterWarning` struct in `Models.swift` (matches the app's existing snake_case→camelCase JSON decoding convention — check how sibling fields like `repoName`/`myLocalCommitTs` are decoded and follow the same pattern).
- In `OffRosterFooter` (`ContentView.swift`, ~line 862), render `w.warningReason` (falling back to the existing "↑N · XM YU" counts line only if `warningReason` is nil) instead of/alongside the current generic counts-only line — matching how `DirtyBannerView` (same file, ~line 823) already surfaces a specific reason string for GH-105's banner.

If `warning_reason` is NOT already on the wire (only computed for the HTML string, not the JSON route), then the minimal fix is adding it to the JSON-building code path too (reuse `off_roster_reason()`, do not duplicate its logic) before doing the Swift-side work above.

- **Out of scope:** any change to ranking eligibility (`rank_recent_activity` stays untouched, per the doc's own acceptance criteria); no new Swift-side classification logic — reuse the server-computed string.
- Tick GH-104's acceptance checklist item ("desktop not done" → done) in the project doc once shipped.

## Ground rules
1. This file is the single source of truth. The agents never share memory — read the whole file.
2. Take a turn only if `NEXT` names your role — otherwise reply "not my turn" and stop.
3. One turn = one block appended at the very bottom, above the marker. Never edit earlier turns.
4. Stay tight — findings are bullets, not essays. Grade every finding.
5. **The Reviewer never edits the artifact.** It proposes graded findings; the Producer implements.
6. The relay ends on **Approved** (Reviewer only). End each turn by committing just this file; no push.

## Log

### Producer — codex — r1
Basis: behaviorally proven for the Swift package build; textual code-path verification for the existing `/focus-5.json` `warning_reason` field.
- Implemented: confirmed the server already puts `warning_reason` on the `/focus-5.json` wire shape (`summarize_focus5()` sets it on each `off_roster_warnings` row; `focus5_json()` returns `JSONResponse(data)` unchanged), so no Python change was needed for this lane.
- Implemented: added `warningReason` to `OffRosterWarning` in `Models.swift` so the desktop client decodes the existing JSON field via `.convertFromSnakeCase`.
- Implemented: updated `OffRosterFooter` so each expanded off-roster row shows the specific server-computed reason, falling back to the old `↑N · XM YU` counts string only when `warningReason` is absent.
- Verification: `env CLANG_MODULE_CACHE_PATH=/private/tmp/focus5float-clang-module-cache SWIFTPM_MODULECACHE_OVERRIDE=/private/tmp/focus5float-swiftpm-module-cache swift build --disable-sandbox --scratch-path /private/tmp/focus5float-build` from `macOS/Apps/Focus5Float` passed.
- Note: the GH-104 project doc checkbox was not updated in this turn because the relay lane was explicitly file-scoped to the Swift files plus this relay file.
VERDICT: PASS

<!-- ↓↓↓ NEXT TURN goes here (append above nothing — this marker stays last) ↓↓↓ -->
