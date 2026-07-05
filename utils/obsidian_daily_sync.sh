#!/bin/bash
# rebalance OS — Obsidian daily activity sync (launchd wrapper, GH-112)
#
# WHY A WRAPPER: launchd cannot exec python3 directly against a script that reads
# ~/Documents — that folder is TCC-protected and a directly-launched interpreter
# is denied (Operation not permitted). Running through /bin/bash inherits the Full
# Disk Access grant the other rebalance launchd jobs already use, so no new Full
# Disk Access entry is needed. (Mirrors utils/obsidian_rollover.sh.)
#
# Unlike the stdlib-only rollover, this job REQUIRES the project venv — it imports
# the rebalance package (pulse snapshot + Gemini synthesis). Fail loudly if absent
# rather than silently degrading.

set -euo pipefail

REBALANCE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT="$REBALANCE_DIR/utils/obsidian_daily_sync.py"
PYTHON="$REBALANCE_DIR/.venv/bin/python"

if [ ! -x "$PYTHON" ]; then
    echo "ERROR: rebalance venv not found at $PYTHON — obsidian-daily-sync needs it." >&2
    exit 1
fi

exec "$PYTHON" "$SCRIPT" "$@"
