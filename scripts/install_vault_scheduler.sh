#!/bin/bash
# Install (or reinstall) the rebalance OS hourly vault refresh scheduler.
#
# What this does:
#   1. Renders com.rebalance-os.vault-sync.plist.template (substituting the
#      local checkout path for {{REBALANCE_DIR}}) into ~/Library/LaunchAgents/.
#   2. Loads it so macOS runs vault_sync.sh at HH:15 from 06:15 through 23:15.
#
# This complements the daily 06:30 full sync by keeping just the vault
# portion fresh through the workday — notes edited after the morning run
# show up in the dashboard / pulse / semantic search within the hour.
#
# Usage:
#   bash scripts/install_vault_scheduler.sh
#
# Policy: SCHEDULER.md (job com.rebalance-os.vault-sync).

set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/lib/install_common.sh"

echo "Installing rebalance OS hourly vault scheduler..."
echo "  REBALANCE_DIR=$REBALANCE_DIR"

rb_install_launchd_job "com.rebalance-os.vault-sync" "scripts/vault_sync.sh"

echo
echo "Done! rebalance OS will refresh the vault on the :15 of every hour, 6 AM through 11 PM."
echo
echo "Commands:"
echo "  Check status:   launchctl list | grep vault-sync"
echo "  Run now:        bash $SCRIPT_DIR/vault_sync.sh"
echo "  View logs:      cat $REBALANCE_DIR/temp/logs/vault_sync_\$(date +%Y-%m-%d).log"
echo "  Uninstall:      launchctl unload $RB_PLIST_DEST && rm $RB_PLIST_DEST"
