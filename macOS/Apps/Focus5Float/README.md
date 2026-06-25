# Focus 5 Float

An always-on-top macOS menu-bar app that renders the rebalance-OS **Focus 5**
roster as a vertical, collapsible card stack. It's a thin, read-only projection:
all ranking and git re-probing happen server-side — the app just fetches and
renders JSON.

- Menu-bar agent (no Dock icon), non-activating floating panel.
- Collapsible repo cards: tree health, newest PR, recent activity.
- In-panel ranking toggle (🎯 Focus 5 / 🧹 Dirty Five), refresh, ⚠ stale badge.
- Top-right roster-health light: green = all clean · orange = some dirty · red = all dirty.
- Offline cache + one-click "Start rebalance serve".

## Prerequisite

**`rebalance serve` must be running** (default `http://localhost:8787`). The app
polls `GET /focus-5.json` from it. With the server down, the app shows the last
cached roster and an offline badge; it can start the server for you.

## Install

```bash
./make-app.sh                # release build, ad-hoc sign, install to /Applications
./make-app.sh --no-install   # assemble into ./dist only
```

> If `swift build` fails with `safe.bareRepository is 'explicit'`, use
> `./make-app.sh` (it handles it) or prefix with
> `GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.bareRepository GIT_CONFIG_VALUE_0=all`.

## Develop

```bash
swift build
swift run Focus5Float        # bare dev build (launch-at-login needs the installed .app)
```

Headless self-checks (no GUI):

```bash
FOCUS5_SELFTEST=1   swift run Focus5Float   # decode the bundled fixture
FOCUS5_LIVETEST=1   swift run Focus5Float   # decode the live server payload
FOCUS5_HEALTHTEST=1 swift run Focus5Float   # roster-health light color rollup
FOCUS5_CACHETEST=1  swift run Focus5Float   # offline cache round-trip
```

## Launch at login

Right-click the **F5** menu-bar item → **Launch at Login** (toggles via
`SMAppService`; checkmark reflects the current state). Only works from the
installed `/Applications` copy, not `swift run`.

## App icon

A menu-bar agent has no Dock icon, so an icon is optional (it only shows in
Finder / Spotlight). To add one: export a 1024×1024 PNG, convert to
`Resources/AppIcon.icns`, and re-run `./make-app.sh` — it auto-wires
`CFBundleIconFile` when that file exists.

```bash
# PNG → .icns (one-liner via sips/iconutil)
mkdir -p AppIcon.iconset && sips -z 1024 1024 icon.png --out AppIcon.iconset/icon_512x512@2x.png
iconutil -c icns AppIcon.iconset -o Resources/AppIcon.icns
```

## Contract

The wire format and field sensitivity (local-only / PII) are frozen in
[CONTRACT.md](CONTRACT.md). The endpoint is **GET-only, localhost-bound**, and
intentionally **not** reusable by any remote mirror without a sanitized projection.

## Settings

Configurable via environment, not a settings window (YAGNI for a personal tool):

- `FOCUS5_BASE_URL` — server base URL (default `http://localhost:8787`, gated to
  loopback unless a debug build).
