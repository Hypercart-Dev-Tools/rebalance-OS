# Git Pulse Tree View

Native VS Code sidebar Tree View for this device's git-pulse/rebalance-OS
activity. See [PROJECT/2-WORKING/GH-123-VSCODE-PULSE-TREE-VIEW.md](../../PROJECT/2-WORKING/GH-123-VSCODE-PULSE-TREE-VIEW.md)
for the full plan.

**Status: Phase 0 (spike).** The tree currently renders hardcoded fixture
data shaped to match `live-pulse.md`'s real section structure — no file
parsing yet. That's Phase 1.

## Run it

```bash
cd extensions/pulse-tree-view
npm install
npm run compile
```

Then open this folder (`extensions/pulse-tree-view`) as its own VS Code
workspace and press `F5` — an Extension Development Host window opens with
a "Git Pulse" icon in the Activity Bar showing the fixture tree.

## Config (not yet wired — Phase 1)

- `pulseTreeView.pulseFilePath` — absolute path to the pulse markdown file
  to display, e.g. `~/git-pulse-sync/live-pulse.md`.
