#!/usr/bin/env bash
# Phase 0-R reproducer: clean build -> wrap headless harness in a minimal .app ->
# ad-hoc codesign WITH the App Sandbox entitlement -> run against a container repo.
#
# NOTE: run OUTSIDE any nesting command-sandbox (SwiftPM itself uses sandbox-exec;
# a nested sandbox fails with "sandbox_apply: Operation not permitted").
set -euo pipefail
cd "$(dirname "$0")"

BUNDLE_ID="com.rebalance-os.focus5.probe"
APP=".build/Focus5Probe.app"
CONT="$HOME/Library/Containers/$BUNDLE_ID/Data"

echo "== 1. clean build =="
swift build --product Focus5Probe

echo "== 2. wrap in minimal .app (sandbox needs a bundle, not a bare Mach-O) =="
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS"
cp .build/debug/Focus5Probe "$APP/Contents/MacOS/Focus5Probe"
cp Info.probe.plist "$APP/Contents/Info.plist"

echo "== 3. ad-hoc codesign WITH App Sandbox entitlement =="
codesign --force --deep --sign - --entitlements Focus5.entitlements --timestamp=none "$APP"
codesign -d --entitlements - "$APP/Contents/MacOS/Focus5Probe" 2>&1 | grep -iE 'app-sandbox|user-selected' || true

echo "== 4. seed a fixture repo inside the app container (a sandbox-permitted path) =="
# First launch creates the container; ensure it exists.
"$APP/Contents/MacOS/Focus5Probe" "$PWD" >/dev/null 2>&1 || true
mkdir -p "$CONT"
FIX="$CONT/fixture-repo"
rm -rf "$FIX"; mkdir -p "$FIX"
( cd "$FIX"
  git init -q .
  git config user.email t@t.co; git config user.name t
  echo hello > a.txt; git add a.txt; git commit -qm first
  echo world > b.txt              # untracked
  echo more >> a.txt; git add a.txt; git commit -qm second
  echo dirtynow >> a.txt          # unstaged modify
)

echo "== 5. SANDBOXED run (A embedded libgit2 / B Process->git / C bookmark) =="
"$APP/Contents/MacOS/Focus5Probe" "$FIX"
