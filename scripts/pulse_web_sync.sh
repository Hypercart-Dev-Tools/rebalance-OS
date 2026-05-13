#!/bin/bash
# rebalance OS — 30-minute pulse web mirror refresh
# Runs every 30 min via launchd (com.rebalance-os.pulse-web-sync) between
# 6:00 AM and 11:30 PM. Calls scripts/pulse_web.py to regenerate web/pulse.html
# from the same SQLite knowledge base the TUI dashboard reads.
#
# This is the local HTML mirror, not the markdown→private-repo flow. The
# markdown publish lives in pulse_sync.sh on a separate hourly schedule.
#
# Robustness notes:
#   - pulse_web.py writes atomically (tmp + replace), so a crashed run leaves
#     the previous web/pulse.html in place rather than truncating it.
#   - Reads SQLite in WAL mode and does not block the writers (daily-sync,
#     vault-sync). PRAGMA busy_timeout=30000 covers the edge cases.
#   - No network calls, no git push. Local file only.

set -euo pipefail

REBALANCE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="$REBALANCE_DIR/.venv/bin/python"
LOG_DIR="$REBALANCE_DIR/temp/logs"

mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/pulse_web_sync_$(date +%Y-%m-%d).log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

cd "$REBALANCE_DIR"

log "=== rebalance pulse-web sync starting ==="

if "$PYTHON" scripts/pulse_web.py >> "$LOG_FILE" 2>&1; then
    EXIT_CODE=0
    log "=== pulse-web sync complete ==="
else
    EXIT_CODE=$?
    log "=== pulse-web sync FAILED (exit $EXIT_CODE) ==="
fi

# Retain 14 days of logs, matching pulse_sync.sh.
find "$LOG_DIR" -name "pulse_web_sync_*.log" -mtime +14 -delete 2>/dev/null || true

exit $EXIT_CODE
