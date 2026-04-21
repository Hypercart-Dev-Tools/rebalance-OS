#!/bin/bash
# One-shot installer for the git-history collector.
# Idempotent: safe to re-run after editing config or updating collect.sh.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="$HOME/.config/git-history"
LOG_DIR="$CONFIG_DIR/logs"
LAUNCH_AGENT_DIR="$HOME/Library/LaunchAgents"
PLIST_LABEL="com.user.git-history"
PLIST_PATH="$LAUNCH_AGENT_DIR/$PLIST_LABEL.plist"
COLLECT_PATH="$SCRIPT_DIR/collect.sh"

echo "Installing git-history collector..."

mkdir -p "$CONFIG_DIR" "$LOG_DIR" "$LAUNCH_AGENT_DIR"
chmod +x "$COLLECT_PATH"

if [ ! -f "$CONFIG_DIR/config.sh" ]; then
    cp "$SCRIPT_DIR/config.example.sh" "$CONFIG_DIR/config.sh"
    echo "Created $CONFIG_DIR/config.sh"
    echo "Edit it to set repos and sync_repo, then re-run install.sh."
    exit 0
fi

# shellcheck disable=SC1091
source "$CONFIG_DIR/config.sh"

if [ -z "${sync_repo:-}" ]; then
    echo "ERROR: sync_repo is empty in $CONFIG_DIR/config.sh" >&2
    exit 1
fi

SYNC_REPO_DIR="${sync_repo_dir:-$CONFIG_DIR/repo}"
if [ ! -d "$SYNC_REPO_DIR/.git" ]; then
    echo "Cloning $sync_repo to $SYNC_REPO_DIR..."
    git clone "$sync_repo" "$SYNC_REPO_DIR"
else
    echo "Sync repo already cloned at $SYNC_REPO_DIR"
fi

sed \
    -e "s|{{COLLECT_SCRIPT_PATH}}|$COLLECT_PATH|g" \
    -e "s|{{LOG_DIR}}|$LOG_DIR|g" \
    "$SCRIPT_DIR/com.user.git-history.plist.template" > "$PLIST_PATH"
echo "Wrote $PLIST_PATH"

# Reload: unload first so changes to StartInterval / paths take effect.
launchctl unload "$PLIST_PATH" 2>/dev/null || true
launchctl load "$PLIST_PATH"
echo "Loaded launchd agent $PLIST_LABEL"

echo
echo "Done. Collector fires every 10 minutes (and at load)."
echo "Test manually:   $COLLECT_PATH --dry-run"
echo "Tail logs:       tail -f $LOG_DIR/git-history.err"
echo "Uninstall:       launchctl unload $PLIST_PATH && rm $PLIST_PATH"
