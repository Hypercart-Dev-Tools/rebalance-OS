#!/bin/bash
# 3-Eyes launchd/cron shim (GH-195) — the ONLY Bash in 3-Eyes.
#
# launchd/cron cannot exec a Python module directly, so this one line bridges to
# it. It resolves its own location (device-agnostic; no hardcoded path), runs from
# the repo root so a job's relative allowlisted command resolves correctly (B4),
# and hands the single job id to the Python entrypoint.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"   # .../utils/3-eyes
repo_root="$(cd "$here/../.." && pwd)"                     # rebalance-OS repo root

# Pick a Python that HAS tomllib (>=3.11). launchd's minimal PATH resolves a bare
# `python3` to the system/Xcode 3.9, which lacks tomllib and would crash on import
# — so prefer the repo venv (absolute, PATH-independent), then any 3.11+ on PATH,
# and fail loudly rather than run under an interpreter that cannot parse the TOML.
#
# The probe is a SUBPROCESS, so it can fail for reasons that have nothing to do
# with the interpreter: under memory pressure or EINTR the fork/exec itself fails.
# That happened 12 times on this machine, each logged as "no Python with tomllib
# (>=3.11) found on this host" — a permanent-sounding misconfiguration message for
# a transient condition, with bash itself reporting "Interrupted system call" two
# lines earlier. So: retry once, and distinguish "no candidate exists" (exit 3,
# genuinely misconfigured) from "a candidate exists but the probe would not run"
# (exit 75 / EX_TEMPFAIL — deferred, retry later). See GH-195 P6 and GH-186.
# The probe's EXIT STATUS is what separates the two cases, and getting this wrong
# in either direction is harmful:
#   0        -> tomllib present; use it.
#   1        -> the interpreter RAN and raised ImportError. Permanent — this is the
#               system/Xcode 3.9 at /usr/bin/python3, which really is too old. Must
#               NOT be treated as transient, or a genuinely misconfigured host
#               retries forever instead of reporting the problem.
#   126/127  -> could not execute at all (fork failure, EINTR, unreadable volume).
#   >128     -> killed by a signal.
#               Those last two say nothing about tomllib. Retry, then defer.
py=""
transient=0
probe() { "$1" -c 'import tomllib' >/dev/null 2>&1; }
for cand in "$repo_root/.venv/bin/python" python3.13 python3.12 python3.11 python3; do
  command -v "$cand" >/dev/null 2>&1 || continue
  status=0; probe "$cand" || status=$?
  if [ "$status" -ge 126 ]; then
    # Retry once. Absolute path + `|| true`: launchd's PATH is minimal, and under
    # `set -e` a bare `sleep` that is not on PATH would abort the shim with 127 —
    # turning a retry meant to add resilience into a new failure mode.
    /bin/sleep 1 || true
    status=0; probe "$cand" || status=$?
  fi
  # Integer comparison, NOT a glob (agy review, P6 QA finding 2). `126|127|1??`
  # looked right because signal deaths land in 128-159, but `1??` matches exactly
  # three characters starting with 1 — so a 255 (bash's out-of-range exit) fell
  # through to "permanent" and would have been reported as a missing interpreter.
  if [ "$status" -eq 0 ]; then
    py="$cand"; break
  elif [ "$status" -ge 126 ]; then
    transient=1                    # still could not execute — remember, keep looking
  fi                               # else: ran and lacks tomllib — permanent, real answer
done

if [ -z "$py" ]; then
  if [ "$transient" = 1 ]; then
    echo "3-eyes: a Python candidate exists but could not be EXECUTED to probe for" \
         "tomllib (machine under pressure / EINTR?); deferring rather than declaring" \
         "it missing" >&2
    exit 75    # EX_TEMPFAIL — matches job_guard.EXIT_REFUSED_TO_START
  fi
  echo "3-eyes: no Python with tomllib (>=3.11) found on this host" >&2
  exit 3
fi

cd "$repo_root"
PYTHONPATH="$here${PYTHONPATH:+:$PYTHONPATH}" exec "$py" -m three_eyes.run "$@"
