#!/bin/bash
# rebalance OS — 30-minute pulse web mirror refresh
# Runs every 30 min via launchd (com.rebalance-os.pulse-web-sync) between
# 6:00 AM and 11:30 PM. Calls scripts/pulse_web.py to regenerate web/pulse.html
# from the same SQLite knowledge base the TUI dashboard reads.
#
# This is the local HTML mirror, not the markdown→private-repo flow. The
# markdown publish lives in pulse_sync.sh on a separate hourly schedule.
#
# Freshness policy: read-only derived stage — renders whatever the ingest
# jobs (daily/vault/github sync) last wrote. It never refreshes sources.
#
# Robustness notes:
#   - pulse_web.py writes atomically (tmp + replace), so a crashed run leaves
#     the previous web/pulse.html in place rather than truncating it.
#   - Reads SQLite in WAL mode and does not block the writers (daily-sync,
#     vault-sync). PRAGMA busy_timeout=30000 covers the edge cases.
#   - No network calls, no git push. Local file only.
#
# Policy: SCHEDULER.md (job com.rebalance-os.pulse-web-sync).

set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/lib/scheduler_common.sh"
rb_job_init "pulse-web-sync" 14

log "=== rebalance pulse-web sync starting ==="

if "$PYTHON" scripts/pulse_web.py >> "$LOG_FILE" 2>&1; then
    EXIT_CODE=0
    log "=== pulse-web sync complete ==="
else
    EXIT_CODE=$?
    log "=== pulse-web sync FAILED (exit $EXIT_CODE) ==="
fi

rb_trim_logs

exit $EXIT_CODE
