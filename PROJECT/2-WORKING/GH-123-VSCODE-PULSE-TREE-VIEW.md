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
| Issue opened, project plan written, branch cut. | Phase 0: spike — confirm data source, validate `TreeDataProvider` against a real pulse file |

Actionable substance from [issue #123](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/123).

## What this is NOT

- Not a replacement for `pulse-server` (127.0.0.1:8767) or the regenerated `web/pulse.html` — both keep working exactly as they do today; this is a third, editor-native view of the same underlying data.
- Not a rebalance-OS "control panel" — no settings UI beyond pointing the extension at a `git-pulse-sync` clone; no write actions back into rebalance-OS.
- Not multi-device in v1 — shows the pulse file for *this* device only (`pulse-<device>.md` / `live-pulse.md`, whichever is configured), matching how the existing pulse docs are already scoped per-device.
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
- Decide the data source: read `pulse-<device>.md` / `live-pulse.md` directly from a configured `git-pulse-sync` path (favored — no daemon dependency, matches `canonical_boundary`) vs. hitting `pulse-server`'s HTTP API (rejected as the v1 default — adds a runtime dependency the extension shouldn't need; revisit only if direct-file parsing proves too fragile).
- Confirm the pulse markdown's actual section structure (headings, list-item shape) is stable enough to parse reliably — spike against the real file at `~/git-pulse-sync/pulse-<this-device>.md`.
- Validate VS Code's `TreeDataProvider` + `registerTreeDataProvider` API against a hand-built fixture tree before wiring real parsing.
- Scaffold: `yo code` (Yeoman VS Code extension generator) vs. hand-rolled `package.json` + `extension.ts` — favor hand-rolled given this is a single-view extension, not the general-purpose scaffold `yo code` optimizes for.
- Directory: extension source lives at `extensions/pulse-tree-view/` in this repo (new top-level `extensions/` dir, following the `macOS/Apps/Focus5Native/` precedent of a standalone artifact living in-repo with no runtime coupling to the rest of rebalance-OS).

**Acceptance:**
- [ ] Data-source decision recorded here with rationale
- [ ] A minimal `TreeDataProvider` with hardcoded fixture data renders in the Extension Development Host sidebar
- [ ] Real pulse markdown section structure documented (what's parseable, what's not)

**QA gate:** Manual: `F5` in the Extension Development Host shows the fixture tree in the sidebar with no console errors.

**Spike findings:**
_(fill in during Phase 0 execution)_

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

**QA gate:** Manual smoke test against this device's real `~/git-pulse-sync/pulse-<device>.md`; `npm run compile` clean; no console errors in the Extension Development Host.

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
