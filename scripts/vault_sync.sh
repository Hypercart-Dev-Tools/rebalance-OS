#!/bin/bash
# rebalance OS — hourly vault refresh
# Runs hourly via launchd (com.rebalance-os.vault-sync) between 6 AM and 11 PM.
# Calls refresh_index(scope=["vault", "semantic"]) so notes edited during the
# day surface in the dashboard / pulse / semantic search without waiting for
# the daily 06:30 sync.
#
# Vault ingest is cheap (~0.02s with no changes; small fractions of a second
# per modified file) and offline, so running it on the hour does not impact
# laptop battery or block other work.
#
# Single source of truth: this calls the same `refresh_index` the MCP server
# exposes — no per-script duplication of the orchestration.
#
# Policy: SCHEDULER.md (job com.rebalance-os.vault-sync).

set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/lib/scheduler_common.sh"
rb_job_init "vault-sync" 14

log "=== rebalance vault sync starting ==="

# Freshness policy: "semantic" is included INTENTIONALLY as the follow-on
# stage — vault ingest alone updates raw tables only; the semantic backfill+
# embed is what makes edited notes searchable within the hour.
if "$PYTHON" - <<'PY' >> "$LOG_FILE" 2>&1
import json
import sys
from rebalance.ingest.index_ops import refresh_index
from rebalance.paths import resolve_database_path

db_path = resolve_database_path()
print(f"database={db_path}")
result = refresh_index(db_path, scope=["vault", "semantic"])
print(json.dumps(result, indent=2, default=str))
sys.exit(1 if result.get("errors") else 0)
PY
then
    EXIT_CODE=0
else
    EXIT_CODE=$?
fi

if [ $EXIT_CODE -eq 0 ]; then
    log "=== rebalance vault sync complete ==="
else
    log "=== rebalance vault sync finished with errors (see JSON above) ==="
fi

rb_trim_logs

exit $EXIT_CODE
