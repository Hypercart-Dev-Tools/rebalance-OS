#!/bin/bash
#
# make-app.sh — package Focus 5 Float into a permanent, double-clickable macOS
# .app bundle (release build, ad-hoc signed) and install it to /Applications.
#
# Focus 5 Float is a menu-bar agent (LSUIElement) — it shows an "F5" status-bar
# item and a floating panel, no Dock icon. It reads the live GET /focus-5.json
# from a running `rebalance serve`.
#
# Usage:
#   ./make-app.sh              # build release, assemble, install to /Applications
#   ./make-app.sh --no-install # assemble into ./dist only
#
set -euo pipefail

PKG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PKG_DIR"

APP_NAME="Focus 5 Float"
EXEC_NAME="Focus5Float"
BUNDLE_ID="me.neochro.Focus5Float"
VERSION="0.50.3"
DIST="$PKG_DIR/dist"
APP="$DIST/$APP_NAME.app"

# Per-process git override in case SwiftPM resolves bare dep repos (harmless here —
# Focus5Float has no external deps). Never touches global config.
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.bareRepository GIT_CONFIG_VALUE_0=all

echo "▸ Building release…"
swift build -c release --product "$EXEC_NAME"

BIN_DIR="$(swift build -c release --product "$EXEC_NAME" --show-bin-path)"
BIN="$BIN_DIR/$EXEC_NAME"
[ -x "$BIN" ] || { echo "✗ release binary not found at $BIN"; exit 1; }

echo "▸ Assembling $APP_NAME.app…"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

# Executable
cp "$BIN" "$APP/Contents/MacOS/$EXEC_NAME"

# SwiftPM resource bundles must sit next to the executable so Bundle.module resolves
# (the bundled sample-focus5.json fixture used by previews / FOCUS5_SELFTEST).
for b in "$BIN_DIR"/*.bundle; do
  [ -e "$b" ] && cp -R "$b" "$APP/Contents/MacOS/"
done

# Icon (optional — none shipped yet; a menu-bar agent has no Dock icon anyway).
ICON_KEY=""
ICON_SRC="$PKG_DIR/Resources/AppIcon.icns"
if [ -f "$ICON_SRC" ]; then
  cp "$ICON_SRC" "$APP/Contents/Resources/AppIcon.icns"
  ICON_KEY="  <key>CFBundleIconFile</key><string>AppIcon</string>"
fi

# Info.plist — LSUIElement=true makes it a menu-bar agent (no Dock icon).
cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>$APP_NAME</string>
  <key>CFBundleDisplayName</key><string>$APP_NAME</string>
  <key>CFBundleIdentifier</key><string>$BUNDLE_ID</string>
  <key>CFBundleExecutable</key><string>$EXEC_NAME</string>
$ICON_KEY
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleInfoDictionaryVersion</key><string>6.0</string>
  <key>CFBundleShortVersionString</key><string>$VERSION</string>
  <key>CFBundleVersion</key><string>$VERSION</string>
  <key>LSMinimumSystemVersion</key><string>14.0</string>
  <key>LSUIElement</key><true/>
  <key>NSHighResolutionCapable</key><true/>
  <!-- Apple Reminders bottom panel reads/writes via EventKit. Full-access key is
       the macOS 14+ requirement; the legacy key is kept for older fallbacks.
       (Reminders grant only — no Full Disk Access; read-back is via EventKit.) -->
  <key>NSRemindersFullAccessUsageDescription</key><string>Focus 5 Float shows your most recent Reminders and lets you check them off.</string>
  <key>NSRemindersUsageDescription</key><string>Focus 5 Float shows your most recent Reminders and lets you check them off.</string>
  <key>NSPrincipalClass</key><string>NSApplication</string>
  <key>LSApplicationCategoryType</key><string>public.app-category.developer-tools</string>
</dict>
</plist>
PLIST

printf 'APPL????' > "$APP/Contents/PkgInfo"

# SwiftPM resource bundles ship without an Info.plist, which makes codesign reject
# them. Give each a minimal one so --deep can seal them (Apple Silicon refuses to
# launch an unsigned executable).
for b in "$APP/Contents/MacOS/"*.bundle; do
  [ -e "$b" ] || continue
  if [ ! -f "$b/Info.plist" ] && [ ! -f "$b/Contents/Info.plist" ]; then
    bn="$(basename "$b" .bundle)"
    cat > "$b/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleIdentifier</key><string>$BUNDLE_ID.resources.$bn</string>
  <key>CFBundleInfoDictionaryVersion</key><string>6.0</string>
  <key>CFBundleName</key><string>$bn</string>
  <key>CFBundlePackageType</key><string>BNDL</string>
</dict>
</plist>
EOF
  fi
done

echo "▸ Ad-hoc signing…"
codesign --force --deep --sign - "$APP"
codesign -v "$APP" && echo "  signature OK"

if [ "${1:-}" = "--no-install" ]; then
  echo "✓ Built: $APP"
  exit 0
fi

echo "▸ Installing to /Applications…"
DEST="/Applications/$APP_NAME.app"
rm -rf "$DEST"
cp -R "$APP" "$DEST"
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$DEST" 2>/dev/null || true

echo "✓ Installed: $DEST"
echo "  Launch with:  open \"$DEST\"   (needs \`rebalance serve\` running for data)"
