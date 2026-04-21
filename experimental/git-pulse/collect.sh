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
    printf '%s' "$1" | tr -cs 'A-Za-z0-9._-' '-' | sed 's/^-*//; s/-*$//'
}

yaml_escape() {
    printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

utc_iso_from_epoch() {
    TZ=UTC date -r "$1" +"%Y-%m-%dT%H:%M:%SZ"
}

: "${hostname:=$(scutil --get ComputerName 2>/dev/null || echo "${HOSTNAME:-unknown-host}")}"
: "${device_name:=$hostname}"
: "${device_id:=}"
: "${sync_repo_dir:=$CONFIG_DIR/repo}"

host_tag="$(sanitize_tag "$hostname")"
[ -z "$host_tag" ] && host_tag="unknown-host"
device_id="$(printf '%s' "${device_id:-$host_tag}" | tr '[:upper:]' '[:lower:]')"
device_id="$(sanitize_tag "$device_id")"
[ -z "$device_id" ] && device_id="$host_tag"

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

mkdir -p "$DEVICE_METADATA_DIR"
cat > "$DEVICE_METADATA_FILE" <<METADATA
schema_version: 1
device_id: "$device_id"
device_name: "$(yaml_escape "$device_name")"
hostname: "$(yaml_escape "$hostname")"
host_tag: "$host_tag"
timezone_name: "$(date +%Z)"
utc_offset: "$(date +%z)"
pulse_file: "$PULSE_FILE_NAME"
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
    printf '%s\n' "$sorted_display" >> "$PULSE_FILE"
fi

cd "$sync_repo_dir"
git add -- "$(basename "$PULSE_FILE")" "devices/$device_id.yaml"
if git diff --cached --quiet; then
    # Nothing actually staged (e.g. file unchanged). Nothing to push.
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
