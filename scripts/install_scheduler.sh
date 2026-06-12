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
# Policy: SCHEDULER.md (job com.rebalance-os.daily-sync).

set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/lib/install_common.sh"

echo "Installing rebalance OS daily sync scheduler..."
echo "  REBALANCE_DIR=$REBALANCE_DIR"

rb_install_launchd_job "com.rebalance-os.daily-sync" "scripts/daily_sync.sh"

echo ""
echo "Done! rebalance OS will sync daily at 6:30 AM and on every boot/login."
echo ""
echo "Commands:"
echo "  Check status:   launchctl list | grep rebalance"
echo "  Run now:        bash $SCRIPT_DIR/daily_sync.sh"
echo "  View logs:      cat $REBALANCE_DIR/temp/logs/daily_sync_\$(date +%Y-%m-%d).log"
echo "  Uninstall:      launchctl unload $RB_PLIST_DEST && rm $RB_PLIST_DEST"
