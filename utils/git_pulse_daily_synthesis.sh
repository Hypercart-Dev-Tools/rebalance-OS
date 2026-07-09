#!/bin/bash
# rebalance OS — Git Pulse daily synthesis (launchd wrapper, GH-114)
#
# WHY A WRAPPER: the optional Obsidian vault write reads/writes ~/Documents,
# which is TCC-protected — a directly-launched interpreter is denied. Running
# through /bin/bash inherits the Full Disk Access grant the other rebalance
# launchd jobs already use, so no new Full Disk Access entry is needed.
# (Mirrors utils/obsidian_daily_sync.sh.) The optional CLIO write does not
# need this (git-pulse-sync lives outside ~/Documents) but shares the wrapper
# since both destinations come out of the same script/run.
#
# Requires the project venv — it imports the rebalance package (pulse
# snapshot + Gemini synthesis). Fail loudly if absent rather than silently
# degrading.

set -euo pipefail

REBALANCE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT="$REBALANCE_DIR/utils/git_pulse_daily_synthesis.py"
PYTHON="$REBALANCE_DIR/.venv/bin/python"

if [ ! -x "$PYTHON" ]; then
    echo "ERROR: rebalance venv not found at $PYTHON — git-pulse-daily-synthesis needs it." >&2
    exit 1
fi

exec "$PYTHON" "$SCRIPT" "$@"
