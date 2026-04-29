#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ASK_SELF_PATH="${ASK_SELF_PATH:-/Users/noelsaw/Documents/GH Repos/ask-self}"
HARNESS_CONFIG="$REPO_ROOT/ask_self/ask_self_harness.json"
ENTRYPOINT="$ASK_SELF_PATH/ask_self_ingest.py"

if [ ! -d "$ASK_SELF_PATH" ]; then
    echo "ask-self repo not found: $ASK_SELF_PATH" >&2
    echo "Set ASK_SELF_PATH to your ask-self checkout and retry." >&2
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
    "$@"
