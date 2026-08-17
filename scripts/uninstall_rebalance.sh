#!/bin/bash
# rebalance OS — reverse everything scripts/install_*.sh put on this device.
#
#     scripts/uninstall_rebalance.sh                    # dry run: print the plan, change nothing
#     scripts/uninstall_rebalance.sh --apply            # unload and delete the launchd jobs
#     scripts/uninstall_rebalance.sh --apply --include-data      # also delete logs and temp state
#     scripts/uninstall_rebalance.sh --apply --include-secrets   # also delete keyring entries
#     scripts/uninstall_rebalance.sh --apply --include-orphans   # also delete jobs whose
#                                                                # executable is already gone
#
# Two design rules do the real work here.
#
# 1. THE JOB LIST IS DERIVED, NEVER HARDCODED. install_common.sh renders
#    scripts/<label>.plist.template into ~/Library/LaunchAgents/<label>.plist, so the set of
#    templates IS the set of installable jobs. Globbing the templates means a job added
#    tomorrow is uninstallable tomorrow, with no edit here. A hardcoded list would be stale on
#    the next install script anyone writes — the exact drift this repo keeps re-learning.
#
# 2. OWNERSHIP IS PROVEN BEFORE ANYTHING IS DELETED. ~/Library/LaunchAgents also holds
#    com.google.keystone.agent, com.setapp.*, homebrew.mxcl.mysql and others. Matching a label
#    is not enough, and neither is finding our path somewhere in the file: this parses each
#    plist and requires the executable it actually LAUNCHES to be ours. A label collision with
#    unrelated software is therefore not removable, which is what makes the tool safe to hand
#    to someone else.
#
# Out of scope by design: the git checkout, .venv, and HiQS. HiQS is independently installed
# (its own keyring service, config, and database) and must keep working after a full uninstall.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REBALANCE_DIR="${RB_UNINSTALL_REPO_DIR:-$(cd "$SCRIPT_DIR/.." && pwd)}"
LAUNCH_AGENTS_DIR="${RB_UNINSTALL_AGENTS_DIR:-$HOME/Library/LaunchAgents}"
TEMPLATE_DIR="${RB_UNINSTALL_TEMPLATE_DIR:-$SCRIPT_DIR}"

APPLY=0
INCLUDE_DATA=0
INCLUDE_SECRETS=0
# Allow removing a job whose executable no longer exists. Separate from the default proof on
# purpose: it is the one case where we delete WITHOUT positive evidence of ownership, so it has
# to be asked for.
INCLUDE_ORPHANS=0

# Jobs this repo installs that do NOT follow the template convention, as `label|marker` pairs.
# Named explicitly and never matched by prefix: `com.user.*` is a generic namespace and
# globbing it would sweep up anything else on the machine that happened to use it.
#
# Each carries its OWN ownership marker because experimental/git-pulse/install.sh copies its
# executable to ~/bin and its config to ~/.config/git-pulse, so the rendered plist never
# mentions this repository. Checking these against the repo path would refuse to remove jobs
# that are genuinely ours — the tool would then exit non-zero on every run and never be able
# to finish an uninstall on a machine where git-pulse is installed.
NON_TEMPLATE_JOBS=(
    "com.user.git-pulse|$HOME/bin/git-pulse"
    "com.user.git-pulse-health|$HOME/bin/git-pulse-write-health"
)

# Directories holding generated state. Removal is irreversible, so it is opt-in and never part
# of a default run: unloading a job can be undone by re-running its installer, but deleting a
# log history cannot be undone at all.
DATA_PATHS=(
    "$HOME/Library/Logs/rebalance-os"
    "$REBALANCE_DIR/temp/logs"
)

KEYRING_SERVICE="rebalance-os"

removed=0
skipped_absent=0
skipped_foreign=0
failures=0

usage() {
    sed -n '2,26p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
    exit 0
}

while [ $# -gt 0 ]; do
    case "$1" in
        --apply) APPLY=1 ;;
        --include-data) INCLUDE_DATA=1 ;;
        --include-secrets) INCLUDE_SECRETS=1 ;;
        --include-orphans) INCLUDE_ORPHANS=1 ;;
        -h|--help) usage ;;
        *) echo "ERROR: unknown option: $1 (try --help)" >&2; exit 2 ;;
    esac
    shift
done

say() { printf '%s\n' "$*"; }
act() { if [ "$APPLY" -eq 1 ]; then printf '  %s\n' "$*"; else printf '  [dry-run] %s\n' "$*"; fi; }

# Print the single executable a plist actually launches. No output means the file could not be
# parsed or launches nothing, and callers must treat that as "not ours" (fail closed).
#
# plistlib rather than plutil because plutil is macOS-only and CI runs ubuntu-latest; a check
# that cannot run in CI is a check nobody is testing.
rb_plist_executables() {
    python3 - "$1" "${2:-1}" <<'PY' 2>/dev/null
import os
import plistlib, sys

try:
    with open(sys.argv[1], "rb") as handle:
        data = plistlib.load(handle)
except Exception:
    sys.exit(1)
if not isinstance(data, dict):
    sys.exit(1)

# ONE authoritative executable, following launchd's own precedence (QA r2 Blocker 2).
# Printing both Program and ProgramArguments[0] and accepting whichever matched was an
# ownership bypass: a foreign plist could set Program=/opt/evil/tool — the binary launchd
# actually runs — while parking a repo path in ProgramArguments[0] purely to satisfy the
# check. launchd uses Program as the executable when present, and treats ProgramArguments[0]
# as argv[0] rather than the binary, so that is the only entry ownership may rest on.
program = data.get("Program")
arguments = data.get("ProgramArguments")

if program is not None:
    if not isinstance(program, str):
        sys.exit(1)
    executable = program
    operands = arguments[1:] if isinstance(arguments, list) else []
elif isinstance(arguments, list) and arguments:
    if not isinstance(arguments[0], str):
        sys.exit(1)
    executable = arguments[0]
    operands = arguments[1:]
else:
    sys.exit(1)

# An interpreter that is ours does not make the JOB ours (QA r9 Blocker). Three templates
# launch {{PYTHON}} — a binary inside the checkout — with their real work in argument 1, so a
# colliding plist could borrow our interpreter to run /opt/foreign.py and pass a check that
# looked only at the executable. Whatever the interpreter is told to run must be ours too.
#
# Round 2 guarded the mirror image (a FOREIGN interpreter running our script, refused). Both
# halves are needed: ownership means we control the binary AND the code it executes.
# A relative path is unresolvable here (QA r10 Blocker). os.path.realpath() would resolve it
# against the UNINSTALLER's working directory, while launchd resolves it against the plist's
# own WorkingDirectory — so a colliding job could pair our real interpreter with a relative
# "scripts/health_issue_reporter.py" and WorkingDirectory=/opt/foreign, look owned from a
# checkout CWD, and actually execute /opt/foreign/scripts/health_issue_reporter.py.
# Every shipped template renders absolute paths ({{REBALANCE_DIR}}/..., {{PYTHON}}), so
# refusing relative ones costs nothing real and removes the ambiguity entirely.
if not os.path.isabs(executable):
    sys.exit(1)

script_operand = None
for candidate in operands:
    if not isinstance(candidate, str):
        sys.exit(1)
    if candidate.startswith("-c") or candidate.startswith("-m"):
        # Inline code or a module name: there is no path to verify, so ownership cannot be
        # proven at all. No template uses either form.
        #
        # startswith, not equality: Python accepts the COMPACT spellings "-cimport os; ..."
        # and "-mhttp.server", which an exact match let through as ordinary flags — the
        # interpreter alone then satisfied the boundary and a colliding plist running
        # arbitrary inline code was deletable. Long options are unaffected ("--close" begins
        # "--"), and every flag in the twelve shipped templates is a long option.
        sys.exit(1)
    if candidate.startswith("-"):
        continue  # a flag, not the thing being run
    script_operand = candidate
    break

# Resolve symlinks before ownership is judged (QA r3 Blocker). Comparing the SPELLING of a
# path is not the same as knowing what runs: a symlink at "$REBALANCE_DIR/bin/owned-looking"
# pointing to /opt/foreign/tool reads as ours and executes something else entirely.
resolved = os.path.realpath(executable)

# The executable must EXIST to prove ownership (QA r4 Blocker). realpath normalises a string
# whether or not anything is there, so without this a foreign plist naming
# "$REBALANCE_DIR/not-ours/never-existed" was deleted. A path that has never existed cannot
# be evidence that the job belongs to this installation. Orphan cleanup — a half-removed
# checkout leaving jobs whose files are already gone — is a real need, but it is a DIFFERENT
# operation and gets its own opt-in flag rather than weakening the default proof.
# Existence alone is not enough (QA r5 Blocker): "$REBALANCE_DIR/scripts" exists and sits
# under the checkout, so a foreign plist naming a DIRECTORY passed the ownership test even
# though launchd could never launch it. What proves ownership is a real, executable file.
#
# --include-orphans relaxes ONLY the absent case — a half-removed checkout whose files are
# gone. An existing-but-not-executable target is never accepted under either mode, because
# that is not an orphan, it is a thing that was never launchable.
if os.path.exists(resolved):
    if not (os.path.isfile(resolved) and os.access(resolved, os.X_OK)):
        sys.exit(1)
elif sys.argv[2] == "1":
    sys.exit(1)

# NOTHING is printed until EVERY path has been validated. Printing the executable first and
# exiting non-zero later leaked a partial result: command substitution keeps the stdout it
# already captured and discards the exit status, so a job with a valid interpreter and an
# invalid script operand arrived at the caller looking like a clean single-path success.
# Caught by the relative-operand test, which deleted the plist it was written to preserve.
lines = [resolved]

# The script operand is checked the same way minus the executable bit — a .py passed to an
# interpreter is read, not executed. The caller requires EVERY line to satisfy the ownership
# boundary, so a foreign script fails the job even though the interpreter passed.
if script_operand is not None:
    if not os.path.isabs(script_operand):
        sys.exit(1)  # same WorkingDirectory ambiguity as the executable above
    resolved_operand = os.path.realpath(script_operand)
    if os.path.exists(resolved_operand):
        if not os.path.isfile(resolved_operand):
            sys.exit(1)
    elif sys.argv[2] == "1":
        sys.exit(1)
    lines.append(resolved_operand)

for line in lines:
    print(line)
PY
}

# The strongest proof available, and the one that ends a whole class of bypasses.
#
# Rounds 9-12 were a losing game: every round modelled a bit more of Python's command line
# (script operand, then `-c`/`-m`, then their compact spellings, then `-X` consuming its next
# argument) and every round the reviewer found another wrinkle. Modelling an interpreter's
# grammar to decide what it will execute is not a fight worth having.
#
# `install_common.sh` RENDERS these plists from `scripts/<label>.plist.template`, substituting
# {{REBALANCE_DIR}}, {{PYTHON}}, {{HOME}}. So the question is not "does this look owned" but
# "is this what our installer would have written" — a structural comparison with no semantics
# to get wrong. Verified against the live backup: all 7 installed template jobs match exactly.
#
# It subsumes the orphan case for free: the comparison is on the plist's contents, so a job
# whose files were already deleted still matches its template.
rb_matches_template() {
    local template="$1"
    local plist="$2"
    RB_REPO="$REBALANCE_DIR" RB_PY="$REBALANCE_DIR/.venv/bin/python" RB_HOME="$HOME" \
    python3 - "$template" "$plist" 2>/dev/null <<'PY' 
import os, plistlib, sys

try:
    rendered = (
        open(sys.argv[1], encoding="utf-8").read()
        .replace("{{REBALANCE_DIR}}", os.environ["RB_REPO"])
        .replace("{{PYTHON}}", os.environ["RB_PY"])
        .replace("{{HOME}}", os.environ["RB_HOME"])
    )
    want = plistlib.loads(rendered.encode("utf-8"))
    with open(sys.argv[2], "rb") as handle:
        got = plistlib.load(handle)
except Exception:
    sys.exit(1)

if not isinstance(want, dict) or not isinstance(got, dict):
    sys.exit(1)

# Compare only what determines WHAT RUNS. Schedules and log paths may legitimately drift
# without changing whose job this is.
# Everything that determines WHAT RUNS and AS WHOM. Label is here because a foreign plist at
# our filename could otherwise copy the launch fields while declaring Label=com.foreign.agent.
for key in (
    "Label", "Program", "ProgramArguments", "WorkingDirectory",
    "RootDirectory", "UserName", "GroupName", "Umask",
):
    if want.get(key) != got.get(key):
        sys.exit(1)

# EnvironmentVariables is deliberately NOT compared wholesale, and this is the one place the
# structural proof has to be a judgement rather than an equality.
#
# Measured on the live machine: comparing the WHOLE plist matched only 1 of 7 installed jobs.
# The installed plists predate template changes (`Nice: 5` was added since), and pulse-sync
# carries a deliberate local `PULSE_PUSH=false`. Byte-equality would refuse six of the
# operator's nine real jobs — a check that refuses everything is not a safe check, it is a
# broken one.
#
# So instead of demanding the environment be identical, require that nothing in it can
# REDIRECT execution. PYTHONPATH/PYTHONHOME make the repo-owned interpreter import
# attacker-controlled code; the DYLD_/LD_ family hijacks the loader; PATH re-points the
# commands a shell job runs. A benign app-level override like PULSE_PUSH cannot.
# INVERTED: the environment must be exactly what the template ships. Nothing else.
#
# Three rounds tried to enumerate the dangerous variables and each list was one behind:
# PYTHONPATH/PYTHONHOME, then PYTHONUSERBASE (user-site sitecustomize.py runs at startup),
# then BASH_ENV (non-interactive bash sources it before the script). Widening to prefix
# families still missed BASH_ENV, and the family after that is unknowable — the set of ways an
# environment can redirect a program is open-ended, so denying known-bad members of it cannot
# terminate.
#
# The only closed formulation is the one this tool already uses everywhere else: ownership
# means "this is what our installer would have written". An environment variable we did not
# render is not ours to reason about, dangerous or benign, so it is refused and NAMED.
#
# This is not free. On the live machine pulse-sync carries a hand-added PULSE_PUSH=false, so it
# is now refused rather than removed — a real job the operator must handle deliberately. That
# is the correct trade for a deletion tool: a refusal is recoverable and loud, a wrong deletion
# is neither.
environment = got.get("EnvironmentVariables") or {}
expected_environment = want.get("EnvironmentVariables") or {}
if not isinstance(environment, dict) or not isinstance(expected_environment, dict):
    sys.exit(1)
if environment != expected_environment:
    differing = sorted(
        set(environment) ^ set(expected_environment)
        | {k for k in set(environment) & set(expected_environment)
           if environment[k] != expected_environment[k]}
    )
    # stdout, not stderr: the caller suppresses stderr to keep plistlib noise out of the
    # report, so a diagnostic written there was promised in the comments and delivered to
    # /dev/null. Names only — a value could hold a secret.
    print("environment differs: " + ", ".join(differing))
    sys.exit(1)
sys.exit(0)
PY
}

# Canonical form of a path, for comparing like with like. The executable side is resolved in
# the parser, so the marker side has to be resolved too or a symlinked checkout would stop
# matching its own jobs.
rb_realpath() {
    python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$1" 2>/dev/null || printf '%s\n' "$1"
}

# Prove a plist belongs to us by inspecting WHAT IT LAUNCHES, not by matching text anywhere in
# the file (QA r1, two Blockers). A substring match over the raw XML was deletion-by-mention:
#
#   * a foreign plist naming our path in a comment or a StandardOutPath passed the check
#   * "$REBALANCE_DIR-archive/tool" passed on a bare prefix, with no path boundary
#   * "$HOME/bin/git-pulse" is itself a prefix of "$HOME/bin/git-pulse-evil"
#
# Two modes, both anchored on the executable:
#   exact  — the launched binary must EQUAL the marker (non-template jobs in ~/bin)
#   under  — the launched binary must live beneath "$marker/" (jobs run from this repo); the
#            trailing slash is the path boundary that kills the prefix attack
#
# Deliberately NOT accepted: a foreign interpreter running a script of ours (Program=/usr/bin/
# python3 with "$REBALANCE_DIR/x.py" as an argument). QA r2 proposed allowing it, but it would
# let any plist claim ownership by naming one of our files as an argument, which is the same
# deletion-by-mention hole in a new place. It is also not a live case: install_common.sh
# renders {{PYTHON}} to "$REBALANCE_DIR/.venv/bin/python", so the interpreter-backed jobs
# (health-check, health-check-triage, pulse-warning-watch) launch a binary INSIDE the repo and
# pass `under` already — verified by rendering one and running the tool against it. If a future
# template ever used a system interpreter, this refuses it loudly rather than deleting on a
# weaker proof, which is the correct direction to fail.
rb_is_ours() {
    local plist="$1"
    local marker="$2"
    local mode="$3"
    local executable
    marker="$(rb_realpath "$marker")"

    local require_exists=1
    [ "$INCLUDE_ORPHANS" -eq 1 ] && require_exists=0
    local seen=0

    # EVERY emitted path must be ours — the executable and, for an interpreter-backed job, the
    # script it runs. Returning on the first match (the previous behaviour) meant a repo-owned
    # interpreter could vouch for a foreign script.
    while IFS= read -r executable; do
        [ -n "$executable" ] || continue
        seen=$((seen + 1))
        case "$mode" in
            exact)
                # Every emitted path must equal the marker. The non-template jobs launch a
                # single binary with no script operand, so this is exactly one comparison.
                # An earlier attempt allowed operands under dirname($marker) — which put
                # "$HOME/bin/git-pulse-evil" back inside the boundary and reopened the round-1
                # prefix hole. If one of these jobs ever gains an operand, refusing it is the
                # safe direction to fail.
                [ "$executable" = "$marker" ] || return 1
                ;;
            under)
                case "$executable" in "$marker"/*) continue ;; esac
                return 1
                ;;
        esac
    done <<EOF
$(rb_plist_executables "$plist" "$require_exists")
EOF
    [ "$seen" -gt 0 ]
}

# rb_remove_job <label> [ownership-marker] [exact|under]
rb_remove_job() {
    local label="$1"
    local marker="${2:-$REBALANCE_DIR}"
    local mode="${3:-under}"
    local template="${4:-}"
    local plist="$LAUNCH_AGENTS_DIR/$label.plist"

    # A broken symlink at the plist path fails -f, so it used to be reported as "not installed"
    # and the run exited 0 while the stale entry sat there (QA r6). "Absent" and "present but
    # unreadable" are different states and must not collapse into the reassuring one. Ownership
    # cannot be proven for a link with no target, so it is refused rather than removed.
    if [ -L "$plist" ] && [ ! -e "$plist" ]; then
        say "  ! $label: broken symlink at $plist — cannot prove ownership, refusing to remove"
        skipped_foreign=$((skipped_foreign + 1))
        return 1
    fi

    if [ ! -f "$plist" ]; then
        say "  - $label: not installed"
        skipped_absent=$((skipped_absent + 1))
        return 0
    fi

    # A template-derived job is proved by matching what the installer would have rendered.
    # Only jobs with no template (the ~/bin ones) fall back to path-based ownership.
    if [ -n "$template" ]; then
        local detail=""
        if ! detail="$(rb_matches_template "$template" "$plist")"; then
            say "  ! $label: EXISTS but does not match $template — refusing to remove"
            say "      $plist"
            [ -n "$detail" ] && say "      $detail"
            say "      (hand-edited, or another program's job under the same label)"
            skipped_foreign=$((skipped_foreign + 1))
            return 1
        fi
    elif ! rb_is_ours "$plist" "$marker" "$mode"; then
        # Reported loudly and counted as a failure: the operator asked for this job to be gone
        # and it is still here. Silently skipping would let a partial uninstall exit 0.
        say "  ! $label: EXISTS but does not launch an existing $marker ($mode) — refusing to remove"
        say "      (if its executable is already gone, re-run with --include-orphans)"
        say "      $plist"
        skipped_foreign=$((skipped_foreign + 1))
        return 1
    fi

    act "unload and delete $plist"
    if [ "$APPLY" -eq 1 ]; then
        # bootout is the modern verb; unload covers older macOS. Neither failing is fatal —
        # the job may simply not be loaded — but the plist removal below must succeed.
        launchctl bootout "gui/$(id -u)/$label" 2>/dev/null || true
        launchctl unload "$plist" 2>/dev/null || true
        if ! rm -f -- "$plist"; then
            say "  ! $label: could not delete $plist"
            return 1
        fi
    fi
    removed=$((removed + 1))
    return 0
}

say "rebalance OS uninstaller"
say "  repo         : $REBALANCE_DIR"
say "  launch agents: $LAUNCH_AGENTS_DIR"
if [ "$APPLY" -eq 0 ]; then
    say "  mode         : DRY RUN — nothing will be changed (pass --apply to act)"
else
    say "  mode         : APPLY"
fi
say ""

# --- launchd jobs, derived from the templates --------------------------------------------
say "launchd jobs (derived from $TEMPLATE_DIR/*.plist.template):"
found_template=0
for template in "$TEMPLATE_DIR"/*.plist.template; do
    [ -e "$template" ] || continue
    found_template=1
    label="$(basename "$template" .plist.template)"
    rb_remove_job "$label" "$REBALANCE_DIR" under "$template" || failures=$((failures + 1))
done
if [ "$found_template" -eq 0 ]; then
    # Without templates there is no inventory, and reporting "nothing to remove" would be a
    # lie indistinguishable from a clean machine.
    say "  ! no *.plist.template found in $TEMPLATE_DIR — cannot derive the job list"
    exit 1
fi

say ""
say "launchd jobs installed outside the template convention:"
for entry in "${NON_TEMPLATE_JOBS[@]}"; do
    # `exact`: these launch a single known binary in ~/bin, and "$HOME/bin/git-pulse" is a
    # prefix of "$HOME/bin/git-pulse-write-health" AND of a hypothetical "…-evil", so prefix
    # matching here would let one job authorise deleting another's plist.
    rb_remove_job "${entry%%|*}" "${entry##*|}" exact || failures=$((failures + 1))
done

# --- generated data ------------------------------------------------------------------------
say ""
if [ "$INCLUDE_DATA" -eq 1 ]; then
    say "generated data:"
    for path in "${DATA_PATHS[@]}"; do
        # -L as well as -e: a broken symlink here was called "absent" and the requested data
        # was left behind under exit 0 — the same collapse of "gone" and "unreadable" fixed
        # for plists in round 6. `rm -rf --` removes the link itself safely.
        if [ -e "$path" ] || [ -L "$path" ]; then
            act "delete $path"
            if [ "$APPLY" -eq 1 ] && ! rm -rf -- "$path"; then
                say "  ! could not delete $path"
                failures=$((failures + 1))
            fi
        else
            say "  - $path: absent"
        fi
    done
else
    say "generated data: left in place (pass --include-data to remove)"
    for path in "${DATA_PATHS[@]}"; do
        [ -e "$path" ] && say "  · $path"
    done
fi

# --- secrets --------------------------------------------------------------------------------
say ""
if [ "$INCLUDE_SECRETS" -eq 1 ]; then
    say "keyring entries (service: $KEYRING_SERVICE):"
    if command -v security > /dev/null 2>&1; then
        act "delete generic password service=$KEYRING_SERVICE"
        if [ "$APPLY" -eq 1 ]; then
            # `security` exits 44 for "item not found", which is how the loop legitimately
            # ends. Every OTHER non-zero code is an operational failure — a locked keychain, a
            # denied authorisation — and the old `while ...; do :; done` swallowed all of them
            # identically, leaving the secret in place and still exiting 0 (QA r2 Blocker 3).
            _rb_secret_guard=0
            while :; do
                # `|| _rb_status=$?` is load-bearing under `set -e`: a bare failing command
                # aborts the script before the next line can read $?, so the whole
                # distinguish-44-from-real-failure logic below would never run.
                _rb_status=0
                security delete-generic-password -s "$KEYRING_SERVICE" > /dev/null 2>&1 \
                    || _rb_status=$?
                if [ "$_rb_status" -eq 0 ]; then
                    _rb_secret_guard=$((_rb_secret_guard + 1))
                    if [ "$_rb_secret_guard" -gt 100 ]; then
                        say "  ! stopped after 100 deletions — refusing to loop forever"
                        failures=$((failures + 1))
                        break
                    fi
                    continue
                fi
                if [ "$_rb_status" -ne 44 ]; then
                    say "  ! 'security' exited $_rb_status — the entry may still be present"
                    failures=$((failures + 1))
                fi
                break
            done
        fi
    else
        say "  ! 'security' not available — cannot remove keyring entries"
        failures=$((failures + 1))
    fi
else
    say "keyring entries: left in place (pass --include-secrets to remove)"
    say "  · service '$KEYRING_SERVICE' — HiQS uses service 'hiqs' and is unaffected either way"
fi

# --- other entry points ----------------------------------------------------------------------
# Found by running this tool for real on a live machine: every launchd job was removed and
# reported "9 removed", yet TWO `rebalance.mcp_server` processes were still running — one of
# them for five days. They are not launchd jobs at all; the checkout's own `.mcp.json`
# registers rebalance as an MCP server and the editor launches it.
#
# Nothing here is removed: `.mcp.json` is checked into the repository, so it is part of the
# git checkout this tool leaves alone by design, and killing a server the operator's editor
# owns is not ours to do. But staying silent would let "9 removed" read as "rebalance is off
# this machine" while it is very much still running — the completeness lie this whole tool is
# built to avoid.
# Parsed, not grepped. `grep -q rebalance` would call any .mcp.json a registration when the
# word appears in a comment, a path, or an unrelated server's arguments — the same
# match-anywhere sloppiness this tool spent four QA rounds removing from the ownership check,
# and there is no excuse for reintroducing it in the reporting.
rb_registers_mcp() {
    python3 - "$1" <<'PY' 2>/dev/null
import json, sys
try:
    with open(sys.argv[1], "rb") as handle:
        data = json.load(handle)
except Exception:
    sys.exit(1)
servers = data.get("mcpServers") if isinstance(data, dict) else None
if not isinstance(servers, dict):
    sys.exit(1)
entry = servers.get("rebalance")
sys.exit(0 if isinstance(entry, dict) else 1)
PY
}

if [ -f "$REBALANCE_DIR/.mcp.json" ] && rb_registers_mcp "$REBALANCE_DIR/.mcp.json"; then
    say ""
    say "other entry points — NOT launchd, NOT removed:"
    say "  · $REBALANCE_DIR/.mcp.json registers rebalance as an MCP server"
    say "    It is checked into the repo, so it goes when the checkout goes."
    _rb_mcp_pids="$(pgrep -f 'rebalance\.mcp_server' 2>/dev/null | tr '\n' ' ' || true)"
    if [ -n "${_rb_mcp_pids// /}" ]; then
        # Deliberately NOT claimed as "this checkout's servers". A command line cannot
        # distinguish this checkout from another clone or a second editor profile, and an
        # unverifiable attribution is worse than an honest hedge in a report whose whole
        # purpose is telling the operator what is really still here.
        say "  · processes matching rebalance.mcp_server: ${_rb_mcp_pids% }"
        say "    Not attributed to this checkout — a command line cannot prove which clone"
        say "    they belong to. If hosted by your editor, they exit when that host restarts;"
        say "    one started another way will not."
    fi
fi

# --- report ----------------------------------------------------------------------------------
say ""
# "removed" in a run that removed nothing is precisely the report this repo keeps getting
# burned by, so a dry run says "would remove" and never claims the past tense.
if [ "$APPLY" -eq 1 ]; then
    say "summary: $removed removed, $skipped_absent already absent, $skipped_foreign refused"
else
    say "summary: $removed would be removed, $skipped_absent already absent, $skipped_foreign refused"
    say "         DRY RUN — nothing was changed. Re-run with --apply."
fi
say "left alone by design: the git checkout (incl. .mcp.json), .venv, and HiQS (separate install)"

if [ "$failures" -gt 0 ]; then
    # A partial uninstall that exits 0 is indistinguishable from a complete one to any caller,
    # which is the silent-success failure this repo exists to stop shipping.
    say ""
    say "FAILED: $failures item(s) could not be removed. See the ! lines above."
    exit 1
fi
exit 0
