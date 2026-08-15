#!/bin/bash
# Fixture harness for the CLIO capture hook (log-prompt.sh).
#
# The hook lives as a heredoc inside utils/CLIO/INSTALL.md, so this harness
# extracts it by MARKER (not line numbers — the heredoc gets edited) and runs
# the extracted script against a throwaway $HOME.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
INSTALL_DOC="$ROOT/utils/CLIO/INSTALL.md"
TMP=$(mktemp -d "${TMPDIR:-/tmp}/clio-capture.XXXXXX")
trap 'rm -rf "$TMP"' EXIT

HOOK="$TMP/log-prompt.sh"
awk '/^cat > ~\/\.claude\/hooks\/log-prompt\.sh << .EOF.$/{f=1;next} f&&/^EOF$/{exit} f' \
  "$INSTALL_DOC" > "$HOOK"
[ -s "$HOOK" ] || { echo "FAIL: could not extract log-prompt.sh from $INSTALL_DOC" >&2; exit 1; }
chmod +x "$HOOK"

fail() { echo "FAIL: $*" >&2; exit 1; }

# Feed a prompt to the hook under a fresh $HOME; echo the resulting line count.
# Usage: capture <case> <prompt-json-string> [env assignments...]
run_hook() {
  shell=$1; case_name=$2; prompt=$3; shift 3
  home="$TMP/$case_name"
  mkdir -p "$home/.claude"
  printf '%s' "$prompt" \
    | env HOME="$home" CLAUDE_PROJECT_DIR="$ROOT" "$@" "$shell" "$HOOK" \
    || fail "$case_name: hook exited non-zero (it must always exit 0)"
  log="$home/.claude/prompt-log.jsonl"
  [ -f "$log" ] || : > "$log"
  wc -l < "$log" | tr -d ' '
}

json_input() { jq -nc --arg p "$1" '{session_id:"s1", prompt:$p}'; }

long_prompt="This is a substantive session-opening prompt that comfortably exceeds the one hundred character minimum threshold."

captures_substantive_prompt() {
  shell=$1
  n=$(run_hook "$shell" "substantive-$2" "$(json_input "$long_prompt")")
  [ "$n" = "1" ] || fail "expected substantive prompt to be captured, got $n line(s)"
  grep -qF "session-opening prompt" "$TMP/substantive-$2/.claude/prompt-log.jsonl" \
    || fail "captured line lost the prompt text"
}

skips_short_prompt() {
  shell=$1
  n=$(run_hook "$shell" "short-$2" "$(json_input 'push it')")
  [ "$n" = "0" ] || fail "expected short prompt to be skipped, got $n line(s)"
}

boundary_is_inclusive() {
  shell=$1
  exactly100=$(printf 'x%.0s' $(seq 1 100))
  n=$(run_hook "$shell" "boundary-$2" "$(json_input "$exactly100")")
  [ "$n" = "1" ] || fail "expected exactly-100-char prompt to be captured, got $n line(s)"
  n=$(run_hook "$shell" "boundary99-$2" "$(json_input "$(printf 'x%.0s' $(seq 1 99))")")
  [ "$n" = "0" ] || fail "expected 99-char prompt to be skipped, got $n line(s)"
}

skips_task_notification() {
  shell=$1
  note='[SYSTEM NOTIFICATION - NOT USER INPUT]
This is an automated background-task event, NOT a message from the user.
<task-notification>
<task-id>b90l1vf7i</task-id>
<summary>Monitor event: "CLIO marathon phase progress + terminal state"</summary>
<event>marathon: phase 1/2 clio-p1-idempotent reviewer=agy round-cap=7</event>
</task-notification>'
  n=$(run_hook "$shell" "tasknote-$2" "$(json_input "$note")")
  [ "$n" = "0" ] || fail "expected task-notification to be skipped, got $n line(s)"
}

skips_bare_system_notification() {
  shell=$1
  # Same automated preamble but no task-notification tag, and long enough to
  # clear the length filter — so only the marker test can catch it.
  note='[SYSTEM NOTIFICATION - NOT USER INPUT]
This is an automated background-task event that is deliberately long enough to exceed one hundred characters on its own.'
  n=$(run_hook "$shell" "sysnote-$2" "$(json_input "$note")")
  [ "$n" = "0" ] || fail "expected bare SYSTEM NOTIFICATION to be skipped, got $n line(s)"
}

strips_injected_blocks_before_measuring() {
  shell=$1
  # Real text is under 100 chars once the injected block is stripped, so this
  # must be SKIPPED — proving length is measured post-strip, not pre-strip.
  padded="<system-reminder>$(printf 'y%.0s' $(seq 1 400))</system-reminder>short ask"
  n=$(run_hook "$shell" "strip-$2" "$(json_input "$padded")")
  [ "$n" = "0" ] || fail "expected length to be measured after stripping, got $n line(s)"
}

threshold_is_configurable() {
  shell=$1
  n=$(run_hook "$shell" "override-$2" "$(json_input 'push it')" CLIO_MIN_PROMPT_CHARS=0)
  [ "$n" = "1" ] || fail "expected CLIO_MIN_PROMPT_CHARS=0 to capture a short prompt, got $n line(s)"
}

malformed_input_never_blocks() {
  shell=$1
  home="$TMP/malformed-$2"
  mkdir -p "$home/.claude"
  # Not JSON at all — the hook must still exit 0 and must not corrupt the log.
  printf '%s' 'this is not json {{{' \
    | env HOME="$home" CLAUDE_PROJECT_DIR="$ROOT" "$shell" "$HOOK" \
    || fail "malformed input made the hook exit non-zero"
  [ -s "$home/.claude/prompt-log-errors.log" ] \
    || fail "malformed input was not recorded in the error log"
  [ ! -s "$home/.claude/prompt-log.jsonl" ] \
    || fail "malformed input wrote a line to the prompt log"
}

captured_lines_are_valid_json() {
  shell=$1
  home="$TMP/substantive-$2"
  jq -e . "$home/.claude/prompt-log.jsonl" >/dev/null \
    || fail "captured line is not valid JSON"
}

run_suite() {
  shell=$1; key=$2
  captures_substantive_prompt "$shell" "$key"
  skips_short_prompt "$shell" "$key"
  boundary_is_inclusive "$shell" "$key"
  skips_task_notification "$shell" "$key"
  skips_bare_system_notification "$shell" "$key"
  strips_injected_blocks_before_measuring "$shell" "$key"
  threshold_is_configurable "$shell" "$key"
  malformed_input_never_blocks "$shell" "$key"
  captured_lines_are_valid_json "$shell" "$key"
  echo "PASS: $shell"
}

command -v jq >/dev/null 2>&1 || fail "jq is required to run this harness"

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
