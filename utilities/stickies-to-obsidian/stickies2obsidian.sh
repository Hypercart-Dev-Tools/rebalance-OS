#!/bin/bash

set -euo pipefail

: "${STICKIES_DIR:=$HOME/Library/Containers/com.apple.stickies/Data/Library/Stickies}"
: "${OBSIDIAN_FILE:=$HOME/Documents/ObsidianVault/Stickies.md}"
: "${STATE_FILE:=$HOME/.stickies2obsidian.state}"
: "${TIMESTAMP_FORMAT:=%Y-%m-%d %H:%M}"
: "${DRY_RUN:=false}"
: "${VERBOSE:=false}"

SCRIPT_NAME="stickies2obsidian"
SCRATCH_DIR=""
OBSIDIAN_TMP=""
STATE_TMP=""

log() {
    printf '[%s] %s\n' "$SCRIPT_NAME" "$*"
}

warn() {
    printf '[%s] %s\n' "$SCRIPT_NAME" "$*" >&2
}

die() {
    warn "ERROR: $*"
    exit 1
}

is_true() {
    case "${1:-false}" in
        1|[Tt][Rr][Uu][Ee]|[Yy][Ee][Ss]|[Oo][Nn])
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

verbose() {
    if is_true "$VERBOSE"; then
        log "$*"
    fi
}

require_cmd() {
    command -v "$1" >/dev/null 2>&1 || die "Missing required tool: $1"
}

ensure_parent_dir() {
    local target_dir="$1"
    if [ -d "$target_dir" ]; then
        return
    fi
    if is_true "$DRY_RUN"; then
        verbose "DRY_RUN: would create directory $target_dir"
        return
    fi
    mkdir -p "$target_dir"
}

ensure_file() {
    local path="$1"
    if [ -f "$path" ]; then
        return
    fi
    if is_true "$DRY_RUN"; then
        return
    fi
    : > "$path"
}

has_non_whitespace() {
    local text="$1"
    [ -n "$(printf '%s' "$text" | tr -d '[:space:]')" ]
}

hash_seen() {
    local hash="$1"
    local ledger="$2"
    [ -f "$ledger" ] && grep -q "^$hash " "$ledger"
}

build_block() {
    local timestamp="$1"
    local hash="$2"
    local note_text="$3"

    printf -- '---\n**📝 Sticky Note** · `%s`\n<!-- stickies-hash: %s -->\n\n%s\n\n---\n' \
        "$timestamp" \
        "$hash" \
        "$note_text"
}

cleanup() {
    if [ -n "${SCRATCH_DIR:-}" ]; then
        rm -rf "$SCRATCH_DIR"
    fi
    if [ -n "${OBSIDIAN_TMP:-}" ]; then
        rm -f "$OBSIDIAN_TMP"
    fi
    if [ -n "${STATE_TMP:-}" ]; then
        rm -f "$STATE_TMP"
    fi
}

list_note_dirs() {
    local stickies_dir="$1"
    local manifest="$2"
    local sorted="$3"

    : > "$manifest"
    : > "$sorted"

    while IFS= read -r -d '' note_dir; do
        local mtime
        mtime="$(stat -f '%m' "$note_dir" 2>/dev/null || printf '0')"
        printf '%s\t%s\n' "$mtime" "$note_dir" >> "$manifest"
    done < <(find "$stickies_dir" -mindepth 1 -maxdepth 1 -type d -name '*.rtfd' -print0)

    if [ -s "$manifest" ]; then
        sort -rn "$manifest" > "$sorted"
    fi
}

main() {
    local obsidian_dir state_dir
    local notes_manifest notes_sorted new_blocks_file state_additions_file
    local imported skipped

    require_cmd textutil
    require_cmd shasum
    require_cmd sed
    require_cmd awk
    require_cmd date
    require_cmd find
    require_cmd sort
    require_cmd mktemp
    require_cmd stat

    [ -d "$STICKIES_DIR" ] || die "Stickies directory not found: $STICKIES_DIR"

    obsidian_dir="$(dirname "$OBSIDIAN_FILE")"
    state_dir="$(dirname "$STATE_FILE")"
    ensure_parent_dir "$obsidian_dir"
    ensure_parent_dir "$state_dir"
    ensure_file "$STATE_FILE"

    SCRATCH_DIR="$(mktemp -d "${TMPDIR:-/tmp}/stickies2obsidian.XXXXXX")"

    notes_manifest="$SCRATCH_DIR/note_manifest.tsv"
    notes_sorted="$SCRATCH_DIR/note_sorted.tsv"
    new_blocks_file="$SCRATCH_DIR/new_blocks.md"
    state_additions_file="$SCRATCH_DIR/state_additions.txt"
    : > "$new_blocks_file"
    : > "$state_additions_file"

    imported=0
    skipped=0

    list_note_dirs "$STICKIES_DIR" "$notes_manifest" "$notes_sorted"

    while IFS=$'\t' read -r _mtime note_dir; do
        local note_name rtf_file plain_text hash timestamp block

        [ -n "$note_dir" ] || continue
        note_name="$(basename "$note_dir")"
        rtf_file="$note_dir/TXT.rtf"

        if [ ! -f "$rtf_file" ]; then
            warn "Skipping malformed note package without TXT.rtf: $note_name"
            skipped=$((skipped + 1))
            continue
        fi

        plain_text="$(textutil -convert txt -stdout "$rtf_file" 2>/dev/null || true)"
        if ! has_non_whitespace "$plain_text"; then
            verbose "Skipping empty sticky note: $note_name"
            skipped=$((skipped + 1))
            continue
        fi

        hash="$(printf '%s\n' "$plain_text" | shasum -a 256 | awk '{print $1}')"
        if hash_seen "$hash" "$STATE_FILE" || hash_seen "$hash" "$state_additions_file"; then
            verbose "Skipping already imported sticky note: $note_name"
            skipped=$((skipped + 1))
            continue
        fi

        timestamp="$(date +"$TIMESTAMP_FORMAT")"
        block="$(build_block "$timestamp" "$hash" "$plain_text")"

        if is_true "$DRY_RUN"; then
            printf '%s\n' "$block"
        else
            printf '%s\n' "$block" >> "$new_blocks_file"
            printf '%s %s\n' "$hash" "$note_name" >> "$state_additions_file"
            log "[+] Imported: $note_name ($timestamp)"
        fi

        imported=$((imported + 1))
    done < "$notes_sorted"

    if ! is_true "$DRY_RUN" && [ "$imported" -gt 0 ]; then
        OBSIDIAN_TMP="$(mktemp "$obsidian_dir/.stickies2obsidian.obsidian.XXXXXX")"
        if [ -f "$OBSIDIAN_FILE" ]; then
            cat "$new_blocks_file" "$OBSIDIAN_FILE" > "$OBSIDIAN_TMP"
        else
            cat "$new_blocks_file" > "$OBSIDIAN_TMP"
        fi
        mv "$OBSIDIAN_TMP" "$OBSIDIAN_FILE"
        OBSIDIAN_TMP=""

        STATE_TMP="$(mktemp "$state_dir/.stickies2obsidian.state.XXXXXX")"
        if [ -f "$STATE_FILE" ]; then
            cat "$STATE_FILE" "$state_additions_file" > "$STATE_TMP"
        else
            cat "$state_additions_file" > "$STATE_TMP"
        fi
        mv "$STATE_TMP" "$STATE_FILE"
        STATE_TMP=""
    fi

    log "$imported imported, $skipped skipped."
}

trap cleanup EXIT

main "$@"
