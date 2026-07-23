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
py=""
for cand in "$repo_root/.venv/bin/python" python3.13 python3.12 python3.11 python3; do
  if command -v "$cand" >/dev/null 2>&1 && "$cand" -c 'import tomllib' >/dev/null 2>&1; then
    py="$cand"; break
  fi
done
[ -n "$py" ] || { echo "3-eyes: no Python with tomllib (>=3.11) found on this host" >&2; exit 3; }

cd "$repo_root"
PYTHONPATH="$here${PYTHONPATH:+:$PYTHONPATH}" exec "$py" -m three_eyes.run "$@"
