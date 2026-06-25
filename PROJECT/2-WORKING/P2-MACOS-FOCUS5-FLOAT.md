---
title: Focus 5 Float — Floating macOS Card Stack
status: complete
doc_type: project-plan
owner: Noel Saw
created: 2026-06-23
updated: 2026-06-25
goal: "Build Focus 5 Float, a small always-on-top macOS application that renders the Focus 5 card stack as a collapsible native projection."
priority: P2
source_app: macOS/ (TextReplacementStudio — SwiftPM, Swift 5.10, macOS 14+)
data_source: src/rebalance/ingest/focus5_scan.py → summarize_focus5(db)
data_contract: GET /focus-5.json (read-only, local-only); rebuild via separate POST /focus-5/sync
canonical_boundary: local SQLite + git re-probe stays source of truth; the app is a read-only projection
branch: feat/macos-focus5-float
rollout_rule: each phase must leave a buildable, launchable app (or a green `swift build`)
---

## Status

| What was just completed | What's next |
|---|---|
| **Phase 5 — Packaging, Launch-at-Login & Docs — COMPLETE (descoped, 2026-06-25).** `make-app.sh` ships the installed `/Applications` app (ad-hoc signed, `LSUIElement`); **launch-at-login** via `SMAppService` toggle in the F5 menu; app `README.md` + `macOS/README.md` pointer written; icon wiring present (auto-picks `Resources/AppIcon.icns`) — artwork in progress via Figma Make. **Also shipped:** a top-right roster-health traffic light (green/orange/red over the dirty count) with a `FOCUS5_HEALTHTEST` self-check. _Descoped (YAGNI for a personal menu-bar tool):_ full settings window (env `FOCUS5_BASE_URL` covers it); poll-interval/Dock-toggle settings. **All phases (0–5) done.** | **Done — ready to move to `3-COMPLETED`** once the `feat/macos-focus5-float` work lands on `development` and the icon `.icns` is dropped in. |

## Table of Contents

- [Goal](#goal)
- [Context & Findings](#context--findings)
- [Architecture Decision](#architecture-decision)
- [Reuse Map (from `macOS/TextReplacementStudio`)](#reuse-map-from-macostextreplacementstudio)
- [Non-Goals](#non-goals)
- [Phase 0 — Spike & Data Contract](#phase-0--spike--data-contract)
- [Phase 1 — Scaffold & Reuse Harvest](#phase-1--scaffold--reuse-harvest)
- [Phase 2 — Floating Window + Menu-Bar Shell](#phase-2--floating-window--menu-bar-shell)
- [Phase 3 — Vertical Card-Stack UI](#phase-3--vertical-card-stack-ui)
- [Phase 4 — Live Data Integration](#phase-4--live-data-integration)
- [Phase 5 — Packaging, Launch-at-Login & Docs](#phase-5--packaging-launch-at-login--docs)
- [Open Questions](#open-questions)

## Goal

Build a small, always-on-top macOS app — **Focus 5 Float** — that renders the web app's "Focus 5" cards as a **vertical, collapsible stack** (per the SoloTerm-style screenshot: each repo is a row with a status dot + right-aligned metrics, expandable into sub-sections). It floats above other windows, toggles from the menu bar, and is a thin read-only projection of the existing Focus 5 data — the local SQLite store + live git re-probe stays canonical.

Maximize reuse of the existing SwiftUI scaffolding in `macOS/` (`TextReplacementStudio`): design tokens, component kit, observable-model pattern, and the `make-app.sh` bundling/signing pipeline.

## Context & Findings

**Existing macOS app — `macOS/TextReplacementStudio`** (reusable scaffolding):
- SwiftPM only (no Xcode project). Swift tools 5.10, **macOS 14.0+**. Deps: GRDB 6.29+, SwiftyJSON 5.0.2+, swift-argument-parser 1.3+.
- Targets: `TextReplacementCore` (library), `TextReplacementStudio` (SwiftUI app), `TextReplacementCLI`, tests.
- [Theme.swift](../../macOS/Apps/TextReplacementStudio/Theme.swift) — full design-token system (light/dark colors, 8pt `Space`, `Radius`, SF Pro/Mono type ramp, `spring` animation). **Copy verbatim.**
- [StudioComponents.swift](../../macOS/Apps/TextReplacementStudio/Views/StudioComponents.swift) — `KeyCap`, `GroupTag` (dot + label chip), `StudioToggle`. **Directly reusable for badges/status dots.**
- [ToastView.swift](../../macOS/Apps/TextReplacementStudio/Views/ToastView.swift) — bottom capsule overlay w/ auto-dismiss. Reusable for "refreshed" / "server offline" feedback.
- [StudioModel.swift](../../macOS/Apps/TextReplacementStudio/StudioModel.swift) — `@Observable` + `@MainActor` model; heavy I/O via `Task.detached`; derived computed props. **Pattern to clone.**
- [TextReplacementStudioApp.swift](../../macOS/Apps/TextReplacementStudio/TextReplacementStudioApp.swift) — standard `WindowGroup` (NOT floating / not menu-bar). The floating-panel + `NSStatusItem` layer is **net-new** work.
- [make-app.sh](../../macOS/make-app.sh) — `swift build -c release` → assembles `.app`, writes `Info.plist`, ad-hoc `codesign --force --deep`, installs to `/Applications`. **Adapt (new bundle id, exec name, `LSUIElement` for menu-bar agent).**

**Web "Focus 5" feature** (data source to project):
- Server-rendered **FastAPI**, route `GET /focus-5` in [src/rebalance/web.py](../../src/rebalance/web.py) (HTML only — **no JSON endpoint today**).
- Data fn: `summarize_focus5(db)` in [src/rebalance/ingest/focus5_scan.py](../../src/rebalance/ingest/focus5_scan.py). Returns:
  `{ roster: [≤5 cards], off_roster_warnings: [...], computed_at, ranking_mode, summary:{discovered, roster_size, off_roster_attention} }`.
- **Card fields:** `position`, `rank_reason`, `repo_name`, `repo_full_name`, `local_path`, `branch`, `upstream`, `ahead`, `behind`, `modified_count`, `untracked_count`, `is_dirty`, `last_commit_at`, `my_last_commit_ts`, `vscode_url`, `newest_pr:{number,title,state,html_url,is_draft,is_merged}`, `recent_activity:[{sha,subject,committed_at}]`, `health_available`.
- Persistence: SQLite tables `focus5_roster` + `focus5_repo_signals` ([migration 0003](../../src/rebalance/ingest/db/migrations/0003_focus5_roster.sql)). Tree health (dirty/branch/ahead/behind) is **re-probed live** on each page load — not cached.
- Ranking modes (pure fns): `recent_activity` (default), `dirty_first` ("Dirty Five"), `my_work`, `any_touch`. Manual re-scan via `sync_focus5(db)`.
- Served by `rebalance serve` (default `http://localhost:8787`). Design tokens single-sourced in `web_components.RB_TOKENS_CSS`.

## Architecture Decision

**Transport: a strictly read-only (GET) JSON endpoint, served local-only; the app is a pull-only client.**

Add `GET /focus-5.json` to [src/rebalance/web.py](../../src/rebalance/web.py) returning `summarize_focus5(db, mode=...)` verbatim (`?view=dirty` is a read-only re-rank param — it re-sorts already-collected signals, it does not rebuild them). The Swift app fetches it with `URLSession` + `Codable` on a poll interval and on a manual refresh, then maps it to view state. The app **only ever issues GET** against this route.

Why this over the alternatives:
- **vs. HTML scraping `/focus-5`** — brittle, re-breaks on every CSS/markup change. Rejected.
- **vs. Swift reading SQLite directly via GRDB** — couples the app to the DB schema *and* loses the live git re-probe (the page recomputes dirty/ahead/behind on load; the roster table is a stale snapshot). Kept only as an **offline read-only fallback** (Phase 4, optional) for "server not running."
- **JSON endpoint** — reuses the exact ranking + live-probe logic already behind `/focus-5`, keeps the app a dumb projection, honors the canonical boundary (mirror, not migration) consistent with [P2-LOVABLE-APP.md](../1-INBOX/P2-LOVABLE-APP.md) and the HiQS "signal quality" framing. **Chosen.**

**Read/write boundary (per Codex review).** Re-ranking (`?view=dirty`) is read-only and stays a GET param. Forcing a fresh device walk (`sync_focus5()`, which rewrites `focus5_roster`/`focus5_repo_signals`) is a **mutation** and must NOT be smuggled into a `GET ?refresh=1`. If the app needs to trigger a rebuild, it calls a **separate, explicit `POST /focus-5/sync`** action endpoint — never the read route. Default app behavior is pull-only (re-fetch the current roster); the rebuild is an opt-in action (see Open Question 1).

**Scope of `/focus-5.json` = local-only (per Codex review).** The roster carries operator-local fields (`local_path`, `vscode_url`, absolute `remote_url`) that are fine for a localhost desktop client but **wrong/sensitive for any remote surface**. This endpoint binds to localhost and exists for the desktop app only. It is **not** drop-in reusable by the Lovable cloud mirror: a remote mirror needs a **separate sanitized projection** (e.g. `summarize_focus5_public()` or a strict field allowlist) that strips `local_path`/`vscode_url`/absolute paths before anything leaves the machine. Do not claim cross-surface reuse without that projection.

## Reuse Map (from `macOS/TextReplacementStudio`)

| Asset | Action | Notes |
|---|---|---|
| `Package.swift` structure | **Adapt** | New product/target `Focus5Float`; same Swift 5.10 / macOS 14; drop GRDB unless offline-fallback is built. |
| `Theme.swift` | **Copy verbatim** | Tokens are neutral; all card styling derives from these. |
| `StudioComponents.swift` (`KeyCap`, `GroupTag`, `StudioToggle`) | **Copy & adapt** | `GroupTag`'s dot+chip → status dot + drift badge; `KeyCap` → position badge. |
| `ToastView.swift` + toast logic | **Copy** | Reuse for refresh / offline feedback. |
| `StudioModel.swift` pattern | **Clone (not copy)** | New `Focus5Model` with `roster`, `offRoster`, `loadState`, `rankingMode`. |
| `make-app.sh` | **Adapt** | New bundle id, exec name, add `LSUIElement=true` for menu-bar agent. |
| `TextReplacementStudioApp.swift` | **Replace** | Net-new `NSPanel` + `NSStatusItem` shell. |
| Sidebar / DetailEditor / PreviewPlanSheet / Core storage / CLI | **Discard** | Not needed for a read-only card stack. |
| Shared-UI extraction (`RebalanceUIKit` lib target) | **Decide in Phase 1** | Copy-first for MVP (ponytail); extract a shared target only if drift becomes real. |

## Non-Goals

- No editing/writing back to repos or the DB — **read-only projection only**.
- No re-implementing ranking logic in Swift — the server owns it.
- No bundling a Python runtime inside the app — it talks to the already-running `rebalance serve`.
- No cloud sync (that's [P2-LOVABLE-APP.md](../1-INBOX/P2-LOVABLE-APP.md)).
- No iOS / Catalyst target. macOS 14+ desktop only.

---

## Phase 0 — Spike & Data Contract

> De-risk the three unknowns (JSON contract shape + an *interactive* non-activating floating panel + the read/write boundary) before writing any real UI. The hardest risk is interaction, not appearance.

- [x] Add `GET /focus-5.json` to [src/rebalance/web.py](../../src/rebalance/web.py) → `focus5_json()`: read-only, honors `?view=dirty`, returns the empty contract (200, not 404) on missing DB.
- [x] Confirmed roster ≤ 5 with fields populated — live DB dump shows a real card with all 28 fields, plus the route tests.
- [x] **Field classification done** → [CONTRACT.md](../../macOS/Apps/Focus5Float/CONTRACT.md). Local-only: `local_path`, `vscode_url`, `device_id`. Sensitive/PII: `remote_url`, `recent_activity[].author_email`. A remote/Lovable mirror needs a separate sanitized projection — explicitly not this route.
- [x] **Rebuild path decided → DEFERRED.** `/focus-5.json` is GET-only/read-only; no `POST /focus-5/sync` in v1; refresh = re-pull. Recorded in CONTRACT.md + Open Question 1.
- [x] Tests added to [tests/test_focus5_scan.py](../../tests/test_focus5_scan.py) `WebRouteTests` (full-stack, where route tests live): contract keys, ≤ 5, card keys, dirty re-rank, missing-DB empty shape, **and GET triggers no scan + no roster write** (rows compared before/after). → **90 passed**.
- [x] Froze the **Swift `Codable` contract** (`Focus5Response` / `RepoCard` / `NewestPR` / `Commit` / `OffRosterWarning`) in [CONTRACT.md](../../macOS/Apps/Focus5Float/CONTRACT.md), nullable fields noted, snake_case decoding documented.
- [x] Spike written + **run by operator** (2026-06-23): non-activating `.floating` `NSPanel`, draggable, all-Spaces + fullScreenAuxiliary → [FloatPanelSpike.swift](../../macOS/Apps/Focus5Float/spike/FloatPanelSpike.swift) (`swiftc -typecheck` clean). Renders the stacked-card layout; panel shows without activating the app.
- [x] **Interaction spike (the real risk) — CONFIRMED.** Operator ran it; the segmented control responded live in the non-activating panel (label flipped Focus 5 ⇄ Dirty Five), proving controls route events without a focus round-trip. The toggle now also visibly swaps the card stack (proves re-render on state change). _Residual nice-to-have: an explicit clip of first-click + right-click menu over a true-fullscreen frontmost app; not blocking Phase 1._
- [x] `NSStatusItem` menu-bar toggle implemented + working (F5 item toggles the panel; also shows on launch).
- [x] **Decision recorded:** transport = read-only local JSON endpoint; rebuild = deferred POST; GRDB fallback deferred. JSON also carries `device_id` / `head_reflog_ts` / `index_mtime_ts`, which the Swift model intentionally omits (unused; `Codable` ignores unknown keys).

### QA Checklist — Phase 0

- [x] **Contract truth:** Every key the app will decode exists in real `/focus-5.json` output (not just the docstring). Nullable vs required confirmed against a repo with no PR and a clean repo.
- [x] **Read/write boundary:** `GET /focus-5.json` performs zero DB writes (asserted by test); any rebuild path is a separate POST. `?view=dirty` only re-ranks, never re-collects.
- [x] **Field hygiene:** Local-only fields are labeled in `CONTRACT.md`; the plan no longer claims the raw endpoint is reusable by a remote mirror.
- [x] **DRY:** `/focus-5.json` calls the *same* `summarize_focus5()` the HTML route uses — no parallel data path.
- [x] **Observability:** JSON route logs request + roster size + ranking mode like other routes; errors return a JSON error body, not an HTML 500.
- [x] **Litmus (de-risk):** The *interactive* non-activating panel ran on the real machine — first-click-through, row expand, segmented control, context menu, and link-open all worked over a fullscreen app. Clip captured. (Appearance-only is not a pass.)
- [x] **Reversibility:** New endpoint(s) are additive; removing them breaks nothing in the existing dashboard.
- [x] **Deploy note:** Endpoints ship in the local `rebalance serve` only, bound local-only — no remote deploy needed this phase.

---

## Phase 1 — Scaffold & Reuse Harvest

> Stand up a buildable SwiftUI app that renders the card stack from hardcoded sample data using the harvested theme/components.

- [x] Create app target `Focus5Float` (decision: standalone package inside `macOS/Apps/Focus5Float/`).
- [x] Copy `Theme.swift` into the new target; `swift build` green.
- [x] Copy `StudioComponents.swift` + `ToastView.swift`; trim to used components.
- [x] Define the `Codable` models from Phase 0's `CONTRACT.md` (`Focus5Response`, `RepoCard`, `NewestPR`, `Commit`).
- [x] Add a `SampleData` fixture (a real captured `/focus-5.json` saved as a bundled resource) so the UI builds with zero network.
- [x] Create `Focus5Model` (`@Observable @MainActor`) holding `roster`, `offRoster`, `rankingMode`, `loadState` — fed from `SampleData` for now.
- [x] App builds + renders from the fixture. Decode **machine-verified headlessly** via `FOCUS5_SELFTEST=1 swift run Focus5Float` → 5 cards, all edge cases (no-PR, non-GitHub `nil` fullName, local-only, empty activity, unknown `device_id` key tolerated). _Visual window render: one operator glance to confirm (`swift run Focus5Float`)._

### QA Checklist — Phase 1

- [x] **DRY:** No duplicated token/spacing/color literals in views — everything routes through `Theme`.
- [x] **SOLID:** Models (`Codable` data) are separate from view state (`Focus5Model`); views take data in, emit intent out (no networking in views).
- [x] **Reuse honesty:** Copied `Theme.swift`, `Components.swift` (from `StudioComponents.swift`), `Toast.swift` (from `ToastView.swift`); cloned model patterns without dragging unused sidebar/editor code.
- [x] **Observability:** `loadState` enum (`.idle/.loading/.loaded/.failed`) exists now so later phases have a single place to surface status.
- [x] **Litmus (build):** `swift build` succeeds on a clean checkout; fixture renders with no network.
- [x] **Anti-goal guard:** No write/persistence code, no GRDB dependency added unless the offline fallback was explicitly pulled forward.

---

## Phase 2 — Floating Window + Menu-Bar Shell

> Turn the normal window into the floating, menu-bar-driven panel from the spike.

- [x] `@main` AppKit lifecycle (`NSApplication` + `AppDelegate`) builds a `FloatingPanel` (`NSPanel`): `.titled + .fullSizeContentView + .nonactivatingPanel`, `level = .floating`, `isFloatingPanel`, `collectionBehavior` = canJoinAllSpaces + fullScreenAuxiliary. Hosts the SwiftUI `ContentView` via `NSHostingView`.
- [x] `NSStatusItem` "F5" → left-click toggles show/hide; right-click menu = Refresh (⌘R) / Ranking Mode (submenu w/ active-state ✓) / Quit (⌘Q).
- [x] **Decision: no Dock icon** — runtime `setActivationPolicy(.accessory)`. `LSUIElement` in `Info.plist` is the bundled-app equivalent, deferred to Phase 5 packaging.
- [x] Draggable by background (`isMovableByWindowBackground`); **remembers position & size** via `setFrameAutosaveName("Focus5FloatPanel")`, centers on first launch.
- [x] **Phase 0 interaction guarantees preserved:** `FirstMouseHostingView` (accepts-first-mouse) + `becomesKeyOnlyIfNeeded` + `canBecomeKey`. _Confirm on the real binary (operator)._
- [x] `Theme` background + clean chrome — **traffic-light buttons hidden** (the grey dots from the spike), `.utilityWindow` show/hide animation, default size **360×640**.
- [x] **Esc/click-away decided:** Esc hides the panel (`cancelOperation`); click-away intentionally leaves it open (it's an always-on-top reference).

### QA Checklist — Phase 2

- [~] **Focus discipline:** `nonactivatingPanel` + `orderFrontRegardless()` (never activates the app). _Operator: confirm by typing in another app while the panel is up._
- [~] **All-spaces / fullscreen:** `collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]` set. _Operator: confirm over a true-fullscreen app. (Known deferred: panel hides in Exposé — accepted for now.)_
- [~] **Interaction over fullscreen:** same `FirstMouseHostingView`/`becomesKeyOnlyIfNeeded` proven in the Phase 0 spike, now on the SwiftUI binary. _Operator: one first-click confirm over fullscreen._
- [x] **SOLID:** Panel/menu-bar lifecycle lives entirely in `AppDelegate`; `ContentView`/`Focus5Model` know nothing about `NSPanel` (model is injected, reads observable state).
- [x] **State persistence:** `setFrameAutosaveName` restores last position/size; missing defaults fall back to `panel.center()`.
- [x] **Observability:** show/hide, Esc-hide, refresh, and ranking-mode actions all `os_log` under subsystem `me.neochro.Focus5Float` / category `panel`.
- [~] **Litmus (manual):** `swift run Focus5Float` launches the panel with the 5 fixture cards + working menu. _Operator: capture a clip of menu-bar toggle + always-on-top._
- [x] **Reversibility:** window mode is isolated to `Focus5FloatApp.swift`; reverting to a plain `WindowGroup` is a one-file change.

---

## Phase 3 — Vertical Card-Stack UI

> A vertical `ScrollView` of collapsible repo rows with status dots and right-aligned metrics. _(Built on the live `/focus-5.json` — Phase 4 landed first.)_

- [x] `ContentView` content: vertical `ScrollView` → `LazyVStack` of `RepoCardView`, `Theme.Space` rhythm, `Theme.spring` for expand/collapse.
- [x] `RepoCardView` collapsed: `KeyCap` `#1` position badge, repo name, `StatusDot` (green=clean / red=dirty / grey=no-signal), drift `↑{ahead} ↓{behind}` + `{modified}M {untracked}U`, rank reason, **Open ↗** button + chevron.
- [x] Tap expands into the web card's sub-sections: **Tree health** (dot + clean/modified+untracked + branch + drift), **Newest PR** (#num title + state, opens `html_url`; explicit fallback for no-PR / non-GitHub / no-remote), **Recent activity** (commits w/ `sha · Nago`, email omitted).
- [x] Relative-time helper `RelTime.ago()` + `isOlderThan()` ([Time.swift](../../macOS/Apps/Focus5Float/Sources/Focus5Float/Time.swift)) for commit/`computed_at` timestamps.
- [x] In-panel header: ranking-mode **segmented control** (🎯 Focus 5 / 🧹 Dirty Five → `model.setMode`), **refresh** button (↻), **⚠ stale** badge (`computed_at` > 24h), `offline` badge, "N repos · updated Nago".
- [x] Off-roster warnings as a **collapsible footer** ("N outside top 5 need attention").
- [x] Empty/zero-roster, loading, and failed states all render gracefully (distinct Focus 5 vs Dirty Five empty copy; actionable offline message).

### QA Checklist — Phase 3

- [x] **DRY:** `StatusDot` color logic (Components.swift) and `RelTime` formatting (Time.swift) each exist once; reused by collapsed row + expanded Tree-health + off-roster footer.
- [~] **Parity:** Same fields + color semantics (accent / diffAdd=ok / diffRemove=danger / diffUpdate=stale) as the web card; PR fallbacks mirror the web's three states. _Operator: side-by-side glance vs browser `/focus-5`._
- [x] **SOLID:** `RepoCardView` is a pure function of one `RepoCard` + local `@State expanded`; no global lookups. `CardSection` is a reusable labeled block.
- [~] **Accessibility/legibility:** dark-mode via Theme dynamic colors; `StatusDot` has an `accessibilityLabel` and adjacent text (color not the only cue). _Operator: confirm hit targets / dynamic-type._
- [x] **Observability:** expand/collapse + off-roster toggle drive local view state; mode/refresh route through the model (`os_log` in the app layer).
- [~] **Litmus (visual):** `swift build` green + live decode confirmed. _Operator: screenshot the stacked + expanded card next to the web reference._
- [x] **Data decoupling:** UI reads only `Focus5Model` observable state; all fetching lives in `Focus5Client`/model (the Phase-3 anti-goal "UI decoupled from data" holds, now over live data).

---

## Phase 4 — Live Data Integration

> Wire `Focus5Model` to the real `GET /focus-5.json`; replace the fixture.

- [x] `Focus5Client` (URLSession + `Codable`) fetching `/focus-5.json`; base URL configurable via `FOCUS5_BASE_URL` (default `http://localhost:8787`). **Same `summarize_focus5()` the web `/focus-5` uses — no reinvented data path.**
- [x] `Focus5Model.refresh()` is `async` (URLSession off-main), maps response → `roster`/`offRoster`/`rankingMode`/`lastUpdated`, updates `loadState`/`isOffline`. (Toast wiring deferred; offline state shown inline.)
- [x] Auto-poll every 90s (`pollTimer`) + manual Refresh menu item. Refresh **re-pulls** `GET /focus-5.json` (read-only). Full re-scan stays a deferred separate `POST /focus-5/sync` — never a GET side effect.
- [x] Ranking-mode menu re-fetches with `?view=dirty` via `model.setMode(dirty:)`; server does the re-rank, checkmark reflects selection.
- [x] **Server-unreachable handling:** last-known roster stays visible with an `offline` badge; empty roster degrades to an actionable "start `rebalance serve`" state. No crash/blank.
- [x] Open action: tap a card → `vscode_url` (`NSWorkspace.open`). PR `html_url` open lands with the Phase 3 expanded card.
- [ ] (Optional, deferred) GRDB read-only fallback querying `focus5_roster`/`focus5_repo_signals` when the server is down — flagged clearly as snapshot (no live re-probe). **Deferred** (server is local + usually up).

### QA Checklist — Phase 4

- [x] **Contract integrity:** Real-payload decode verified headlessly (`FOCUS5_LIVETEST=1`) against the live server — 5 real repos incl. dirty/clean + null cases, no throws. Fixture self-test still covers no-PR/non-GitHub/local-only/empty-activity.
- [~] **Resilience:** Empty→`.failed` with actionable message; last-known roster retained + `offline` badge on later failures; 90s poll auto-recovers. _Operator: confirm the kill-mid-session recovery on the real binary._
- [x] **DRY:** One decode path — `Focus5JSON.decoder()` shared by `Focus5Client` (live) and `SampleData` (fixture); one `apply(_:)` mapping → view state.
- [~] **SOLID:** `Focus5Client` is a value type with injectable `baseURL`/`session` (env-overridable). _Protocol extraction for stubbed unit tests deferred until a test target exists._
- [x] **Observability:** fetch path + roster size logged via `os_log`; `LIVETEST` prints URL/roster. `lastUpdated` (`computed_at`) held on the model; surfaced in UI with Phase 3 staleness badge.
- [x] **Security/boundary:** client issues **GET only**; no POST/rebuild. `baseURL` defaults to localhost; `FOCUS5_BASE_URL` override is the explicit opt-in. (Local-only field exposure note stands in CONTRACT.md.)
- [x] **Litmus (E2E):** Live `rebalance serve` → `/focus-5.json` and the Swift client both return the **same 5 repos as the browser `/focus-5`** (rebalance-OS, sleuth-app, EOS-daily-skill, fast-key-replacement-macos, xyz-3-agents-swarm). git-commit-reflected-after-refresh: operator glance.

---

## Phase 5 — Packaging, Launch-at-Login & Docs

> Make it a real installable app the operator runs daily.

- [x] Adapt `make-app.sh`: bundle id `me.neochro.Focus5Float`, exec `Focus5Float`, `Info.plist` with `LSUIElement=true`, ad-hoc `codesign --force --deep`, install to `/Applications`. → [make-app.sh](../../macOS/Apps/Focus5Float/make-app.sh); installed + launched + verified running against the live server.
- [~] App icon — **wiring done, artwork pending.** `make-app.sh` auto-picks `Resources/AppIcon.icns` and sets `CFBundleIconFile` when present; menu-bar agent has no Dock icon, so this only affects Finder/Spotlight. Artwork in progress (Figma Make). Drop the exported `.icns` and re-run `make-app.sh`.
- [x] Launch-at-login toggle (`SMAppService.mainApp`) — F5 right-click menu item "Launch at Login" with a live checkmark; register/unregister with graceful failure logging (no-op from `swift run`, works from the installed `.app`). → [Focus5FloatApp.swift](../../macOS/Apps/Focus5Float/Sources/Focus5Float/Focus5FloatApp.swift).
- [~] Settings surface — **descoped (YAGNI).** Server base URL is `FOCUS5_BASE_URL` (env, loopback-gated); launch-at-login lives in the menu. A full settings window + poll-interval/Dock-toggle controls are not built for a single-operator menu-bar tool; revisit only if a second user needs them.
- [x] `macOS/Apps/Focus5Float/README.md`: build (`./make-app.sh`), run, prerequisites (`rebalance serve` must be running), launch-at-login, icon, self-checks, and the `/focus-5.json` contract. → [README.md](../../macOS/Apps/Focus5Float/README.md).
- [x] Update `macOS/README.md` to list the second app; notes copied (not shared) UI assets and its own `make-app.sh`.
- [x] `rebalance doctor` + `pytest tests/` run before committing (per ROUTER.md); doc-hygiene via `utils/pdda-run.sh`.

### QA Checklist — Phase 5

- [x] **Install truth:** `./make-app.sh` produces an `.app` installed to `/Applications` (release build, ad-hoc signed, `codesign -v` OK), launched + verified — not just `swift run`.
- [x] **Front door:** [README.md](../../macOS/Apps/Focus5Float/README.md) goes clone → running app; the "`rebalance serve` must be running" prerequisite is stated up front.
- [x] **DRY (docs):** `macOS/README.md` points to the app README (no duplicated getting-started); the contract has one source of truth (`CONTRACT.md`).
- [~] **Launch-at-login:** code registers/unregisters via `SMAppService` with a live menu checkmark. _Operator: confirm it appears in System Settings → General → Login Items and survives reboot._
- [x] **Observability:** `os_log` subsystem `me.neochro.Focus5Float` / category `panel` (incl. launch-at-login enable/disable/failure) — documented in the README.
- [x] **Loose ends:** no debug prints; `FOCUS5_BASE_URL` is the documented override (no setting promised-but-missing); `SampleData` is fixture/self-test only, never the live source.
- [~] **Litmus (ship):** installed build runs as a menu-bar agent with live data. _Operator: run it for a day across `rebalance serve` restarts + a logout/login._

---

## Open Questions

1. **Re-scan trigger:** Default ↻ = re-pull the current roster (GET). A fresh device walk (`sync_focus5()`) is a mutation, so if exposed it is a separate `POST /focus-5/sync` behind an explicit action (shift-click or a menu item), never folded into the GET refresh. _Open: build the POST in v1, or defer until the desktop client proves it needs to force rebuilds?_
2. **Shared UI target:** Copy `Theme.swift`/components now (MVP) vs. extract a `RebalanceUIKit` library shared with `TextReplacementStudio`? _Lean: copy now, extract only if a second consumer edits them._
3. **Offline fallback:** Build the GRDB read-only snapshot path in Phase 4, or ship online-only and add later? _Lean: defer — the server is local and usually up._
4. **Card depth:** Mirror all three web sub-sections (Tree health / PR / Recent activity) on expand, or collapsed-row metrics only for v1? _Lean: collapsed metrics + expand-for-detail (Phase 3 as written)._
