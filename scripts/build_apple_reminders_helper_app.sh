#!/usr/bin/env bash
#
# Build (and codesign) the Apple Reminders write helper app bundle.
#
# This is the single out-of-process writer the Python orchestrator
# (src/rebalance/ingest/apple_reminders_write.py) invokes via LaunchServices
# (`open -a <bundle> --args --request <path>`). It needs ONLY a Reminders TCC
# grant (read-back is via EventKit, not SQLite, so no Full Disk Access).
#
# One-time operator setup after the first build:
#   1. Run the helper once (the orchestrator will, or `open` it) and approve the
#      Reminders 'Allow' prompt. The grant is durable on the stable bundle id.
#
# Usage:
#   scripts/build_apple_reminders_helper_app.sh
#
# Note: swiftc fails under Claude Code's Bash sandbox (module-cache writes to
# /var/folders are blocked) — build with the sandbox disabled.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [[ ! -f "${REPO_ROOT}/pyproject.toml" || ! -d "${REPO_ROOT}/src/rebalance" ]]; then
  echo "error: ${REPO_ROOT} is not a rebalance repo root" >&2
  exit 1
fi

SRC="${SCRIPT_DIR}/apple_reminders_helper_app.swift"
PLIST_SRC="${SCRIPT_DIR}/apple_reminders_helper_app_Info.plist"
APP_NAME="AppleRemindersHelper"
BUNDLE_ID="com.rebalanceos.apple-reminders-helper"
BUILD_DIR="${REPO_ROOT}/temp/apple-reminders/build"
APP="${BUILD_DIR}/${APP_NAME}.app"

for f in "${SRC}" "${PLIST_SRC}"; do
  [[ -f "${f}" ]] || { echo "error: missing source file ${f}" >&2; exit 1; }
done

SWIFTC="swiftc"
command -v xcrun >/dev/null 2>&1 && SWIFTC="xcrun swiftc"
command -v "${SWIFTC%% *}" >/dev/null 2>&1 || {
  echo "error: swiftc not found (install Xcode command line tools)" >&2; exit 1; }

echo "==> building: ${APP}"
rm -rf "${APP}"
mkdir -p "${APP}/Contents/MacOS"

# @main requires -parse-as-library (no top-level script code).
${SWIFTC} -O -target arm64-apple-macos14.0 -parse-as-library \
  -o "${APP}/Contents/MacOS/${APP_NAME}" \
  "${SRC}"

cp "${PLIST_SRC}" "${APP}/Contents/Info.plist"

# Ad-hoc codesign; stable bundle id keeps the Reminders TCC grant durable across
# rebuilds. The Python orchestrator verifies this signature + id before trusting
# a response (confused-deputy guard).
codesign --force --sign - --identifier "${BUNDLE_ID}" "${APP}"
codesign --verify --deep --strict "${APP}" >/dev/null 2>&1 \
  || echo "warning: codesign --verify reported issues (ad-hoc signature)" >&2

echo "==> built and signed: ${APP}"
echo "    bundle id: ${BUNDLE_ID}"
echo
echo "One-time: approve the Reminders 'Allow' prompt on first run (no Full Disk"
echo "Access needed). The Python orchestrator launches it via LaunchServices."
