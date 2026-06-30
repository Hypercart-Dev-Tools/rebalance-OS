#!/bin/bash

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_TEMPLATE="$PROJECT_DIR/com.user.stickies2obsidian.plist.template"
SCRIPT_PATH="$PROJECT_DIR/stickies2obsidian.sh"
PLIST_DEST="$HOME/Library/LaunchAgents/com.user.stickies2obsidian.plist"
STICKIES_DIR_DEFAULT="$HOME/Library/Containers/com.apple.stickies/Data/Library/Stickies"
OBSIDIAN_FILE_DEFAULT="$HOME/Documents/ObsidianVault/Stickies.md"
STATE_FILE_DEFAULT="$HOME/.stickies2obsidian.state"

STICKIES_DIR="${STICKIES_DIR:-$STICKIES_DIR_DEFAULT}"
OBSIDIAN_FILE="${OBSIDIAN_FILE:-$OBSIDIAN_FILE_DEFAULT}"
STATE_FILE="${STATE_FILE:-$STATE_FILE_DEFAULT}"

usage() {
    cat <<'EOF'
Usage:
  install_launch_agent.sh [--obsidian-file PATH] [--state-file PATH] [--stickies-dir PATH]
EOF
}

xml_escape_for_sed() {
    local raw="$1"
    local xml_escaped
    xml_escaped="$(printf '%s' "$raw" | sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g')"
    printf '%s' "$xml_escaped" | sed 's/[\/&]/\\&/g'
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --obsidian-file)
            [ "$#" -ge 2 ] || {
                usage >&2
                exit 1
            }
            OBSIDIAN_FILE="$2"
            shift 2
            ;;
        --state-file)
            [ "$#" -ge 2 ] || {
                usage >&2
                exit 1
            }
            STATE_FILE="$2"
            shift 2
            ;;
        --stickies-dir)
            [ "$#" -ge 2 ] || {
                usage >&2
                exit 1
            }
            STICKIES_DIR="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            printf 'Unknown argument: %s\n' "$1" >&2
            usage >&2
            exit 1
            ;;
    esac
done

[ -f "$PLIST_TEMPLATE" ] || {
    printf 'Missing plist template: %s\n' "$PLIST_TEMPLATE" >&2
    exit 1
}
[ -f "$SCRIPT_PATH" ] || {
    printf 'Missing sync script: %s\n' "$SCRIPT_PATH" >&2
    exit 1
}

mkdir -p "$(dirname "$PLIST_DEST")"

ESCAPED_SCRIPT_PATH="$(xml_escape_for_sed "$SCRIPT_PATH")"
ESCAPED_STICKIES_DIR="$(xml_escape_for_sed "$STICKIES_DIR")"
ESCAPED_OBSIDIAN_FILE="$(xml_escape_for_sed "$OBSIDIAN_FILE")"
ESCAPED_STATE_FILE="$(xml_escape_for_sed "$STATE_FILE")"

sed \
    -e "s/{{SCRIPT_PATH}}/$ESCAPED_SCRIPT_PATH/g" \
    -e "s/{{STICKIES_DIR}}/$ESCAPED_STICKIES_DIR/g" \
    -e "s/{{OBSIDIAN_FILE}}/$ESCAPED_OBSIDIAN_FILE/g" \
    -e "s/{{STATE_FILE}}/$ESCAPED_STATE_FILE/g" \
    "$PLIST_TEMPLATE" > "$PLIST_DEST"

launchctl unload "$PLIST_DEST" >/dev/null 2>&1 || true
launchctl load "$PLIST_DEST"

printf 'Installed launchd agent:\n'
printf '  Script: %s\n' "$SCRIPT_PATH"
printf '  Plist:  %s\n' "$PLIST_DEST"
printf '  Target: %s\n' "$OBSIDIAN_FILE"
printf '  State:  %s\n' "$STATE_FILE"
printf '  Source: %s\n' "$STICKIES_DIR"
printf '  Logs:   /tmp/stickies2obsidian.log, /tmp/stickies2obsidian.err\n'
