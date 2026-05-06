#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ASK_SELF_PATH="${ASK_SELF_PATH:-/path/to/ask-self}"
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
    else
        PYTHON_BIN="python3"
    fi
fi

DEFAULT_ARGS=()
HAS_MODE=0
HAS_SHARED_INDEX=0
HAS_SOURCE_FILTER=0
HAS_EXCLUDE_PATTERN=0
for arg in "$@"; do
    case "$arg" in
        --shared-index)
            HAS_SHARED_INDEX=1
            ;;
        --mode|--mode=*)
            HAS_MODE=1
            ;;
        --source|--source=*)
            HAS_SOURCE_FILTER=1
            ;;
        --exclude-pattern|--exclude-pattern=*)
            HAS_EXCLUDE_PATTERN=1
            ;;
        -h|--help)
            HAS_MODE=1
            ;;
    esac
done

if [ "$HAS_SHARED_INDEX" -eq 1 ] && [ "$HAS_MODE" -eq 0 ]; then
    DEFAULT_ARGS+=(--mode code)
fi

if [ "$HAS_SHARED_INDEX" -eq 1 ] && [ "$HAS_SOURCE_FILTER" -eq 0 ]; then
    DEFAULT_ARGS+=(--source module --source script)
fi

if [ "$HAS_SHARED_INDEX" -eq 1 ] && [ "$HAS_EXCLUDE_PATTERN" -eq 0 ]; then
    DEFAULT_ARGS+=(--exclude-pattern '^tests?/' --exclude-pattern '^experimental/')
fi

if [ "$HAS_SHARED_INDEX" -eq 0 ] && [ "$HAS_MODE" -eq 0 ]; then
    exec "$PYTHON_BIN" "$ENTRYPOINT" \
        --repo-root "$REPO_ROOT" \
        --harness-config "$HARNESS_CONFIG" \
        --mode all \
        "$@"
fi

if [ "${#DEFAULT_ARGS[@]}" -gt 0 ]; then
    exec "$PYTHON_BIN" "$ENTRYPOINT" \
        --repo-root "$REPO_ROOT" \
        --harness-config "$HARNESS_CONFIG" \
        "${DEFAULT_ARGS[@]}" \
        "$@"
fi

exec "$PYTHON_BIN" "$ENTRYPOINT" \
    --repo-root "$REPO_ROOT" \
    --harness-config "$HARNESS_CONFIG" \
    "$@"
