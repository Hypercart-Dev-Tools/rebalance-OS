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
#
# Policy: SCHEDULER.md (job com.rebalance-os.pulse-server).

set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/lib/scheduler_common.sh"

PORT="${PULSE_PORT:-8767}"

# Daemon: mark started only — exec replaces this shell, so an EXIT trap for
# completed/failed events would never fire. launchd KeepAlive owns restarts.
rb_job_mark_started "pulse-server"

exec "$PYTHON" scripts/pulse_server.py --port "$PORT" "$@"
