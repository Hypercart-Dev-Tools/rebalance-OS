#!/bin/bash
# rebalance OS — hourly vault refresh
# Runs hourly via launchd (com.rebalance-os.vault-sync) between 6 AM and 11 PM.
# Calls refresh_index(scope=["vault"]) so notes edited during the day surface
# in the dashboard / pulse / semantic search without waiting for the daily
# 06:30 sync.
#
# Vault ingest is cheap (~0.02s with no changes; small fractions of a second
# per modified file) and offline, so running it on the hour does not impact
# laptop battery or block other work.
#
# Single source of truth: this calls the same `refresh_index` the MCP server
# exposes — no per-script duplication of the orchestration.

set -euo pipefail

REBALANCE_DIR="/Users/noelsaw/Documents/rebalance-OS"
PYTHON="$REBALANCE_DIR/.venv/bin/python"
DATABASE="$REBALANCE_DIR/rebalance.db"
LOG_DIR="$REBALANCE_DIR/temp/logs"

mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/vault_sync_$(date +%Y-%m-%d).log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

cd "$REBALANCE_DIR"

log "=== rebalance vault sync starting ==="

"$PYTHON" - <<'PY' >> "$LOG_FILE" 2>&1
import json
import sys
from pathlib import Path
from rebalance.ingest.index_ops import refresh_index

result = refresh_index(Path("rebalance.db").resolve(), scope=["vault"])
print(json.dumps(result, indent=2, default=str))
sys.exit(1 if result.get("errors") else 0)
PY
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    log "=== rebalance vault sync complete ==="
else
    log "=== rebalance vault sync finished with errors (see JSON above) ==="
fi

# Retain 14 days of vault sync logs (more frequent than daily, so trim sooner).
find "$LOG_DIR" -name "vault_sync_*.log" -mtime +14 -delete 2>/dev/null || true

exit $EXIT_CODE
