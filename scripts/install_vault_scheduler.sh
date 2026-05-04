#!/bin/bash
# Install (or reinstall) the rebalance OS hourly vault refresh scheduler.
#
# What this does:
#   1. Copies com.rebalance-os.vault-sync.plist to ~/Library/LaunchAgents/
#   2. Loads it so macOS runs vault_sync.sh at HH:15 from 06:15 through 23:15.
#
# This complements the daily 06:30 full sync by keeping just the vault
# portion fresh through the workday — notes edited after the morning run
# show up in the dashboard / pulse / semantic search within the hour.
#
# Usage:
#   bash scripts/install_vault_scheduler.sh
#
# To uninstall:
#   launchctl unload ~/Library/LaunchAgents/com.rebalance-os.vault-sync.plist
#   rm ~/Library/LaunchAgents/com.rebalance-os.vault-sync.plist

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_SRC="$SCRIPT_DIR/com.rebalance-os.vault-sync.plist"
PLIST_DEST="$HOME/Library/LaunchAgents/com.rebalance-os.vault-sync.plist"
VAULT_SCRIPT="$SCRIPT_DIR/vault_sync.sh"

echo "Installing rebalance OS hourly vault scheduler..."

if [ ! -x "$VAULT_SCRIPT" ]; then
    chmod +x "$VAULT_SCRIPT"
    echo "  Made vault_sync.sh executable"
fi

if launchctl list | grep -q "com.rebalance-os.vault-sync"; then
    echo "  Unloading existing vault scheduler..."
    launchctl unload "$PLIST_DEST" 2>/dev/null || true
fi

cp "$PLIST_SRC" "$PLIST_DEST"
echo "  Copied plist to $PLIST_DEST"

mkdir -p "$SCRIPT_DIR/../temp/logs"

launchctl load "$PLIST_DEST"
echo "  Loaded scheduler"

echo
echo "Done! rebalance OS will refresh the vault on the :15 of every hour, 6 AM through 11 PM."
echo
echo "Commands:"
echo "  Check status:   launchctl list | grep vault-sync"
echo "  Run now:        bash $VAULT_SCRIPT"
echo "  View logs:      cat $SCRIPT_DIR/../temp/logs/vault_sync_\$(date +%Y-%m-%d).log"
echo "  Uninstall:      launchctl unload $PLIST_DEST && rm $PLIST_DEST"
