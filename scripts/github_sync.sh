#!/bin/bash
# rebalance OS — hourly github sync
# Runs hourly via launchd to keep github context fresh.

set -euo pipefail

REBALANCE_DIR="/Users/noelsaw/Documents/rebalance-OS"
PYTHON="$REBALANCE_DIR/.venv/bin/python"
DATABASE="$REBALANCE_DIR/rebalance.db"
LOG_DIR="$REBALANCE_DIR/temp/logs"

mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/github_sync_$(date +%Y-%m-%d).log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

cd "$REBALANCE_DIR"

log "=== rebalance hourly github sync starting ==="

"$PYTHON" - <<'PY' >> "$LOG_FILE" 2>&1
import json
import sys
from pathlib import Path
from rebalance.ingest.index_ops import refresh_index

result = refresh_index(Path("rebalance.db").resolve(), scope=["github"])
print(json.dumps(result, indent=2, default=str))
sys.exit(1 if result.get("errors") else 0)
PY
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    log "=== rebalance hourly github sync complete ==="
else
    log "=== rebalance hourly github sync finished with errors ==="
fi

find "$LOG_DIR" -name "github_sync_*.log" -mtime +14 -delete 2>/dev/null || true

exit $EXIT_CODE