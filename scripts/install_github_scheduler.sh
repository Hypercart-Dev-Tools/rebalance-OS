#!/bin/bash
# Install (or reinstall) the rebalance OS hourly github sync scheduler.
#
# What this does:
#   1. Renders com.rebalance-os.github-sync.plist.template (substituting the
#      local checkout path for {{REBALANCE_DIR}}) into ~/Library/LaunchAgents/.
#   2. Loads it so macOS runs github_sync.sh at HH:45 from 06:45 through 23:45.
#
# Usage:
#   bash scripts/install_github_scheduler.sh
#
# Policy: SCHEDULER.md (job com.rebalance-os.github-sync).

set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/lib/install_common.sh"

echo "Installing rebalance OS hourly github scheduler..."
echo "  REBALANCE_DIR=$REBALANCE_DIR"

rb_install_launchd_job "com.rebalance-os.github-sync" "scripts/github_sync.sh"

echo
echo "Done! rebalance OS will refresh GitHub data on the :45 of every hour, 6 AM through 11 PM."
echo
echo "Commands:"
echo "  Check status:   launchctl list | grep github-sync"
echo "  Run now:        bash $SCRIPT_DIR/github_sync.sh"
echo "  View logs:      cat $REBALANCE_DIR/temp/logs/github_sync_\$(date +%Y-%m-%d).log"
echo "  Uninstall:      launchctl unload $RB_PLIST_DEST && rm $RB_PLIST_DEST"
