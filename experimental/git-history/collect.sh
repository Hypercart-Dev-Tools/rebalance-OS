#!/bin/bash
# Collect new local commits from each watched repo since last run,
# append to this machine's history file in the sync repo, commit, push.

set -euo pipefail

CONFIG_DIR="${GIT_HISTORY_CONFIG_DIR:-$HOME/.config/git-history}"
CONFIG_FILE="$CONFIG_DIR/config.sh"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "Config not found at $CONFIG_FILE" >&2
    echo "Run install.sh to set up." >&2
    exit 1
fi

# shellcheck disable=SC1090
source "$CONFIG_FILE"

: "${hostname:=$(scutil --get ComputerName 2>/dev/null || echo "$HOSTNAME")}"
: "${sync_repo_dir:=$CONFIG_DIR/repo}"

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
# Fields: epoch \t YYYY-MM-DD HH:MM \t repo \t branch \t short-sha \t subject
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
    while IFS=$'\t' read -r gd hash gs subject; do
        # Only locally-authored commits (excludes pull/fetch/merge/rebase/cherry-pick reflog entries)
        case "$gs" in
            commit:*|"commit (initial):"*) ;;
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

        short_date=$(date -r "$entry_epoch" +"%Y-%m-%d %H:%M")
        short_hash="${hash:0:7}"

        new_entries+=("$(printf '%s\t%s\t%s\t%s\t%s\t%s' "$entry_epoch" "$short_date" "$repo_name" "$branch" "$short_hash" "$subject")")
    done < <(git -C "$repo_path" log -g --date=iso-strict --pretty=format:'%gd%x09%H%x09%gs%x09%s')
done

HISTORY_FILE="$sync_repo_dir/history-$hostname.md"

if [ "${#new_entries[@]}" -eq 0 ]; then
    # Advance the watermark anyway so we don't re-scan indefinitely.
    echo "$scan_started" > "$LAST_RUN_FILE"
    exit 0
fi

# Sort by epoch ascending, then drop the epoch column for display.
sorted_display=$(printf '%s\n' "${new_entries[@]}" | sort -n -k1,1 | cut -f2-)

if [ "$DRY_RUN" -eq 1 ]; then
    echo "Dry run: would append ${#new_entries[@]} entries to $HISTORY_FILE:"
    printf '%s\n' "$sorted_display"
    exit 0
fi

# Bring in any peer-machine updates before writing.
git -C "$sync_repo_dir" pull --quiet --rebase

# Initialize the per-machine file on first run.
if [ ! -f "$HISTORY_FILE" ]; then
    cat > "$HISTORY_FILE" <<HEADER
# Git history — $hostname

<!-- Append-only chronological log. Tab-separated columns:
     YYYY-MM-DD HH:MM \t repo \t branch \t short-sha \t subject
     Oldest at top; newest at bottom. Grep-friendly; not meant for pretty rendering. -->

HEADER
fi

printf '%s\n' "$sorted_display" >> "$HISTORY_FILE"

cd "$sync_repo_dir"
git add -- "$(basename "$HISTORY_FILE")"
if git diff --cached --quiet; then
    # Nothing actually staged (e.g. file unchanged). Nothing to push.
    echo "$scan_started" > "$LAST_RUN_FILE"
    exit 0
fi

git commit --quiet -m "history-$hostname: +${#new_entries[@]}"

# One retry on push race (peer pushed between our pull and push).
if ! git push --quiet 2>/dev/null; then
    git pull --quiet --rebase
    git push --quiet
fi

# Only advance last-run on a successful write + push.
echo "$scan_started" > "$LAST_RUN_FILE"
