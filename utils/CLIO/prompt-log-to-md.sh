#!/bin/bash
# Converts ~/.claude/prompt-log.jsonl into a human-readable Markdown file by
# APPENDING only entries not already present in the note. Each entry has a stable
# ID derived from its session and timestamp. A cursor (the line count already
# processed) is stored in ~/.claude/prompt-log-to-md.state as a scan optimization;
# each run prepends new prompts below a fixed header, newest first.
#
# It never rewrites entries it has already emitted. When the output file lives in
# a folder synced between machines (e.g. an Obsidian vault), each device only adds
# its own new prompts to whatever the shared file currently holds — so both
# devices' history accumulates into the one file instead of overwriting. Each
# device tracks its own cursor against its own local JSONL and never reads the
# other's log; the cross-device merge is emergent from sync + incremental append.
#
# Usage: prompt-log-to-md.sh [--status] [output_md_path]
# Default output: ~/.claude/prompt-log.md
#
# Filtering: prompts whose text matches PROMPT_LOG_EXCLUDE (a case-insensitive
# regex) are skipped — used to drop machine-triggered relay turns. The cursor
# still advances past them, so they're never reconsidered. Set it empty to keep all.

set -euo pipefail

JSONL="$HOME/.claude/prompt-log.jsonl"
STATUS_MODE=0
if [ "${1:-}" = "--status" ]; then
  STATUS_MODE=1
  shift
fi
OUT="${1:-$HOME/.claude/prompt-log.md}"
STATE="$HOME/.claude/prompt-log-to-md.state"
MANIFEST="${CLIO_MANIFEST:-$HOME/.claude/prompt-log-manifest.txt}"
STATUS_SNAPSHOT="${CLIO_STATUS_SNAPSHOT:-$STATE.target-count}"
EXCLUDE_REGEX="${PROMPT_LOG_EXCLUDE:-file-based relay|cross-agent dependency drift}"
MARKER="<!-- CLIO:ENTRIES -->"
RECONCILE_DRY_RUN="${CLIO_RECONCILE_DRY_RUN:-0}"
OUT_DIR=$(dirname "$OUT")
OUT_NAME=$(basename "$OUT")
OUT_BASE=${OUT_NAME%.md}

command -v jq >/dev/null 2>&1 || { echo "jq is required (brew install jq / apt install jq)"; exit 1; }

# This is deliberately independent of export/reconciliation. In particular,
# --status must not create the note, state, manifest, or a quarantine folder.
# jq does the full source pass at once so the 60-second scheduled check does not
# spawn a process for every prompt.
reconcile_status() {
  status_jsonl=$JSONL
  status_target=$OUT
  status_manifest=$MANIFEST
  [ -f "$status_jsonl" ] || status_jsonl=/dev/null
  [ -f "$status_target" ] || status_target=/dev/null
  [ -f "$status_manifest" ] || status_manifest=/dev/null
  status_cursor=$( [ -f "$STATE" ] && cat "$STATE" || echo 0 )
  case "$status_cursor" in ''|*[!0-9]*) status_cursor=0 ;; esac
  status_previous=$( [ -f "$STATUS_SNAPSHOT" ] && cat "$STATUS_SNAPSHOT" || echo -1 )
  case "$status_previous" in ''|*[!0-9-]*) status_previous=-1 ;; esac
  status_source_lines=$(grep -c '' "$status_jsonl" 2>/dev/null || true)

  jq -Rrs \
    --rawfile target "$status_target" \
    --rawfile manifest "$status_manifest" \
    --arg exclude "$EXCLUDE_REGEX" \
    --arg cursor "$status_cursor" \
    --arg source_lines "$status_source_lines" \
    --arg previous "$status_previous" '
      . as $raw
      | ($raw | split("\n") | map(select(length > 0) | try fromjson catch empty)) as $entries
      | ([$target | scan("clio:id:[^ >]+") ] | unique) as $target_ids
      | ($manifest | split("\n") | map(select(startswith("clio:id:"))) | unique) as $manifest_ids
      | ($target | split("\n")) as $target_lines
      | ($target_lines | index("<!-- CLIO:ENTRIES -->")) as $marker_index
      | [ $entries[]
          | ((.session_id // "") + ":" + (.timestamp // "")) as $raw_id
          | ("clio:id:" + $raw_id) as $id
          | (.prompt // "") as $prompt
          | (.timestamp // "") as $timestamp
          | (.machine // "") as $machine
          | ($prompt | gsub("\n"; "\n> ")) as $rendered_prompt
          | (if (($exclude | length) > 0 and ($prompt | test($exclude; "i"))) then "excluded"
            elif ($manifest_ids | index($id)) != null then
              if ($target_ids | index($id)) != null then "delivered-present" else "delivered-missing" end
            elif ($target_ids | index($id)) != null then "delivered-present"
            elif (($target | contains($timestamp))
                  and ($target | contains($machine))
                  and ($target | contains("> \"" + $rendered_prompt + "\""))) then "legacy-unlabelled"
            else "never-delivered"
            end) as $state
          | { id: $id, state: $state }
        ] as $classified
      | ([ $classified[] | select(.state == "delivered-missing") | .id ]) as $missing
      | (["delivered-present", "delivered-missing", "never-delivered", "legacy-unlabelled", "excluded"]
          | map(. as $state | {key: $state, value: ([ $classified[] | select(.state == $state) ] | length) })) as $counts
      | (($manifest_ids | length) > 0 and (($target_ids | length) == 0 or (($previous | tonumber) >= 0 and ($target_ids | length) < ($previous | tonumber)))) as $replacement
      | "source-count: \($source_lines)",
        "manifest-count: \($manifest_ids | length)",
        "target-rendered-id-count: \($target_ids | length)",
        "cursor: \($cursor)",
        ($counts[] | "state: \(.key)=\(.value)"),
        (if $marker_index == null then "marker: absent"
         elif $marker_index == 0 then "marker: top"
         else "marker: displaced line=\($marker_index + 1) lines-above=\($marker_index)"
         end),
        "target-replacement: \(if $replacement then "yes" else "no" end) previous-target-rendered-id-count=\($previous)",
        (if $replacement and ($missing | length) > 1 then
           "missing-clio-ids: suppressed=\($missing | length) reason=target-replacement"
         elif ($missing | length) == 0 then "missing-clio-ids: none"
         else
           ($missing[0:20][] | "missing-clio-id: \(.)"),
           (if ($missing | length) > 20 then "missing-clio-ids: … and \(($missing | length) - 20) more" else empty end)
         end)
    ' < "$status_jsonl"
}

status_requires_attention() {
  status_report=$1
  case "$status_report" in
    *"state: delivered-missing="[1-9]*|*"target-replacement: yes"*) return 0 ;;
    *) return 1 ;;
  esac
}

if [ "$STATUS_MODE" = 1 ]; then
  status_report=$(reconcile_status)
  printf '%s\n' "$status_report"
  if status_requires_attention "$status_report"; then
    exit 1
  fi
  exit 0
fi

if [ "$RECONCILE_DRY_RUN" != 1 ]; then
  mkdir -p "$OUT_DIR"
fi

# Ensure the file has the fixed header and the insertion MARKER. Everything above
# the marker is preserved verbatim every run; new entries go directly below it;
# existing entries below it are never rewritten. Any content from an older
# headerless/markerless file is kept (moved below the new marker).
if [ "$RECONCILE_DRY_RUN" != 1 ] && { [ ! -f "$OUT" ] || ! grep -qF "$MARKER" "$OUT"; }; then
  old=$(mktemp)
  [ -f "$OUT" ] && cat "$OUT" > "$old"
  {
    printf '%s\n' \
      '# Claude Code Prompt Log' \
      '' \
      'Generated by CLIO (A member of the rebalanceOS | XYZ | HiQS family)' \
      'https://github.com/Claude-AI-Tools-Ventura-County/clio' \
      '' \
      "$MARKER"
    cat "$old"
  } > "$OUT.tmp.$$" && mv "$OUT.tmp.$$" "$OUT"
  rm -f "$old"
fi

# Recover complete CLIO entry blocks stranded in sync conflict siblings before
# considering the local JSONL cursor. Only files derived from this note's base
# name are candidates, so unrelated conflict notes in the same folder are safe.
# IDs are added to the in-memory set as they are planned, which also deduplicates
# the same entry when it appears in more than one conflict sibling.
existing_ids=$(grep -o 'clio:id:[^ ]*' "$OUT" 2>/dev/null || true)
shopt -s nullglob
conflict_siblings=(
  "$OUT_DIR/$OUT_BASE".sync-conflict-*.md
  "$OUT_DIR/$OUT_BASE"' (conflicted copy'*.md
  "$OUT_DIR/$OUT_BASE"' '[0-9]*.md
)
shopt -u nullglob

# `${arr[@]+...}` guard: on macOS's bash 3.2, expanding an EMPTY array under
# `set -u` aborts with "unbound variable" (only fixed in bash 4.4+), and the
# common case is zero conflict siblings — so the bare `"${conflict_siblings[@]}"`
# broke every normal run. This form expands to nothing when the array is empty.
for conflict in ${conflict_siblings[@]+"${conflict_siblings[@]}"}; do
  [ "$conflict" = "$OUT" ] && continue

  recovered=$(mktemp)
  merged_count=0
  conflict_ids=$(grep -o 'clio:id:[^ ]*' "$conflict" 2>/dev/null || true)
  while IFS= read -r conflict_id; do
    [ -z "$conflict_id" ] && continue
    case $'\n'"$existing_ids"$'\n' in
      *$'\n'"$conflict_id"$'\n'*) continue ;;
    esac

    block=$(mktemp)
    awk -v wanted="$conflict_id" '
      $0 == "<!-- " wanted " -->" { copying = 1; heading = 0 }
      copying {
        if ($0 ~ /^<!-- clio:id:/ && $0 != "<!-- " wanted " -->") exit
        if ($0 ~ /^## /) {
          if (heading) exit
          heading = 1
        }
        print
      }
    ' "$conflict" > "$block"

    # A bare ID is not recoverable: require the rendered heading and prompt so
    # reconciliation can never claim success after merging metadata alone.
    if grep -q '^## ' "$block" && grep -q '^> "' "$block"; then
      cat "$block" >> "$recovered"
      printf '\n' >> "$recovered"
      existing_ids="${existing_ids}${existing_ids:+$'\n'}${conflict_id}"
      merged_count=$((merged_count + 1))
    fi
    rm -f "$block"
  done <<< "$conflict_ids"

  quarantine_dir="$OUT_DIR/.clio-reconciled"
  destination="$quarantine_dir/$(basename "$conflict")"
  suffix=1
  while [ -e "$destination" ]; do
    destination="$quarantine_dir/$(basename "$conflict").$suffix"
    suffix=$((suffix + 1))
  done

  if [ "$RECONCILE_DRY_RUN" = 1 ]; then
    echo "reconciled $(basename "$conflict"): merged=$merged_count quarantined=$destination (dry-run)"
  else
    if [ -s "$recovered" ]; then
      marker_line=$(grep -nF "$MARKER" "$OUT" | head -1 | cut -d: -f1)
      merged="$OUT.tmp.$$"
      {
        head -n "$marker_line" "$OUT"
        echo
        cat "$recovered"
        tail -n +"$((marker_line + 1))" "$OUT"
      } > "$merged"
      mv "$merged" "$OUT"
    fi
    mkdir -p "$quarantine_dir"
    mv "$conflict" "$destination"
    echo "reconciled $(basename "$conflict"): merged=$merged_count quarantined=$destination"
  fi
  rm -f "$recovered"
done

# Reconciliation dry-run is a read-only operation: do not continue into the
# normal exporter, which could create the note or advance its cursor.
[ "$RECONCILE_DRY_RUN" = 1 ] && exit 0

[ -f "$JSONL" ] || { echo "No log yet at $JSONL"; exit 0; }

TOTAL_LINES=$(grep -c '' "$JSONL")
LAST_LINE=$( [ -f "$STATE" ] && cat "$STATE" || echo 0 )
case "$LAST_LINE" in ''|*[!0-9]*) LAST_LINE=0 ;; esac   # corrupt state → start over
[ "$LAST_LINE" -gt "$TOTAL_LINES" ] && LAST_LINE=0      # JSONL shrank/rotated → re-emit all

reverse_lines() { if command -v tac >/dev/null 2>&1; then tac; else tail -r; fi; }

# Render the new entries (newest first). jq -R reads each raw line; fromjson parses
# it; malformed lines, excluded prompts, and IDs already in the note are dropped
# without aborting the run. The ID is derived inline without per-entry subprocesses.
new_entries=$(mktemp)
if [ "$LAST_LINE" -lt "$TOTAL_LINES" ]; then
tail -n +"$((LAST_LINE + 1))" "$JSONL" | reverse_lines | jq -Rr \
  --arg exclude "$EXCLUDE_REGEX" --arg existing_ids "$existing_ids" '
  (fromjson? // empty)
  | select(($exclude | length) == 0 or ((.prompt // "") | test($exclude; "i") | not))
  | ((.session_id // "") + ":" + (.timestamp // "")) as $id
  | select(($existing_ids | split("\n") | index("clio:id:" + $id)) == null)
  | "<!-- clio:id:\($id) -->\n## \(.repo // "unknown" | ascii_upcase)\n\(.timestamp)  \n\(.machine // "")\(if (.branch // "") != "" then " · \(.branch)" else "" end)\n\n> \"\((.prompt // "") | gsub("\n"; "\n> "))\"\n"
' > "$new_entries"
else
  : > "$new_entries"
fi

emitted_ids=$(grep -o 'clio:id:[^ ]*' "$new_entries" 2>/dev/null || true)
emitted_count=$(grep -c '^<!-- clio:id:' "$new_entries" 2>/dev/null || true)

# Insert the new entries right after the MARKER, preserving everything else. Write
# atomically (temp + mv) so a reader like Obsidian never sees a half-written file.
if [ -s "$new_entries" ]; then
  marker_line=$(grep -nF "$MARKER" "$OUT" | head -1 | cut -d: -f1)
  merged="$OUT.tmp.$$"   # same dir as $OUT so the mv is a true atomic rename
  {
    head -n "$marker_line" "$OUT"
    echo
    cat "$new_entries"
    tail -n +"$((marker_line + 1))" "$OUT"
  } > "$merged"
  mv "$merged" "$OUT"

  # Do not advance the cursor until every entry from this run is visible in the
  # atomically replaced output. A failed verification leaves the state untouched,
  # so the next run retries the same JSONL range.
  written_ids=$(grep -o 'clio:id:[^ ]*' "$OUT" 2>/dev/null || true)
  while IFS= read -r emitted_id; do
    [ -z "$emitted_id" ] && continue
    case $'\n'"$written_ids"$'\n' in
      *$'\n'"$emitted_id"$'\n'*) ;;
      *)
        rm -f "$new_entries"
        echo "Failed to verify emitted CLIO entry $emitted_id; cursor not advanced." >&2
        exit 1
        ;;
    esac
  done <<< "$emitted_ids"
fi
rm -f "$new_entries"

# The manifest is a source-owned, cursor-independent delivery receipt. It only
# contains rendered IDs (never prompt text), and a receipt failure must not lose a
# successful export. Build a complete replacement beside the manifest, then rename
# it atomically so a reader never sees a partial receipt.
record_manifest() {
  [ -n "$emitted_ids" ] || return 0

  manifest_dir=$(dirname "$MANIFEST")
  mkdir -p "$manifest_dir" || return 1
  manifest_tmp="$manifest_dir/.prompt-log-manifest.tmp.$$"
  if [ -f "$MANIFEST" ]; then
    cat "$MANIFEST" > "$manifest_tmp" || { rm -f "$manifest_tmp"; return 1; }
  else
    : > "$manifest_tmp" || return 1
  fi

  while IFS= read -r emitted_id; do
    [ -z "$emitted_id" ] && continue
    grep -qxF "$emitted_id" "$manifest_tmp" || printf '%s\n' "$emitted_id" >> "$manifest_tmp" || {
      rm -f "$manifest_tmp"
      return 1
    }
  done <<< "$emitted_ids"
  mv "$manifest_tmp" "$MANIFEST" || { rm -f "$manifest_tmp"; return 1; }
}

if ! record_manifest; then
  echo "Unable to update CLIO manifest at $MANIFEST; export completed." >&2
fi

state_tmp="$STATE.tmp.$$"
printf '%s\n' "$TOTAL_LINES" > "$state_tmp" && mv "$state_tmp" "$STATE"
echo "✅ Synced $emitted_count new prompt(s) to $OUT"

# Detection runs after a completed export. Its snapshot is only a baseline for
# the next scheduled run; a detected loss never undoes the export or cursor.
status_report=$(reconcile_status)
printf '%s\n' "$status_report"
snapshot_tmp="$STATUS_SNAPSHOT.tmp.$$"
printf '%s\n' "$(printf '%s\n' "$status_report" | sed -n 's/^target-rendered-id-count: //p')" > "$snapshot_tmp"
mv "$snapshot_tmp" "$STATUS_SNAPSHOT"
if status_requires_attention "$status_report"; then
  echo "CLIO delivery loss detected after export; run --status for details." >&2
  exit 1
fi
