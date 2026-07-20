#!/bin/bash
# Install (or reinstall) the rebalance OS Obsidian daily-notes rollover.
#
# What this does:
#   1. Renders com.rebalance-os.obsidian-rollover.plist.template into
#      ~/Library/LaunchAgents/.
#   2. Loads it so macOS runs utils/obsidian_rollover.sh at 00:00 daily
#      (or on next wake if the Mac was asleep at midnight).
#
# RunAtLoad is intentionally false in the template — loading must never fire
# the rollover immediately, or it would wipe Today's Notes unexpectedly.
#
# Usage:
#   bash scripts/install_obsidian_rollover_scheduler.sh
#
# Policy: SCHEDULER.md (job com.rebalance-os.obsidian-rollover).

set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/lib/install_common.sh"

echo "Installing rebalance OS Obsidian rollover (00:00 daily)..."
echo "  REBALANCE_DIR=$REBALANCE_DIR"

# Job log lives outside the TCC-protected ~/Documents tree.
mkdir -p "$HOME/Library/Logs/rebalance-os"

rb_install_launchd_job "com.rebalance-os.obsidian-rollover" "utils/obsidian_rollover.sh"

echo
echo "Done! Daily notes roll over at midnight (or on next wake)."
echo
echo "Commands:"
echo "  Check status: launchctl list | grep obsidian-rollover"
echo "  View logs:    cat $HOME/Library/Logs/rebalance-os/obsidian-rollover.log"
echo "  Uninstall:    launchctl unload $RB_PLIST_DEST && rm $RB_PLIST_DEST"
