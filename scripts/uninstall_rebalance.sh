#!/bin/bash
# rebalance OS — reverse everything scripts/install_*.sh put on this device.
#
#     scripts/uninstall_rebalance.sh                    # dry run: print the plan, change nothing
#     scripts/uninstall_rebalance.sh --apply            # unload and delete the launchd jobs
#     scripts/uninstall_rebalance.sh --apply --include-data      # also delete logs and temp state
#     scripts/uninstall_rebalance.sh --apply --include-secrets   # also delete keyring entries
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
#    is not enough: this reads each plist and requires it to reference THIS repository's path
#    before removing it. A label collision with unrelated software is therefore not removable,
#    which is what makes the tool safe to hand to someone else.
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
        -h|--help) usage ;;
        *) echo "ERROR: unknown option: $1 (try --help)" >&2; exit 2 ;;
    esac
    shift
done

say() { printf '%s\n' "$*"; }
act() { if [ "$APPLY" -eq 1 ]; then printf '  %s\n' "$*"; else printf '  [dry-run] %s\n' "$*"; fi; }

# Prove a plist belongs to this repository before it can be deleted. Reads the file rather
# than trusting the label, so unrelated software that happens to collide on a name survives.
# Print the executable(s) a plist actually launches, one per line. Empty output means the file
# could not be parsed or launches nothing, and callers must treat that as "not ours".
#
# plistlib rather than plutil because plutil is macOS-only and CI runs ubuntu-latest; a check
# that cannot run in CI is a check nobody is testing.
rb_plist_executables() {
    python3 - "$1" <<'PY' 2>/dev/null
import plistlib, sys
try:
    with open(sys.argv[1], "rb") as handle:
        data = plistlib.load(handle)
except Exception:
    sys.exit(1)
if not isinstance(data, dict):
    sys.exit(1)
arguments = data.get("ProgramArguments")
if isinstance(arguments, list) and arguments and isinstance(arguments[0], str):
    print(arguments[0])
program = data.get("Program")
if isinstance(program, str):
    print(program)
PY
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
rb_is_ours() {
    local plist="$1"
    local marker="$2"
    local mode="$3"
    local executable

    while IFS= read -r executable; do
        [ -n "$executable" ] || continue
        case "$mode" in
            exact) [ "$executable" = "$marker" ] && return 0 ;;
            under) case "$executable" in "$marker"/*) return 0 ;; esac ;;
        esac
    done <<EOF
$(rb_plist_executables "$plist")
EOF
    return 1
}

# rb_remove_job <label> [ownership-marker] [exact|under]
rb_remove_job() {
    local label="$1"
    local marker="${2:-$REBALANCE_DIR}"
    local mode="${3:-under}"
    local plist="$LAUNCH_AGENTS_DIR/$label.plist"

    if [ ! -f "$plist" ]; then
        say "  - $label: not installed"
        skipped_absent=$((skipped_absent + 1))
        return 0
    fi

    if ! rb_is_ours "$plist" "$marker" "$mode"; then
        # Reported loudly and counted as a failure: the operator asked for this job to be gone
        # and it is still here. Silently skipping would let a partial uninstall exit 0.
        say "  ! $label: EXISTS but does not launch $marker ($mode) — refusing to remove"
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
        if ! rm -f "$plist"; then
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
    rb_remove_job "$label" || failures=$((failures + 1))
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
        if [ -e "$path" ]; then
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
            while security delete-generic-password -s "$KEYRING_SERVICE" > /dev/null 2>&1; do :; done
        fi
    else
        say "  ! 'security' not available — cannot remove keyring entries"
        failures=$((failures + 1))
    fi
else
    say "keyring entries: left in place (pass --include-secrets to remove)"
    say "  · service '$KEYRING_SERVICE' — HiQS uses service 'hiqs' and is unaffected either way"
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
say "left alone by design: the git checkout, .venv, and HiQS (separate install)"

if [ "$failures" -gt 0 ]; then
    # A partial uninstall that exits 0 is indistinguishable from a complete one to any caller,
    # which is the silent-success failure this repo exists to stop shipping.
    say ""
    say "FAILED: $failures item(s) could not be removed. See the ! lines above."
    exit 1
fi
exit 0
