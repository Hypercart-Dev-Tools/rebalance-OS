#!/bin/bash
# 3-Eyes launchd/cron shim (GH-195) — the ONLY Bash in 3-Eyes.
#
# launchd/cron cannot exec a Python module directly, so this one line bridges to
# it. It resolves its own location (device-agnostic; no hardcoded path), puts the
# package dir on PYTHONPATH, and hands the single job id straight to the Python
# entrypoint. All real logic lives in three_eyes/run.py.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"   # .../utils/3-eyes
repo_root="$(cd "$here/../.." && pwd)"                     # rebalance-OS repo root
# Run FROM the repo root (B4: so a job's relative allowlisted command resolves
# against the repo, not utils/3-eyes), but keep the package importable.
cd "$repo_root"
PYTHONPATH="$here${PYTHONPATH:+:$PYTHONPATH}" exec python3 -m three_eyes.run "$@"
