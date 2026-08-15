#!/bin/bash
# Fixture harness for utils/CLIO/prompt-log-to-md.sh.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
EXPORTER="$ROOT/utils/CLIO/prompt-log-to-md.sh"
TMP=$(mktemp -d "${TMPDIR:-/tmp}/clio-exporter.XXXXXX")
trap 'rm -rf "$TMP"' EXIT

fail() { echo "FAIL: $*" >&2; exit 1; }
assert_contains() { grep -qF "$2" "$1" || fail "expected $1 to contain: $2"; }
assert_not_contains() { ! grep -qF "$2" "$1" || fail "expected $1 not to contain: $2"; }
assert_count() {
  actual=$(grep -cF "$2" "$1" || true)
  [ "$actual" = "$3" ] || fail "expected $1 to contain $3 occurrence(s) of $2, got $actual"
}
assert_before() {
  first=$(grep -nF "$2" "$1" | head -1 | cut -d: -f1)
  second=$(grep -nF "$3" "$1" | head -1 | cut -d: -f1)
  [ "$first" -lt "$second" ] || fail "expected $2 before $3 in $1"
}

json_line() {
  printf '{"timestamp":"%s","repo":"%s","branch":"main","machine":"fixture","session_id":"%s","prompt":"%s"}\n' "$1" "$2" "$3" "$4"
}

run_exporter() {
  shell=$1
  home=$2
  out=$3
  HOME="$home" PROMPT_LOG_EXCLUDE= "$shell" "$EXPORTER" "$out"
}

run_status() {
  shell=$1
  home=$2
  out=$3
  HOME="$home" PROMPT_LOG_EXCLUDE= "$shell" "$EXPORTER" --status "$out"
}

run_mode() {
  shell=$1
  home=$2
  out=$3
  mode=$4
  apply=${5:-}
  HOME="$home" PROMPT_LOG_EXCLUDE= "$shell" "$EXPORTER" "$mode" $apply "$out"
}

fresh_note_and_idempotency() {
  shell=$1
  case_dir="$TMP/fresh-$2"
  home="$case_dir/home"
  out="$case_dir/note.md"
  mkdir -p "$home/.claude"
  {
    json_line '2026-07-19T10:00:00Z' alpha one 'first prompt'
    json_line '2026-07-19T10:01:00Z' beta two 'second prompt'
  } > "$home/.claude/prompt-log.jsonl"

  run_exporter "$shell" "$home" "$out" > "$case_dir/first.out"
  assert_contains "$out" '# Claude Code Prompt Log'
  assert_contains "$out" '<!-- CLIO:ENTRIES -->'
  assert_before "$out" 'second prompt' 'first prompt'
  assert_count "$home/.claude/prompt-log-manifest.txt" 'clio:id:' 2

  cp "$out" "$case_dir/before.md"
  cp "$home/.claude/prompt-log-manifest.txt" "$case_dir/before-manifest.txt"
  run_exporter "$shell" "$home" "$out" > "$case_dir/second.out"
  cmp -s "$out" "$case_dir/before.md" || fail "second run changed output"
  cmp -s "$home/.claude/prompt-log-manifest.txt" "$case_dir/before-manifest.txt" || fail "second run changed manifest"
  assert_contains "$case_dir/second.out" 'Synced 0 new prompt(s)'

  # The receipt is independent of the cursor: a reset does not remove or duplicate it.
  rm "$home/.claude/prompt-log-to-md.state"
  run_exporter "$shell" "$home" "$out" > "$case_dir/reset.out"
  cmp -s "$home/.claude/prompt-log-manifest.txt" "$case_dir/before-manifest.txt" || fail "cursor reset changed manifest"
}

legacy_unidentified_note() {
  shell=$1
  case_dir="$TMP/legacy-$2"
  home="$case_dir/home"
  out="$case_dir/note.md"
  mkdir -p "$home/.claude"
  printf '%s\n' 'Legacy heading' '> "legacy prompt"' > "$out"
  json_line '2026-07-19T10:00:00Z' legacy session 'legacy prompt' > "$home/.claude/prompt-log.jsonl"

  run_exporter "$shell" "$home" "$out" > /dev/null
  # Pre-ID entries cannot participate in ID deduplication; documenting this current
  # behaviour keeps a future P3 migration deliberate rather than accidental.
  assert_count "$out" 'legacy prompt' 2
  assert_contains "$out" '<!-- clio:id:session:2026-07-19T10:00:00Z -->'
}

status_detection_is_read_only() {
  shell=$1
  case_dir="$TMP/status-$2"
  home="$case_dir/home"
  out="$case_dir/note.md"
  mkdir -p "$home/.claude"
  {
    json_line '2026-07-19T12:00:00Z' healthy delivered 'healthy prompt'
    json_line '2026-07-19T12:01:00Z' missing lost 'missing prompt'
    json_line '2026-07-19T12:02:00Z' legacy old 'legacy prompt'
    json_line '2026-07-19T12:03:00Z' excluded skip 'skip this prompt'
  } > "$home/.claude/prompt-log.jsonl"
  printf '%s\n' '# Heading' '<!-- CLIO:ENTRIES -->' \
    '<!-- clio:id:delivered:2026-07-19T12:00:00Z -->' '2026-07-19T12:00:00Z  ' 'fixture' '> "healthy prompt"' \
    '## LEGACY' '2026-07-19T12:02:00Z  ' 'fixture' '> "legacy prompt"' > "$out"
  printf '%s\n' 'clio:id:delivered:2026-07-19T12:00:00Z' 'clio:id:lost:2026-07-19T12:01:00Z' > "$home/.claude/prompt-log-manifest.txt"
  printf '%s\n' 4 > "$home/.claude/prompt-log-to-md.state"
  cp "$out" "$case_dir/note-before"
  cp "$home/.claude/prompt-log-manifest.txt" "$case_dir/manifest-before"
  cp "$home/.claude/prompt-log-to-md.state" "$case_dir/state-before"
  if HOME="$home" PROMPT_LOG_EXCLUDE='skip this prompt' "$shell" "$EXPORTER" --status "$out" > "$case_dir/status.out"; then
    fail "--status did not flag the missing delivered entry"
  fi
  cmp -s "$out" "$case_dir/note-before" || fail "--status changed note"
  cmp -s "$home/.claude/prompt-log-manifest.txt" "$case_dir/manifest-before" || fail "--status changed manifest"
  cmp -s "$home/.claude/prompt-log-to-md.state" "$case_dir/state-before" || fail "--status changed cursor"
  assert_contains "$case_dir/status.out" 'state: delivered-present=1'
  assert_contains "$case_dir/status.out" 'state: delivered-missing=1'
  assert_contains "$case_dir/status.out" 'state: legacy-unlabelled=1'
  assert_contains "$case_dir/status.out" 'state: excluded=1'
  assert_contains "$case_dir/status.out" 'missing-clio-id: clio:id:lost:2026-07-19T12:01:00Z'
  assert_contains "$case_dir/status.out" 'marker: displaced line=2 lines-above=1'
}

target_replacement_fails_after_export() {
  shell=$1
  case_dir="$TMP/replacement-$2"
  home="$case_dir/home"
  out="$case_dir/note.md"
  mkdir -p "$home/.claude"
  json_line '2026-07-19T13:00:00Z' replace one 'replacement prompt' > "$home/.claude/prompt-log.jsonl"
  run_exporter "$shell" "$home" "$out" > /dev/null
  printf '%s\n' '# replacement' '<!-- CLIO:ENTRIES -->' > "$out"
  if run_exporter "$shell" "$home" "$out" > "$case_dir/stdout" 2> "$case_dir/stderr"; then
    fail "replacement was not reported as failure"
  fi
  assert_contains "$case_dir/stdout" 'target-replacement: yes'
  assert_contains "$case_dir/stderr" 'run --status for details'
}

single_missing_entry_fails_after_export() {
  shell=$1
  case_dir="$TMP/missing-$2"
  home="$case_dir/home"
  out="$case_dir/note.md"
  mkdir -p "$home/.claude"
  {
    json_line '2026-07-19T14:00:00Z' loss one 'kept prompt'
    json_line '2026-07-19T14:01:00Z' loss two 'removed prompt'
  } > "$home/.claude/prompt-log.jsonl"
  run_exporter "$shell" "$home" "$out" > /dev/null
  awk '
    $0 == "<!-- clio:id:two:2026-07-19T14:01:00Z -->" { dropping = 1; next }
    dropping && /^<!-- clio:id:/ { dropping = 0 }
    !dropping { print }
  ' "$out" > "$out.missing" && mv "$out.missing" "$out"
  if run_exporter "$shell" "$home" "$out" > "$case_dir/stdout" 2> "$case_dir/stderr"; then
    fail "a missing delivered entry was not reported as failure"
  fi
  assert_contains "$case_dir/stdout" 'state: delivered-missing=1'
  assert_contains "$case_dir/stdout" 'missing-clio-id: clio:id:two:2026-07-19T14:01:00Z'
}

marker_displaced() {
  shell=$1
  case_dir="$TMP/displaced-$2"
  home="$case_dir/home"
  out="$case_dir/note.md"
  mkdir -p "$home/.claude"
  printf '%s\n' '# Custom heading' 'This text is above the live marker.' '<!-- CLIO:ENTRIES -->' > "$out"
  head -n 2 "$out" > "$case_dir/above-before"
  json_line '2026-07-19T10:00:00Z' marker session 'marker prompt' > "$home/.claude/prompt-log.jsonl"

  run_exporter "$shell" "$home" "$out" > /dev/null
  head -n 2 "$out" > "$case_dir/above-after"
  cmp -s "$case_dir/above-before" "$case_dir/above-after" || fail "content above marker changed"
  assert_contains "$out" 'marker prompt'
}

conflict_sibling() {
  shell=$1
  case_dir="$TMP/conflict-$2"
  home="$case_dir/home"
  out="$case_dir/note.md"
  sibling="$case_dir/note.sync-conflict-fixture.md"
  mkdir -p "$home/.claude"
  printf '%s\n' '# Note' '<!-- CLIO:ENTRIES -->' '<!-- clio:id:present:2026-07-19T09:00:00Z -->' '## PRESENT' '> "already here"' > "$out"
  printf '%s\n' '<!-- clio:id:recovered:2026-07-19T09:01:00Z -->' '## RECOVERED' '> "from conflict"' > "$sibling"
  json_line '2026-07-19T09:00:00Z' present present 'already here' > "$home/.claude/prompt-log.jsonl"

  run_exporter "$shell" "$home" "$out" > "$case_dir/run.out"
  assert_contains "$out" 'clio:id:recovered:2026-07-19T09:01:00Z'
  [ ! -e "$sibling" ] || fail "conflict sibling was not quarantined"
  [ -f "$case_dir/.clio-reconciled/$(basename "$sibling")" ] || fail "quarantined sibling missing"
}

manifest_failure_is_nonfatal() {
  shell=$1
  case_dir="$TMP/manifest-failure-$2"
  home="$case_dir/home"
  out="$case_dir/note.md"
  bad_manifest="/dev/null/clio-manifest.txt"
  mkdir -p "$home/.claude"
  json_line '2026-07-19T11:00:00Z' receipt receipt 'receipt survives failure' > "$home/.claude/prompt-log.jsonl"

  HOME="$home" PROMPT_LOG_EXCLUDE= CLIO_MANIFEST="$bad_manifest" "$shell" "$EXPORTER" "$out" > "$case_dir/stdout" 2> "$case_dir/stderr" || fail "manifest failure aborted export"
  assert_contains "$out" 'receipt survives failure'
  assert_contains "$case_dir/stderr" 'Unable to update CLIO manifest'
}

backfill_then_targeted_repair() {
  shell=$1
  case_dir="$TMP/p3-$2"
  home="$case_dir/home"
  out="$case_dir/note.md"
  mkdir -p "$home/.claude"
  {
    json_line '2026-07-17T19:03:00Z' import legacy 'first CLIO-import prompt'
    json_line '2026-07-17T19:05:00Z' import missing-one 'second CLIO-import prompt'
    json_line '2026-07-17T19:07:00Z' import missing-two 'third CLIO-import prompt'
  } > "$home/.claude/prompt-log.jsonl"
  printf '%s\n' '# Protected heading' 'This must survive byte-for-byte.' '<!-- CLIO:ENTRIES -->' \
    '## IMPORT' '2026-07-17T19:03:00Z  ' 'fixture · main' '' '> "first CLIO-import prompt"' \
    '## UNKNOWN' '2026-07-17T19:09:00Z  ' 'fixture' '' '> "no matching source prompt"' > "$out"
  printf '%s\n' 'clio:id:missing-one:2026-07-17T19:05:00Z' 'clio:id:missing-two:2026-07-17T19:07:00Z' > "$home/.claude/prompt-log-manifest.txt"
  head -n 3 "$out" > "$case_dir/above-before"
  cp "$out" "$case_dir/before-dry-run"

  run_mode "$shell" "$home" "$out" --backfill > "$case_dir/backfill-dry.out"
  cmp -s "$out" "$case_dir/before-dry-run" || fail "backfill dry-run changed note"
  assert_contains "$case_dir/backfill-dry.out" 'clio:id:legacy:2026-07-17T19:03:00Z'
  assert_contains "$case_dir/backfill-dry.out" 'dry-run'
  assert_contains "$case_dir/backfill-dry.out" 'skipped 1 unlabelled entry(s)'

  if run_mode "$shell" "$home" "$out" --repair --apply > "$case_dir/repair-blocked.out" 2> "$case_dir/repair-blocked.err"; then
    fail "repair applied with legacy entries still unlabelled"
  fi
  assert_contains "$case_dir/repair-blocked.err" 'run --backfill --apply first'
  assert_not_contains "$out" 'clio:id:missing-one:2026-07-17T19:05:00Z'

  run_mode "$shell" "$home" "$out" --backfill --apply > "$case_dir/backfill-apply.out"
  assert_contains "$out" '<!-- clio:id:legacy:2026-07-17T19:03:00Z -->'
  assert_contains "$home/.claude/prompt-log-manifest.txt" 'clio:id:legacy:2026-07-17T19:03:00Z'
  assert_contains "$case_dir/backfill-apply.out" 'backup:'
  head -n 3 "$out" > "$case_dir/above-after-backfill"
  cmp -s "$case_dir/above-before" "$case_dir/above-after-backfill" || fail "backfill changed content above marker"
  cp "$out" "$case_dir/backfilled-note"
  run_mode "$shell" "$home" "$out" --backfill --apply > "$case_dir/backfill-second.out"
  cmp -s "$out" "$case_dir/backfilled-note" || fail "second backfill changed note"
  assert_contains "$case_dir/backfill-second.out" '0 confident legacy entries'
  assert_not_contains "$out" 'clio:id:unknown:'

  run_mode "$shell" "$home" "$out" --repair > "$case_dir/repair-dry.out"
  assert_contains "$case_dir/repair-dry.out" 'repair: clio:id:missing-one:2026-07-17T19:05:00Z'
  assert_contains "$case_dir/repair-dry.out" 'repair: clio:id:missing-two:2026-07-17T19:07:00Z'
  assert_not_contains "$out" 'clio:id:missing-one:2026-07-17T19:05:00Z'
  run_mode "$shell" "$home" "$out" --repair --apply > "$case_dir/repair-apply.out"
  assert_contains "$case_dir/repair-apply.out" 'backup:'
  assert_contains "$out" '<!-- clio:id:missing-one:2026-07-17T19:05:00Z -->'
  assert_contains "$out" '<!-- clio:id:missing-two:2026-07-17T19:07:00Z -->'
  assert_contains "$out" '> "second CLIO-import prompt"'
  assert_contains "$out" '> "third CLIO-import prompt"'
  head -n 3 "$out" > "$case_dir/above-after-repair"
  cmp -s "$case_dir/above-before" "$case_dir/above-after-repair" || fail "repair changed content above marker"
  cp "$out" "$case_dir/repaired-note"
  run_mode "$shell" "$home" "$out" --repair --apply > "$case_dir/repair-second.out"
  cmp -s "$out" "$case_dir/repaired-note" || fail "second repair changed note"
  assert_contains "$case_dir/repair-second.out" 'repair: 0 delivered-missing entries'
}

local_time_display_keeps_utc_ids() {
  shell=$1
  case_dir="$TMP/localtime-$2"
  home="$case_dir/home"
  out="$case_dir/note.md"
  mkdir -p "$home/.claude"
  json_line '2026-07-19T21:27:50Z' demo s1 'summer prompt' > "$home/.claude/prompt-log.jsonl"
  json_line '2026-01-15T21:27:50Z' demo s2 'winter prompt' >> "$home/.claude/prompt-log.jsonl"

  run_exporter "$shell" "$home" "$out" > /dev/null

  # The ID must stay UTC — it is "session:timestamp" and is the dedup key.
  assert_contains "$out" '<!-- clio:id:s1:2026-07-19T21:27:50Z -->'
  assert_contains "$out" '<!-- clio:id:s2:2026-01-15T21:27:50Z -->'

  # The DISPLAYED line must be local. Skip the assertion when python3 is
  # absent, since the exporter then deliberately falls back to UTC.
  if command -v python3 >/dev/null 2>&1 || [ -x /usr/bin/python3 ]; then
    py=$(command -v python3 || echo /usr/bin/python3)
    summer=$("$py" -c "from datetime import datetime; print(datetime.fromisoformat('2026-07-19T21:27:50+00:00').astimezone().strftime('%Y-%m-%d %H:%M:%S %Z'))")
    winter=$("$py" -c "from datetime import datetime; print(datetime.fromisoformat('2026-01-15T21:27:50+00:00').astimezone().strftime('%Y-%m-%d %H:%M:%S %Z'))")
    assert_contains "$out" "$summer"
    assert_contains "$out" "$winter"
    # Guards the jq strflocaltime DST bug: summer and winter must not render
    # with the same zone abbreviation in a DST-observing zone.
    if [ "$(date +%Z)" != "UTC" ]; then
      [ "$summer" != "$winter" ] || fail "summer and winter rendered identically"
    fi
  fi

  # Re-running must not duplicate: the localized display line must never be
  # mistaken for a new entry. This is the whole duplication hazard.
  cp "$out" "$case_dir/before.md"
  run_exporter "$shell" "$home" "$out" > "$case_dir/second.out"
  cmp -s "$out" "$case_dir/before.md" || fail "second run changed a localized note"
  assert_count "$out" '<!-- clio:id:s1:' 1
  assert_count "$out" '<!-- clio:id:s2:' 1

  # A cursor reset must also stay idempotent against localized display lines.
  rm "$home/.claude/prompt-log-to-md.state"
  run_exporter "$shell" "$home" "$out" > /dev/null
  cmp -s "$out" "$case_dir/before.md" || fail "cursor reset duplicated a localized note"
}

malformed_source_row_is_dropped() {
  shell=$1
  case_dir="$TMP/malformed-$2"
  home="$case_dir/home"
  out="$case_dir/note.md"
  mkdir -p "$home/.claude"
  {
    json_line '2026-07-20T07:59:00Z' before before 'row before malformed'
    # Truncated JSON: unterminated string, no closing brace. jq's `fromjson?`
    # turns this into an error, which `// empty` swallows — the documented
    # "malformed lines ... are dropped without aborting the run" behaviour.
    printf '%s\n' '{"timestamp":"2026-07-20T08:00:00Z","repo":"broken","branch":"main","machine":"fixture","session_id":"broken","prompt":"truncated row'
    json_line '2026-07-20T08:01:00Z' after after 'row after malformed'
  } > "$home/.claude/prompt-log.jsonl"

  run_exporter "$shell" "$home" "$out" > "$case_dir/first.out"
  assert_contains "$out" 'row before malformed'
  assert_contains "$out" 'row after malformed'
  assert_not_contains "$out" 'truncated row'
  assert_not_contains "$out" 'broken'
  assert_count "$out" 'clio:id:before:2026-07-20T07:59:00Z' 1
  assert_count "$out" 'clio:id:after:2026-07-20T08:01:00Z' 1

  # The cursor must still advance past the malformed line (it's consumed, not
  # retried forever), and re-running must stay a clean no-op — no crash, no
  # duplicate entries, no attempt to re-parse the dropped row.
  cp "$out" "$case_dir/before.md"
  run_exporter "$shell" "$home" "$out" > "$case_dir/second.out"
  cmp -s "$out" "$case_dir/before.md" || fail "second run changed output after a malformed row"
  assert_contains "$case_dir/second.out" 'Synced 0 new prompt(s)'
}

run_suite() {
  shell=$1
  key=$2
  fresh_note_and_idempotency "$shell" "$key"
  local_time_display_keeps_utc_ids "$shell" "$key"
  legacy_unidentified_note "$shell" "$key"
  marker_displaced "$shell" "$key"
  status_detection_is_read_only "$shell" "$key"
  single_missing_entry_fails_after_export "$shell" "$key"
  target_replacement_fails_after_export "$shell" "$key"
  conflict_sibling "$shell" "$key"
  manifest_failure_is_nonfatal "$shell" "$key"
  backfill_then_targeted_repair "$shell" "$key"
  malformed_source_row_is_dropped "$shell" "$key"
  echo "PASS: $shell"
}

[ -x "$EXPORTER" ] || fail "exporter is not executable: $EXPORTER"

# GH-242: the second cell is only meaningful when the two interpreters are actually
# different binaries. On a host where `bash` on PATH resolves to /bin/bash they are the
# same file, and running the suite twice produced two PASS lines that together proved
# nothing more than one. Report the truth instead of the reassuring number.
run_second_cell() {
  local first_resolved second_resolved
  first_resolved="$(readlink -f "$(command -v bash)" 2>/dev/null || command -v bash)"
  second_resolved="$(readlink -f /bin/bash 2>/dev/null || echo /bin/bash)"
  if [ "$first_resolved" = "$second_resolved" ]; then
    echo "SKIP: /bin/bash — same interpreter as \`bash\` on this host ($first_resolved);"
    echo "      a second run would repeat the first, not widen coverage."
    return 0
  fi
  run_suite /bin/bash system-bash
}

run_suite bash default-bash
run_second_cell
