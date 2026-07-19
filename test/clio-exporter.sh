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

run_suite() {
  shell=$1
  key=$2
  fresh_note_and_idempotency "$shell" "$key"
  legacy_unidentified_note "$shell" "$key"
  marker_displaced "$shell" "$key"
  conflict_sibling "$shell" "$key"
  manifest_failure_is_nonfatal "$shell" "$key"
  echo "PASS: $shell"
}

[ -x "$EXPORTER" ] || fail "exporter is not executable: $EXPORTER"
run_suite bash default-bash
run_suite /bin/bash system-bash
