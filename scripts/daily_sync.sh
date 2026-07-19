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


def classify_sync_outcome(result):
    """Return the scheduler outcome and exit code without hiding source errors."""
    errors = result.get("errors") or []
    if not errors:
        return "complete", 0

    # A migration failure means no collector can safely write to the database.
    # It is an infrastructure failure, rather than a degraded source refresh.
    if any(error.get("scope") == "migrations" for error in errors):
        return "fatal", 1

    # A non-migration error is only fatal when every attempted stage failed or
    # was skipped. Otherwise the scheduler completed useful work and should
    # allow the next run to self-heal the degraded source.
    successful_results = [
        entry for entry in result.get("results", [])
        if not entry.get("skipped") and not entry.get("error")
    ]
    if not successful_results:
        return "fatal", 1
    return "degraded", 0


db_path = resolve_database_path()
print(f"database={db_path}")
result = refresh_index(db_path)  # default recipe: raw sources + code/semantic/sync
result["sync_outcome"], exit_code = classify_sync_outcome(result)
print(json.dumps(result, indent=2, default=str))
sys.exit(exit_code)
PY
then
    EXIT_CODE=0
else
    EXIT_CODE=$?
fi

if [ $EXIT_CODE -eq 0 ]; then
    if grep -Fq '"sync_outcome": "degraded"' "$LOG_FILE"; then
        log "=== rebalance daily sync degraded; partial errors recorded (see JSON above) ==="
    else
        log "=== rebalance daily sync complete ==="
    fi
else
    log "=== rebalance daily sync failed fatally (see JSON above) ==="
fi

rb_trim_logs

exit $EXIT_CODE
