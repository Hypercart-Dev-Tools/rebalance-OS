#!/bin/bash
# rebalance OS — shared install flow for launchd jobs.
#
# Source this from an install_*.sh (after `set -euo pipefail`) and call:
#
#     rb_install_launchd_job <label> [wrapper-relative-path]
#
# e.g. rb_install_launchd_job "com.rebalance-os.vault-sync" "scripts/vault_sync.sh"
#
# One flow for every job:
#   1. chmod +x the wrapper script (when one is named)
#   2. ALWAYS `launchctl unload` first — `launchctl load` fails with an opaque
#      "Input/output error" if the job is already registered, and a grep of
#      `launchctl list` can miss a job that is loaded but momentarily absent
#   3. render scripts/<label>.plist.template into ~/Library/LaunchAgents/,
#      substituting {{REBALANCE_DIR}}, {{PYTHON}}, and {{HOME}}
#   4. `plutil -lint` the rendered plist before loading it
#   5. ensure temp/logs exists, `launchctl load`, verify the label registered
#
# The job inventory, cadences, and scopes live in SCHEDULER.md (the policy
# table); tests/test_scheduler_policy.py enforces that installers stay in sync.

RB_INSTALL_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_DIR="$(cd "$RB_INSTALL_LIB_DIR/.." && pwd)"
REBALANCE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON_BIN="$REBALANCE_DIR/.venv/bin/python"

# Escape '/' and '&' so a path is safe as a sed replacement string.
_rb_sed_escape() {
    printf '%s\n' "$1" | sed 's/[\/&]/\\&/g'
}

rb_install_launchd_job() {
    local label="$1"
    local wrapper="${2:-}"
    local template="$SCRIPT_DIR/$label.plist.template"
    local dest="$HOME/Library/LaunchAgents/$label.plist"

    if [ ! -f "$template" ]; then
        echo "ERROR: missing plist template: $template" >&2
        return 1
    fi
    if grep -q "{{PYTHON}}" "$template" && [ ! -x "$PYTHON_BIN" ]; then
        echo "ERROR: expected virtualenv python at $PYTHON_BIN" >&2
        return 1
    fi
    if [ -n "$wrapper" ]; then
        if [ ! -f "$REBALANCE_DIR/$wrapper" ]; then
            echo "ERROR: wrapper script not found: $REBALANCE_DIR/$wrapper" >&2
            return 1
        fi
        if [ ! -x "$REBALANCE_DIR/$wrapper" ]; then
            chmod +x "$REBALANCE_DIR/$wrapper"
            echo "  Made $wrapper executable"
        fi
    fi

    launchctl unload "$dest" 2>/dev/null || true

    sed \
        -e "s/{{REBALANCE_DIR}}/$(_rb_sed_escape "$REBALANCE_DIR")/g" \
        -e "s/{{PYTHON}}/$(_rb_sed_escape "$PYTHON_BIN")/g" \
        -e "s/{{HOME}}/$(_rb_sed_escape "$HOME")/g" \
        "$template" > "$dest"
    echo "  Rendered plist to $dest"

    plutil -lint -- "$dest" > /dev/null

    mkdir -p "$REBALANCE_DIR/temp/logs"

    launchctl load "$dest"

    # Exposed for the caller's uninstall/status hints.
    RB_PLIST_DEST="$dest"

    # Registration can lag the load by a moment — poll briefly before warning.
    local _i
    for _i in 1 2 3 4 5; do
        if launchctl list "$label" > /dev/null 2>&1; then
            echo "  Loaded $label"
            return 0
        fi
        sleep 1
    done
    echo "  WARNING: $label did not appear in launchctl list after load" >&2
}
