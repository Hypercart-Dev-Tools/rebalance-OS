"""
Slack user lookup — single source of truth for friendly-name rendering.

Reads ``temp/slack_users.json`` (gitignored, user-editable) and exposes
two helpers:

  - ``load_user_map()`` — returns the {user_id: friendly_name} dict
  - ``format_slack_mentions(text)`` — rewrites ``<@U…>`` mentions in
    arbitrary text using the lookup, with sensible fallbacks

The file shape:

    {
      "_README": "...",
      "users": {
        "U01EXAMPLE1": "Alice",
        "U02EXAMPLE2": "Bob"
      }
    }

Edits are picked up automatically — the loader keys its cache off the
file's mtime, so a running dashboard or background pulse job will reflect
new entries on the next read without a restart.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from threading import Lock
from typing import Any


SLACK_USERS_PATH = (
    Path(__file__).parent.parent.parent.parent / "temp" / "slack_users.json"
)

# Slack mention forms we know about:
#   <@U12345678>           — plain user mention
#   <@U12345678|alice>     — user mention with display name fallback
#   <@W12345678>           — Slack Connect / external workspace user
# We deliberately do NOT match <#C…> (channel) or <!subteam^…> (groups)
# — those are different surface forms and not the user's request.
_MENTION_RE = re.compile(r"<@([UW][A-Z0-9]+)(?:\|([^>]+))?>")

_cache_lock = Lock()
_cache: dict[str, Any] = {"mtime": None, "users": {}}


def get_slack_users_path() -> Path:
    """Return the canonical lookup-file path (used by setup and docs)."""
    return SLACK_USERS_PATH


def load_user_map() -> dict[str, str]:
    """Return the current {user_id: friendly_name} mapping.

    Cached against the file's mtime so callers can hammer this on every
    UI tick without an inflated read cost; an external editor save will
    invalidate the cache on the next call.
    """
    path = SLACK_USERS_PATH
    if not path.exists():
        return {}
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return {}

    with _cache_lock:
        if _cache["mtime"] == mtime:
            return dict(_cache["users"])

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            # Bad JSON shouldn't kill the dashboard — fall back to empty
            # and let the next save fix it.
            _cache["mtime"] = mtime
            _cache["users"] = {}
            return {}

        users_block = raw.get("users") if isinstance(raw, dict) else None
        users: dict[str, str] = {}
        if isinstance(users_block, dict):
            for k, v in users_block.items():
                if isinstance(k, str) and isinstance(v, str) and k and v:
                    users[k] = v
        _cache["mtime"] = mtime
        _cache["users"] = users
        return dict(users)


def format_slack_mentions(text: str | None) -> str:
    """Rewrite Slack mention markup in *text* using the lookup file.

    Resolution order per mention:
      1. Friendly name from ``slack_users.json``
      2. Inline display name (the ``|name`` fallback in the mention markup)
      3. The raw user id, prefixed with ``@``
    """
    if not text:
        return text or ""

    users = load_user_map()

    def _sub(match: re.Match[str]) -> str:
        uid = match.group(1)
        inline = match.group(2)
        name = users.get(uid) or inline or uid
        return f"@{name}"

    return _MENTION_RE.sub(_sub, text)
