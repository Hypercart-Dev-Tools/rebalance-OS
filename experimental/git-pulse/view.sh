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
FILTER_DAYS=""
FILTER_DEVICE_ID=""
INCLUDE_LOCAL_UNSYNCED=0
OUTPUT_FILE=""

sanitize_tag() {
    printf '%s' "$1" | sed "s/'//g" | tr -cs 'A-Za-z0-9._-' '-' | sed 's/^-*//; s/-*$//'
}

current_device_id() {
    local current_hostname
    local current_host_tag
    local current_device_id

    current_hostname="${hostname:-$(scutil --get ComputerName 2>/dev/null || echo "${HOSTNAME:-unknown-host}")}"
    current_host_tag="$(sanitize_tag "$current_hostname")"
    [ -z "$current_host_tag" ] && current_host_tag="unknown-host"

    current_device_id="$(printf '%s' "${device_id:-$current_host_tag}" | tr '[:upper:]' '[:lower:]')"
    current_device_id="$(sanitize_tag "$current_device_id")"
    [ -z "$current_device_id" ] && current_device_id="$current_host_tag"

    printf '%s' "$current_device_id"
}

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
        --days)
            FILTER_DAYS="${2:?missing value for --days}"
            shift 2
            ;;
        --device-id)
            FILTER_DEVICE_ID="${2:?missing value for --device-id}"
            shift 2
            ;;
        --include-local-unsynced)
            INCLUDE_LOCAL_UNSYNCED=1
            shift
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

if [ -n "$FILTER_DATE" ] && [ -n "$FILTER_DAYS" ]; then
    echo "Use either --date or --days, not both." >&2
    exit 1
fi

if [ -n "$FILTER_DAYS" ]; then
    case "$FILTER_DAYS" in
        ''|*[!0-9]*)
            echo "--days must be a positive integer." >&2
            exit 1
            ;;
    esac
    if [ "$FILTER_DAYS" -lt 1 ]; then
        echo "--days must be at least 1." >&2
        exit 1
    fi
fi

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
today_local="$(date +"%Y-%m-%d")"
range_start_local=""

if [ -n "$FILTER_DAYS" ]; then
    range_start_local="$(date -v-"$((FILTER_DAYS - 1))"d +"%Y-%m-%d")"
fi

cleanup() {
    rm -f "$rendered_rows" "$rendered_output"
}
trap cleanup EXIT

local_day_in_scope() {
    local local_day="$1"

    if [ -n "$FILTER_DATE" ] && [ "$local_day" != "$FILTER_DATE" ]; then
        return 1
    fi
    if [ -n "$range_start_local" ] && { [[ "$local_day" < "$range_start_local" ]] || [[ "$local_day" > "$today_local" ]]; }; then
        return 1
    fi

    return 0
}

append_rendered_row() {
    local epoch="$1"
    local utc_iso="$2"
    local row_device_id="$3"
    local row_device_name="$4"
    local repo="$5"
    local branch="$6"
    local short_sha="$7"
    local subject="$8"
    local local_day
    local local_time

    local_day="$(date -r "$epoch" +"%Y-%m-%d")"
    if ! local_day_in_scope "$local_day"; then
        return
    fi

    local_time="$(date -r "$epoch" +"%H:%M %Z")"
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
        "$epoch" \
        "$local_day" \
        "$local_time" \
        "$utc_iso" \
        "$row_device_id" \
        "$row_device_name" \
        "$repo" \
        "$branch" \
        "$short_sha" \
        "$subject" >> "$rendered_rows"
}

metadata_found=0
for metadata_file in "$sync_repo_dir"/devices/*.yaml; do
    [ -e "$metadata_file" ] || continue
    metadata_found=1

    row_device_id="$(yaml_value "$metadata_file" "device_id")"
    row_device_name="$(yaml_value "$metadata_file" "device_name")"
    pulse_file_rel="$(yaml_value "$metadata_file" "pulse_file")"
    [ -z "$pulse_file_rel" ] && pulse_file_rel="pulse-$row_device_id.md"

    if [ -n "$FILTER_DEVICE_ID" ] && [ "$row_device_id" != "$FILTER_DEVICE_ID" ]; then
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
        append_rendered_row "$epoch" "$utc_iso" "$row_device_id" "$row_device_name" "$repo" "$branch" "$short_sha" "$subject"
    done < "$pulse_file"
done

if [ "$metadata_found" -eq 0 ]; then
    echo "No device metadata found under $sync_repo_dir/devices" >&2
    exit 1
fi

if [ "$INCLUDE_LOCAL_UNSYNCED" -eq 1 ]; then
    local_device_id="$(current_device_id)"
    local_device_name="${device_name:-${hostname:-$(scutil --get ComputerName 2>/dev/null || echo "${HOSTNAME:-unknown-device}")}}"

    if [ -z "$FILTER_DEVICE_ID" ] || [ "$FILTER_DEVICE_ID" = "$local_device_id" ]; then
        if declare -p repos >/dev/null 2>&1; then
            for repo_path in "${repos[@]}"; do
                if [ ! -d "$repo_path/.git" ]; then
                    continue
                fi
                repo_name=$(basename "$repo_path")

                while IFS=$'\t' read -r gd hash gs subject || [ -n "${gd:-}" ]; do
                    case "$gs" in
                        commit:*|"commit (initial):"*|"commit (amend):"*) ;;
                        *) continue ;;
                    esac

                    ts="${gd#*\{}"
                    ts="${ts%\}}"
                    ts_for_parse="${ts:0:22}${ts:23:2}"
                    if ! entry_epoch=$(date -j -f "%Y-%m-%dT%H:%M:%S%z" "$ts_for_parse" +%s 2>/dev/null); then
                        continue
                    fi

                    branch=$(git -C "$repo_path" branch --contains "$hash" --format='%(refname:short)' 2>/dev/null | head -n1)
                    [ -z "$branch" ] && branch="(detached)"

                    utc_iso="$(TZ=UTC date -r "$entry_epoch" +"%Y-%m-%dT%H:%M:%SZ")"
                    short_hash="${hash:0:7}"
                    clean_subject=${subject//$'\t'/ }
                    clean_subject=${clean_subject//$'\r'/ }

                    append_rendered_row "$entry_epoch" "$utc_iso" "$local_device_id" "$local_device_name" "$repo_name" "$branch" "$short_hash" "$clean_subject"
                done < <(git -C "$repo_path" log -g --date=iso-strict --pretty=format:'%gd%x09%H%x09%gs%x09%s')
            done
        fi
    fi
fi

{
    printf 'local_day\tlocal_time\tutc_time\tdevice_id\tdevice_name\trepo\tbranch\tshort_sha\tsubject\n'
    if [ -s "$rendered_rows" ]; then
        sort -t $'\t' -n -k1,1 -k2,10 "$rendered_rows" | awk '!seen[$0]++' | cut -f2-
    fi
} > "$rendered_output"

if [ -n "$OUTPUT_FILE" ]; then
    mkdir -p "$(dirname "$OUTPUT_FILE")"
    cp "$rendered_output" "$OUTPUT_FILE"
fi

cat "$rendered_output"
