#!/bin/bash
# rebalance OS — hourly github sync
# Runs hourly via launchd to keep github context fresh.
#
# Policy: SCHEDULER.md (job com.rebalance-os.github-sync).

set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/lib/scheduler_common.sh"
rb_job_init "github-sync" 14

log "=== rebalance hourly github sync starting ==="

# Freshness policy: intentionally NO "semantic" follow-on here. GitHub rows
# land in the raw tables hourly; the github -> semantic backfill+embed runs
# in the 06:30 daily sync. The gap is observable as the
# github_documents_missing_from_semantic drift metric (index_status).
if "$PYTHON" - <<'PY' >> "$LOG_FILE" 2>&1
import json
import sys
from rebalance.ingest.index_ops import refresh_index
from rebalance.paths import resolve_database_path

db_path = resolve_database_path()
print(f"database={db_path}")
result = refresh_index(db_path, scope=["github"])
print(json.dumps(result, indent=2, default=str))
sys.exit(1 if result.get("errors") else 0)
PY
then
    EXIT_CODE=0
else
    EXIT_CODE=$?
fi

if [ $EXIT_CODE -eq 0 ]; then
    log "=== rebalance hourly github sync complete ==="
else
    log "=== rebalance hourly github sync finished with errors ==="
fi

rb_trim_logs

exit $EXIT_CODE
