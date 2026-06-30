#!/usr/bin/env bash
#
# Build (and optionally launch) the Apple Reminders write-spike app bundle.
#
# Why this exists (Phase 5.0 finding): EventKit write access is suppressed by macOS TCC
# when the helper runs under the VS Code / agent-owned responsible process tree. The only
# runtime that reaches the Reminders permission prompt and earns a durable grant is a
# signed app bundle launched via LaunchServices (`open`). Under that launch the app has
# cwd=/ and no inherited env, so it cannot find the repo by cwd or RBOS_REPO_ROOT. This
# harness bakes the absolute repo root into the bundle's Info.plist (key: RBOSRepoRoot),
# which appRepoRoot() reads. That makes the bundle self-locating regardless of launch mode.
#
# Usage:
#   scripts/build_apple_reminders_write_spike_app.sh            # build only
#   scripts/build_apple_reminders_write_spike_app.sh --launch   # build, then `open` it
#
# After --launch: approve the macOS "Allow" prompt. The app runs the
# create -> extractor-visibility -> update -> converge -> delete -> absence loop and writes
# temp/apple-reminders/PHASE5-WRITE-SPIKE-APP.json. Progress streams to
# temp/apple-reminders/PHASE5-WRITE-SPIKE-APP.status.txt (and /tmp/...status.txt).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Sanity: confirm we resolved an actual rebalance repo root before baking the path in.
if [[ ! -f "${REPO_ROOT}/pyproject.toml" || ! -d "${REPO_ROOT}/src/rebalance" ]]; then
  echo "error: ${REPO_ROOT} does not look like a rebalance repo root (missing pyproject.toml or src/rebalance)" >&2
  exit 1
fi

SRC="${SCRIPT_DIR}/apple_reminders_write_spike_app.swift"
PLIST_SRC="${SCRIPT_DIR}/apple_reminders_write_spike_app_Info.plist"
APP_NAME="AppleRemindersWriteSpikeApp"
BUNDLE_ID="com.rebalanceos.apple-reminders-write-spike-app"
BUILD_DIR="${REPO_ROOT}/temp/apple-reminders/build"
APP="${BUILD_DIR}/${APP_NAME}.app"

for f in "${SRC}" "${PLIST_SRC}"; do
  [[ -f "${f}" ]] || { echo "error: missing source file ${f}" >&2; exit 1; }
done

SWIFTC="swiftc"
if command -v xcrun >/dev/null 2>&1; then
  SWIFTC="xcrun swiftc"
fi
command -v "${SWIFTC%% *}" >/dev/null 2>&1 || { echo "error: swiftc not found (install Xcode command line tools)" >&2; exit 1; }

echo "==> repo root:   ${REPO_ROOT}"
echo "==> building:    ${APP}"

rm -rf "${APP}"
mkdir -p "${APP}/Contents/MacOS"

# 1. Compile the Swift source. System frameworks (AppKit/EventKit/Foundation) auto-link.
#    -parse-as-library is required because the file uses @main (no top-level script code).
${SWIFTC} -O -target arm64-apple-macos14.0 -parse-as-library \
  -o "${APP}/Contents/MacOS/${APP_NAME}" \
  "${SRC}"

# 2. Install Info.plist and bake the absolute repo root into it.
cp "${PLIST_SRC}" "${APP}/Contents/Info.plist"
PLIST="${APP}/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Add :RBOSRepoRoot string ${REPO_ROOT}" "${PLIST}" 2>/dev/null \
  || /usr/libexec/PlistBuddy -c "Set :RBOSRepoRoot ${REPO_ROOT}" "${PLIST}"

# 3. Ad-hoc codesign. Stable bundle id keeps the TCC grant durable across rebuilds.
codesign --force --sign - --identifier "${BUNDLE_ID}" "${APP}"
codesign --verify --verbose=2 "${APP}" >/dev/null 2>&1 || {
  echo "warning: codesign --verify reported issues (ad-hoc signature)" >&2
}

echo "==> built and signed: ${APP}"
echo "    Info.plist RBOSRepoRoot = $(/usr/libexec/PlistBuddy -c 'Print :RBOSRepoRoot' "${PLIST}")"

cat <<EOF

TWO macOS grants are required for the convergence loop to pass:
  1. Reminders (EventKit write)  -> approve the 'Allow' prompt the app shows on launch.
  2. Full Disk Access            -> add this app bundle in
       System Settings -> Privacy & Security -> Full Disk Access:
       ${APP}
     This is needed because the read-side check re-reads the Reminders SQLite store
     directly; without it the *_extractor_visibility probes fail even after #1.
EOF

if [[ "${1:-}" == "--launch" ]]; then
  echo
  echo "==> launching via LaunchServices (open). Approve the 'Allow' prompt."
  echo "    Watch progress: tail -f ${REPO_ROOT}/temp/apple-reminders/PHASE5-WRITE-SPIKE-APP.status.txt"
  open "${APP}"
else
  echo
  echo "Next: scripts/build_apple_reminders_write_spike_app.sh --launch   (or:  open '${APP}')"
fi
