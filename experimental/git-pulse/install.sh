#!/bin/bash
# One-shot installer for the git-pulse collector.
# Idempotent: safe to re-run after editing config or updating collect.sh.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="$HOME/.config/git-pulse"
LOG_DIR="$CONFIG_DIR/logs"
BIN_DIR="$HOME/bin"
LAUNCH_AGENT_DIR="$HOME/Library/LaunchAgents"
PLIST_LABEL="com.user.git-pulse"
PLIST_PATH="$LAUNCH_AGENT_DIR/$PLIST_LABEL.plist"
COLLECT_PATH="$SCRIPT_DIR/collect.sh"
VIEW_PATH="$SCRIPT_DIR/view.sh"
REPORT_PATH="$SCRIPT_DIR/report.py"
COLLECT_LINK_PATH="$BIN_DIR/git-pulse"
VIEW_LINK_PATH="$BIN_DIR/git-pulse-view"
REPORT_LINK_PATH="$BIN_DIR/git-pulse-report"
LEGACY_CONFIG_DIR="$HOME/.config/git-history"
LEGACY_PLIST_PATH="$LAUNCH_AGENT_DIR/com.user.git-history.plist"

needs_launchd_copy() {
    case "$1" in
        "$HOME/Desktop"/*|"$HOME/Documents"/*|"$HOME/Downloads"/*)
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

escape_config_value() {
    printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

set_config_value() {
    local key="$1"
    local value="$2"
    local comment="${3:-}"
    local escaped_value
    local temp_file
    local updated
    local line

    escaped_value="$(escape_config_value "$value")"
    temp_file="$(mktemp "${TMPDIR:-/tmp}/git-pulse-config.XXXXXX")"
    updated=0

    while IFS= read -r line || [ -n "$line" ]; do
        if [ "$updated" -eq 0 ] && [[ "$line" == "$key="* ]]; then
            printf '%s="%s"\n' "$key" "$escaped_value" >> "$temp_file"
            updated=1
            continue
        fi
        printf '%s\n' "$line" >> "$temp_file"
    done < "$CONFIG_DIR/config.sh"

    if [ "$updated" -eq 0 ]; then
        if [ -n "$comment" ]; then
            printf '\n%s\n' "$comment" >> "$temp_file"
        fi
        printf '%s="%s"\n' "$key" "$escaped_value" >> "$temp_file"
    fi

    mv "$temp_file" "$CONFIG_DIR/config.sh"
}

generate_device_id() {
    uuidgen | tr '[:upper:]' '[:lower:]'
}

install_entrypoint() {
    local source_path="$1"
    local target_path="$2"

    chmod +x "$source_path"
    if needs_launchd_copy "$source_path"; then
        rm -f "$target_path"
        cp "$source_path" "$target_path"
        chmod +x "$target_path"
        INSTALL_MODE="copy"
    else
        ln -sfn "$source_path" "$target_path"
        INSTALL_MODE="symlink"
    fi
}

echo "Installing git-pulse collector..."

mkdir -p "$CONFIG_DIR" "$LOG_DIR" "$BIN_DIR" "$LAUNCH_AGENT_DIR"
install_entrypoint "$COLLECT_PATH" "$COLLECT_LINK_PATH"
LINK_MODE="$INSTALL_MODE"
install_entrypoint "$VIEW_PATH" "$VIEW_LINK_PATH"
install_entrypoint "$REPORT_PATH" "$REPORT_LINK_PATH"

if [ ! -f "$CONFIG_DIR/config.sh" ]; then
    if [ -f "$LEGACY_CONFIG_DIR/config.sh" ]; then
        cp "$LEGACY_CONFIG_DIR/config.sh" "$CONFIG_DIR/config.sh"
        echo "Copied existing config from $LEGACY_CONFIG_DIR/config.sh"
    else
        cp "$SCRIPT_DIR/config.example.sh" "$CONFIG_DIR/config.sh"
    fi
    echo "Created $CONFIG_DIR/config.sh"
    echo "Edit it to set repos and sync_repo_dir (and sync_repo if cloning is needed), then re-run install.sh."
    exit 0
fi

# shellcheck disable=SC1091
source "$CONFIG_DIR/config.sh"

config_updated=0
if [ -z "${device_id:-}" ]; then
    device_id="$(generate_device_id)"
    set_config_value "device_id" "$device_id" "# Stable per-machine identity used in filenames and metadata."
    echo "Generated device_id=$device_id"
    config_updated=1
fi

if [ -z "${device_name:-}" ]; then
    default_device_name="$(scutil --get ComputerName 2>/dev/null || echo "${HOSTNAME:-unknown-device}")"
    set_config_value "device_name" "$default_device_name"
    echo "Set device_name=\"$default_device_name\""
    config_updated=1
fi

if [ "$config_updated" -eq 1 ]; then
    # Reload config so the rest of the installer sees the generated values.
    # shellcheck disable=SC1091
    source "$CONFIG_DIR/config.sh"
fi

SYNC_REPO_DIR="${sync_repo_dir:-$CONFIG_DIR/repo}"
if [ ! -d "$SYNC_REPO_DIR/.git" ]; then
    if [ -z "${sync_repo:-}" ]; then
        echo "ERROR: sync_repo_dir=$SYNC_REPO_DIR is not a git repo and sync_repo is empty in $CONFIG_DIR/config.sh" >&2
        exit 1
    fi
    echo "Cloning $sync_repo to $SYNC_REPO_DIR..."
    git clone "$sync_repo" "$SYNC_REPO_DIR"
else
    echo "Sync repo already cloned at $SYNC_REPO_DIR"
fi

sed \
    -e "s|{{COLLECT_SCRIPT_PATH}}|$COLLECT_LINK_PATH|g" \
    -e "s|{{WORKING_DIRECTORY}}|$HOME|g" \
    -e "s|{{LOG_DIR}}|$LOG_DIR|g" \
    "$SCRIPT_DIR/com.user.git-pulse.plist.template" > "$PLIST_PATH"
echo "Wrote $PLIST_PATH"

# Clean up the old agent if it exists so only one scheduler is active.
if [ -f "$LEGACY_PLIST_PATH" ]; then
    launchctl unload "$LEGACY_PLIST_PATH" 2>/dev/null || true
    rm -f "$LEGACY_PLIST_PATH"
    echo "Removed legacy launchd agent $LEGACY_PLIST_PATH"
fi

# Reload: unload first so changes to StartInterval / paths take effect.
launchctl unload "$PLIST_PATH" 2>/dev/null || true
launchctl load "$PLIST_PATH"
echo "Loaded launchd agent $PLIST_LABEL"

echo
echo "Done. Collector fires every hour (and at load)."
if [ "$LINK_MODE" = "copy" ]; then
    echo "Collector install: copied $COLLECT_PATH to $COLLECT_LINK_PATH"
    echo "View install:      copied $VIEW_PATH to $VIEW_LINK_PATH"
    echo "Report install:    copied $REPORT_PATH to $REPORT_LINK_PATH"
    echo "Refresh after repo pulls by re-running install.sh."
else
    echo "Collector install: symlinked $COLLECT_LINK_PATH -> $COLLECT_PATH"
    echo "View install:      symlinked $VIEW_LINK_PATH -> $VIEW_PATH"
    echo "Report install:    symlinked $REPORT_LINK_PATH -> $REPORT_PATH"
fi
echo "Test manually:   $COLLECT_LINK_PATH --dry-run"
echo "Unified view:    $VIEW_LINK_PATH --today"
echo "HTML report:     $REPORT_LINK_PATH /path/to/combined.tsv --output /path/to/report.html"
echo "Tail logs:       tail -f $LOG_DIR/git-pulse.err"
echo "Uninstall:       launchctl unload $PLIST_PATH && rm $PLIST_PATH"
