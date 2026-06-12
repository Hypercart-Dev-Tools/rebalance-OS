#!/bin/bash
# Install (or reinstall) the rebalance OS 30-minute pulse-web mirror refresh.
#
# What this does:
#   1. Renders com.rebalance-os.pulse-web-sync.plist.template into
#      ~/Library/LaunchAgents/.
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
# Policy: SCHEDULER.md (job com.rebalance-os.pulse-web-sync).

set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/lib/install_common.sh"

echo "Installing rebalance OS 30-minute pulse-web scheduler..."
echo "  REBALANCE_DIR=$REBALANCE_DIR"

rb_install_launchd_job "com.rebalance-os.pulse-web-sync" "scripts/pulse_web_sync.sh"

echo
echo "Done! rebalance OS will refresh web/pulse.html every 30 minutes, 6:00 AM through 11:30 PM."
echo
echo "Commands:"
echo "  Check status:   launchctl list | grep pulse-web-sync"
echo "  Run now:        bash $SCRIPT_DIR/pulse_web_sync.sh"
echo "  View logs:      cat $REBALANCE_DIR/temp/logs/pulse_web_sync_\$(date +%Y-%m-%d).log"
echo "  Open page:      open $REBALANCE_DIR/web/pulse.html"
echo "  Uninstall:      launchctl unload $RB_PLIST_DEST && rm $RB_PLIST_DEST"
