#!/bin/bash
# Install (or reinstall) the rebalance OS pulse server (autostart at login).
#
# What this does:
#   1. Renders com.rebalance-os.pulse-server.plist.template (substituting the
#      local checkout path for {{REBALANCE_DIR}}) into ~/Library/LaunchAgents/.
#   2. Loads it so macOS keeps pulse_server.sh running:
#      - RunAtLoad + KeepAlive — the FastAPI server on 127.0.0.1:8767 stays up
#      - ThrottleInterval=30s — a crash-looping server is restarted no faster
#        than every 30 seconds
#
# This is the interactive layer (real Refresh button + filter) on top of the
# static web/pulse.html that com.rebalance-os.pulse-web-sync regenerates every
# 30 minutes. Loopback bind is enforced in pulse_server.py.
#
# Usage:
#   bash scripts/install_pulse_server_scheduler.sh
#
# Policy: SCHEDULER.md (job com.rebalance-os.pulse-server).

set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/lib/install_common.sh"

echo "Installing rebalance OS pulse server (autostart)..."
echo "  REBALANCE_DIR=$REBALANCE_DIR"

rb_install_launchd_job "com.rebalance-os.pulse-server" "scripts/pulse_server.sh"

echo
echo "Done! The rebalance OS pulse server is running at http://127.0.0.1:8767/"
echo "and will restart on login and after crashes."
echo
echo "Commands:"
echo "  Check status:   launchctl list | grep pulse-server"
echo "  Health check:   curl -fsS http://127.0.0.1:8767/api/health"
echo "  View logs:      cat $REBALANCE_DIR/temp/logs/pulse_server_stderr.log"
echo "  Uninstall:      launchctl unload $RB_PLIST_DEST && rm $RB_PLIST_DEST"
