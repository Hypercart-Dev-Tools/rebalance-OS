#!/bin/bash
# rebalance OS — Obsidian daily notes rollover (launchd wrapper)
#
# WHY A WRAPPER: launchd cannot exec python3 directly against a script under
# ~/Documents — that folder is TCC-protected and a directly-launched interpreter
# is denied (Operation not permitted). Running through /bin/bash inherits the
# Full Disk Access grant the other rebalance launchd jobs already use, so no new
# Full Disk Access entry is required. (Mirrors scripts/pulse_sync.sh.)

set -euo pipefail

REBALANCE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT="$REBALANCE_DIR/utils/obsidian_daily_rollover.py"

# Prefer the project venv; fall back to system python3 (script is stdlib-only).
if [ -x "$REBALANCE_DIR/.venv/bin/python" ]; then
    PYTHON="$REBALANCE_DIR/.venv/bin/python"
else
    PYTHON="/usr/bin/python3"
fi

exec "$PYTHON" "$SCRIPT" "$@"
