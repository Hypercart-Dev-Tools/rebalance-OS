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

The app first tries **`rebalance serve`** (`http://localhost:8787`) and, if that
is unavailable, falls back to the always-on **pulse server**
(`http://127.0.0.1:8767`) for the mirrored Focus 5 routes. With both servers
down, the app shows the last cached roster and an offline badge; it can start
`rebalance serve` for you.

### Making `rebalance` findable (required for "Start server")

macOS GUI apps — launched from Finder or as a login item — do not inherit your
shell `PATH`. The app resolves the binary in this order:

1. `REBALANCE_BIN` env var (explicit per-process override)
2. Known paths probed directly (no shell): `~/bin/rebalance`,
   `/opt/homebrew/bin/rebalance`, `/usr/local/bin/rebalance`,
   `~/.local/bin/rebalance`
3. Interactive login-shell lookup: `$SHELL -ilc 'command -v rebalance'`

If the app shows **"Couldn't find the `rebalance` binary"**, the binary exists
only inside the project `.venv` — invisible to all three paths above. The
durable fix is to install `rebalance` as a system-accessible CLI tool via
`pipx`, which places it at `~/.local/bin/rebalance` (path 2 above):

```bash
brew install pipx                         # once per machine; skip if already installed
pipx install -e /path/to/rebalance-OS     # run from anywhere; path is absolute
```

Run this once per device after cloning. `pipx` manages its own isolated
environment separate from the project `.venv`, so it survives venv recreations
and continues to reflect live source edits (editable install).

> A symlink at `~/bin/rebalance` pointing into `.venv` also satisfies path 2
> but is fragile — it breaks when the venv is recreated. `pipx` is preferred.

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

An icon is included at `Resources/AppIcon.icns` (wired automatically by
`make-app.sh`). A menu-bar agent has no Dock icon, so it only appears in
Finder / Spotlight.

To replace the icon: export a new 1024×1024 PNG with the visible artwork inside
a centered 824×824 region (100 px of transparent margin on every edge). The
margin is part of the macOS optical-size contract; full-bleed artwork appears
larger than neighboring Dock and app-switcher icons. Convert the padded PNG to
`Resources/AppIcon.icns`, and re-run `./make-app.sh`:

```bash
# PNG → .icns via sips/iconutil (all required sizes)
ICONSET=AppIcon.iconset
mkdir -p "$ICONSET"
for size in 16 32 128 256 512; do
  sips -z $size $size icon.png --out "$ICONSET/icon_${size}x${size}.png"
done
sips -z 32   32   icon.png --out "$ICONSET/icon_16x16@2x.png"
sips -z 64   64   icon.png --out "$ICONSET/icon_32x32@2x.png"
sips -z 256  256  icon.png --out "$ICONSET/icon_128x128@2x.png"
sips -z 512  512  icon.png --out "$ICONSET/icon_256x256@2x.png"
sips -z 1024 1024 icon.png --out "$ICONSET/icon_512x512@2x.png"
iconutil -c icns "$ICONSET" -o Resources/AppIcon.icns
./make-app.sh
```

## Contract

The wire format and field sensitivity (local-only / PII) are frozen in
[CONTRACT.md](CONTRACT.md). The endpoint is **GET-only, localhost-bound**, and
intentionally **not** reusable by any remote mirror without a sanitized projection.

## Settings

Configurable via environment, not a settings window (YAGNI for a personal tool):

- `FOCUS5_BASE_URL` — server base URL override. When unset, the app probes
  `http://localhost:8787` first, then `http://127.0.0.1:8767`. The override is
  loopback-gated unless a debug build.
