#!/bin/bash
# Install (or reinstall) the rebalance OS 3×-daily health check with LLM triage.
#
# What this does:
#   1. Renders com.rebalance-os.health-check-triage.plist.template (substituting
#      {{REBALANCE_DIR}} and the venv python for {{PYTHON}}) into
#      ~/Library/LaunchAgents/.
#   2. Loads it so macOS runs health_issue_reporter.py at 8 AM, 2 PM, and 8 PM
#      with --warn --close --llm-triage (daily limit 8, per-run cap 5).
#
# SECRETS: the LLM triage needs GEMINI_API_KEY. NEVER add it to the
# template (tracked in git). After installing, either add it to the RENDERED
# plist's EnvironmentVariables dict (~/Library/LaunchAgents is gitignored) and
# re-run `launchctl unload`/`load`, or rely on the reporter's keyring lookup.
# Reinstalling OVERWRITES the rendered plist — a hand-added key must be re-added.
#
# Usage:
#   bash scripts/install_health_check_triage_scheduler.sh
#
# Policy: SCHEDULER.md (job com.rebalance-os.health-check-triage).

set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/lib/install_common.sh"

echo "Installing rebalance OS health check with LLM triage (8 AM / 2 PM / 8 PM)..."
echo "  REBALANCE_DIR=$REBALANCE_DIR"

DEST="$HOME/Library/LaunchAgents/com.rebalance-os.health-check-triage.plist"
if [ -f "$DEST" ] && grep -q "GEMINI_API_KEY" "$DEST"; then
    echo
    echo "  WARNING: the currently installed plist carries a hand-added"
    echo "  GEMINI_API_KEY. Reinstalling will remove it — re-add it to"
    echo "  $DEST afterwards and reload the job."
    echo
fi

rb_install_launchd_job "com.rebalance-os.health-check-triage"

echo
echo "Done! LLM-triaged health checks run at 8 AM, 2 PM, and 8 PM."
echo
echo "Commands:"
echo "  Check status: launchctl list | grep health-check-triage"
echo "  View logs:    cat $REBALANCE_DIR/temp/logs/health-check-triage-stderr.log"
echo "  Disable LLM:  add <key>HEALTH_LLM_DISABLE</key><string>1</string> to the rendered plist"
echo "  Uninstall:    launchctl unload $RB_PLIST_DEST && rm $RB_PLIST_DEST"
