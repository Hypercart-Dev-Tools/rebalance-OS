#!/usr/bin/env bash
set -euo pipefail

# Source of truth: GH-250 / 3-Eyes registry / launchd inventory
#
# Every com.rebalance-os.* job that is LOADED must appear here, not merely the ones that write.
# cmd_verify fails closed on any loaded label it does not recognise, so an unlisted job does not
# quietly slip through the fence — it makes the fence unsatisfiable, and the reclaim can never
# start. Six jobs were missing when this was first run for real against the fleet.
#
# The distinction between "writer" and "reader" is deliberately not drawn: a reader breaks this
# window just as effectively, because the reclaim needs wal_checkpoint(TRUNCATE) to return 0|0|0
# and an EXCLUSIVE lock, and any open connection defeats both. pulse-web-sync is the worked
# example — it looks like a static page generator, and it imports run_doctor, which opens the
# database. Quiescing the whole fleet for one maintenance window is the cheap, obviously-correct
# reading; unfence restores exactly the pre-fence state.
KNOWN_WRITERS=(
    "com.rebalance-os.github-sync"
    "com.rebalance-os.pulse-sync"
    "com.rebalance-os.daily-sync"
    "com.rebalance-os.3eyes.collector-health"
    "com.rebalance-os.vault-sync"
    "com.rebalance-os.pulse-web-sync"
    "com.rebalance-os.obsidian-daily-sync"
    "com.rebalance-os.obsidian-rollover"
    "com.rebalance-os.3eyes.selfcheck"
    "com.rebalance-os.3eyes.skill-sync"
    "com.rebalance-os.pulse-server"
)

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STATE_FILE="${STATE_FILE:-${REPO_ROOT}/rebalance_fenced_writers.state}"
REBALANCE_DB="${REBALANCE_DB:-${REPO_ROOT}/rebalance.db}"

LAUNCHCTL_CMD="${LAUNCHCTL_CMD:-launchctl}"
PYTHON_CMD="${PYTHON_CMD:-python}"
LSOF_CMD="${LSOF_CMD:-lsof}"
SQLITE_CMD="${SQLITE_CMD:-sqlite3}"

get_3eyes_id() {
    local launchd_id="$1"
    case "$launchd_id" in
        com.rebalance-os.3eyes.collector-health) echo "collector-health" ;;
        com.rebalance-os.github-sync) echo "github-sync" ;;
        com.rebalance-os.pulse-sync) echo "pulse-sync" ;;
        com.rebalance-os.daily-sync) echo "daily-sync" ;;
        com.rebalance-os.vault-sync) echo "vault-sync" ;;
        com.rebalance-os.pulse-web-sync) echo "pulse-web-sync" ;;
        com.rebalance-os.obsidian-daily-sync) echo "obsidian-daily-sync" ;;
        com.rebalance-os.obsidian-rollover) echo "obsidian-rollover" ;;
        com.rebalance-os.3eyes.selfcheck) echo "selfcheck" ;;
        com.rebalance-os.3eyes.skill-sync) echo "skill-sync" ;;
        # pulse-server is deliberately absent: it is a long-running server, not a
        # 3-Eyes scheduled job, so it takes the launchctl bootout/bootstrap path.
        *) echo "" ;;
    esac
}

is_3eyes_managed() {
    local job_id="$1"
    (cd "$REPO_ROOT/utils/3-eyes" && "$PYTHON_CMD" -m three_eyes list 2>/dev/null | grep -q "^${job_id} ")
}

cmd_fence() {
    echo "Fencing database writers..."
    
    if [ -f "$STATE_FILE" ]; then
        echo "State file already exists ($STATE_FILE). A fence is already active. Doing nothing."
        return 0
    fi
    
    # We must record pre-state BEFORE acting
    local pre_state=""
    local to_pause=()
    local to_unload=()
    
    for w in "${KNOWN_WRITERS[@]}"; do
        if "$LAUNCHCTL_CMD" list | awk '{print $3}' | grep -q "^${w}$"; then
            local t_id
            t_id=$(get_3eyes_id "$w")
            if [ -n "$t_id" ] && is_3eyes_managed "$t_id"; then
                local why_out
                why_out=$(cd "$REPO_ROOT/utils/3-eyes" && "$PYTHON_CMD" -m three_eyes why "$t_id" 2>/dev/null || true)
                if echo "$why_out" | grep -q "OPEN/quarantined" && echo "$why_out" | grep -q "reason: paused via CLI"; then
                    echo "$w is 3-Eyes managed and already paused."
                else
                    pre_state+="${w}:3eyes:${t_id}\n"
                    to_pause+=("$t_id")
                fi
            else
                pre_state+="${w}:launchctl:none\n"
                to_unload+=("$w")
            fi
        fi
    done
    
    if [ -n "$pre_state" ]; then
        echo "# State recorded at $(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$STATE_FILE"
        echo -e -n "$pre_state" >> "$STATE_FILE"
        echo "Recorded pre-state to $STATE_FILE"
    else
        echo "Nothing to fence, state already clear."
        echo "# State recorded at $(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$STATE_FILE"
        return 0
    fi
    
    trap 'echo "Interrupt or exit received, restoring..."; cmd_unfence || true; exit 1' EXIT INT TERM
    
    for t_id in "${to_pause[@]:-}"; do
        echo "Pausing $t_id via 3-Eyes..."
        (cd "$REPO_ROOT/utils/3-eyes" && "$PYTHON_CMD" -m three_eyes pause "$t_id" >/dev/null) || { echo "Failed to pause $t_id"; exit 1; }
        echo "  -> 3-Eyes path taken for $t_id"
    done
    
    for w in "${to_unload[@]:-}"; do
        echo "Unloading $w via launchctl..."
        "$LAUNCHCTL_CMD" bootout "gui/$(id -u)" "$HOME/Library/LaunchAgents/${w}.plist" >/dev/null 2>&1 || { echo "Failed to bootout $w"; exit 1; }
        echo "  -> launchctl path taken for $w"
    done
    
    trap - EXIT INT TERM
    echo "Fencing complete."
}

cmd_verify() {
    echo "Verifying writers are fenced..."
    local failed=0
    
    local all_loaded
    all_loaded=$("$LAUNCHCTL_CMD" list | awk '{print $3}' | grep '^com\.rebalance-os\.' || true)
    
    for loaded in $all_loaded; do
        local known=0
        for w in "${KNOWN_WRITERS[@]}"; do
            if [ "$w" = "$loaded" ]; then
                known=1
                break
            fi
        done
        
        if [ $known -eq 0 ]; then
            echo "FAIL: Unknown writer loaded: $loaded. Update KNOWN_WRITERS in script!"
            failed=1
        fi
    done
    
    for w in "${KNOWN_WRITERS[@]}"; do
        if "$LAUNCHCTL_CMD" list | awk '{print $3}' | grep -q "^${w}$"; then
            local t_id
            t_id=$(get_3eyes_id "$w")
            if [ -n "$t_id" ] && is_3eyes_managed "$t_id"; then
                local why_out
                why_out=$(cd "$REPO_ROOT/utils/3-eyes" && "$PYTHON_CMD" -m three_eyes why "$t_id" 2>/dev/null || true)
                if ! (echo "$why_out" | grep -q "OPEN/quarantined" && echo "$why_out" | grep -q "reason: paused via CLI"); then
                    echo "FAIL: 3-Eyes managed writer $w ($t_id) is NOT paused!"
                    failed=1
                fi
            else
                echo "FAIL: Unmanaged writer $w is still loaded in launchctl!"
                failed=1
            fi
        fi
    done
    
    if command -v "$LSOF_CMD" >/dev/null 2>&1; then
        if "$LSOF_CMD" "$REBALANCE_DB" >/dev/null 2>&1; then
            echo "FAIL: A live process has rebalance.db open!"
            "$LSOF_CMD" "$REBALANCE_DB" || true
            failed=1
        fi
    fi
    
    if command -v "$SQLITE_CMD" >/dev/null 2>&1; then
        if ! "$SQLITE_CMD" "$REBALANCE_DB" "BEGIN EXCLUSIVE; COMMIT;" 2>/dev/null; then
            echo "FAIL: Could not acquire EXCLUSIVE lock on rebalance.db!"
            failed=1
        fi
    fi
    
    if [ $failed -eq 0 ]; then
        echo "PASS: Database is fully fenced."
        return 0
    else
        return 1
    fi
}

cmd_unfence() {
    echo "Restoring fenced writers..."
    if [ ! -f "$STATE_FILE" ]; then
        echo "Error: No state file found at $STATE_FILE."
        return 1
    fi
    
    if [ ! -s "$STATE_FILE" ]; then
        echo "State file is empty, nothing to unfence."
        rm -f "$STATE_FILE"
        return 0
    fi
    
    local any_failed=0
    
    # Temporarily disable error exit for unfence to try restoring all
    set +e
    
    while IFS=: read -r w method t_id; do
        if [[ "$w" == \#* ]] || [ -z "$w" ]; then
            continue
        fi
        
        if [ "$method" = "3eyes" ]; then
            if (cd "$REPO_ROOT/utils/3-eyes" && "$PYTHON_CMD" -m three_eyes why "$t_id" 2>/dev/null | grep -q "closed"); then
                echo "$w ($t_id) is already resumed (or was never paused)."
            else
                echo "Resuming $w via 3-Eyes ($t_id)..."
                (cd "$REPO_ROOT/utils/3-eyes" && "$PYTHON_CMD" -m three_eyes resume "$t_id" >/dev/null)
            fi
            
            if (cd "$REPO_ROOT/utils/3-eyes" && "$PYTHON_CMD" -m three_eyes why "$t_id" 2>/dev/null | grep -q "closed") && "$LAUNCHCTL_CMD" list | awk '{print $3}' | grep -q "^${w}$"; then
                echo "  -> Confirmed $t_id is resumed and loaded."
            else
                echo "  -> Error: $t_id did not resume properly or is not loaded!"
                any_failed=1
            fi
        elif [ "$method" = "launchctl" ]; then
            if "$LAUNCHCTL_CMD" list | awk '{print $3}' | grep -q "^${w}$"; then
                echo "$w is already loaded."
            else
                echo "Bootstrapping $w via launchctl..."
                "$LAUNCHCTL_CMD" bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/${w}.plist" >/dev/null 2>&1
            fi
            
            if "$LAUNCHCTL_CMD" list | awk '{print $3}' | grep -q "^${w}$"; then
                echo "  -> Confirmed $w is loaded."
            else
                echo "  -> Error: $w did not load properly!"
                any_failed=1
            fi
        fi
    done < "$STATE_FILE"
    
    set -e
    
    if [ $any_failed -ne 0 ]; then
        echo "Unfence encountered errors. State file retained."
        return 1
    fi
    
    echo "Unfence complete. Removing state file."
    rm -f "$STATE_FILE"
    return 0
}

case "${1:-}" in
    fence) cmd_fence ;;
    verify) cmd_verify ;;
    unfence) cmd_unfence ;;
    *)
        echo "Usage: $0 {fence|verify|unfence}"
        exit 1
        ;;
esac
