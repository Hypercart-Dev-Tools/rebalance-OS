#!/bin/bash
# rebalance OS — Apple Reminders Phase 0 spike wrapper
#
# Purpose:
#   Run the local Apple Reminders probe through a stable bash entrypoint so the
#   operator can grant Full Disk Access to `/bin/bash` (or the host app) and
#   rerun the spike consistently.
#
# Usage:
#   bash scripts/apple_reminders.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REBALANCE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON="$REBALANCE_DIR/.venv/bin/python"
LOG_DIR="$REBALANCE_DIR/temp/logs"

if [ ! -x "$PYTHON" ]; then
    PYTHON="python3"
fi

export PYTHONPATH="$REBALANCE_DIR/src${PYTHONPATH:+:$PYTHONPATH}"

mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/apple_reminders_spike_$(date +%Y-%m-%d).log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

cd "$REBALANCE_DIR"

log "=== Apple Reminders Phase 0 spike starting ==="
log "python=$PYTHON"

if "$PYTHON" temp/apple_reminders_spike.py 2>&1 | tee -a "$LOG_FILE"; then
    EXIT_CODE=0
else
    EXIT_CODE=$?
fi

if [ $EXIT_CODE -eq 0 ]; then
    log "=== Apple Reminders Phase 0 spike complete ==="
else
    log "=== Apple Reminders Phase 0 spike finished with exit code $EXIT_CODE ==="
fi

exit $EXIT_CODE
