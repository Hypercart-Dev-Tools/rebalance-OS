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

has_flag() {
    local needle="$1"
    shift
    local arg
    for arg in "$@"; do
        case "$arg" in
            "$needle"|"$needle="*)
                return 0
                ;;
        esac
    done
    return 1
}

read_harness_json() {
    local expr="$1"
    "$PYTHON_BIN" -c "import json, sys; data=json.load(open(sys.argv[1], encoding='utf-8')); value=${expr}; print(value if value is not None else '')" "$HARNESS_CONFIG"
}

DEFAULT_ARGS=()
if ! has_flag "--mode" "$@"; then
    DEFAULT_ARGS+=(--mode all)
fi

GITHUB_OWNER="$(read_harness_json "((data.get('github') or {}).get('owner'))")"
GITHUB_REPO="$(read_harness_json "((data.get('github') or {}).get('repo'))")"

if [ -n "$GITHUB_OWNER" ] && [ -n "$GITHUB_REPO" ] && ! has_flag "--no-prs" "$@"; then
    if [ -z "${GITHUB_TOKEN:-}" ] && [ -n "${SLEUTH_RAG_GITHUB_PAT:-}" ]; then
        export GITHUB_TOKEN="$SLEUTH_RAG_GITHUB_PAT"
    fi

    if [ -z "${GITHUB_TOKEN:-}" ]; then
        if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
            GH_TOKEN="$(gh auth token 2>/dev/null || true)"
            if [ -n "$GH_TOKEN" ]; then
                export GITHUB_TOKEN="$GH_TOKEN"
            fi
        fi
    fi

    if [ -z "${GITHUB_TOKEN:-}" ]; then
        echo "GITHUB_TOKEN not set and gh CLI not authorized — run 'gh auth login', export GITHUB_TOKEN, or pass --no-prs." >&2
        exit 1
    fi
fi

CMD=(
    "$PYTHON_BIN"
    "$ENTRYPOINT"
    --repo-root "$REPO_ROOT"
    --harness-config "$HARNESS_CONFIG"
    --db-path "$PORTABLE_DB"
    --no-register
)

if [ "${#DEFAULT_ARGS[@]}" -gt 0 ]; then
    CMD+=("${DEFAULT_ARGS[@]}")
fi

if [ "$#" -gt 0 ]; then
    CMD+=("$@")
fi

exec "${CMD[@]}"
