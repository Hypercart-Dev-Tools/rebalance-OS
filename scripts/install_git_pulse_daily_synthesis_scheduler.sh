#!/bin/bash
# Install (or reinstall) the rebalance OS Git Pulse daily synthesis (GH-114).
#
# What this does:
#   1. Renders com.rebalance-os.git-pulse-daily-synthesis.plist.template into
#      ~/Library/LaunchAgents/.
#   2. Loads it so macOS runs utils/git_pulse_daily_synthesis.sh at 18:05 daily
#      (or on next wake if the Mac was asleep) — 5 minutes after obsidian-daily-sync
#      so, when both destinations are configured, this block lands after the
#      GH-112 AI Daily Summary block. A catch-up run that fires after midnight
#      skips itself — see the script's late-run guard.
#
# RunAtLoad is intentionally false in the template — loading should not fire an
# off-schedule summary write.
#
# Usage:
#   bash scripts/install_git_pulse_daily_synthesis_scheduler.sh
#
# Policy: SCHEDULER.md (job com.rebalance-os.git-pulse-daily-synthesis).

set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/lib/install_common.sh"

echo "Installing rebalance OS Git Pulse daily synthesis (18:05 daily)..."
echo "  REBALANCE_DIR=$REBALANCE_DIR"

# Job log lives outside the TCC-protected ~/Documents tree.
mkdir -p "$HOME/Library/Logs/rebalance-os"

rb_install_launchd_job "com.rebalance-os.git-pulse-daily-synthesis" "utils/git_pulse_daily_synthesis.sh"

echo
echo "Done! A Git Pulse daily summary lands at 18:05 (or next wake) — in Today's"
echo "Notes if the Obsidian vault is configured, and/or in git-pulse-sync/CLIO if"
echo "git_pulse_clio_enabled is set (see rebalance.ingest.config.set_pulse_config)."
echo
echo "Commands:"
echo "  Check status: launchctl list | grep git-pulse-daily-synthesis"
echo "  View logs:    cat $HOME/Library/Logs/rebalance-os/git-pulse-daily-synthesis.log"
echo "  Dry run now:  bash utils/git_pulse_daily_synthesis.sh --dry-run --force"
echo "  Status now:   bash utils/git_pulse_daily_synthesis.sh --status"
echo "  Uninstall:    launchctl unload $RB_PLIST_DEST && rm $RB_PLIST_DEST"
