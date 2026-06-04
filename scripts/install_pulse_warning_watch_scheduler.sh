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

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REBALANCE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PLIST_TEMPLATE="$SCRIPT_DIR/com.rebalance-os.pulse-warning-watch.plist.template"
PLIST_DEST="$HOME/Library/LaunchAgents/com.rebalance-os.pulse-warning-watch.plist"
PYTHON_BIN="$REBALANCE_DIR/.venv/bin/python"

echo "Installing rebalance pulse warning watcher..."
echo "  REBALANCE_DIR=$REBALANCE_DIR"

if [ ! -x "$PYTHON_BIN" ]; then
    echo "Expected virtualenv python at $PYTHON_BIN" >&2
    exit 1
fi

launchctl unload "$PLIST_DEST" 2>/dev/null || true

ESCAPED_DIR=$(printf '%s\n' "$REBALANCE_DIR" | sed 's/[\/&]/\\&/g')
ESCAPED_PY=$(printf '%s\n' "$PYTHON_BIN" | sed 's/[\/&]/\\&/g')
sed \
    -e "s/{{REBALANCE_DIR}}/$ESCAPED_DIR/g" \
    -e "s/{{PYTHON}}/$ESCAPED_PY/g" \
    "$PLIST_TEMPLATE" > "$PLIST_DEST"

mkdir -p "$REBALANCE_DIR/temp/logs"

launchctl load "$PLIST_DEST"

echo "  Rendered plist to $PLIST_DEST"
echo "  Loaded pulse warning watcher"
echo
echo "Logs:"
echo "  JSONL:   $REBALANCE_DIR/temp/pulse-warning-watch.jsonl"
echo "  stdout:  $REBALANCE_DIR/temp/logs/pulse-warning-watch-stdout.log"
echo "  stderr:  $REBALANCE_DIR/temp/logs/pulse-warning-watch-stderr.log"
echo
echo "Commands:"
echo "  Check status: launchctl list | grep pulse-warning-watch"
echo "  Uninstall:    launchctl unload $PLIST_DEST && rm $PLIST_DEST"
