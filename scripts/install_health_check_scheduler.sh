#!/bin/bash
# Install (or reinstall) the rebalance OS hourly health check.
#
# What this does:
#   1. Renders com.rebalance-os.health-check.plist.template (substituting
#      {{REBALANCE_DIR}} and the venv python for {{PYTHON}}) into
#      ~/Library/LaunchAgents/.
#   2. Loads it so macOS runs health_issue_reporter.py --close every hour on
#      the hour — FAIL-only, no LLM, cheap and fast.
#
# Usage:
#   bash scripts/install_health_check_scheduler.sh
#
# Policy: SCHEDULER.md (job com.rebalance-os.health-check).

set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/lib/install_common.sh"

echo "Installing rebalance OS hourly health check..."
echo "  REBALANCE_DIR=$REBALANCE_DIR"

rb_install_launchd_job "com.rebalance-os.health-check"

echo
echo "Done! The health check runs every hour on the hour (FAIL-only, no LLM)."
echo
echo "Commands:"
echo "  Check status: launchctl list | grep health-check"
echo "  View logs:    cat $REBALANCE_DIR/temp/logs/health-check-stderr.log"
echo "  Uninstall:    launchctl unload $RB_PLIST_DEST && rm $RB_PLIST_DEST"
