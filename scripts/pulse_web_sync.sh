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
export PYTHONPATH="$REBALANCE_DIR/src${PYTHONPATH:+:$PYTHONPATH}"
LOG_DIR="$REBALANCE_DIR/temp/logs"

mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/pulse_web_sync_$(date +%Y-%m-%d).log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

cd "$REBALANCE_DIR"

_JOB_START_TS=$(date +%s)
"$PYTHON" -c "from rebalance.ingest.auth_log import log_job_started; log_job_started('pulse-web-sync')" 2>/dev/null || true
_job_exit() {
    local _code=$?
    local _elapsed=$(( $(date +%s) - _JOB_START_TS ))
    if [ "$_code" -eq 0 ]; then
        "$PYTHON" -c "from rebalance.ingest.auth_log import log_job_completed; log_job_completed('pulse-web-sync', $_elapsed)" 2>/dev/null || true
    else
        "$PYTHON" -c "from rebalance.ingest.auth_log import log_job_failed; log_job_failed('pulse-web-sync', $_code, $_elapsed)" 2>/dev/null || true
    fi
}
trap _job_exit EXIT

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
