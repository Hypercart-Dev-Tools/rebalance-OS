#!/bin/bash
# Install (or reinstall) the rebalance OS daily sync scheduler.
#
# What this does:
#   1. Copies the launchd plist to ~/Library/LaunchAgents/
#   2. Loads it so macOS runs daily_sync.sh:
#      - At 6:30 AM every day
#      - On boot/login if 6:30 AM was missed (laptop was asleep)
#
# Usage:
#   bash scripts/install_scheduler.sh
#
# To uninstall:
#   launchctl unload ~/Library/LaunchAgents/com.rebalance-os.daily-sync.plist
#   rm ~/Library/LaunchAgents/com.rebalance-os.daily-sync.plist

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_SRC="$SCRIPT_DIR/com.rebalance-os.daily-sync.plist"
PLIST_DEST="$HOME/Library/LaunchAgents/com.rebalance-os.daily-sync.plist"

echo "Installing rebalance OS daily sync scheduler..."

# Unload if already loaded
if launchctl list | grep -q "com.rebalance-os.daily-sync"; then
    echo "  Unloading existing scheduler..."
    launchctl unload "$PLIST_DEST" 2>/dev/null || true
fi

# Copy plist
cp "$PLIST_SRC" "$PLIST_DEST"
echo "  Copied plist to $PLIST_DEST"

# Create log directory
mkdir -p "$SCRIPT_DIR/../temp/logs"

# Load
launchctl load "$PLIST_DEST"
echo "  Loaded scheduler"

echo ""
echo "Done! rebalance OS will sync daily at 6:30 AM and on every boot/login."
echo ""
echo "Commands:"
echo "  Check status:   launchctl list | grep rebalance"
echo "  Run now:        bash $SCRIPT_DIR/daily_sync.sh"
echo "  View logs:      cat $SCRIPT_DIR/../temp/logs/daily_sync_\$(date +%Y-%m-%d).log"
echo "  Uninstall:      launchctl unload $PLIST_DEST && rm $PLIST_DEST"
