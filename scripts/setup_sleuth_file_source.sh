#!/bin/bash
# One-command onboarding for the Sleuth reminders FILE source on this device.
#
# Production Sleuth reminders are read from a file the Sleuth box publishes to the
# private git-pulse repo — no SSH tunnel, no open port, no API token. This script:
#   1. Clones (or reuses) the private export repo.
#   2. Points rebalance-OS at the local export file via `rebalance config set-sleuth`.
#   3. Verifies with `rebalance sleuth-sync` + `rebalance doctor`.
# Idempotent — safe to re-run. See SLEUTH_SYNC.md.
#
# Usage:
#   bash scripts/setup_sleuth_file_source.sh
#   bash scripts/setup_sleuth_file_source.sh --workspace neochrome --clone-dir ~/git-pulse-sync
#
# Flags (all optional; defaults shown):
#   --workspace neochrome
#   --clone-dir ~/git-pulse-sync
#   --repo-url  https://github.com/Hypercart-Dev-Tools/rebalance-git-pulse.git

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REBALANCE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REBALANCE="$REBALANCE_DIR/.venv/bin/rebalance"
[ -x "$REBALANCE" ] || REBALANCE="rebalance"

WORKSPACE="neochrome"
CLONE_DIR="$HOME/git-pulse-sync"
REPO_URL="https://github.com/Hypercart-Dev-Tools/rebalance-git-pulse.git"

while [ $# -gt 0 ]; do
    case "$1" in
        --workspace) WORKSPACE="$2"; shift 2 ;;
        --clone-dir) CLONE_DIR="$2"; shift 2 ;;
        --repo-url)  REPO_URL="$2";  shift 2 ;;
        *) echo "Unknown argument: $1" >&2; exit 2 ;;
    esac
done

# Expand a leading ~ in --clone-dir.
case "$CLONE_DIR" in "~"|"~/"*) CLONE_DIR="${HOME}/${CLONE_DIR#\~/}";; esac
EXPORT_FILE="$CLONE_DIR/sync/sleuth/reminders-${WORKSPACE}.json"

echo "Setting up Sleuth file source..."
echo "  workspace=$WORKSPACE"
echo "  clone=$CLONE_DIR"

# 1. Clone or refresh the export repo.
if [ -d "$CLONE_DIR/.git" ]; then
    echo "  repo already cloned — pulling latest"
    git -C "$CLONE_DIR" pull --rebase --autostash --quiet || echo "  WARN: pull failed (continuing)" >&2
elif [ -e "$CLONE_DIR" ]; then
    echo "ERROR: $CLONE_DIR exists but is not a git repo. Move it aside or pass --clone-dir." >&2
    exit 1
else
    echo "  cloning $REPO_URL"
    git clone --quiet "$REPO_URL" "$CLONE_DIR"
fi

# 2. Confirm the published file exists (the publisher must have run for this workspace).
if [ ! -f "$EXPORT_FILE" ]; then
    echo "ERROR: export file not found: $EXPORT_FILE" >&2
    echo "       Is the publisher running on the Sleuth box for workspace '$WORKSPACE'?" >&2
    echo "       (systemctl list-timers sleuth-reminders-export.timer)" >&2
    exit 1
fi

# 3. Point rebalance-OS at the local file (token unused for a file source).
echo "  configuring rebalance (set-sleuth → file source)"
"$REBALANCE" config set-sleuth \
    --base-url "$EXPORT_FILE" \
    --token "file-source" \
    --workspace "$WORKSPACE"

# 4. Verify.
echo "  verifying (sleuth-sync + doctor)"
"$REBALANCE" sleuth-sync --active-only --json | head -c 400; echo
"$REBALANCE" doctor 2>/dev/null | grep -iE "sleuth" || true

echo
echo "Done. Reminders now read from: $EXPORT_FILE"
echo "Keep it fresh: the daily sync auto-refreshes the clone; or 'git -C $CLONE_DIR pull'."
