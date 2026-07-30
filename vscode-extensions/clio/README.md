# Sidebar Markdown

Shows one markdown file — from anywhere on disk, unrelated to the open folder — in its own activity bar view, in every VS Code window.

Built for viewing a [CLIO](https://github.com/Claude-AI-Tools-Ventura-County/clio) prompt log, but works with any markdown file.

## Features

- **Own activity bar icon** — a markdown icon appears in the vertical icon bar; the view lives in the sidebar and moves automatically when the sidebar is switched to the other side (`workbench.sideBar.location`). It can also be dragged into the secondary sidebar or panel.
- **One file, every window** — the file path is an application-scoped user setting, so all open windows show the same file. It also syncs across machines via Settings Sync.
- **Live refresh** — the view updates automatically when the file changes on disk (atomic saves included). A refresh button is available in the view title bar.
- **Rendered ↔ Source toggle** — view-title buttons switch between rendered markdown and the raw text (shown in the editor font), mirroring the built-in markdown preview toggle. An **Open in Editor** button opens the file in a normal editor tab.
- **Two visual styles** — match the current VS Code color theme (default), or a cream "clio" style approximating the CLIO macOS app.
- **Tolerant of non-standard files** — HTML comments (e.g. CLIO's `<!-- clio:... -->` markers) render invisibly, and Unicode LS/PS line terminators are normalized in memory. The file on disk is never modified.

## Install

1. Open VS Code and press `Cmd+Shift+P` to open the command palette.
2. Run **Extensions: Install from VSIX…** and pick `sidebar-markdown-<version>.vsix`.
3. Click the markdown icon in the activity bar (left icon strip).
4. Click **Choose Markdown File…** in the view and select the file to display.

To switch to a different file later, use any of:

- the `⋯` menu in the view's title bar → **Choose Markdown File…**
- the command palette → **Sidebar Markdown: Choose Markdown File…**
- Settings → `sidebarMarkdown.file` (paste a path directly)

## Settings

| Setting | Default | Description |
|---|---|---|
| `sidebarMarkdown.file` | `""` | Absolute path to the markdown file to display. User-setting only (applies to every window). |
| `sidebarMarkdown.style` | `"theme"` | `"theme"` matches the active VS Code theme; `"clio"` uses the cream CLIO-like style. |

## Development

1. `npm install`
2. `npm run build` — type-check and bundle to `dist/` with sourcemaps
3. Press `F5` in VS Code to launch an Extension Development Host with the extension loaded.
4. `npm run lint` — ESLint with type-aware rules
5. `npm test` — unit tests for the pure render helpers (`node:test`)

For producing the installable `.vsix`, see [Production build and install](#production-build-and-install).

### Toolchain versions

Three of these are pinned deliberately and will look out of date to `npm outdated`:

| Package | Pinned to | Why not latest |
|---|---|---|
| `@types/vscode` | exactly `engines.vscode` | A caret range lets it float above the declared minimum, which allows compiling against APIs that do not exist in the oldest supported VS Code. |
| `@types/node` | `^24` | Describes the Node the extension host actually runs (24.18 in VS Code 1.130 / Electron 42), not the newest Node released. Newer types would permit APIs missing at runtime. |
| `typescript` | `^5.6` | TypeScript 7 is the native-port rewrite. 5.x is the conservative choice for an extension; revisit once 7 has settled. |

Tools with no runtime presence — `esbuild`, `eslint`, `@vscode/vsce` — track latest.

## Production build and install

1. When distributing a new build, bump `"version"` in `package.json` first — a changed version defeats any caching of a same-version install and keeps builds distinguishable.
2. `npm install` — only needed if dependencies have not been installed yet.
3. `npm run package -- --allow-missing-repository` — type-checks, produces the production bundle (minified, no sourcemaps) and packages it as `sidebar-markdown-<version>.vsix` in the project root. The flag suppresses vsce's interactive prompt about the missing `repository` field; CI passes the same flag.
4. In VS Code, open the command palette (`Cmd+Shift+P`), run **Extensions: Install from VSIX…** and select the `.vsix`. Installing over an already-installed version replaces it.
5. Run **Developer: Reload Window** so the newly installed code takes over — VS Code can keep the previous extension host running until a reload.

Changes to `media/` (CSS, webview JS) and `package.json` contributions ship in the `.vsix` as-is, but still require steps 3–5 to reach an installed copy. During development, prefer `F5` (Extension Development Host) — it always runs the freshly built code with no packaging or install step.

## Roadmap ideas

- Parse CLIO's `<!-- clio:id:... -->` markers into a real card UI with repo filtering and pinning, like the CLIO macOS app.
- Virtualized rendering for very large logs (the current file renders in full; ~650 entries is fine, tens of thousands may warrant chunking).
