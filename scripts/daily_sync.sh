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

REBALANCE_DIR="/Users/noelsaw/Documents/rebalance-OS"
PYTHON="$REBALANCE_DIR/.venv/bin/python"
DATABASE="$REBALANCE_DIR/rebalance.db"
LOG_DIR="$REBALANCE_DIR/temp/logs"

mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/daily_sync_$(date +%Y-%m-%d).log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

cd "$REBALANCE_DIR"

log "=== rebalance daily sync starting ==="
log "scope=all database=$DATABASE"

# refresh_index orchestrates: vault ingest+embed -> github scan+sync+embed ->
# calendar -> sleuth -> unified semantic backfill+embed. Per-scope failures
# are captured in the result.errors list rather than aborting the run.
"$PYTHON" - <<'PY' >> "$LOG_FILE" 2>&1
import json
import sys
from pathlib import Path
from rebalance.ingest.index_ops import refresh_index

result = refresh_index(Path("rebalance.db").resolve(), scope=["all"])
print(json.dumps(result, indent=2, default=str))
sys.exit(1 if result.get("errors") else 0)
PY
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    log "=== rebalance daily sync complete ==="
else
    log "=== rebalance daily sync finished with errors (see JSON above) ==="
fi

# Retain 30 days of logs.
find "$LOG_DIR" -name "daily_sync_*.log" -mtime +30 -delete 2>/dev/null || true

exit $EXIT_CODE
