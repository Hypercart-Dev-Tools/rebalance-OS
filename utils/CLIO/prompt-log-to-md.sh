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
# Usage: prompt-log-to-md.sh [--status|--backfill|--repair] [--apply] [output_md_path]
# Default output: ~/.claude/prompt-log.md
#
# Filtering: prompts whose text matches PROMPT_LOG_EXCLUDE (a case-insensitive
# regex) are skipped — used to drop machine-triggered relay turns. The cursor
# still advances past them, so they're never reconsidered. Set it empty to keep all.

set -euo pipefail

JSONL="$HOME/.claude/prompt-log.jsonl"
MODE=export
APPLY=0
OUT=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --status) MODE=status ;;
    --backfill) MODE=backfill ;;
    --repair) MODE=repair ;;
    --apply) APPLY=1 ;;
    --*) echo "Unknown option: $1" >&2; exit 2 ;;
    *)
      if [ -n "$OUT" ]; then
        echo "Only one output path may be supplied." >&2
        exit 2
      fi
      OUT=$1
      ;;
  esac
  shift
done
OUT="${OUT:-$HOME/.claude/prompt-log.md}"
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

# ---------------------------------------------------------------------------
# LOCAL-TIME DISPLAY
# ---------------------------------------------------------------------------
# Raw JSONL and clio:id keep UTC. ONLY the displayed timestamp line is
# localized, because clio:id is "session_id:timestamp" — changing the stored
# timestamp would change every ID, break dedup, and re-emit the whole note as
# duplicates.
#
# Conversion goes through python3, NOT jq: jq's strflocaltime is not DST-aware
# here (it renders 2026-07 as "PST / -0800" when the correct zone is
# "PDT / -0700"), which would print self-contradictory times in the note.
# python3's datetime.astimezone() uses the real zone database.
#
# If python3 is unavailable the map is empty and rendering falls back to UTC —
# degraded but never wrong, and never a crash.
CLIO_PY=""
for _cand in /usr/bin/python3 python3; do
  if command -v "$_cand" >/dev/null 2>&1; then CLIO_PY=$_cand; break; fi
done

# stdin: JSONL. stdout: JSON object mapping UTC timestamp -> local display.
local_time_map() {
  if [ -z "$CLIO_PY" ]; then printf '%s' '{}'; return 0; fi
  _map=$("$CLIO_PY" -c '
import json, sys
from datetime import datetime
out = {}
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        ts = json.loads(line).get("timestamp", "")
    except Exception:
        continue
    if not ts or ts in out:
        continue
    try:
        local = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone()
    except Exception:
        continue
    out[ts] = local.strftime("%Y-%m-%d %H:%M:%S %Z")
json.dump(out, sys.stdout)
' 2>/dev/null) || _map=""
  # Only trust well-formed output; anything else degrades to UTC rendering.
  case "$_map" in
    '{'*'}') printf '%s' "$_map" ;;
    *) printf '%s' '{}' ;;
  esac
}

LOCALMAP=""
ensure_local_map() {
  [ -n "$LOCALMAP" ] && return 0
  if [ -f "$JSONL" ]; then LOCALMAP=$(local_time_map < "$JSONL"); else LOCALMAP='{}'; fi
  [ -n "$LOCALMAP" ] || LOCALMAP='{}'
  return 0
}

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
  ensure_local_map

  jq -Rrs \
    --rawfile target "$status_target" \
    --rawfile manifest "$status_manifest" \
    --arg exclude "$EXCLUDE_REGEX" \
    --arg cursor "$status_cursor" \
    --arg source_lines "$status_source_lines" \
    --argjson localmap "$LOCALMAP" \
    --arg previous "$status_previous" '
      . as $raw
      | ($raw | split("\n") | map(select(length > 0) | try fromjson catch empty)) as $entries
      | ([$target | scan("clio:id:[^ >]+") ] | unique) as $target_ids
      | ($manifest | split("\n") | map(select(startswith("clio:id:"))) | unique) as $manifest_ids
      | ($target | split("\n")) as $target_lines
      | ($target | split("\n## ")[1:]) as $target_blocks
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
            elif any($target_blocks[];
                . as $block
                | ($block | split("\n")) as $lines
                | ((($lines[1] // "") | rtrimstr("  ")) as $shown
                   | $shown == $timestamp or $shown == ($localmap[$timestamp] // $timestamp))
                and (((($lines[2] // "") | split(" · ")[0]) == $machine))
                and ($block | contains("> \"" + $rendered_prompt + "\""))) then "legacy-unlabelled"
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

reverse_lines() { if command -v tac >/dev/null 2>&1; then tac; else tail -r; fi; }

backup_target() {
  backup="$OUT_DIR/${OUT_NAME}.clio-backup.$(date +%Y%m%d%H%M%S).$$"
  cp "$OUT" "$backup"
  echo "backup: $backup"
}

# Print tab-separated entry-index and source ID for only unambiguous legacy
# blocks. An ID that matches more than one target block is ambiguous too.
backfill_plan() {
  [ -f "$JSONL" ] || return 0
  [ -f "$OUT" ] || return 0
  ensure_local_map
  jq -Rrs --rawfile target "$OUT" --argjson localmap "$LOCALMAP" '
    . as $raw
    | ($raw | split("\n") | map(select(length > 0) | try fromjson catch empty)
       | map(. + {id: ("clio:id:" + ((.session_id // "") + ":" + (.timestamp // ""))), rendered: ((.prompt // "") | gsub("\n"; "\n> "))})) as $source
    | ([$target | scan("clio:id:[^ >]+") ] | unique) as $target_ids
    | ($target | split("\n## ")) as $pieces
    | [range(1; $pieces | length) as $index
       | $pieces[$index] as $block
       | ($block | split("\n")) as $lines
       | [ $source[] | . as $source_entry
           | select(($target_ids | index($source_entry.id)) == null)
           | select((($lines[1] // "") | rtrimstr("  ")) as $shown
         | $shown == $source_entry.timestamp
           or $shown == ($localmap[$source_entry.timestamp] // $source_entry.timestamp))
           | select($source_entry.machine == ((($lines[2] // "") | split(" · ")[0])))
           | select($block | contains("> \"" + $source_entry.rendered + "\""))
           | $source_entry
         ] as $candidates
       | select(($candidates | length) == 1)
       | {index: $index, id: $candidates[0].id}
      ] as $matches
    | [ $matches[] | . as $match | select(([$matches[] | select(.id == $match.id)] | length) == 1) ]
    | .[] | "\(.index)\t\(.id)"
  ' < "$JSONL"
}

backfill_unlabelled_count() {
  [ -f "$OUT" ] || { echo 0; return; }
  jq -n --rawfile target "$OUT" '
    ($target | split("\n## ")) as $pieces
    | [range(1; $pieces | length) as $index
       | select(($pieces[$index - 1] | test("<!-- clio:id:[^ >]+ -->$")) | not)
      ] | length
  '
}

record_manifest_ids() {
  manifest_ids=$1
  [ -n "$manifest_ids" ] || return 0
  manifest_dir=$(dirname "$MANIFEST")
  mkdir -p "$manifest_dir" || return 1
  manifest_tmp="$manifest_dir/.prompt-log-manifest.tmp.$$"
  if [ -f "$MANIFEST" ]; then
    cat "$MANIFEST" > "$manifest_tmp" || { rm -f "$manifest_tmp"; return 1; }
  else
    : > "$manifest_tmp" || return 1
  fi
  while IFS= read -r manifest_id; do
    [ -z "$manifest_id" ] && continue
    grep -qxF "$manifest_id" "$manifest_tmp" || printf '%s\n' "$manifest_id" >> "$manifest_tmp" || {
      rm -f "$manifest_tmp"
      return 1
    }
  done <<EOF
$manifest_ids
EOF
  mv "$manifest_tmp" "$MANIFEST" || { rm -f "$manifest_tmp"; return 1; }
}

run_backfill() {
  plan=$(backfill_plan)
  plan_count=$(printf '%s\n' "$plan" | sed '/^$/d' | wc -l | tr -d ' ')
  unlabelled_count=$(backfill_unlabelled_count)
  skipped_count=$((unlabelled_count - plan_count))
  if [ "$plan_count" = 0 ]; then
    echo "backfill: 0 confident legacy entries"
    [ "$unlabelled_count" -gt 0 ] && echo "backfill: skipped $unlabelled_count unlabelled entry(s) without a confident source match"
    return 0
  fi
  printf '%s\n' "$plan" | while IFS=$'\t' read -r plan_index plan_id; do
    echo "backfill: $plan_id at entry $plan_index"
  done
  [ "$skipped_count" -gt 0 ] && echo "backfill: skipped $skipped_count unlabelled entry(s) without a confident source match"
  [ "$APPLY" = 1 ] || { echo "backfill: dry-run (pass --apply to write)"; return 0; }

  backup_target
  transformed=$(mktemp "$OUT_DIR/.${OUT_NAME}.clio-backfill.XXXXXX")
  awk -F '\t' 'NR == FNR { ids[$1] = $2; next }
    /^## / { entry++; if (entry in ids) print "<!-- " ids[entry] " -->" }
    { print }
  ' <(printf '%s\n' "$plan") "$OUT" > "$transformed"
  mv "$transformed" "$OUT"
  backfilled_ids=$(printf '%s\n' "$plan" | cut -f2)
  if ! record_manifest_ids "$backfilled_ids"; then
    echo "Unable to update CLIO manifest at $MANIFEST; backfill completed." >&2
  fi
  echo "backfill: applied $plan_count entry(s)"
}

run_repair() {
  repair_status=$(reconcile_status)
  printf '%s\n' "$repair_status"
  legacy_count=$(printf '%s\n' "$repair_status" | sed -n 's/^state: legacy-unlabelled=//p')
  case "$legacy_count" in ''|*[!0-9]*) legacy_count=0 ;; esac
  if [ "$APPLY" = 1 ] && [ "$legacy_count" -gt 0 ]; then
    echo "Repair refused: $legacy_count legacy-unlabelled entry(s) remain; run --backfill --apply first." >&2
    return 1
  fi
  repair_ids=$(printf '%s\n' "$repair_status" | sed -n 's/^missing-clio-id: //p')
  repair_count=$(printf '%s\n' "$repair_ids" | sed '/^$/d' | wc -l | tr -d ' ')
  if [ "$repair_count" = 0 ]; then
    echo "repair: 0 delivered-missing entries"
    return 0
  fi
  printf '%s\n' "$repair_ids" | while IFS= read -r repair_id; do echo "repair: $repair_id"; done
  [ "$APPLY" = 1 ] || { echo "repair: dry-run (pass --apply to write)"; return 0; }
  [ -f "$OUT" ] || { echo "Repair refused: target note is absent." >&2; return 1; }
  [ -f "$JSONL" ] || { echo "Repair refused: source JSONL is absent." >&2; return 1; }

  repair_entries=$(mktemp)
  ensure_local_map
  reverse_lines < "$JSONL" | jq -Rr --arg ids "$repair_ids" --argjson localmap "$LOCALMAP" '
    (fromjson? // empty)
    | ((.session_id // "") + ":" + (.timestamp // "")) as $raw_id
    | ("clio:id:" + $raw_id) as $id
    | select(($ids | split("\n") | index($id)) != null)
    | "<!-- \($id) -->\n## \(.repo // "unknown" | ascii_upcase)\n\($localmap[.timestamp] // .timestamp)  \n\(.machine // "")\(if (.branch // "") != "" then " · \(.branch)" else "" end)\n\n> \"\((.prompt // "") | gsub("\n"; "\n> "))\"\n"
  ' > "$repair_entries"
  rendered_count=$(grep -c '^<!-- clio:id:' "$repair_entries" 2>/dev/null || true)
  [ "$rendered_count" = "$repair_count" ] || {
    rm -f "$repair_entries"
    echo "Repair refused: one or more delivered-missing IDs are absent from the source JSONL." >&2
    return 1
  }
  backup_target
  marker_line=$(grep -nF "$MARKER" "$OUT" | head -1 | cut -d: -f1)
  [ -n "$marker_line" ] || { rm -f "$repair_entries"; echo "Repair refused: marker is absent." >&2; return 1; }
  merged="$OUT_DIR/.${OUT_NAME}.clio-repair.$$"
  { head -n "$marker_line" "$OUT"; echo; cat "$repair_entries"; tail -n +"$((marker_line + 1))" "$OUT"; } > "$merged"
  mv "$merged" "$OUT"
  rm -f "$repair_entries"
  written_ids=$(grep -o 'clio:id:[^ ]*' "$OUT" 2>/dev/null || true)
  while IFS= read -r repair_id; do
    case $'\n'"$written_ids"$'\n' in *$'\n'"$repair_id"$'\n'*) ;; *) echo "Failed to verify repaired CLIO entry $repair_id." >&2; return 1 ;; esac
  done <<EOF
$repair_ids
EOF
  echo "repair: applied $repair_count entry(s)"
}

if [ "$MODE" = status ]; then
  status_report=$(reconcile_status)
  printf '%s\n' "$status_report"
  if status_requires_attention "$status_report"; then
    exit 1
  fi
  exit 0
fi

if [ "$MODE" = backfill ]; then run_backfill; exit $?; fi
if [ "$MODE" = repair ]; then run_repair; exit $?; fi

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
ensure_local_map
if [ "$LAST_LINE" -lt "$TOTAL_LINES" ]; then
tail -n +"$((LAST_LINE + 1))" "$JSONL" | reverse_lines | jq -Rr \
  --arg exclude "$EXCLUDE_REGEX" --arg existing_ids "$existing_ids" --argjson localmap "$LOCALMAP" '
  (fromjson? // empty)
  | select(($exclude | length) == 0 or ((.prompt // "") | test($exclude; "i") | not))
  | ((.session_id // "") + ":" + (.timestamp // "")) as $id
  | select(($existing_ids | split("\n") | index("clio:id:" + $id)) == null)
  | "<!-- clio:id:\($id) -->\n## \(.repo // "unknown" | ascii_upcase)\n\($localmap[.timestamp] // .timestamp)  \n\(.machine // "")\(if (.branch // "") != "" then " · \(.branch)" else "" end)\n\n> \"\((.prompt // "") | gsub("\n"; "\n> "))\"\n"
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
