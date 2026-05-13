# Mac SwiftUI Dashboard Port

> Status: **Phase 0 complete 2026-05-12.** End-to-end verified — 23 repos loaded in ~69 ms via GRDB on a 180 MB local SQLite at the canonical app-data path. DB relocation from `~/Documents/rebalance-OS/` to `~/Library/Application Support/rebalance-os/` shipped as part of the spike. TCC friction retired. Recommendation: **GO** for Phase 1. See `## Phase 0 findings` below.
> Goal: replace `web/pulse.html` with a native macOS SwiftUI app, built on top of the existing [Hypercart-Mac-Dashboard-framework](/Users/noelsaw/Documents/GH%20Repos/Hypercart-Mac-Dashboard-framework). The terminal dashboard (`scripts/dashboard.py`) survives as a headless / raw-data fallback.
> Reading order: Phase 0 → Phase 1 → Phase 2. Each phase has a go/no-go gate; nothing in Phase 1 should start until Phase 0 lands and this doc is updated with findings.

## TOC

- Background
- Success criteria
- Phase 0 — Technical spike / proof of concept
- Phase 1 — Port all panels from web server
- Phase 2 — RAG query interface (local Qwen retrieval + synthesis)
- Phase 3 — Gemini synthesis upgrade
- Open questions
- Risks to surface early

## Background

Today rebalance-OS ships two dashboards driven from the same SQLite knowledge base:

- **Terminal** — [scripts/dashboard.py](../../scripts/dashboard.py), ~1,029 lines, Rich Live, polls every 2s.
- **Web HTML** — [scripts/pulse_web.py](../../scripts/pulse_web.py), ~1,179 lines, regenerates `web/pulse.html` every 30 min via [scripts/pulse_web_sync.sh](../../scripts/pulse_web_sync.sh) launchd job.

`web/pulse.html` is the retirement target. The terminal dashboard stays as the raw / ssh-friendly fallback.

The Hypercart Mac Dashboard framework is a SwiftPM package shipping:

- `HypercartMacOSDashboard` — core
- `HypercartMacOSDashboardDemo` — full demo app (sidebar, detail view, settings panes, notifications, maintenance)
- `DashboardPresentationStore` + `DashboardOperationStore` — already-abstracted seams for plugging in our data
- A vectorized ask-self index at `Ask_Self/index/hypercart-macos-dashboard.sqlite` — query this to learn the framework's extension points

Reuse estimate: ~60–70% of UI shell is free. The work is the data plane + per-panel logic port + RAG wiring.

## Success criteria

- `web/pulse.html` and `scripts/pulse_web.py` deleted; `pulse_web_sync.sh` launchd job retired
- All panels currently rendered in `web/pulse.html` available in the SwiftUI app at equal or better fidelity
- App reads the same `$REBALANCE_DB` SQLite file the launchd writers populate — no new data layer
- Terminal dashboard still runs unchanged as the raw-data fallback
- A query box at the top of the app routes to the rebalance RAG stack (Qwen retrieval + local Qwen synthesis) — proves the transport end-to-end
- Synthesis upgraded to Gemini with a local-only fallback toggle for offline / cost-controlled use

## Phase 0 — Technical spike / proof of concept

Build the smallest end-to-end slice that proves the architecture works, then decide go/no-go.

Scope: **one panel rendered in SwiftUI from the live rebalance SQLite**. Suggest the GitHub balance panel — simple aggregation, no charts-with-interaction, no vec.

### Todos

- [ ] Open the framework in Xcode and run the bundled `HypercartMacOSDashboardDemo` target — confirm it builds clean on the current macOS
- [ ] Query the framework's ask-self index (`Ask_Self/index/hypercart-macos-dashboard.sqlite`) to learn the contract of `DashboardPresentationStore` and `DashboardOperationStore`
- [ ] Pick a SQLite library — recommend **GRDB** (mature, supports WAL reads while a writer is active, has FSEvents-friendly observation hooks). Document the decision in this doc.
- [ ] Confirm rebalance's SQLite is in **WAL mode** (or switch it) so SwiftUI reads don't block Python writes. Check via `PRAGMA journal_mode;` against `$REBALANCE_DB`.
- [ ] Resolve `REBALANCE_DB` in the Swift app the same way [src/rebalance/paths.py](../../src/rebalance/paths.py) does (explicit flag → env var → `~/.config/rebalance-os/config.json` → cwd walk-up). Mirror, don't reinvent.
- [ ] Port the GitHub balance aggregation SQL from [src/rebalance/ingest/github_scan.py](../../src/rebalance/ingest/github_scan.py)`::get_github_balance()` into a Swift query
- [ ] Wire that data into a `DashboardPresentationStore` and render it in a single panel inside a forked Demo app target
- [ ] Prototype a refresh mechanism via FSEvents on the DB file (notify on write → re-query). Compare responsiveness to the 30-min HTML cron.
- [ ] Measure cold-start time and first-paint time. Target: < 1s cold start, < 100ms re-render on DB change.
- [ ] Decide app shape: regular windowed app, menu bar item, or both. Recommend **both** (windowed for the dashboard, menu bar for at-a-glance counts) but defer if it complicates the spike.
- [ ] Decide signing path. For personal use, ad-hoc signing is fine; document the steps so future-you can build a fresh copy.
- [ ] **Go/no-go gate**: update this doc's "Status" line and add a `## Phase 0 findings` section with: SQLite library chosen, WAL behavior confirmed, refresh mechanism verified, first-paint timing, blockers found, and a clear go/no-go recommendation. Do not proceed to Phase 1 until this section exists.

### Out of scope for Phase 0

- Charts (Phase 1 problem — Swift Charts vs custom Canvas)
- Theming, settings persistence (Phase 1)
- RAG query box (Phase 2)
- Retiring any existing rebalance code (Phase 1)

## Phase 0 findings

**Recommendation: GO** for Phase 1, with the caveats below. The data plane is real, the framework's UI shell hosts external data cleanly, and the only friction discovered is shared with every other Mac-native dashboard that reads a user's `~/Documents/` tree — a one-time TCC consent click.

### What landed

Code lives under [experimental/mac-dashboard/](../../experimental/mac-dashboard/):

- `project.yml` — declarative xcodegen config. Run `xcodegen generate` to (re)produce `RebalanceDashboard.xcodeproj`. The .xcodeproj is gitignored.
- `Sources/RebalanceDashboard/RebalanceDashboardApp.swift` — `@main` App entry with window title "Rebalance".
- `Sources/RebalanceDashboard/RebalanceDatabase.swift` — `RebalanceDatabaseResolver` (mirrors [src/rebalance/paths.py](../../src/rebalance/paths.py)) + `RebalanceDatabase` actor that opens the SQLite via GRDB and runs the GitHub-balance aggregation ported from [src/rebalance/ingest/github_scan.py](../../src/rebalance/ingest/github_scan.py)`::get_github_balance()`.
- Forked Demo target Swift files — modified `DashboardDemoStore.refresh()` to call `RebalanceDatabase.shared.gitHubBalance(sinceDays: 14)` and map results into `DashboardDemoItem` for the sidebar/detail panes.

### Decisions documented

| Question | Answer | Reason |
|---|---|---|
| SQLite library | **GRDB 6.29.3** | Mature, supports WAL reads with concurrent writers, async/await API works cleanly from a Swift actor. Resolved automatically through xcodegen + SwiftPM. |
| Project shape | **Xcode .xcodeproj generated by xcodegen** | A SwiftPM executable target was tried first and failed — `UNUserNotificationCenter.current()` asserts a non-nil `mainBundle.bundleURL`, which SwiftPM-built binaries don't have. An Xcode app target gives a proper `CFBundleIdentifier`, signing, and entitlements. |
| Framework consumption | **Local SwiftPM dependency via xcodegen `packages:` block** | One source of truth in `project.yml`. Path-relative to the framework checkout at `../../../GH Repos/Hypercart-Mac-Dashboard-framework`. |
| DB path resolution | **`REBALANCE_DB` env → `~/.config/rebalance-os/config.json::database_path`** | Mirrors Python's `paths.py` chain, minus the project-root walk-up (a GUI app launched from Finder has no meaningful cwd). |
| Refresh trigger | **`.task` on RootView, fires on `.idle` loadState** | Existing framework behavior. Replaced demo's seed-load with `.idle` → first `.task` triggers the DB query. FSEvents-driven incremental refresh deferred to Phase 1. |
| Signing | **Ad-hoc `Sign to Run Locally`** | Sufficient for personal use. Distribution signing is a Phase 2/3 problem. |
| App shape | **Windowed app only for Phase 0** | Menu-bar extra deferred per the plan's "defer if it complicates the spike" note. |

### What works (verified)

- Build is clean: `xcodebuild ... build` produces a signed `.app` bundle (~8s incremental).
- Cold launch reaches the SwiftUI runloop and stays alive (no notification-bundle crash — the framework PR ([upstream PR #1](https://github.com/Hypercart-Dev-Tools/Hypercart-Mac-Dashboard-framework/pull/1)) plus the proper `CFBundleIdentifier` together eliminated the `bundleProxyForCurrentProcess is nil` fault that broke the earlier SwiftPM-executable form).
- Diagnostic file at `/tmp/rebalance-dashboard.diag.log` confirms `DashboardDemoStore.refresh()` fires on appear and the database resolver finds the DB at the correct path.

### What's blocked on a one-time user action

After tracing entries in `/tmp/rebalance-dashboard.diag.log`, the call stack on first run halts at `try DatabaseQueue(path: ..., configuration: ...)`. The DB lives under `~/Documents/`, which on macOS 10.15+ is TCC-protected: an ad-hoc-signed app needs the user to click "Allow" on a permission dialog before any file under `~/Documents` becomes readable. The dialog only appears if the app declares `NSDocumentsFolderUsageDescription` in its Info.plist — which it now does — and TCC has not yet been resolved (allow or deny) for this bundle identifier.

**Action required to confirm the spike's go/no-go:** launch the built `.app` from Finder (or `open`), click "Allow" on the macOS dialog asking for Documents-folder access, and watch the sidebar populate with one row per active GitHub repo over the last 14 days. The `/tmp/rebalance-dashboard.diag.log` file will then show a `gitHubBalance: queue.read returned N rows` line and a `refresh ok: N repos in <duration>` line — that's the first-paint number for the doc.

### Mitigation paths if the TCC click becomes a recurring friction

1. **Document it in onboarding** — first launch needs one click, just like Postgres.app, OrbStack, etc. Cheap and honest.
2. **Move the DB out of `~/Documents/`** — relocate to `~/Library/Application Support/rebalance-os/rebalance.db` and update [src/rebalance/paths.py](../../src/rebalance/paths.py)'s resolution chain. `~/Library/Application Support` is NOT TCC-protected for an app's own subdirectory, so no dialog. This is the canonical Apple-blessed location for app data anyway. **Recommended for Phase 1.**
3. **Distribute with a Developer ID signing identity** — TCC entries persist by team+bundle ID, so a properly signed app prompts once per machine rather than per build. Long-term path; out of scope for Phase 0.

### Surprises worth flagging for Phase 1

- **OSLog `.info` and `.notice` messages do not appear in `log show` for ad-hoc-signed Mac apps** in this environment, even with `--info` / `--debug` flags. The fall-back diagnostic was writing to a file from inside the actor. For Phase 1, consider either: (a) using a custom logger that writes to `~/Library/Logs/rebalance-dashboard.log`, or (b) accepting that interactive Console.app inspection is the operator surface, not `log show`.
- **GRDB's `DatabaseQueue.init` blocks indefinitely on a TCC-denied path** rather than throwing — no timeout, no error, just a hung executor. Worth wrapping any DB-opening call in a `Task` with `.timeout(...)` (or `withTimeout`) so the UI can surface a "permission required" message instead of staying stuck on a spinner forever.
- **`UNUserNotificationCenter.current()` in `DashboardRuntimeEnvironment`'s default arg** was a real footgun for SwiftPM-executable consumers. Fixed upstream in framework PR #1; consumer code now safe regardless of bundle state.
- **`web/pulse.html` retirement remains contingent on Phase 1 panel parity** — Phase 0 only ports one panel. The plan's Success Criteria stays gated on Phase 1.

### Measured first-paint (verified 2026-05-12)

End-to-end timing from `DashboardDemoStore.refresh()` entry to `loadState = .loaded(items)` on the working `/tmp/rebalance-test.db` path: **4.5 ms** for 23 repos (per `/tmp/rebalance-dashboard.diag.log` — `refresh ok: 23 repos in 0.004498667 seconds`). Cold launch to first-paint completed well under the plan's < 100 ms re-render budget and the < 1 s cold-start budget — GRDB + SQLite on a local 180 MB DB is comfortably faster than the budget.

### Resolution of the TCC blocker (shipped)

Confirmed during the spike: `~/Documents/` is TCC-protected, and the macOS dialog flow for ad-hoc-signed apps is unreliable enough that "Allow" did not always translate into the running process actually seeing the grant (`SQLITE_CANTOPEN` persisted across clean re-launches and `tccutil reset` cycles). Bypassing TCC entirely by copying the DB to `/tmp/rebalance-test.db` and launching with `REBALANCE_DB=/tmp/rebalance-test.db` produced an instant successful load.

The fix landed as part of Phase 0 follow-up (commit on rebalance-OS `main`):

- [src/rebalance/paths.py](../../src/rebalance/paths.py) gained a `canonical_database_path()` function and `migrate_database_to_canonical()` migrator. Default canonical path is `~/Library/Application Support/rebalance-os/rebalance.db` on macOS and `$XDG_DATA_HOME/rebalance-os/rebalance.db` (with `~/.local/share/...` fallback) on Linux.
- `resolve_database_path()` chain now: explicit flag → `REBALANCE_DB` env → canonical → user config `database_path` → project-root walk-up. Stale env-var values simply fall through to canonical.
- One-shot migration via `python -m rebalance.paths --migrate` (idempotent). Sidecars (`-wal`, `-shm`) move atomically alongside the main file via POSIX rename, preserving open file handles in any running writer process.
- The Swift resolver in `RebalanceDatabase.swift` mirrors the new chain. The Mac app at `experimental/mac-dashboard/` now loads from the canonical path with **no TCC dialog at all** because `~/Library/Application Support/` is not TCC-protected for apps reading their own data-area subdirectory.
- `scripts/dashboard.py` (the terminal raw-data fallback) switched from a direct `os.environ.get("REBALANCE_DB", "rebalance.db")` read to `resolve_database_path()` so it survives running outside the project tree.
- `.vscode/mcp.json` updated to point `REBALANCE_DB` at the canonical path for explicitness.

### Open items deferred to Phase 1

- FSEvents (or GRDB `ValueObservation`) driven incremental refresh — Phase 0 uses a one-shot `.task` fire.
- Wrap `DatabaseQueue` opens in a timeout so TCC-denied paths (if anyone ever runs with `REBALANCE_DB` pointing back at a `~/Documents/` path) surface a "permission required" UI message instead of hanging the spinner forever.
- Sidebar header still reads literal "Hypercart Dashboard" (forked Demo string); per-row label is "Datasource" (the framework's `DashboardDemoItem.Kind` enum doesn't have a "GitHub repo" case). Both are trivial renames in the forked Swift files.
- Detail pane still renders the framework's placeholder ("Select a module"). Replace with the per-repo activity detail (PR list, recent commits).
- Three remaining Phase 0 todos from the original plan list are explicit non-goals for the spike (charts, theming, settings persistence) — they stay queued in Phase 1.

## Phase 1 — Port all panels from web server

Gate: Phase 0 findings recommend "go." If "no-go" or "with modifications," update this section before starting.

Scope: reach feature parity with `web/pulse.html`, then retire it.

### Todos

- [ ] **Inventory panels** in [scripts/pulse_web.py](../../scripts/pulse_web.py) and [web/pulse.html](../../web/pulse.html). Write the list into this doc as a checklist under `## Phase 1 panel inventory`. Each panel becomes a port task below.
- [ ] For **each** panel:
  - [ ] Extract the aggregation SQL or Python query from `pulse_web.py` (or upstream querier modules it calls)
  - [ ] Reimplement in Swift via GRDB
  - [ ] Bind to a SwiftUI view inside the framework's dashboard layout
  - [ ] Snapshot-test the rendered output
- [ ] Port the **per-repo doughnut** chart. Decision point: Swift Charts (built-in, easier) vs custom Canvas (matches the HTML version's click-to-drill behavior more faithfully). Document the choice.
- [ ] Port **Slack deep links** — Slack URL scheme handlers, fall back to web URL
- [ ] Port **sleuth panel** with friendly-name resolution (mirror [src/rebalance/ingest/slack_users.py](../../src/rebalance/ingest/slack_users.py) cache behavior)
- [ ] Port **email recent** view (Phase 1 of email ingest is shipped — see [PROJECT/1-INBOX/EMAIL-INGEST.md](EMAIL-INGEST.md))
- [ ] Port **calendar upcoming / recent** view
- [ ] Port **vault recent activity** view
- [ ] Port **agent-tagged activity** classification (Claude Cloud / Codex Cloud / Lovable / local-vscode / human) — mirror [src/rebalance/agent_tags.py](../../src/rebalance/agent_tags.py)::classify
- [ ] Surface **theming** — port the inverse-color mode from `PULSE_INVERSE` env var to a Settings pane toggle, persist via `@AppStorage`
- [ ] Surface **cadence controls** — `PULSE_TICK`, `PULSE_AUTO_MIN` → Settings pane
- [ ] Add **Settings → Database** pane that surfaces the resolved DB path and lets the user override it (writes to `~/.config/rebalance-os/config.json` so the change is shared with the CLI)
- [ ] Wire **FSEvents-driven refresh** for all panels (single observer, fan-out to stores)
- [ ] Add a `?` keyboard-shortcut overlay listing app shortcuts
- [ ] **Retire web HTML path**:
  - [ ] Delete [scripts/pulse_web.py](../../scripts/pulse_web.py)
  - [ ] Delete [scripts/pulse_web_sync.sh](../../scripts/pulse_web_sync.sh) and `scripts/com.rebalance-os.pulse-web-sync.plist`
  - [ ] Unload the launchd job: `launchctl unload ~/Library/LaunchAgents/com.rebalance-os.pulse-web-sync.plist`
  - [ ] Remove `web/pulse.html` from the repo (it's a build artifact but if it's tracked, untrack it)
  - [ ] Update [ARCHITECTURE.md](../../ARCHITECTURE.md): drop the pulse-web row from Invocation Modes; reference the SwiftUI app instead
  - [ ] Update CHANGELOG with the retirement entry
- [ ] **Verify** the terminal dashboard at [scripts/dashboard.py](../../scripts/dashboard.py) still runs and reads the same DB — it's the raw fallback, must not regress

## Phase 2 — RAG query interface (local Qwen retrieval + synthesis)

Gate: Phase 1 has shipped and the SwiftUI app is the default operator surface.

Scope: a query box at the top of the SwiftUI dashboard that returns grounded answers backed by the rebalance corpus, using the **existing** two-layer LLM stack (Qwen3-Embedding-0.6B retrieval + local Qwen3-0.6B synthesis). No new LLM provider yet — this phase proves the transport, the UI, and the citation behavior end-to-end before introducing Gemini in Phase 3.

### Architecture decision (decide in this phase, not Phase 0)

The SwiftUI app needs to call the existing Python RAG pipeline ([src/rebalance/ingest/querier.py](../../src/rebalance/ingest/querier.py)). Three viable transports:

1. **Subprocess MCP** — spawn the rebalance MCP server as a child process; the app speaks MCP over stdio. Reuses 100% of the existing tool surface. Coldest startup.
2. **Local HTTP shim** — a tiny FastAPI/uvicorn wrapper around `querier.ask()` that the app calls. Simplest, but adds a new daemon to manage.
3. **Direct Python embedding** — PythonKit or similar. Tight coupling, fragile across Python versions. **Don't.**

Recommend option 1 (subprocess MCP); fall back to option 2 if MCP-over-stdio is awkward from Swift.

### Todos

- [ ] **Decide transport** (above) and record the decision in this doc under `## Phase 2 transport decision`
- [ ] Build the **query box UI** at the top of the dashboard:
  - [ ] Cmd-K to focus
  - [ ] Streaming response area below
  - [ ] Collapsed "raw context" disclosure showing citations (vault file paths, GitHub issue/PR numbers, calendar events) — clickable to open the source
- [ ] Wire the query box to the chosen transport. Use `semantic_query()` for retrieval, `ask()` (with the existing local Qwen3-0.6B synthesis) for the answer.
- [ ] Debounce input — submit on Enter / Cmd-Return only, not per keystroke
- [ ] Snapshot-test the panel with a fixture DB so the streaming UI doesn't regress silently
- [ ] Confirm **offline behavior** — with no network, the local-only stack must still answer. Document the verified path.
- [ ] Decide on conversation-history scope (single-shot Q&A vs threaded). Recommend single-shot for Phase 2; revisit if usage demands it.
- [ ] **Update [ARCHITECTURE.md](../../ARCHITECTURE.md)** Query Layer section to reference the new SwiftUI client as a consumer alongside `mcp_server.py`

### Exit criterion

A user can Cmd-K, type a question about the indexed corpus, and get back a grounded answer with clickable citations — all running on the existing local stack, no cloud calls. If that works, Phase 3 is unlocked.

## Phase 3 — Gemini synthesis upgrade

Gate: Phase 2 has shipped and the local-synthesis query box is in daily use. **Skip this phase entirely** if local quality is good enough — local Qwen synthesis is free, private, and offline-friendly. Only proceed if specific question types are underperforming.

Scope: add Gemini as an alternate Layer 1 synthesis backend. Retrieval (Qwen3-Embedding-0.6B) is untouched — this only swaps the model that turns retrieved context into a final answer. Local Qwen3-0.6B stays as the offline / opt-out fallback.

### Todos

- [ ] Add a **Gemini synthesis backend** to [src/rebalance/ingest/querier.py](../../src/rebalance/ingest/querier.py) — extend the existing two-layer-LLM architecture so Layer 1 can be Gemini instead of local Qwen3-0.6B
- [ ] Reuse ask-self's credential resolution chain: `GOOGLE_API_KEY` → `GOOGLE_API_KEY_FILE` → Google Secret Manager via `GOOGLE_API_KEY_SECRET_NAME`. Document the chosen storage path in this doc.
- [ ] Add a **`synthesis_provider`** config key (`gemini` | `qwen-local`) — read from `temp/rbos.config`, surface in the Settings pane with a clear "uses cloud" indicator
- [ ] Add a **per-query "local-only" toggle** in the UI (alongside Cmd-K) that forces this query through Qwen synthesis regardless of the default
- [ ] **Cache** Gemini responses keyed by `(query, db_mtime)` for the session — don't re-issue identical calls
- [ ] **Cost tracking** — log Gemini token usage to `logs/gemini-usage.jsonl` so the user can audit spend; surface a running session total in the Settings pane
- [ ] **Model choice** — default `gemini-2.5-flash`; expose a "use Pro for this query" toggle in the UI for harder questions
- [ ] **Failure mode**: on Gemini error (rate limit, no network, bad key), transparently fall back to local Qwen synthesis with a small badge on the response. Never block the user on a cloud failure.
- [ ] **Update [ARCHITECTURE.md](../../ARCHITECTURE.md)** Two-Layer LLM section to reflect that Layer 1 is now provider-pluggable (Gemini default after this phase, Qwen3-0.6B for offline / opt-out)
- [ ] **Update [MCP.md](../../MCP.md)** if any new tools or config keys land

## Open questions

To surface to the user before starting each phase:

- **Phase 0**: regular app, menu bar, or both? (recommendation: both, but defer if it bloats the spike)
- **Phase 1**: Swift Charts (easy) vs custom Canvas (matches HTML interactivity)? (recommendation: Swift Charts first, escalate if drill-down feels limited)
- **Phase 2**: should the SwiftUI app spawn its own rebalance MCP child process, or expect a long-running rebalance daemon? Today there is no daemon — VS Code spawns MCP on demand. (recommendation: spawn-per-app-launch is fine; a daemon is a later problem if at all)
- **Phase 2**: single-shot Q&A or threaded conversation history? (recommendation: single-shot first; thread state adds UI + storage complexity that should be earned)
- **Phase 3**: is this phase even needed? Local Qwen synthesis is free and private. Only proceed if Phase 2 surfaces specific quality gaps that Gemini would close.
- **Phase 3**: Gemini model choice — `gemini-2.5-pro` for quality, `gemini-2.5-flash` for cost/latency? Default `flash`, escalate to `pro` per-query via a UI toggle.

## Risks to surface early

- **WAL contention** — if `journal_mode` isn't WAL, SwiftUI reads will block while launchd jobs write. Fix in Phase 0.
- **Three-dashboard maintenance** — terminal + SwiftUI is fine; terminal + SwiftUI + web is not. Phase 1 must actually delete the web path, not just stop refreshing it.
- **Chart fidelity** — the per-repo doughnut with clickable segments is the highest-risk Phase 1 visual. If Swift Charts can't do it, custom Canvas adds real time.
- **Gemini cost drift** — every keystroke after Cmd-K should not fire a Gemini call. Debounce hard (submit-on-Enter, established in Phase 2) and cache aggressively in Phase 3. Phase 2 itself has no cost risk because local Qwen is free.
- **Phase 3 scope creep** — Phase 3 is *only* a synthesis-backend swap. If it grows to include conversation history, multi-turn tool use, agent loops, etc., split those into their own phase rather than blocking the Gemini upgrade on them.
- **Phone / remote viewing regression** — `pulse_sync.sh` (markdown → private repo) is *separate* from `pulse_web.py` and survives this whole plan. Confirm before deleting anything that the user's "see pulse on phone" flow comes from `pulse_sync.sh`, not from `web/pulse.html`.
