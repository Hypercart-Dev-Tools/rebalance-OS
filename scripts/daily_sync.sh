#!/bin/bash
# rebalance OS — daily data sync
# Runs on boot and daily via launchd. Refreshes all data sources
# so the MCP server always has fresh context.
#
# Install: see scripts/install_scheduler.sh

set -euo pipefail

# --- Configuration ---
REBALANCE_DIR="/Users/noelsaw/Documents/Obsidian Vault/rebalance-OS"
DATABASE="$REBALANCE_DIR/rebalance.db"
PYTHON="$REBALANCE_DIR/.venv/bin/python"
CLI="$REBALANCE_DIR/.venv/bin/rebalance"
LOG_DIR="$REBALANCE_DIR/temp/logs"

# Vault path: read from canonical config (temp/rbos.config). Falls back to the
# legacy path if the config key is missing so the cron still runs.
VAULT_PATH=$("$PYTHON" -c "from rebalance.ingest.config import get_vault_path; print(get_vault_path() or '')")
if [ -z "$VAULT_PATH" ]; then
    VAULT_PATH="/Users/noelsaw/Documents/Obsidian Vault"
fi

mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/daily_sync_$(date +%Y-%m-%d).log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

log "=== rebalance daily sync starting ==="

# 1. Vault notes — parse, chunk, keywords (delta: skips unchanged files)
log "Syncing vault notes..."
"$CLI" ingest notes --vault "$VAULT_PATH" --database "$DATABASE" >> "$LOG_FILE" 2>&1 \
    && log "  Vault notes: OK" \
    || log "  Vault notes: FAILED"

# 2. Embeddings — embed new/changed chunks (skips already-embedded)
log "Updating embeddings..."
"$CLI" ingest embed --database "$DATABASE" --batch-size 16 >> "$LOG_FILE" 2>&1 \
    && log "  Embeddings: OK" \
    || log "  Embeddings: FAILED"

# 3. GitHub activity scan
GITHUB_TOKEN=$("$PYTHON" -c "from rebalance.ingest.config import get_github_token; t=get_github_token(); print(t or '')")
if [ -n "$GITHUB_TOKEN" ]; then
    log "Scanning GitHub activity..."
    "$CLI" github-scan --token "$GITHUB_TOKEN" --database "$DATABASE" >> "$LOG_FILE" 2>&1 \
        && log "  GitHub scan: OK" \
        || log "  GitHub scan: FAILED"
else
    log "  GitHub scan: SKIPPED (no token configured)"
fi

# 4. Google Calendar sync (30 days back, 14 days forward)
log "Syncing Google Calendar..."
"$CLI" calendar-sync --database "$DATABASE" --days-back 30 --days-forward 14 >> "$LOG_FILE" 2>&1 \
    && log "  Calendar sync: OK" \
    || log "  Calendar sync: FAILED"

# 5. Sleuth reminders sync (do not fail the whole pipeline if Sleuth is down)
log "Syncing Sleuth reminders..."
"$CLI" sleuth-sync --all --database-path "$DATABASE" >> "$LOG_FILE" 2>&1 \
    && log "  Sleuth reminders: OK" \
    || log "  Sleuth reminders: FAILED"

# 6. Cleanup old logs (keep 30 days)
find "$LOG_DIR" -name "daily_sync_*.log" -mtime +30 -delete 2>/dev/null || true

log "=== rebalance daily sync complete ==="
