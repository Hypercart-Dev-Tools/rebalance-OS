# Git Pulse Tree View

A native VS Code sidebar **Tree View** — not a webview, not a browser tab —
showing this device's git-pulse / rebalance-OS activity: **Today**,
**Yesterday**, **Upcoming Meetings**, and **Assigned Issues**.

Tracks [GH-123](https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/123),
Phase 0 (data source spike) + Phase 1 (MVP tree view).

## What this is NOT

- Not a replacement for `pulse-server` (`127.0.0.1:8767`) or the regenerated
  `web/pulse.html` — both keep working exactly as they do today.
- Not a general rebalance-OS dashboard — no config UI beyond the one setting
  below, no multi-device aggregation.
- Not a data collector — it purely reads a file that `pulse-sync` /
  `git-pulse` already write. If that job isn't running, the tree shows
  stale or empty content; it never tries to fetch anything itself.
- No live file-watching yet (Phase 2), no click-through to open items in
  a browser yet (Phase 3), no `.vsix` packaging yet (Phase 3). Use the
  manual **Refresh** command in the meantime.

## Data source

This extension reads **one local file directly from disk** — no network
access, no dependency on the rebalance-OS Python venv, no dependency on the
`pulse-server` daemon being up.

Set the absolute (or `~`-relative) path via the
`pulseTreeView.pulseFilePath` setting, e.g.:

```json
{
  "pulseTreeView.pulseFilePath": "~/git-pulse-sync/live-pulse.md"
}
```

**Important — there are two differently-shaped "pulse" files; this
extension wants the rendered one, not the raw one:**

| File | What it is | Use it? |
|---|---|---|
| `live-pulse.md` (or similar rendered doc from your `git-pulse-sync` clone) | Rendered by `rebalance.ingest.pulse.render_pulse_markdown()` / the `pulse-sync` job. Has the `# Live Pulse — ...` header and `## Current Day` / `## Yesterday` sections this extension parses. | **Yes — this is what `pulseTreeView.pulseFilePath` should point at.** |
| `pulse-<device-id>.md` | Written by the separate hourly `git-pulse` collector (`experimental/git-pulse/collect.sh`). Append-only, tab-separated `epoch_utc / timestamp_utc / repo / branch / short-sha / subject` rows. Its own header says outright: "Grep-friendly; not meant for pretty rendering." | No — this file has no Today/Yesterday/Upcoming-Meetings/Assigned-Issues sections at all; the parser will show all 4 sections empty. |

There is no single universal default path — `git-pulse-sync` clone
locations vary per machine (`~/.config/git-pulse/repo`,
`~/git-pulse-sync`, `~/code/rebalance-git-pulse`, etc., see
`experimental/git-pulse/README.md` in the main rebalance-OS repo). The
setting defaults to empty; until it's set, the tree shows a single
"No pulse file configured" item instead of throwing or showing a blank
pane.

If the configured path doesn't exist or can't be read, the tree shows a
single "Pulse file not found" item (with the resolved path as a hint)
instead of crashing.

## Sections

- **Today** — from the `### What I've been working on` block under
  `## Current Day` (commits/issues created or updated, Obsidian vault
  edits, etc., as bullet or bold-group-label rows).
- **Yesterday** — from `### What I worked on yesterday` under
  `## Yesterday`.
- **Upcoming Meetings** — from `### Upcoming Meetings` under
  `## Current Day`.
- **Assigned Issues** — from `### GitHub Issues assigned to me (last 7
  days)` under `## Current Day`.

Two other real sections in the source file (`### Watched repos (external
activity)` and `### Sleuth (Slack) reminders assigned to/by me`) are
intentionally not surfaced as their own tree nodes in this Phase 1 pass.

## Refreshing

This extension does **not** watch the file for changes yet (that's
Phase 2). Two ways to re-read it:

- Command palette → **"Pulse: Refresh"**
- The refresh icon in the "Pulse" view's title bar (Explorer sidebar)

## Try it (Extension Development Host)

1. `cd vscode-extension/pulse-tree-view`
2. `npm install`
3. `npm run compile`
4. Open this folder (`vscode-extension/pulse-tree-view`) as its own VS
   Code workspace (not the whole `rebalance-OS` repo) — extension dev
   host activation is workspace-scoped to the folder containing
   `package.json`.
5. Press `F5` (or Run → Start Debugging). This launches a new
   "Extension Development Host" VS Code window with the extension loaded.
6. In that new window, open Settings (`Cmd+,`) and set
   `pulseTreeView.pulseFilePath` to a real pulse markdown file, e.g.
   `~/git-pulse-sync/live-pulse.md`.
7. Open the Explorer sidebar — a **"Pulse"** view appears with the 4
   sections. Use the refresh icon (or "Pulse: Refresh" from the command
   palette) after editing the setting or the underlying file.

## Tests

The parser (`src/pulseParser.ts`) has no dependency on the `vscode`
module, so it's tested directly with `mocha` + Node's built-in `assert`
— no Extension Development Host or `@vscode/test-electron` needed:

```bash
npm test
```

## Non-goals (this lane)

Explicitly out of scope for Phase 0+1 (see the GH-123 issue's phased
plan): live file-watcher refresh, click-through navigation to open
source items in a browser, `.vsix` packaging. All planned for Phase 2/3.
