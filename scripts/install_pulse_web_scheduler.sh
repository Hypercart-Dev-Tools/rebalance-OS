#!/bin/bash
# Install (or reinstall) the rebalance OS 30-minute pulse-web mirror refresh.
#
# What this does:
#   1. Copies com.rebalance-os.pulse-web-sync.plist to ~/Library/LaunchAgents/
#   2. Loads it so macOS runs pulse_web_sync.sh every 30 minutes from
#      6:00 AM through 11:30 PM.
#
# This is separate from the hourly pulse-sync (markdown→private-repo). The
# pulse-web job only regenerates the local web/pulse.html artifact.
#
# Pre-flight:
#   - vault_path must be set in temp/rbos.config (used to locate "0. Goals.md").
#   - Override with PULSE_GOALS env var or pass --goals to scripts/pulse_web.py
#     for non-default layouts.
#
# Usage:
#   bash scripts/install_pulse_web_scheduler.sh
#
# To uninstall:
#   launchctl unload ~/Library/LaunchAgents/com.rebalance-os.pulse-web-sync.plist
#   rm ~/Library/LaunchAgents/com.rebalance-os.pulse-web-sync.plist

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REBALANCE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PLIST_TEMPLATE="$SCRIPT_DIR/com.rebalance-os.pulse-web-sync.plist.template"
PLIST_DEST="$HOME/Library/LaunchAgents/com.rebalance-os.pulse-web-sync.plist"
PULSE_WEB_SCRIPT="$SCRIPT_DIR/pulse_web_sync.sh"

echo "Installing rebalance OS 30-minute pulse-web scheduler..."
echo "  REBALANCE_DIR=$REBALANCE_DIR"

if [ ! -x "$PULSE_WEB_SCRIPT" ]; then
    chmod +x "$PULSE_WEB_SCRIPT"
    echo "  Made pulse_web_sync.sh executable"
fi

if launchctl list | grep -q "com.rebalance-os.pulse-web-sync"; then
    echo "  Unloading existing pulse-web scheduler..."
    launchctl unload "$PLIST_DEST" 2>/dev/null || true
fi

# Render template into LaunchAgents — escape '/' and '&' for sed.
ESCAPED_DIR=$(printf '%s\n' "$REBALANCE_DIR" | sed 's/[\/&]/\\&/g')
sed "s/{{REBALANCE_DIR}}/$ESCAPED_DIR/g" "$PLIST_TEMPLATE" > "$PLIST_DEST"
echo "  Rendered plist to $PLIST_DEST"

mkdir -p "$REBALANCE_DIR/temp/logs"

launchctl load "$PLIST_DEST"
echo "  Loaded scheduler"

echo
echo "Done! rebalance OS will refresh web/pulse.html every 30 minutes, 6:00 AM through 11:30 PM."
echo
echo "Commands:"
echo "  Check status:   launchctl list | grep pulse-web-sync"
echo "  Run now:        bash $PULSE_WEB_SCRIPT"
echo "  View logs:      cat $SCRIPT_DIR/../temp/logs/pulse_web_sync_\$(date +%Y-%m-%d).log"
echo "  Open page:      open $SCRIPT_DIR/../web/pulse.html"
echo "  Uninstall:      launchctl unload $PLIST_DEST && rm $PLIST_DEST"
