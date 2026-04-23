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
RECAP_PATH="$SCRIPT_DIR/recap.py"
HEALTH_PATH="$SCRIPT_DIR/health-check.py"
VALIDATE_PATH="$SCRIPT_DIR/validators.py"
SCOPE_PATH="$SCRIPT_DIR/scope.py"
DISCOVER_PATH="$SCRIPT_DIR/discover-repos.py"
PULSE_COMMON_PATH="$SCRIPT_DIR/pulse_common.py"
EXEC_SUMMARY_PATH="$SCRIPT_DIR/EXEC-SUMMARY.md"
TEAM_EXEC_SUMMARY_PATH="$SCRIPT_DIR/TEAM-EXEC-SUMMARY.md"
COLLECT_LINK_PATH="$BIN_DIR/git-pulse"
VIEW_LINK_PATH="$BIN_DIR/git-pulse-view"
RECAP_LINK_PATH="$BIN_DIR/git-pulse-recap"
HEALTH_LINK_PATH="$BIN_DIR/git-pulse-health"
VALIDATE_LINK_PATH="$BIN_DIR/git-pulse-validate"
SCOPE_LINK_PATH="$BIN_DIR/git-pulse-scope"
DISCOVER_LINK_PATH="$BIN_DIR/git-pulse-discover"
PULSE_COMMON_LINK_PATH="$BIN_DIR/pulse_common.py"
EXEC_SUMMARY_LINK_PATH="$BIN_DIR/EXEC-SUMMARY.md"
TEAM_EXEC_SUMMARY_LINK_PATH="$BIN_DIR/TEAM-EXEC-SUMMARY.md"
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

sanitize_tag() {
    printf '%s' "$1" | sed "s/'//g" | tr -cs 'A-Za-z0-9._-' '-' | sed 's/^-*//; s/-*$//'
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

set_config_array() {
    local key="$1"
    local comment="${2:-}"
    shift 2
    local temp_file
    local updated
    local skipping
    local line
    local value

    temp_file="$(mktemp "${TMPDIR:-/tmp}/git-pulse-config.XXXXXX")"
    updated=0
    skipping=0

    while IFS= read -r line || [ -n "$line" ]; do
        if [ "$skipping" -eq 1 ]; then
            if [ "$line" = ")" ]; then
                skipping=0
            fi
            continue
        fi

        if [ "$updated" -eq 0 ] && [[ "$line" == "$key=()" ]]; then
            printf '%s=(\n' "$key" >> "$temp_file"
            for value in "$@"; do
                printf '    "%s"\n' "$(escape_config_value "$value")" >> "$temp_file"
            done
            printf ')\n' >> "$temp_file"
            updated=1
            continue
        fi

        if [ "$updated" -eq 0 ] && [[ "$line" == "$key=(" ]]; then
            printf '%s=(\n' "$key" >> "$temp_file"
            for value in "$@"; do
                printf '    "%s"\n' "$(escape_config_value "$value")" >> "$temp_file"
            done
            printf ')\n' >> "$temp_file"
            updated=1
            skipping=1
            continue
        fi

        printf '%s\n' "$line" >> "$temp_file"
    done < "$CONFIG_DIR/config.sh"

    if [ "$updated" -eq 0 ]; then
        if [ -n "$comment" ]; then
            printf '\n%s\n' "$comment" >> "$temp_file"
        fi
        printf '%s=(\n' "$key" >> "$temp_file"
        for value in "$@"; do
            printf '    "%s"\n' "$(escape_config_value "$value")" >> "$temp_file"
        done
        printf ')\n' >> "$temp_file"
    fi

    mv "$temp_file" "$CONFIG_DIR/config.sh"
}

merge_unique_paths() {
    local value
    local existing
    local found
    local merged=()

    for value in "$@"; do
        [ -n "$value" ] || continue
        found=0
        for existing in "${merged[@]-}"; do
            if [ "$existing" = "$value" ]; then
                found=1
                break
            fi
        done
        if [ "$found" -eq 0 ]; then
            merged+=("$value")
        fi
    done

    printf '%s\n' "${merged[@]-}"
}

load_discovered_repos() {
    local discover_args=()
    local root

    for root in "$@"; do
        [ -n "$root" ] || continue
        discover_args+=("--root" "$root")
    done

    if [ "${#discover_args[@]}" -eq 0 ]; then
        return 0
    fi

    "$DISCOVER_PATH" "${discover_args[@]}"
}

generate_device_id() {
    local default_device_name
    local slug

    default_device_name="$(scutil --get ComputerName 2>/dev/null || echo "${HOSTNAME:-unknown-device}")"
    slug="$(printf '%s' "$default_device_name" | tr '[:upper:]' '[:lower:]')"
    slug="$(sanitize_tag "$slug")"

    if [ -n "$slug" ]; then
        printf '%s' "$slug"
    else
        uuidgen | tr '[:upper:]' '[:lower:]'
    fi
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

install_support_file() {
    local source_path="$1"
    local target_path="$2"

    if needs_launchd_copy "$source_path"; then
        rm -f "$target_path"
        cp "$source_path" "$target_path"
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
install_entrypoint "$RECAP_PATH" "$RECAP_LINK_PATH"
install_entrypoint "$HEALTH_PATH" "$HEALTH_LINK_PATH"
install_entrypoint "$VALIDATE_PATH" "$VALIDATE_LINK_PATH"
install_entrypoint "$SCOPE_PATH" "$SCOPE_LINK_PATH"
install_entrypoint "$DISCOVER_PATH" "$DISCOVER_LINK_PATH"
install_support_file "$PULSE_COMMON_PATH" "$PULSE_COMMON_LINK_PATH"
install_support_file "$EXEC_SUMMARY_PATH" "$EXEC_SUMMARY_LINK_PATH"
install_support_file "$TEAM_EXEC_SUMMARY_PATH" "$TEAM_EXEC_SUMMARY_LINK_PATH"

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

if ! declare -p repo_roots >/dev/null 2>&1; then
    repo_roots=(
        "$HOME/code"
        "$HOME/src"
        "$HOME/Projects"
    )
    set_config_array "repo_roots" "# Roots scanned for local GitHub repos during install." "${repo_roots[@]}"
    config_updated=1
fi

if [ -z "${repo_discovery_mode:-}" ]; then
    repo_discovery_mode="append"
    set_config_value "repo_discovery_mode" "$repo_discovery_mode" "# Repo discovery mode: append | replace | fill-if-empty | off"
    config_updated=1
fi

configured_repos=()
if declare -p repos >/dev/null 2>&1; then
    while IFS= read -r repo_path; do
        [ -n "$repo_path" ] || continue
        configured_repos+=("$repo_path")
    done <<EOF
$(printf '%s\n' "${repos[@]-}")
EOF
fi
configured_repo_count="${#configured_repos[@]}"

discovered_repos=()
while IFS= read -r repo_path; do
    [ -n "$repo_path" ] || continue
    discovered_repos+=("$repo_path")
done < <(load_discovered_repos "${repo_roots[@]}")

if [ "${repo_discovery_mode:-append}" != "off" ] && [ "${#discovered_repos[@]}" -gt 0 ]; then
    merged_repos=()
    case "$repo_discovery_mode" in
        append)
            while IFS= read -r repo_path; do
                [ -n "$repo_path" ] || continue
                merged_repos+=("$repo_path")
            done < <(merge_unique_paths "${configured_repos[@]-}" "${discovered_repos[@]}")
            ;;
        replace)
            while IFS= read -r repo_path; do
                [ -n "$repo_path" ] || continue
                merged_repos+=("$repo_path")
            done < <(merge_unique_paths "${discovered_repos[@]}")
            ;;
        fill-if-empty)
            if [ "$configured_repo_count" -eq 0 ]; then
                while IFS= read -r repo_path; do
                    [ -n "$repo_path" ] || continue
                    merged_repos+=("$repo_path")
                done < <(merge_unique_paths "${discovered_repos[@]}")
            else
                while IFS= read -r repo_path; do
                    [ -n "$repo_path" ] || continue
                    merged_repos+=("$repo_path")
                done < <(merge_unique_paths "${configured_repos[@]-}")
            fi
            ;;
        *)
            echo "ERROR: unsupported repo_discovery_mode=$repo_discovery_mode" >&2
            exit 1
            ;;
    esac

    merged_current=$(printf '%s\n' "${configured_repos[@]-}")
    merged_next=$(printf '%s\n' "${merged_repos[@]-}")
    if [ "$merged_current" != "$merged_next" ]; then
        repos=("${merged_repos[@]}")
        set_config_array "repos" "# Absolute repo paths monitored by git-pulse." "${repos[@]}"
        echo "Discovered ${#discovered_repos[@]} local GitHub repo(s); monitoring ${#repos[@]} total."
        config_updated=1
    fi
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
    echo "Recap install:     copied $RECAP_PATH to $RECAP_LINK_PATH"
    echo "Health install:    copied $HEALTH_PATH to $HEALTH_LINK_PATH"
    echo "Validate install:  copied $VALIDATE_PATH to $VALIDATE_LINK_PATH"
    echo "Scope install:     copied $SCOPE_PATH to $SCOPE_LINK_PATH"
    echo "Discover install:  copied $DISCOVER_PATH to $DISCOVER_LINK_PATH"
    echo "Refresh after repo pulls by re-running install.sh."
else
    echo "Collector install: symlinked $COLLECT_LINK_PATH -> $COLLECT_PATH"
    echo "View install:      symlinked $VIEW_LINK_PATH -> $VIEW_PATH"
    echo "Recap install:     symlinked $RECAP_LINK_PATH -> $RECAP_PATH"
    echo "Health install:    symlinked $HEALTH_LINK_PATH -> $HEALTH_PATH"
    echo "Validate install:  symlinked $VALIDATE_LINK_PATH -> $VALIDATE_PATH"
    echo "Scope install:     symlinked $SCOPE_LINK_PATH -> $SCOPE_PATH"
    echo "Discover install:  symlinked $DISCOVER_LINK_PATH -> $DISCOVER_PATH"
fi
echo "Test manually:   $COLLECT_LINK_PATH --dry-run"
echo "Unified view:    $VIEW_LINK_PATH --today"
echo "Recap reports:   $RECAP_LINK_PATH"
echo "Health check:    $HEALTH_LINK_PATH"
echo "Validate recap:  $VALIDATE_LINK_PATH <recap-file.md>"
echo "Scope section:   $SCOPE_LINK_PATH <recap-file.md> --section tldr|focus|observations"
echo "Discover repos:   $DISCOVER_LINK_PATH --root \"$HOME/code\""
echo "Tail logs:       tail -f $LOG_DIR/git-pulse.err"
echo "Uninstall:       launchctl unload $PLIST_PATH && rm $PLIST_PATH"
