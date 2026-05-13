#!/bin/bash
# rebalance OS — start the local pulse FastAPI server (POC).
#
# Opt-in: launchd still regenerates web/pulse.html every 30 min. This server
# adds an interactive layer on top — real Refresh button + filter input.
# Loopback only; do not bind to a public interface.
#
#   Start:    scripts/pulse_server.sh
#   Open:     http://127.0.0.1:8767/
#   Stop:     Ctrl-C

set -euo pipefail

REBALANCE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="$REBALANCE_DIR/.venv/bin/python"
PORT="${PULSE_PORT:-8767}"

cd "$REBALANCE_DIR"
exec "$PYTHON" scripts/pulse_server.py --port "$PORT" "$@"
