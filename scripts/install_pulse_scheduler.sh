#!/bin/bash
# Install (or reinstall) the rebalance OS hourly pulse publisher.
#
# What this does:
#   1. Copies com.rebalance-os.pulse-sync.plist to ~/Library/LaunchAgents/
#   2. Loads it so macOS runs pulse_sync.sh every hour from 6 AM to 11 PM.
#
# Pre-flight:
#   - Pulse config must be set in temp/rbos.config (github_login, slack_user_id,
#     pulse_target_path, pulse_filename, pulse_timezone). Use
#     rebalance.ingest.config.set_pulse_config() to populate.
#   - pulse_target_path must be an existing local clone of a (private) git repo
#     with `origin` configured.
#
# Usage:
#   bash scripts/install_pulse_scheduler.sh
#
# To uninstall:
#   launchctl unload ~/Library/LaunchAgents/com.rebalance-os.pulse-sync.plist
#   rm ~/Library/LaunchAgents/com.rebalance-os.pulse-sync.plist

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_SRC="$SCRIPT_DIR/com.rebalance-os.pulse-sync.plist"
PLIST_DEST="$HOME/Library/LaunchAgents/com.rebalance-os.pulse-sync.plist"
PULSE_SCRIPT="$SCRIPT_DIR/pulse_sync.sh"

echo "Installing rebalance OS hourly pulse scheduler..."

if [ ! -x "$PULSE_SCRIPT" ]; then
    chmod +x "$PULSE_SCRIPT"
    echo "  Made pulse_sync.sh executable"
fi

if launchctl list | grep -q "com.rebalance-os.pulse-sync"; then
    echo "  Unloading existing pulse scheduler..."
    launchctl unload "$PLIST_DEST" 2>/dev/null || true
fi

cp "$PLIST_SRC" "$PLIST_DEST"
echo "  Copied plist to $PLIST_DEST"

mkdir -p "$SCRIPT_DIR/../temp/logs"

launchctl load "$PLIST_DEST"
echo "  Loaded scheduler"

echo
echo "Done! rebalance OS will publish a pulse on the hour, every hour, 6 AM through 11 PM."
echo
echo "Commands:"
echo "  Check status:   launchctl list | grep pulse-sync"
echo "  Run now:        bash $PULSE_SCRIPT"
echo "  View logs:      cat $SCRIPT_DIR/../temp/logs/pulse_sync_\$(date +%Y-%m-%d).log"
echo "  Uninstall:      launchctl unload $PLIST_DEST && rm $PLIST_DEST"
