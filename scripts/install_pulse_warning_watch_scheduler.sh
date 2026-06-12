#!/bin/bash
# Install a 15-minute launchd watcher for the local pulse warning banner.
#
# This renders the plist template into ~/Library/LaunchAgents/ and loads it so
# macOS invokes scripts/pulse_warning_watch.py every 15 minutes. The watcher
# curls http://127.0.0.1:8767/, extracts the top collector-warning banner, and
# appends JSONL records under temp/.
#
# Usage:
#   bash scripts/install_pulse_warning_watch_scheduler.sh
#
# Policy: SCHEDULER.md (job com.rebalance-os.pulse-warning-watch).

set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/lib/install_common.sh"

echo "Installing rebalance pulse warning watcher..."
echo "  REBALANCE_DIR=$REBALANCE_DIR"

rb_install_launchd_job "com.rebalance-os.pulse-warning-watch"

echo
echo "Logs:"
echo "  JSONL:   $REBALANCE_DIR/temp/pulse-warning-watch.jsonl"
echo "  stdout:  $REBALANCE_DIR/temp/logs/pulse-warning-watch-stdout.log"
echo "  stderr:  $REBALANCE_DIR/temp/logs/pulse-warning-watch-stderr.log"
echo
echo "Commands:"
echo "  Check status: launchctl list | grep pulse-warning-watch"
echo "  Uninstall:    launchctl unload $RB_PLIST_DEST && rm $RB_PLIST_DEST"
