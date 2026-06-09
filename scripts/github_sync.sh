#!/bin/bash
# rebalance OS — hourly github sync
# Runs hourly via launchd to keep github context fresh.

set -euo pipefail

REBALANCE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="$REBALANCE_DIR/.venv/bin/python"
export PYTHONPATH="$REBALANCE_DIR/src${PYTHONPATH:+:$PYTHONPATH}"
LOG_DIR="$REBALANCE_DIR/temp/logs"

mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/github_sync_$(date +%Y-%m-%d).log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

cd "$REBALANCE_DIR"

_JOB_START_TS=$(date +%s)
"$PYTHON" -c "from rebalance.ingest.auth_log import log_job_started; log_job_started('github-sync')" 2>/dev/null || true
_job_exit() {
    local _code=$?
    local _elapsed=$(( $(date +%s) - _JOB_START_TS ))
    if [ "$_code" -eq 0 ]; then
        "$PYTHON" -c "from rebalance.ingest.auth_log import log_job_completed; log_job_completed('github-sync', $_elapsed)" 2>/dev/null || true
    else
        "$PYTHON" -c "from rebalance.ingest.auth_log import log_job_failed; log_job_failed('github-sync', $_code, $_elapsed)" 2>/dev/null || true
    fi
}
trap _job_exit EXIT

log "=== rebalance hourly github sync starting ==="

if "$PYTHON" - <<'PY' >> "$LOG_FILE" 2>&1
import json
import sys
from rebalance.ingest.index_ops import refresh_index
from rebalance.paths import resolve_database_path

db_path = resolve_database_path()
print(f"database={db_path}")
result = refresh_index(db_path, scope=["github"])
print(json.dumps(result, indent=2, default=str))
sys.exit(1 if result.get("errors") else 0)
PY
then
    EXIT_CODE=0
else
    EXIT_CODE=$?
fi

if [ $EXIT_CODE -eq 0 ]; then
    log "=== rebalance hourly github sync complete ==="
else
    log "=== rebalance hourly github sync finished with errors ==="
fi

find "$LOG_DIR" -name "github_sync_*.log" -mtime +14 -delete 2>/dev/null || true

exit $EXIT_CODE
