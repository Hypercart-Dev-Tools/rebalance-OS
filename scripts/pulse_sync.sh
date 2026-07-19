#!/bin/bash
# rebalance OS — hourly pulse publish
# Runs hourly via launchd (com.rebalance-os.pulse-sync) between 6 AM and 11 PM.
# Calls publish_pulse() to render today's + yesterday's activity to a markdown
# file in a private git repo and push it. The push is only done when content
# actually changed since the previous run.
#
# Single source of truth: this is the same orchestration the MCP publish_pulse
# tool exposes to interactive agents.
#
# Freshness policy: this job READS what the ingest jobs wrote — it does not
# refresh sources itself. The :00 slot deliberately trails the previous hour's
# vault (:15) and github (:45) syncs, so the pulse reflects data at most ~1h old.
#
# Policy: SCHEDULER.md (job com.rebalance-os.pulse-sync).

set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/lib/scheduler_common.sh"
rb_job_init "pulse-sync" 14

log "=== rebalance pulse sync starting ==="

"$PYTHON" - <<'PY' >> "$LOG_FILE" 2>&1
import json
import os
import sys
from rebalance.ingest.pulse import publish_pulse
from rebalance.paths import resolve_database_path

db_path = resolve_database_path()
print(f"database={db_path}")
# Push is on by default. A device can opt out (render + commit locally only,
# letting the git-pulse collector own the push) by setting PULSE_PUSH=false in
# its launchd plist — this avoids redundant push conflicts on the shared
# live-pulse.md when origin advances between runs.
push = os.environ.get("PULSE_PUSH", "true").strip().lower() not in ("0", "false", "no", "off")
print(f"push={push} (PULSE_PUSH={os.environ.get('PULSE_PUSH', 'unset')})")

# Reconcile step (GH-152): fetch origin and rebase the local mirror onto it so
# the dashboard-read freshness signals don't freeze. Failure is surfaced LOUDLY
# but is NON-FATAL: reconcile is a freshness optimization, not a prerequisite for
# publishing, so a diverged/conflicting mirror must not brick the hourly publish.
from pathlib import Path
from rebalance.ingest.config import get_pulse_config
from rebalance.ingest.pulse import reconcile_pulse_mirror, PulseReconcileError

target = get_pulse_config().get("pulse_target_path")
if not target:
    print("WARNING: pulse_target_path not configured — skipping mirror reconcile", file=sys.stderr)
else:
    target_path = Path(target).expanduser().resolve()
    print(f"Reconciling pulse mirror at {target_path}...")
    try:
        reconcile_pulse_mirror(target_path)
        print("Reconciliation successful.")
    except PulseReconcileError as exc:
        # Loud, non-fatal: publish still proceeds with the mirror as-is.
        print(f"WARNING: pulse mirror reconcile failed — publishing anyway: {exc}", file=sys.stderr)

result = publish_pulse(db_path, dry_run=False, push=push)
# Drop the rendered markdown from the log to keep it readable; the file on
# disk is the artifact.
result.pop("markdown", None)
print(json.dumps(result, indent=2, default=str))

if not result.get("ok"):
    sys.exit(1)

git = result.get("git") or {}
if git.get("git_error"):
    sys.exit(2)
sys.exit(0)
PY
EXIT_CODE=$?

case $EXIT_CODE in
    0) log "=== pulse sync complete ===" ;;
    1) log "=== pulse sync FAILED (config or render error) ===" ;;
    2) log "=== pulse sync FAILED (git error — see JSON) ===" ;;
    *) log "=== pulse sync exited with code $EXIT_CODE ===" ;;
esac

rb_trim_logs

exit $EXIT_CODE
