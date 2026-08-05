#!/bin/bash
# rebalance OS — shared runtime for launchd job wrapper scripts.
#
# Source this from any scripts/*.sh wrapper (after `set -euo pipefail`):
#
#     source "$(cd "$(dirname "$0")" && pwd)/lib/scheduler_common.sh"
#     rb_job_init "vault-sync" 14    # job name + log retention days
#     log "=== starting ==="
#     ...job work, appending detail to "$LOG_FILE"...
#     rb_trim_logs
#
# Sourcing bootstraps the environment every job needs:
#   REBALANCE_DIR — repo root (derived from this file's location)
#   PYTHON        — the project virtualenv python (never system python)
#   PYTHONPATH    — src/ prepended so `from rebalance...` imports work
#   LOG_DIR       — temp/logs (created), and cwd moves to REBALANCE_DIR
#
# rb_job_init wires the unified job-lifecycle stream
# (temp/logs/auth_activity.jsonl via rebalance.ingest.auth_log):
# log_job_started immediately, log_job_completed / log_job_failed on EXIT.
# Lifecycle calls are best-effort (`|| true`) — telemetry must never fail a job.
#
# The job inventory, cadences, and scopes live in SCHEDULER.md (the policy
# table); tests/test_scheduler_policy.py enforces that wrappers stay in sync.

RB_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REBALANCE_DIR="$(cd "$RB_LIB_DIR/../.." && pwd)"
PYTHON="$REBALANCE_DIR/.venv/bin/python"
export PYTHONPATH="$REBALANCE_DIR/src${PYTHONPATH:+:$PYTHONPATH}"
LOG_DIR="$REBALANCE_DIR/temp/logs"

mkdir -p "$LOG_DIR"
cd "$REBALANCE_DIR"

# Timestamped line to stdout and the job log (no-op target until rb_job_init).
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "${LOG_FILE:-/dev/null}"
}

# Emit a job_started lifecycle event without registering an EXIT trap.
# For daemons (pulse-server) that exec their payload — the trap would not
# survive the exec, so completed/failed events are not meaningful there.
rb_job_mark_started() {
    "$PYTHON" -c "from rebalance.ingest.auth_log import log_job_started; log_job_started('$1')" 2>/dev/null || true
}

_rb_job_exit() {
    local _code=$?
    local _elapsed=$(( $(date +%s) - _RB_JOB_START_TS ))
    if [ "$_code" -eq 0 ]; then
        "$PYTHON" -c "from rebalance.ingest.auth_log import log_job_completed; log_job_completed('$RB_JOB_NAME', $_elapsed)" 2>/dev/null || true
    else
        "$PYTHON" -c "from rebalance.ingest.auth_log import log_job_failed; log_job_failed('$RB_JOB_NAME', $_code, $_elapsed)" 2>/dev/null || true
    fi
}

# rb_job_init <job-name> [retention-days=14]
# Sets LOG_FILE to temp/logs/<job_name>_YYYY-MM-DD.log (dashes become
# underscores), emits job_started, and traps EXIT for completed/failed.
rb_job_init() {
    RB_JOB_NAME="$1"
    RB_LOG_RETENTION_DAYS="${2:-14}"
    RB_LOG_PREFIX="${RB_JOB_NAME//-/_}"
    LOG_FILE="$LOG_DIR/${RB_LOG_PREFIX}_$(date +%Y-%m-%d).log"
    _RB_JOB_START_TS=$(date +%s)
    rb_job_mark_started "$RB_JOB_NAME"
    trap _rb_job_exit EXIT
}

# Delete this job's daily logs older than the retention window.
rb_trim_logs() {
    find "$LOG_DIR" -name "${RB_LOG_PREFIX}_*.log" -mtime "+$RB_LOG_RETENTION_DAYS" -delete 2>/dev/null || true
}

# --- GH-186: transient interpreter-bootstrap EINTR retry -------------------
#
# A rare macOS/CPython bug: during interpreter bootstrap (inside frozen
# modules like <frozen getpath>, before any application code has run) a
# signal interrupts a syscall and raises an uncaught
# `InterruptedError: [Errno 4] Interrupted system call`, killing the process
# before main() starts. This is a transient startup race, not an application
# failure, and it has been observed across multiple scheduled jobs
# (github-sync, pulse-warning-watch, pulse_server, vault_sync) that all
# invoke `$PYTHON` via this shared runtime — so the retry lives here once,
# not per-wrapper.
#
# Detection is intentionally narrow (both substrings must be present) so a
# real application-level InterruptedError, or any other non-zero exit, is
# never retried/masked — only this specific bootstrap crash signature is.
RB_PY_EINTR_MAX_RETRIES="${RB_PY_EINTR_MAX_RETRIES:-2}"

_rb_is_bootstrap_eintr() {
    grep -q '<frozen getpath>' "$1" 2>/dev/null \
        && grep -q 'InterruptedError: \[Errno 4\] Interrupted system call' "$1" 2>/dev/null
}

# rb_run_python_stdin
# Drop-in replacement for `"$PYTHON" - <<'PY' ... PY`: reads a python script
# from stdin (the heredoc) and runs it via $PYTHON, retrying up to
# RB_PY_EINTR_MAX_RETRIES times ONLY when the failure matches the transient
# interpreter-bootstrap EINTR signature above. Any other non-zero exit
# (real application errors/exceptions) is returned immediately, unretried,
# so a genuine failure is never silently masked as a "success after retry".
# Output from every attempt (including a failed retry) is emitted on stdout
# so it still lands wherever the caller redirected, e.g. `>> "$LOG_FILE"`.
rb_run_python_stdin() {
    local script capture attempt=0 code
    script="$(mktemp "${TMPDIR:-/tmp}/rb_py_src.XXXXXX")"
    capture="$(mktemp "${TMPDIR:-/tmp}/rb_py_out.XXXXXX")"
    cat > "$script"
    while :; do
        if "$PYTHON" "$script" > "$capture" 2>&1; then
            code=0
        else
            code=$?
        fi
        cat "$capture"
        if [ "$code" -eq 0 ]; then
            rm -f "$script" "$capture"
            return 0
        fi
        if [ "$attempt" -lt "$RB_PY_EINTR_MAX_RETRIES" ] && _rb_is_bootstrap_eintr "$capture"; then
            attempt=$((attempt + 1))
            echo "[$(date '+%Y-%m-%d %H:%M:%S')] transient interpreter-bootstrap EINTR on python startup, retrying (attempt $attempt/$RB_PY_EINTR_MAX_RETRIES)..." >&2
            continue
        fi
        rm -f "$script" "$capture"
        return "$code"
    done
}
