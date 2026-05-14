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
# To uninstall:
#   launchctl unload ~/Library/LaunchAgents/com.rebalance-os.pulse-server.plist
#   rm ~/Library/LaunchAgents/com.rebalance-os.pulse-server.plist

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REBALANCE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PLIST_TEMPLATE="$SCRIPT_DIR/com.rebalance-os.pulse-server.plist.template"
PLIST_DEST="$HOME/Library/LaunchAgents/com.rebalance-os.pulse-server.plist"
SERVER_SCRIPT="$SCRIPT_DIR/pulse_server.sh"

echo "Installing rebalance OS pulse server (autostart)..."
echo "  REBALANCE_DIR=$REBALANCE_DIR"

if [ ! -x "$SERVER_SCRIPT" ]; then
    chmod +x "$SERVER_SCRIPT"
    echo "  Made pulse_server.sh executable"
fi

# Always attempt an unload first — `launchctl load` fails with an opaque
# "Input/output error" if the job is already registered, and the grep check
# can miss a job that is loaded but momentarily absent from `launchctl list`.
launchctl unload "$PLIST_DEST" 2>/dev/null || true

# Render template into LaunchAgents — escape '/' and '&' for sed.
ESCAPED_DIR=$(printf '%s\n' "$REBALANCE_DIR" | sed 's/[\/&]/\\&/g')
sed "s/{{REBALANCE_DIR}}/$ESCAPED_DIR/g" "$PLIST_TEMPLATE" > "$PLIST_DEST"
echo "  Rendered plist to $PLIST_DEST"

mkdir -p "$REBALANCE_DIR/temp/logs"

launchctl load "$PLIST_DEST"
echo "  Loaded pulse server"

echo
echo "Done! The rebalance OS pulse server is running at http://127.0.0.1:8767/"
echo "and will restart on login and after crashes."
echo
echo "Commands:"
echo "  Check status:   launchctl list | grep pulse-server"
echo "  Health check:   curl -fsS http://127.0.0.1:8767/api/health"
echo "  View logs:      cat $REBALANCE_DIR/temp/logs/pulse_server_stderr.log"
echo "  Uninstall:      launchctl unload $PLIST_DEST && rm $PLIST_DEST"
