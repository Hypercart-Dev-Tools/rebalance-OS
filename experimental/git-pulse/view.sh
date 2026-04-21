#!/bin/bash
# Render a unified git-pulse view across all registered device files.

set -euo pipefail

CONFIG_DIR="${GIT_PULSE_CONFIG_DIR:-${GIT_HISTORY_CONFIG_DIR:-$HOME/.config/git-pulse}}"
CONFIG_FILE="$CONFIG_DIR/config.sh"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "Config not found at $CONFIG_FILE" >&2
    echo "Run install.sh to set up." >&2
    exit 1
fi

# shellcheck disable=SC1090
source "$CONFIG_FILE"

: "${sync_repo_dir:=$CONFIG_DIR/repo}"

FILTER_DATE=""
FILTER_DEVICE_ID=""
OUTPUT_FILE=""

while [ "$#" -gt 0 ]; do
    case "$1" in
        --today)
            FILTER_DATE="$(date +"%Y-%m-%d")"
            shift
            ;;
        --date)
            FILTER_DATE="${2:?missing value for --date}"
            shift 2
            ;;
        --device-id)
            FILTER_DEVICE_ID="${2:?missing value for --device-id}"
            shift 2
            ;;
        --output)
            OUTPUT_FILE="${2:?missing value for --output}"
            shift 2
            ;;
        *)
            echo "Unknown argument: $1" >&2
            exit 1
            ;;
    esac
done

if [ ! -d "$sync_repo_dir/.git" ]; then
    echo "Sync repo not found at $sync_repo_dir" >&2
    exit 1
fi

yaml_value() {
    local file="$1"
    local key="$2"
    local value

    value=$(sed -n "s/^$key: //p" "$file" | head -n1)
    value=${value#\"}
    value=${value%\"}
    value=${value//\\\"/\"}
    value=${value//\\\\/\\}
    printf '%s' "$value"
}

rendered_rows=$(mktemp "${TMPDIR:-/tmp}/git-pulse-view.rows.XXXXXX")
rendered_output=$(mktemp "${TMPDIR:-/tmp}/git-pulse-view.out.XXXXXX")

cleanup() {
    rm -f "$rendered_rows" "$rendered_output"
}
trap cleanup EXIT

metadata_found=0
for metadata_file in "$sync_repo_dir"/devices/*.yaml; do
    [ -e "$metadata_file" ] || continue
    metadata_found=1

    device_id="$(yaml_value "$metadata_file" "device_id")"
    device_name="$(yaml_value "$metadata_file" "device_name")"
    pulse_file_rel="$(yaml_value "$metadata_file" "pulse_file")"
    [ -z "$pulse_file_rel" ] && pulse_file_rel="pulse-$device_id.md"

    if [ -n "$FILTER_DEVICE_ID" ] && [ "$device_id" != "$FILTER_DEVICE_ID" ]; then
        continue
    fi

    pulse_file="$sync_repo_dir/$pulse_file_rel"
    [ -f "$pulse_file" ] || continue

    while IFS=$'\t' read -r epoch utc_iso repo branch short_sha subject || [ -n "${epoch:-}" ]; do
        case "$epoch" in
            ""|\#*)
                continue
                ;;
        esac

        if [[ "$epoch" == '<!--'* ]]; then
            continue
        fi

        case "$epoch" in
            *[!0-9]*)
                continue
                ;;
        esac

        local_day="$(date -r "$epoch" +"%Y-%m-%d")"
        if [ -n "$FILTER_DATE" ] && [ "$local_day" != "$FILTER_DATE" ]; then
            continue
        fi

        local_time="$(date -r "$epoch" +"%Y-%m-%d %H:%M %Z")"
        printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
            "$epoch" \
            "$local_time" \
            "$utc_iso" \
            "$device_id" \
            "$device_name" \
            "$repo" \
            "$branch" \
            "$short_sha" \
            "$subject" >> "$rendered_rows"
    done < "$pulse_file"
done

if [ "$metadata_found" -eq 0 ]; then
    echo "No device metadata found under $sync_repo_dir/devices" >&2
    exit 1
fi

{
    echo "# git-pulse view"
    echo "# generated_at_local: $(date +"%Y-%m-%d %H:%M %Z")"
    if [ -n "$FILTER_DATE" ]; then
        echo "# filter_date_local: $FILTER_DATE"
    fi
    if [ -n "$FILTER_DEVICE_ID" ]; then
        echo "# filter_device_id: $FILTER_DEVICE_ID"
    fi
    echo "# columns: local_time\tutc_time\tdevice_id\tdevice_name\trepo\tbranch\tshort_sha\tsubject"
    if [ -s "$rendered_rows" ]; then
        sort -n -k1,1 "$rendered_rows" | cut -f2-
    fi
} > "$rendered_output"

if [ -n "$OUTPUT_FILE" ]; then
    mkdir -p "$(dirname "$OUTPUT_FILE")"
    cp "$rendered_output" "$OUTPUT_FILE"
fi

cat "$rendered_output"
