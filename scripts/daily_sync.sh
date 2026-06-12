#!/bin/bash
# rebalance OS — daily data sync
# Runs on boot and daily via launchd. Calls refresh_index() (default recipe:
# all raw sources + code/semantic/sync) so the MCP server always has fresh context.
#
# Single source of truth: this is the same orchestration the MCP
# refresh_index tool exposes to interactive agents.
#
# Policy: SCHEDULER.md (job com.rebalance-os.daily-sync).
# Install: see scripts/install_scheduler.sh

set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/lib/scheduler_common.sh"
rb_job_init "daily-sync" 30

log "=== rebalance daily sync starting ==="

# refresh_index orchestrates: vault ingest+embed -> github scan+sync+embed ->
# calendar -> sleuth -> unified semantic backfill+embed. Per-scope failures
# are captured in the result.errors list rather than aborting the run.
# DB path resolves via rebalance.paths.resolve_database_path() so we hit the
# same canonical location the dashboard/MCP reads from — never a stale
# project-tree rebalance.db left behind by an older script.
if "$PYTHON" - <<'PY' >> "$LOG_FILE" 2>&1
import json
import sys
from rebalance.ingest.index_ops import refresh_index
from rebalance.paths import resolve_database_path

db_path = resolve_database_path()
print(f"database={db_path}")
result = refresh_index(db_path)  # default recipe: raw sources + code/semantic/sync
print(json.dumps(result, indent=2, default=str))
sys.exit(1 if result.get("errors") else 0)
PY
then
    EXIT_CODE=0
else
    EXIT_CODE=$?
fi

if [ $EXIT_CODE -eq 0 ]; then
    log "=== rebalance daily sync complete ==="
else
    log "=== rebalance daily sync finished with errors (see JSON above) ==="
fi

rb_trim_logs

exit $EXIT_CODE
