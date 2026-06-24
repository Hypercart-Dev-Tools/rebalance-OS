#!/bin/bash
#
# make-app.sh — package Text Replacement Studio into a permanent, double-clickable
# macOS .app bundle (release build, real icon, ad-hoc signed) and install it to
# /Applications.
#
# SwiftPM produces a bare executable plus per-target resource bundles; this wraps
# them in a proper bundle with an Info.plist so Finder/Dock treat it as a real app.
#
# Usage:
#   ./make-app.sh            # build release, assemble, install to /Applications
#   ./make-app.sh --no-install   # assemble into ./dist only
#
set -euo pipefail

PKG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PKG_DIR"

APP_NAME="Text Replacement Studio"
EXEC_NAME="TextReplacementStudio"
BUNDLE_ID="me.neochro.TextReplacementStudio"
VERSION="1.0"
DIST="$PKG_DIR/dist"
APP="$DIST/$APP_NAME.app"

# The user's global git config blocks SwiftPM's bare dep repos; scope a per-process
# override (never touches global config). See the project notes.
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.bareRepository GIT_CONFIG_VALUE_0=all

echo "▸ Building release…"
swift build -c release --product "$EXEC_NAME"

BIN_DIR="$(swift build -c release --product "$EXEC_NAME" --show-bin-path)"
BIN="$BIN_DIR/$EXEC_NAME"
[ -x "$BIN" ] || { echo "✗ release binary not found at $BIN"; exit 1; }

ICON_SRC="$PKG_DIR/Apps/TextReplacementStudio/Resources/AppIcon.icns"
[ -f "$ICON_SRC" ] || { echo "✗ AppIcon.icns missing at $ICON_SRC"; exit 1; }

echo "▸ Assembling $APP_NAME.app…"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

# Executable
cp "$BIN" "$APP/Contents/MacOS/$EXEC_NAME"

# SwiftPM resource bundles must sit next to the executable so Bundle.module resolves.
for b in "$BIN_DIR"/*.bundle; do
  [ -e "$b" ] && cp -R "$b" "$APP/Contents/MacOS/"
done

# Icon
cp "$ICON_SRC" "$APP/Contents/Resources/AppIcon.icns"

# Info.plist
cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>$APP_NAME</string>
  <key>CFBundleDisplayName</key><string>$APP_NAME</string>
  <key>CFBundleIdentifier</key><string>$BUNDLE_ID</string>
  <key>CFBundleExecutable</key><string>$EXEC_NAME</string>
  <key>CFBundleIconFile</key><string>AppIcon</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleInfoDictionaryVersion</key><string>6.0</string>
  <key>CFBundleShortVersionString</key><string>$VERSION</string>
  <key>CFBundleVersion</key><string>$VERSION</string>
  <key>LSMinimumSystemVersion</key><string>14.0</string>
  <key>NSHighResolutionCapable</key><true/>
  <key>NSPrincipalClass</key><string>NSApplication</string>
  <key>LSApplicationCategoryType</key><string>public.app-category.productivity</string>
</dict>
</plist>
PLIST

printf 'APPL????' > "$APP/Contents/PkgInfo"

# SwiftPM resource bundles ship without an Info.plist, which makes codesign reject
# them ("bundle format unrecognized"). Give each a minimal one so --deep can seal
# them. Apple Silicon refuses to launch an unsigned executable, so this matters.
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
# Refresh LaunchServices so Finder/Dock pick up the new icon + identity.
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$DEST" 2>/dev/null || true

echo "✓ Installed: $DEST"
echo "  Launch with:  open \"$DEST\""
