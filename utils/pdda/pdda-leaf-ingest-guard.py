#!/usr/bin/env python3
"""pdda-leaf-ingest-guard.py — PreToolUse(Bash) advisory nudge away from bypassing the collector
registry / refresh_index dispatcher via ad-hoc inline Python.

Fires only when a Bash command both (a) runs Python inline (python -c / python3 -c /
.venv/bin/python -c) AND (b) imports from rebalance.ingest. That combination is the "leaf
entrypoint" bypass ROUTER.md warns about — the correct extension point is one
register_collector(...) call, dispatched by refresh_index() (src/rebalance/ingest/index_ops.py),
not a hand-rolled call into an ingest module.

ADVISORY ONLY — never blocks. Injects additionalContext guidance via the documented Claude Code
PreToolUse hook-output schema (the same schema gsd-core's gsd-read-guard.js uses), then exits 0.
A future hardening pass could escalate a well-proven pattern to a hard block (exit 2) once this
has run false-positive-free for a while — deliberately not done yet (GH-106).
"""
import json
import sys


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0  # fail-open: never block on a malformed/unreadable payload

    if payload.get("tool_name") != "Bash":
        return 0

    command = payload.get("tool_input", {}).get("command", "")
    if not command:
        return 0

    has_inline_python = any(
        marker in command for marker in ("python -c", "python3 -c", ".venv/bin/python -c")
    )
    if not has_inline_python or "rebalance.ingest" not in command:
        return 0

    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": (
                "LEAF-INGEST REMINDER: this command calls into rebalance.ingest directly via "
                "inline Python, bypassing the collector registry. Prefer `rebalance refresh` / "
                "`refresh_index()` (src/rebalance/ingest/index_ops.py) so the call goes through "
                "register_collector's dispatch chain, health tracking, and doctor visibility. "
                "If this genuinely needs a raw one-off call (e.g. a diagnostic), proceed — this "
                "is advisory only."
            ),
        }
    }
    print(json.dumps(output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
