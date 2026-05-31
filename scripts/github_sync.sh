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
