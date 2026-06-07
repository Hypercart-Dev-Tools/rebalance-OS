#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# Resolve the ask-self checkout. Explicit ASK_SELF_PATH wins; otherwise
# autodetect — no per-machine absolute path baked in.
if [ -z "${ASK_SELF_PATH:-}" ]; then
    for _candidate in \
        "$REPO_ROOT/../ask-self" \
        "$HOME/Documents/GitHub-Repos/ask-self" \
        "$HOME/Documents/GitHub/ask-self" \
        "$HOME/ask-self"; do
        if [ -f "$_candidate/ask_self_query.py" ]; then
            ASK_SELF_PATH="$(cd "$_candidate" && pwd)"
            break
        fi
    done
fi
if [ -z "${ASK_SELF_PATH:-}" ] && command -v ask-self >/dev/null 2>&1; then
    _bin="$(command -v ask-self)"
    _root="$(cd "$(dirname "$_bin")/.." && pwd)"
    if [ -f "$_root/ask_self_query.py" ]; then
        ASK_SELF_PATH="$_root"
    fi
fi
if [ -z "${ASK_SELF_PATH:-}" ]; then
    echo "ask-self: could not locate your ask-self checkout." >&2
    echo "    Set ASK_SELF_PATH, e.g.: export ASK_SELF_PATH=\"\$HOME/Documents/GitHub-Repos/ask-self\"" >&2
    exit 1
fi
HARNESS_CONFIG="$REPO_ROOT/ask_self/ask_self_harness.json"
ENTRYPOINT="$ASK_SELF_PATH/ask_self_query.py"
# Portable mode: query the committed DB so a fresh clone works with no ingest.
# Note: --db-path conflicts with --target/--targets/--all-targets in ask_self_query.py;
# use the upstream ask-self CLI directly for cross-repo registry queries.
PORTABLE_DB="$REPO_ROOT/ask_self/index/rebalance-OS.sqlite"

if [ ! -d "$ASK_SELF_PATH" ]; then
    echo "ASK_SELF_PATH points at $ASK_SELF_PATH but no directory is there." >&2
    exit 1
fi

if [ ! -f "$ENTRYPOINT" ]; then
    echo "ask-self query entrypoint missing: $ENTRYPOINT" >&2
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

# ask-self disables local Qwen providers by default (gemini-first upstream). This
# repo is a portable local-Qwen index, so re-enable Qwen on the query path when
# the harness uses a local provider — otherwise retrieval errors out demanding a
# Gemini key. Honors an explicit override if the caller already set the flag.
EMBED_PROVIDER="$("$PYTHON_BIN" -c "import json,sys; print((json.load(open(sys.argv[1])).get('embedding') or {}).get('provider') or '')" "$HARNESS_CONFIG" 2>/dev/null || true)"
case "$EMBED_PROVIDER" in
    qwen-local|qwen-mlx)
        export ASK_SELF_ENABLE_QWEN="${ASK_SELF_ENABLE_QWEN:-1}"
        ;;
esac

exec "$PYTHON_BIN" "$ENTRYPOINT" \
    --repo-root "$REPO_ROOT" \
    --harness-config "$HARNESS_CONFIG" \
    --db-path "$PORTABLE_DB" \
    "$@"
