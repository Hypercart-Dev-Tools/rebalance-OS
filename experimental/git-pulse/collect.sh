#!/bin/bash
# Collect new local commits from each watched repo since last run,
# append to this machine's pulse file in the sync repo, commit, push.

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

sanitize_tag() {
    printf '%s' "$1" | sed "s/'//g" | tr -cs 'A-Za-z0-9._-' '-' | sed 's/^-*//; s/-*$//'
}

legacy_sanitize_tag() {
    printf '%s' "$1" | tr -cs 'A-Za-z0-9._-' '-' | sed 's/^-*//; s/-*$//'
}

yaml_escape() {
    printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

utc_iso_from_epoch() {
    TZ=UTC date -r "$1" +"%Y-%m-%dT%H:%M:%SZ"
}

read_hardware_uuid() {
    # Stable hardware-backed identifier that survives renames and OS reinstalls.
    # Used downstream as the canonical dedupe key in the SQLite history layer;
    # the friendly slug-based device_id remains for filenames and display.
    local uuid=""
    if command -v ioreg >/dev/null 2>&1; then
        uuid="$(ioreg -rd1 -c IOPlatformExpertDevice 2>/dev/null \
            | awk -F'"' '/IOPlatformUUID/ { print $4; exit }')"
    fi
    if [ -z "$uuid" ] && [ -r /etc/machine-id ]; then
        uuid="$(cat /etc/machine-id 2>/dev/null)"
    fi
    printf '%s' "$uuid"
}

escape_config_value() {
    printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

set_config_value() {
    local key="$1"
    local value="$2"
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
    done < "$CONFIG_FILE"

    if [ "$updated" -eq 0 ]; then
        printf '\n%s="%s"\n' "$key" "$escaped_value" >> "$temp_file"
    fi

    mv "$temp_file" "$CONFIG_FILE"
}

canonical_device_id_from_hostname() {
    local raw_hostname="$1"
    local slug

    slug="$(printf '%s' "$raw_hostname" | tr '[:upper:]' '[:lower:]')"
    slug="$(sanitize_tag "$slug")"
    [ -n "$slug" ] || slug="unknown-host"
    printf '%s' "$slug"
}

legacy_device_id_candidates() {
    local raw_name="$1"
    local lower_name
    local legacy_slug

    lower_name="$(printf '%s' "$raw_name" | tr '[:upper:]' '[:lower:]')"
    legacy_slug="$(legacy_sanitize_tag "$lower_name")"
    if [ -n "$legacy_slug" ]; then
        printf '%s\n' "$legacy_slug"
    fi
}

looks_like_uuid() {
    case "$1" in
        ????????-????-????-????-????????????) return 0 ;;
        *) return 1 ;;
    esac
}

extract_canonical_rows() {
    local file="$1"

    [ -f "$file" ] || return 0
    awk -F '\t' 'NF == 6 && $1 ~ /^[0-9]+$/ { print }' "$file"
}

filter_existing_rows() {
    local pulse_file="$1"
    local candidate_rows="$2"
    local existing_rows

    [ -s "$candidate_rows" ] || return 0
    if [ ! -f "$pulse_file" ]; then
        cat "$candidate_rows"
        return 0
    fi

    existing_rows="$(mktemp "${TMPDIR:-/tmp}/git-pulse-existing.XXXXXX")"
    extract_canonical_rows "$pulse_file" | sort -u > "$existing_rows"

    if [ ! -s "$existing_rows" ]; then
        rm -f "$existing_rows"
        cat "$candidate_rows"
        return 0
    fi

    grep -Fvx -f "$existing_rows" "$candidate_rows" || true
    rm -f "$existing_rows"
}

write_pulse_file() {
    local file="$1"
    local pulse_device_name="$2"
    local pulse_device_id="$3"
    local rows_file="$4"

    cat > "$file" <<HEADER
# Git pulse — $pulse_device_name

<!-- Append-only chronological log. Tab-separated columns:
     epoch_utc \t timestamp_utc \t repo \t branch \t short-sha \t subject
     device_id: $pulse_device_id
     canonical time: UTC
     Oldest at top; newest at bottom. Grep-friendly; not meant for pretty rendering. -->

HEADER

    if [ -s "$rows_file" ]; then
        cat "$rows_file" >> "$file"
    fi
}

stage_paths=()

append_stage_path() {
    local path="$1"

    [ -n "$path" ] || return 0
    stage_paths+=("$path")
}

migrate_legacy_device_identity() {
    local configured_device_id="$1"
    local desired_device_id="$2"
    local old_metadata_file
    local old_metadata_rel
    local new_metadata_file
    local new_metadata_rel
    local old_pulse_file
    local old_pulse_rel
    local new_pulse_file
    local new_pulse_rel
    local merge_rows

    if [ "$configured_device_id" = "$desired_device_id" ]; then
        return
    fi

    old_metadata_file="$sync_repo_dir/devices/$configured_device_id.yaml"
    new_metadata_file="$sync_repo_dir/devices/$desired_device_id.yaml"
    old_pulse_file="$sync_repo_dir/pulse-$configured_device_id.md"
    new_pulse_file="$sync_repo_dir/pulse-$desired_device_id.md"
    old_metadata_rel="devices/$configured_device_id.yaml"
    new_metadata_rel="devices/$desired_device_id.yaml"
    old_pulse_rel="pulse-$configured_device_id.md"
    new_pulse_rel="pulse-$desired_device_id.md"

    mkdir -p "$sync_repo_dir/devices"

    if [ -f "$old_pulse_file" ] || [ -f "$new_pulse_file" ]; then
        merge_rows="$(mktemp "${TMPDIR:-/tmp}/git-pulse-migrate.XXXXXX")"
        {
            extract_canonical_rows "$new_pulse_file"
            extract_canonical_rows "$old_pulse_file"
        } | sort -t $'\t' -n -k1,1 -u > "$merge_rows"
        write_pulse_file "$new_pulse_file" "$device_name" "$desired_device_id" "$merge_rows"
        rm -f "$merge_rows"
        if [ -f "$old_pulse_file" ] && [ "$old_pulse_file" != "$new_pulse_file" ]; then
            rm -f "$old_pulse_file"
        fi
    fi

    cat > "$new_metadata_file" <<METADATA
schema_version: 2
device_id: "$desired_device_id"
hardware_uuid: "$(yaml_escape "$hardware_uuid")"
device_name: "$(yaml_escape "$device_name")"
hostname: "$(yaml_escape "$hostname")"
host_tag: "$host_tag"
timezone_name: "$(date +%Z)"
utc_offset: "$(date +%z)"
pulse_file: "pulse-$desired_device_id.md"
METADATA

    if [ -f "$old_metadata_file" ] && [ "$old_metadata_file" != "$new_metadata_file" ]; then
        rm -f "$old_metadata_file"
    fi

    append_stage_path "$old_metadata_rel"
    append_stage_path "$new_metadata_rel"
    append_stage_path "$old_pulse_rel"
    append_stage_path "$new_pulse_rel"

    set_config_value "device_id" "$desired_device_id"
}

: "${hostname:=$(scutil --get ComputerName 2>/dev/null || echo "${HOSTNAME:-unknown-host}")}"
: "${device_name:=$hostname}"
: "${device_id:=}"
: "${sync_repo_dir:=$CONFIG_DIR/repo}"

host_tag="$(sanitize_tag "$hostname")"
[ -z "$host_tag" ] && host_tag="unknown-host"
hardware_uuid="$(read_hardware_uuid)"
configured_device_id="$(printf '%s' "${device_id:-}" | tr '[:upper:]' '[:lower:]')"
configured_device_id="$(sanitize_tag "$configured_device_id")"
desired_device_id="$(canonical_device_id_from_hostname "$hostname")"

should_migrate_device_id=0
if [ -n "$configured_device_id" ]; then
    if looks_like_uuid "$configured_device_id"; then
        should_migrate_device_id=1
    else
        while IFS= read -r legacy_candidate; do
            [ -n "$legacy_candidate" ] || continue
            if [ "$configured_device_id" = "$legacy_candidate" ] && [ "$configured_device_id" != "$desired_device_id" ]; then
                should_migrate_device_id=1
                break
            fi
        done < <(
            legacy_device_id_candidates "$hostname"
            legacy_device_id_candidates "$device_name"
        )
    fi
fi

if [ -n "$configured_device_id" ] && [ "$should_migrate_device_id" -eq 0 ]; then
    device_id="$configured_device_id"
else
    device_id="$desired_device_id"
fi

LOCK_DIR="$CONFIG_DIR/collect.lock"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
    echo "Another git-pulse collector run is already in progress; skipping." >&2
    exit 0
fi
cleanup() {
    rmdir "$LOCK_DIR"
}
trap cleanup EXIT

if ! declare -p repos >/dev/null 2>&1; then
    echo "repos array is not defined in $CONFIG_FILE" >&2
    exit 1
fi

if [ ! -d "$sync_repo_dir/.git" ]; then
    echo "Sync repo not found at $sync_repo_dir" >&2
    echo "Run install.sh to clone it." >&2
    exit 1
fi

DRY_RUN=0
if [ "${1:-}" = "--dry-run" ]; then
    DRY_RUN=1
fi

# last-run is epoch seconds (avoids timezone-comparison bugs)
LAST_RUN_FILE="$CONFIG_DIR/last-run"
if [ -f "$LAST_RUN_FILE" ]; then
    last_run=$(cat "$LAST_RUN_FILE")
else
    last_run=0
fi
scan_started=$(date +%s)

# Collect entries: one tab-separated line per new local commit.
# Fields: epoch_utc \t timestamp_utc \t repo \t branch \t short-sha \t subject
new_entries=()

for repo_path in "${repos[@]}"; do
    if [ ! -d "$repo_path/.git" ]; then
        echo "Skipping $repo_path: not a git repo" >&2
        continue
    fi
    if ! git -C "$repo_path" rev-parse --verify HEAD >/dev/null 2>&1; then
        echo "Skipping $repo_path: no commits yet" >&2
        continue
    fi
    repo_name=$(basename "$repo_path")

    # Walk HEAD reflog with iso-strict reflog-entry timestamps in %gd.
    # %gd format with --date=iso-strict: HEAD@{2026-04-20T14:32:15-07:00}
    # Fields separated by tabs to survive spaces in %gs and %s.
    while IFS=$'\t' read -r gd hash gs subject || [ -n "${gd:-}" ]; do
        # Only locally-authored commits (excludes pull/fetch/merge/rebase/cherry-pick reflog entries)
        case "$gs" in
            commit:*|"commit (initial):"*|"commit (amend):"*) ;;
            *) continue ;;
        esac

        # Extract ISO timestamp from HEAD@{...}
        ts="${gd#*\{}"
        ts="${ts%\}}"

        # BSD date expects +HHMM without a colon; strip the colon in the TZ offset.
        ts_for_parse="${ts:0:22}${ts:23:2}"
        if ! entry_epoch=$(date -j -f "%Y-%m-%dT%H:%M:%S%z" "$ts_for_parse" +%s 2>/dev/null); then
            continue
        fi

        if (( entry_epoch <= last_run )); then
            continue
        fi

        # Branch-at-scan-time: first current branch that still contains the commit.
        # Accurate for unmerged work; for merged+deleted feature branches this reports
        # the merge target (usually main), which is acceptable for a passive log.
        branch=$(git -C "$repo_path" branch --contains "$hash" --format='%(refname:short)' 2>/dev/null | head -n1)
        [ -z "$branch" ] && branch="(detached)"

        utc_iso="$(utc_iso_from_epoch "$entry_epoch")"
        short_hash="${hash:0:7}"
        clean_subject=${subject//$'\t'/ }
        clean_subject=${clean_subject//$'\r'/ }

        new_entries+=("$(printf '%s\t%s\t%s\t%s\t%s\t%s' "$entry_epoch" "$utc_iso" "$repo_name" "$branch" "$short_hash" "$clean_subject")")
    done < <(git -C "$repo_path" log -g --date=iso-strict --pretty=format:'%gd%x09%H%x09%gs%x09%s')
done

PULSE_FILE_NAME="pulse-$device_id.md"
PULSE_FILE="$sync_repo_dir/$PULSE_FILE_NAME"
DEVICE_METADATA_DIR="$sync_repo_dir/devices"
DEVICE_METADATA_FILE="$DEVICE_METADATA_DIR/$device_id.yaml"

# Sort by epoch ascending and keep the canonical epoch column in storage.
sorted_display=""
if [ "${#new_entries[@]}" -gt 0 ]; then
    sorted_display=$(printf '%s\n' "${new_entries[@]}" | sort -n -k1,1)
fi

if [ "$DRY_RUN" -eq 1 ]; then
    if [ "${#new_entries[@]}" -eq 0 ]; then
        echo "Dry run: no new entries for $PULSE_FILE"
    else
        echo "Dry run: would append ${#new_entries[@]} entries to $PULSE_FILE:"
        printf '%s\n' "$sorted_display"
    fi
    exit 0
fi

# Bring in any peer-machine updates before writing.
if git -C "$sync_repo_dir" rev-parse --verify HEAD >/dev/null 2>&1; then
    git -C "$sync_repo_dir" pull --quiet --rebase
fi

if [ "$DRY_RUN" -eq 0 ] && [ "$should_migrate_device_id" -eq 1 ] && [ -n "$configured_device_id" ]; then
    migrate_legacy_device_identity "$configured_device_id" "$desired_device_id"
    device_id="$desired_device_id"
    PULSE_FILE_NAME="pulse-$device_id.md"
    PULSE_FILE="$sync_repo_dir/$PULSE_FILE_NAME"
    DEVICE_METADATA_FILE="$DEVICE_METADATA_DIR/$device_id.yaml"
fi

mkdir -p "$DEVICE_METADATA_DIR"
cat > "$DEVICE_METADATA_FILE" <<METADATA
schema_version: 2
device_id: "$device_id"
hardware_uuid: "$(yaml_escape "$hardware_uuid")"
device_name: "$(yaml_escape "$device_name")"
hostname: "$(yaml_escape "$hostname")"
host_tag: "$host_tag"
timezone_name: "$(date +%Z)"
utc_offset: "$(date +%z)"
pulse_file: "$PULSE_FILE_NAME"
last_scan_epoch: "$scan_started"
last_scan_utc: "$(utc_iso_from_epoch "$scan_started")"
METADATA

# Initialize the per-machine file on first run.
if [ ! -f "$PULSE_FILE" ]; then
    cat > "$PULSE_FILE" <<HEADER
# Git pulse — $device_name

<!-- Append-only chronological log. Tab-separated columns:
     epoch_utc \t timestamp_utc \t repo \t branch \t short-sha \t subject
     device_id: $device_id
     canonical time: UTC
     Oldest at top; newest at bottom. Grep-friendly; not meant for pretty rendering. -->

HEADER
fi

if [ "${#new_entries[@]}" -gt 0 ]; then
    candidate_rows_file="$(mktemp "${TMPDIR:-/tmp}/git-pulse-candidates.XXXXXX")"
    printf '%s\n' "$sorted_display" > "$candidate_rows_file"
    filtered_display="$(filter_existing_rows "$PULSE_FILE" "$candidate_rows_file")"
    rm -f "$candidate_rows_file"

    if [ -n "$filtered_display" ]; then
        new_entries=()
        while IFS= read -r entry_line; do
            [ -n "$entry_line" ] || continue
            new_entries+=("$entry_line")
        done <<EOF
$filtered_display
EOF
        sorted_display="$filtered_display"
    else
        new_entries=()
        sorted_display=""
    fi
fi

if [ "${#new_entries[@]}" -gt 0 ]; then
    printf '%s\n' "$sorted_display" >> "$PULSE_FILE"
fi

cd "$sync_repo_dir"
append_stage_path "$(basename "$PULSE_FILE")"
append_stage_path "devices/$device_id.yaml"
git add -A -- "${stage_paths[@]}"
if git diff --cached --quiet; then
    # Nothing actually staged (e.g. a same-second rerun that produced
    # identical metadata heartbeat values). Nothing to push.
    echo "$scan_started" > "$LAST_RUN_FILE"
    exit 0
fi

if [ "${#new_entries[@]}" -gt 0 ]; then
    git commit --quiet -m "pulse-$device_id: +${#new_entries[@]}"
else
    git commit --quiet -m "pulse-$device_id: metadata refresh"
fi

push_current_branch() {
    if git rev-parse --abbrev-ref --symbolic-full-name '@{u}' >/dev/null 2>&1; then
        git push --quiet
    else
        git push --quiet -u origin HEAD
    fi
}

# One retry on push race (peer pushed between our pull and push).
if ! push_current_branch 2>/dev/null; then
    git pull --quiet --rebase
    push_current_branch
fi

# Only advance last-run on a successful write + push.
echo "$scan_started" > "$LAST_RUN_FILE"
