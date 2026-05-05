#!/bin/bash
# Install (or reinstall) the rebalance OS daily sync scheduler.
#
# What this does:
#   1. Renders com.rebalance-os.daily-sync.plist.template (substituting the
#      local checkout path for {{REBALANCE_DIR}}) into ~/Library/LaunchAgents/.
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
REBALANCE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PLIST_TEMPLATE="$SCRIPT_DIR/com.rebalance-os.daily-sync.plist.template"
PLIST_DEST="$HOME/Library/LaunchAgents/com.rebalance-os.daily-sync.plist"

echo "Installing rebalance OS daily sync scheduler..."
echo "  REBALANCE_DIR=$REBALANCE_DIR"

# Unload if already loaded
if launchctl list | grep -q "com.rebalance-os.daily-sync"; then
    echo "  Unloading existing scheduler..."
    launchctl unload "$PLIST_DEST" 2>/dev/null || true
fi

# Render template into LaunchAgents — escape '/' and '&' for sed.
ESCAPED_DIR=$(printf '%s\n' "$REBALANCE_DIR" | sed 's/[\/&]/\\&/g')
sed "s/{{REBALANCE_DIR}}/$ESCAPED_DIR/g" "$PLIST_TEMPLATE" > "$PLIST_DEST"
echo "  Rendered plist to $PLIST_DEST"

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
