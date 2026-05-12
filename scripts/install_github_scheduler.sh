#!/bin/bash
# Install (or reinstall) the rebalance OS hourly github sync scheduler.
#
# What this does:
#   1. Copies com.rebalance-os.github-sync.plist to ~/Library/LaunchAgents/
#   2. Loads it so macOS runs github_sync.sh at HH:45 from 06:45 through 23:45.
#
# Usage:
#   bash scripts/install_github_scheduler.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_SRC="$SCRIPT_DIR/com.rebalance-os.github-sync.plist"
PLIST_DEST="$HOME/Library/LaunchAgents/com.rebalance-os.github-sync.plist"
SYNC_SCRIPT="$SCRIPT_DIR/github_sync.sh"

echo "Installing rebalance OS hourly github scheduler..."

if [ ! -x "$SYNC_SCRIPT" ]; then
    chmod +x "$SYNC_SCRIPT"
    echo "  Made github_sync.sh executable"
fi

if launchctl list | grep -q "com.rebalance-os.github-sync"; then
    echo "  Unloading existing github scheduler..."
    launchctl unload "$PLIST_DEST" 2>/dev/null || true
fi

cp "$PLIST_SRC" "$PLIST_DEST"
echo "  Copied plist to $PLIST_DEST"

mkdir -p "$SCRIPT_DIR/../temp/logs"

launchctl load "$PLIST_DEST"
echo "  Loaded scheduler"

echo
echo "Done! rebalance OS will refresh GitHub data on the :45 of every hour, 6 AM through 11 PM."