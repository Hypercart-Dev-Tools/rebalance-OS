#!/usr/bin/env bash
# Smoke test for the optional PDDA lifecycle annotation in collect.sh (GH-193).
# Proves the happy path + the two Codex-review blockers before the feature ships
# (AGENTS.md: "write the smoke test that proves the happy path works before any feature code").
#
# Builds a throwaway scan root with two git repos and asserts collect.sh output:
#   * a PDDA repo (has PROJECT/PDDA.md) → emits pdda=yes + working_doc lines w/ ISO mtime
#   * a NON-PDDA repo that merely has a ROUTER.md → emits NO pdda= line (strict additivity)
#   * filenames with spaces survive; inbox=/working= count all *.md
# Read-only against the real device; all writes land in a mktemp dir it removes on exit.
set -uo pipefail

HERE=$(cd "$(dirname "$0")" && pwd -P)
COLLECT="$HERE/collect.sh"
fails=0
pass() { printf '  ok   %s\n' "$1"; }
fail() { printf '  FAIL %s\n' "$1"; fails=$((fails+1)); }

root=$(mktemp -d "${TMPDIR:-/tmp}/gh193-smoke.XXXXXX") || { echo "mktemp failed"; exit 1; }
trap 'rm -rf "$root"' EXIT

gitq() { git -C "$1" -c user.email=t@t -c user.name=t -c commit.gpgsign=false "${@:2}" >/dev/null 2>&1; }

# --- repo 1: PDDA-compliant -------------------------------------------------
pd="$root/pdda-repo"
mkdir -p "$pd/PROJECT/1-INBOX" "$pd/PROJECT/2-WORKING"
gitq "$pd" init
: > "$pd/PROJECT/PDDA.md"
: > "$pd/PROJECT/1-INBOX/GH-1-alpha.md"
: > "$pd/PROJECT/1-INBOX/notes.md"                 # non-GH inbox doc → inbox= must count it (=2)
: > "$pd/PROJECT/2-WORKING/GH-2-beta.md"
: > "$pd/PROJECT/2-WORKING/GH 3 spaces in name.md" # spaces must survive
gitq "$pd" add -A
gitq "$pd" commit -m "seed pdda repo"

# --- repo 2: NON-PDDA but carries a decoy ROUTER.md -------------------------
np="$root/plain-repo"
mkdir -p "$np"
gitq "$np" init
: > "$np/ROUTER.md"                                 # decoy: ROUTER.md alone must NOT trigger pdda=
: > "$np/README.md"
gitq "$np" add -A
gitq "$np" commit -m "seed plain repo"

# --- run the collector over just this throwaway root ------------------------
out=$(bash "$COLLECT" "$root" 2>/dev/null)

# Slice each repo's stanza (from its "## REPO …<name>" to the next "## REPO"/EOF).
stanza() { printf '%s\n' "$out" | awk -v r="$1" '
  $0 ~ "^## REPO " && index($0, r) {grab=1; print; next}
  /^## REPO /{grab=0}
  grab{print}'; }

pdda_stanza=$(stanza "/pdda-repo")
plain_stanza=$(stanza "/plain-repo")

# --- assertions -------------------------------------------------------------
printf '%s\n' "$pdda_stanza" | grep -q 'pdda=yes' \
  && pass "PDDA repo emits pdda=yes" || fail "PDDA repo missing pdda=yes"

printf '%s\n' "$pdda_stanza" | grep -q 'inbox=2' \
  && pass "inbox= counts all 1-INBOX/*.md (=2)" || fail "inbox= wrong (want 2): $(printf '%s' "$pdda_stanza" | grep -o 'inbox=[0-9]*')"

printf '%s\n' "$pdda_stanza" | grep -q 'working=2' \
  && pass "working= counts all 2-WORKING/*.md (=2)" || fail "working= wrong (want 2): $(printf '%s' "$pdda_stanza" | grep -o 'working=[0-9]*')"

printf '%s\n' "$pdda_stanza" | grep -q 'working_doc=GH 3 spaces in name.md' \
  && pass "working_doc preserves filenames with spaces" || fail "spaces filename lost"

printf '%s\n' "$pdda_stanza" | grep -Eq 'mtime=[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}' \
  && pass "mtime renders as YYYY-MM-DD HH:MM" || fail "mtime format wrong"

if printf '%s\n' "$plain_stanza" | grep -q 'pdda='; then
  fail "non-PDDA repo (ROUTER.md decoy) leaked a pdda= line — strict additivity broken"
else
  pass "non-PDDA repo emits no pdda= line (ROUTER.md alone does not trigger)"
fi

echo
if [ "$fails" -eq 0 ]; then echo "PASS — all GH-193 PDDA-annotation smoke checks green"; exit 0
else echo "FAIL — $fails check(s) failed"; exit 1; fi
