---
gh_issue: 123
source: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/123
title: VS Code Extension — Native Tree View for Git Pulse / Rebalance Device Data
status: Active
created: 2026-07-09
updated: 2026-07-09
owner: Noel
goal: >
  A standalone VS Code extension that renders this device's git-pulse /
  rebalance-OS activity (today's commits, yesterday's, upcoming meetings,
  assigned issues) as a native Tree View sidebar pane, reading the local
  pulse markdown file directly — no editor context switch, no dependency on
  pulse-server or a browser tab.
doc_type: project
effort: 2
complexity: 2
risk: 2
phases: 4
branch: feature/gh-123-vscode-pulse-tree-view
non_goals:
  - Replacing pulse-server or web/pulse.html (both stay as-is)
  - A general rebalance-OS dashboard/config UI
  - Multi-device aggregation in v1 (this device's own pulse file only)
  - Collecting or syncing data itself (pure reader of already-synced files)
canonical_boundary: "Standalone VS Code extension (TypeScript); reads a configured git-pulse-sync clone's local pulse markdown file directly from disk — no runtime dependency on the rebalance-OS Python venv, the pulse-server daemon, or network access."
---

# GH-123 — VS Code Extension: Native Tree View for Git Pulse / Rebalance Device Data

## Status

| What was just completed | What's next |
|---|---|
| **Phase 0 complete**: data source confirmed as `live-pulse.md` (not `pulse-<device>.md` — see Spike findings); extension scaffolded at `extensions/pulse-tree-view/`, fixture `TreeDataProvider` compiles clean (`tsc` zero errors). | Phase 1: MVP Tree View — real parser reading `pulseTreeView.pulseFilePath` |

Actionable substance from [issue #123](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/123).

## What this is NOT

- Not a replacement for `pulse-server` (127.0.0.1:8767) or the regenerated `web/pulse.html` — both keep working exactly as they do today; this is a third, editor-native view of the same underlying data.
- Not a rebalance-OS "control panel" — no settings UI beyond pointing the extension at a `git-pulse-sync` clone; no write actions back into rebalance-OS.
- Not multi-device in v1 — shows `live-pulse.md` (see Spike findings for why, not the per-device `pulse-<device>.md` TSV files), matching how the existing rendered pulse doc is already scoped to "this device's current status."
- Not a new data collector — purely reads files that `pulse-sync` / `git-pulse` already write; if those jobs aren't running, the tree shows stale/empty, it doesn't try to fetch anything itself.

## Table of contents

- [Phase 0 — Spike: data source and TreeDataProvider validation](#phase-0--spike-data-source-and-treedataprovider-validation-2-3h) _(2-3h)_
- [Phase 1 — MVP Tree View](#phase-1--mvp-tree-view)
- [Phase 2 — Live refresh](#phase-2--live-refresh)
- [Phase 3 — Polish and packaging](#phase-3--polish-and-packaging)

## Acceptance criteria

- [ ] Extension activates without error in a workspace that has no `git-pulse-sync` clone configured (shows an empty/"not configured" tree state, never throws)
- [ ] Sidebar tree renders Today / Yesterday / Upcoming Meetings / Assigned Issues sections parsed from the real local pulse markdown
- [ ] Tree refreshes automatically within ~1s of the underlying pulse file changing on disk, with no manual reload
- [ ] Packaged as a `.vsix` and installable locally via `code --install-extension`
- [ ] No dependency on the rebalance-OS Python venv or `pulse-server` being up

## Phase 0 — Spike: data source and TreeDataProvider validation (2-3h)

**Discuss:**
- Decide the data source: read a pulse markdown file directly from a configured `git-pulse-sync` path (favored — no daemon dependency, matches `canonical_boundary`) vs. hitting `pulse-server`'s HTTP API (rejected as the v1 default — adds a runtime dependency the extension shouldn't need; revisit only if direct-file parsing proves too fragile).
- Confirm the pulse markdown's actual section structure (headings, list-item shape) is stable enough to parse reliably — spike against the real files in `~/git-pulse-sync/`.
- Validate VS Code's `TreeDataProvider` + `registerTreeDataProvider` API against a hand-built fixture tree before wiring real parsing.
- Scaffold: `yo code` (Yeoman VS Code extension generator) vs. hand-rolled `package.json` + `extension.ts` — went hand-rolled given this is a single-view extension, not the general-purpose scaffold `yo code` optimizes for.
- Directory: extension source lives at `extensions/pulse-tree-view/` in this repo (new top-level `extensions/` dir, following the `macOS/Apps/Focus5Native/` precedent of a standalone artifact living in-repo with no runtime coupling to the rest of rebalance-OS).

**Acceptance:**
- [x] Data-source decision recorded here with rationale
- [x] A minimal `TreeDataProvider` with hardcoded fixture data renders in the Extension Development Host sidebar — code complete, compiles clean; visual F5 confirmation is the operator's manual step (see QA gate)
- [x] Real pulse markdown section structure documented (what's parseable, what's not)

**QA gate:** Manual: `F5` in the Extension Development Host shows the fixture tree in the sidebar with no console errors. **Not yet run by a human** — `npm run compile` is clean (0 TypeScript errors) and the compiled output passes `node -c` syntax checks, which is as far as this can be automated without a GUI VS Code session. Operator should run `F5` per `extensions/pulse-tree-view/README.md` to close this out before Phase 1 starts.

**Spike findings:**
- **Data source correction — there are two structurally different "pulse" files, not one.** The plan originally assumed `pulse-<device>.md` was the per-device rendered file to parse. It is not: `pulse-noels-macbook-pro-14.md` (and its siblings) are raw, **append-only TSV git-commit logs** written by the separate `git-pulse` collector (`experimental/git-pulse/collect.sh`, LaunchAgent `com.user.git-pulse`) — columns `epoch_utc \t timestamp_utc \t repo \t branch \t short-sha \t subject`, with a header comment stating outright "Grep-friendly; not meant for pretty rendering." It has no Today/Yesterday/Upcoming-Meetings/Assigned-Issues sections at all.
- **`live-pulse.md`** (rendered by `rebalance.ingest.pulse.publish_pulse()` / `pulse-sync`) is the file with the actual section structure the acceptance criteria describe. Confirmed headings: `## Current Day`, `## Yesterday`, each containing `### What I've been working on`, `### Watched repos (external activity)`, `### Upcoming Meetings`, `### GitHub Issues assigned to me (last 7 days)`, `### Sleuth (Slack) reminders assigned to/by me`.
- List-item shapes vary by section — Phase 1's parser needs at least these three patterns:
  - Upcoming Meetings: `` - **5:00 PM–5:15 PM** — End of Day Check-In `` (bold time range, em-dash, free text)
  - Assigned Issues: `` - `Hypercart-Dev-Tools/pdda` [#15](https://github.com/Hypercart-Dev-Tools/pdda/issues/15) — title _(updated Jul 8 8:13 PM)_ `` (backtick repo, markdown link, em-dash, italic timestamp)
  - Commits/Issues under "What I've been working on": `` - `🤖cloud-claude` `repo` description ([sha](commit-url)) `` — an optional leading agent-tag backtick token before the repo token
- **v1 decision: `live-pulse.md` is the data source**, confirming the Phase 0 Discuss bullet's daemon-independence rationale still holds (it's a plain file, no server needed) — just the wrong filename in the original plan text, now corrected throughout this doc.
- `TreeDataProvider` fixture (`extensions/pulse-tree-view/src/pulseTreeDataProvider.ts`) was built directly from real excerpts of this device's own `live-pulse.md` (see the source file), not synthetic placeholder text — so it doubles as a concrete parsing target for Phase 1.

## Phase 1 — MVP Tree View

**Discuss:**
- `PulseTreeDataProvider implements vscode.TreeDataProvider<PulseTreeItem>` — one class, parses the configured pulse file into typed sections on each `getChildren()` call (no caching yet — that's Phase 2's job alongside the file watcher).
- Config: one setting, `pulseTreeView.pulseFilePath` (absolute path), no auto-discovery in v1 — explicit is simpler and matches the "no assumed defaults" posture from Phase 0.
- Manual refresh via a command (`pulseTreeView.refresh`) bound to a toolbar icon on the view — this is the fallback before Phase 2's automatic watcher lands.
- Empty/unconfigured state: a single tree item reading "Configure pulseTreeView.pulseFilePath to get started" rather than a silent blank pane or a thrown error.

**Acceptance:**
- [ ] Sidebar view registered under a dedicated Activity Bar icon (not nested under Explorer)
- [ ] Today / Yesterday / Upcoming Meetings / Assigned Issues render as top-level nodes, each expandable into the real parsed items
- [ ] Manual refresh command updates the tree from the current on-disk file content
- [ ] Unconfigured state renders the guidance item instead of erroring

**QA gate:** Manual smoke test against this device's real `~/git-pulse-sync/live-pulse.md`; `npm run compile` clean; no console errors in the Extension Development Host.

## Phase 2 — Live refresh

**Discuss:**
- `vscode.workspace.createFileSystemWatcher` on the configured pulse file path — on change, re-run `getChildren()` via `_onDidChangeTreeData.fire()`.
- Debounce: the hourly `pulse-sync` job's write is a single atomic file write, not a burst, so a short (e.g. 250ms) debounce is enough — no need for anything fancier.
- Status bar item showing last-refreshed time, so it's visible the tree is live without needing to expand it.

**Acceptance:**
- [ ] Editing/touching the pulse file on disk updates the tree within ~1s, no manual refresh needed
- [ ] Status bar shows last-refreshed timestamp, updates on each watcher-triggered refresh
- [ ] Watcher is disposed cleanly on extension deactivation (no leaked handles)

**QA gate:** Manual: run `pulse_sync.sh` (or touch the file) while the Extension Development Host is open; confirm the tree updates without a manual reload.

## Phase 3 — Polish and packaging

**Discuss:**
- Icons per section (commit, calendar, issue) using VS Code's built-in Codicons — no custom icon assets needed.
- Click-through: clicking a GitHub issue/PR item opens it in the default browser (`vscode.env.openExternal`); clicking a commit item could open the repo at that SHA (stretch, not required for v1).
- Packaging: `vsce package` → `.vsix`, installed locally via `code --install-extension pulse-tree-view-x.y.z.vsix`. No marketplace publish in v1 — this is a personal tool.

**Acceptance:**
- [ ] Section/item icons render (not the default generic icon)
- [ ] Clicking a GitHub issue/PR item opens it in the browser
- [ ] `vsce package` produces an installable `.vsix`; `code --install-extension` succeeds and the view persists across an editor restart

**QA gate:** Manual: install the packaged `.vsix` in a real (non-dev-host) VS Code window; confirm the view survives a full editor restart.

## Deferred

- Multi-device view (aggregating every `pulse-<device>.md` in the configured `git-pulse-sync` clone into one tree) — v2 candidate once v1 is in daily use.
- `pulse-server` as an alternate/fallback data source — only if direct file parsing proves too fragile against real-world pulse markdown drift.
- Marketplace publish — stays a locally-installed personal tool unless that changes.
