#!/bin/bash
# Install (or reinstall) the rebalance OS Obsidian daily activity sync (GH-112).
#
# What this does:
#   1. Renders com.rebalance-os.obsidian-daily-sync.plist.template into
#      ~/Library/LaunchAgents/.
#   2. Loads it so macOS runs utils/obsidian_daily_sync.sh at 18:00 daily
#      (or on next wake if the Mac was asleep at 6 PM). A catch-up run that fires
#      after midnight skips itself — see the script's late-run guard.
#
# RunAtLoad is intentionally false in the template — loading should not fire an
# off-schedule summary write.
#
# Usage:
#   bash scripts/install_obsidian_daily_sync_scheduler.sh
#
# Policy: SCHEDULER.md (job com.rebalance-os.obsidian-daily-sync).

set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/lib/install_common.sh"

echo "Installing rebalance OS Obsidian daily sync (18:00 daily)..."
echo "  REBALANCE_DIR=$REBALANCE_DIR"

# Job log lives outside the TCC-protected ~/Documents tree.
mkdir -p "$HOME/Library/Logs/rebalance-os"

rb_install_launchd_job "com.rebalance-os.obsidian-daily-sync" "utils/obsidian_daily_sync.sh"

echo
echo "Done! A Gemini daily-activity summary lands in Today's Notes at 6 PM (or next wake)."
echo
echo "Commands:"
echo "  Check status: launchctl list | grep obsidian-daily-sync"
echo "  View logs:    cat $HOME/Library/Logs/rebalance-os/obsidian-daily-sync.log"
echo "  Dry run now:  bash utils/obsidian_daily_sync.sh --dry-run"
echo "  Uninstall:    launchctl unload $RB_PLIST_DEST && rm $RB_PLIST_DEST"
