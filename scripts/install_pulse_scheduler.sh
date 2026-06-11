#!/bin/bash
# Install (or reinstall) the rebalance OS hourly pulse publisher.
#
# What this does:
#   1. Renders com.rebalance-os.pulse-sync.plist.template (substituting the
#      local checkout path for {{REBALANCE_DIR}}) into ~/Library/LaunchAgents/.
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
# Policy: SCHEDULER.md (job com.rebalance-os.pulse-sync).

set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/lib/install_common.sh"

echo "Installing rebalance OS hourly pulse scheduler..."
echo "  REBALANCE_DIR=$REBALANCE_DIR"

rb_install_launchd_job "com.rebalance-os.pulse-sync" "scripts/pulse_sync.sh"

echo
echo "Done! rebalance OS will publish a pulse on the hour, every hour, 6 AM through 11 PM."
echo
echo "Commands:"
echo "  Check status:   launchctl list | grep pulse-sync"
echo "  Run now:        bash $SCRIPT_DIR/pulse_sync.sh"
echo "  View logs:      cat $REBALANCE_DIR/temp/logs/pulse_sync_\$(date +%Y-%m-%d).log"
echo "  Uninstall:      launchctl unload $RB_PLIST_DEST && rm $RB_PLIST_DEST"
