#!/bin/bash
# rebalance OS — daily data sync
# Runs on boot and daily via launchd. Calls refresh_index(scope=["all"])
# so the MCP server always has fresh context.
#
# Single source of truth: this is the same orchestration the MCP
# refresh_index tool exposes to interactive agents.
#
# Install: see scripts/install_scheduler.sh

set -euo pipefail

REBALANCE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="$REBALANCE_DIR/.venv/bin/python"
export PYTHONPATH="$REBALANCE_DIR/src${PYTHONPATH:+:$PYTHONPATH}"
LOG_DIR="$REBALANCE_DIR/temp/logs"

mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/daily_sync_$(date +%Y-%m-%d).log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

cd "$REBALANCE_DIR"

_JOB_START_TS=$(date +%s)
"$PYTHON" -c "from rebalance.ingest.auth_log import log_job_started; log_job_started('daily-sync')" 2>/dev/null || true
_job_exit() {
    local _code=$?
    local _elapsed=$(( $(date +%s) - _JOB_START_TS ))
    if [ "$_code" -eq 0 ]; then
        "$PYTHON" -c "from rebalance.ingest.auth_log import log_job_completed; log_job_completed('daily-sync', $_elapsed)" 2>/dev/null || true
    else
        "$PYTHON" -c "from rebalance.ingest.auth_log import log_job_failed; log_job_failed('daily-sync', $_code, $_elapsed)" 2>/dev/null || true
    fi
}
trap _job_exit EXIT

log "=== rebalance daily sync starting ==="

# refresh_index orchestrates: vault ingest+embed -> github scan+sync+embed ->
# calendar -> sleuth -> unified semantic backfill+embed. Per-scope failures
# are captured in the result.errors list rather than aborting the run.
# DB path resolves via rebalance.paths.resolve_database_path() so we hit the
# same canonical location the dashboard/MCP reads from — never a stale
# project-tree rebalance.db left behind by an older script.
if "$PYTHON" - <<'PY' >> "$LOG_FILE" 2>&1
import json
import sys
from rebalance.ingest.index_ops import refresh_index
from rebalance.paths import resolve_database_path

db_path = resolve_database_path()
print(f"database={db_path}")
result = refresh_index(db_path, scope=["all"])
print(json.dumps(result, indent=2, default=str))
sys.exit(1 if result.get("errors") else 0)
PY
then
    EXIT_CODE=0
else
    EXIT_CODE=$?
fi

if [ $EXIT_CODE -eq 0 ]; then
    log "=== rebalance daily sync complete ==="
else
    log "=== rebalance daily sync finished with errors (see JSON above) ==="
fi

# Retain 30 days of logs.
find "$LOG_DIR" -name "daily_sync_*.log" -mtime +30 -delete 2>/dev/null || true

exit $EXIT_CODE
