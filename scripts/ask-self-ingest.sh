#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
if [ -z "${ASK_SELF_PATH:-}" ]; then
    echo "ASK_SELF_PATH is not set. Point it at your ask-self checkout, e.g.:" >&2
    echo "    export ASK_SELF_PATH=\"\$HOME/Documents/GitHub/ask-self\"" >&2
    exit 1
fi
HARNESS_CONFIG="$REPO_ROOT/ask_self/ask_self_harness.json"
ENTRYPOINT="$ASK_SELF_PATH/ask_self_ingest.py"
# Portable mode: write the committed DB at a tracked path so a fresh clone can query
# without running ingest. Pinned via --db-path; --no-register because committed DBs
# are not registry entries (the multi-repo registry is for local working indexes).
PORTABLE_DB="$REPO_ROOT/ask_self/index/rebalance-OS.sqlite"
mkdir -p "$REPO_ROOT/ask_self/index"

if [ ! -d "$ASK_SELF_PATH" ]; then
    echo "ASK_SELF_PATH points at $ASK_SELF_PATH but no directory is there." >&2
    exit 1
fi

if [ ! -f "$ENTRYPOINT" ]; then
    echo "ask-self ingest entrypoint missing: $ENTRYPOINT" >&2
    exit 1
fi

if [ ! -f "$HARNESS_CONFIG" ]; then
    echo "Harness config missing: $HARNESS_CONFIG" >&2
    exit 1
fi

PYTHON_BIN="${ASK_SELF_PYTHON:-}"
if [ -z "$PYTHON_BIN" ]; then
    if [ -x "$ASK_SELF_PATH/.venv/bin/python" ]; then
        PYTHON_BIN="$ASK_SELF_PATH/.venv/bin/python"
    elif [ -x "$REPO_ROOT/.venv/bin/python" ]; then
        PYTHON_BIN="$REPO_ROOT/.venv/bin/python"
    else
        PYTHON_BIN="python3"
    fi
fi

exec "$PYTHON_BIN" "$ENTRYPOINT" \
    --repo-root "$REPO_ROOT" \
    --harness-config "$HARNESS_CONFIG" \
    --db-path "$PORTABLE_DB" \
    --no-register \
    "$@"
