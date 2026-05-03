#!/bin/bash
# rebalance OS — hourly pulse publish
# Runs hourly via launchd (com.rebalance-os.pulse-sync) between 6 AM and 11 PM.
# Calls publish_pulse() to render today's + yesterday's activity to a markdown
# file in a private git repo and push it. The push is only done when content
# actually changed since the previous run.
#
# Single source of truth: this is the same orchestration the MCP publish_pulse
# tool exposes to interactive agents.

set -euo pipefail

REBALANCE_DIR="/Users/noelsaw/Documents/rebalance-OS"
PYTHON="$REBALANCE_DIR/.venv/bin/python"
LOG_DIR="$REBALANCE_DIR/temp/logs"

mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/pulse_sync_$(date +%Y-%m-%d).log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

cd "$REBALANCE_DIR"

log "=== rebalance pulse sync starting ==="

"$PYTHON" - <<'PY' >> "$LOG_FILE" 2>&1
import json
import sys
from pathlib import Path
from rebalance.ingest.pulse import publish_pulse

result = publish_pulse(Path("rebalance.db").resolve(), dry_run=False, push=True)
# Drop the rendered markdown from the log to keep it readable; the file on
# disk is the artifact.
result.pop("markdown", None)
print(json.dumps(result, indent=2, default=str))

if not result.get("ok"):
    sys.exit(1)

git = result.get("git") or {}
if git.get("git_error"):
    sys.exit(2)
sys.exit(0)
PY
EXIT_CODE=$?

case $EXIT_CODE in
    0) log "=== pulse sync complete ===" ;;
    1) log "=== pulse sync FAILED (config or render error) ===" ;;
    2) log "=== pulse sync FAILED (git error — see JSON) ===" ;;
    *) log "=== pulse sync exited with code $EXIT_CODE ===" ;;
esac

# Retain 14 days of pulse logs.
find "$LOG_DIR" -name "pulse_sync_*.log" -mtime +14 -delete 2>/dev/null || true

exit $EXIT_CODE
