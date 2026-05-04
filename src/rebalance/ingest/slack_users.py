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

# Sleuth reminders posted by the Sleuth bot follow a stable shape:
#
#   <@U…>, <@U…> - please follow up on <https://…>
#   <@U…> — please follow up on <https://…>
#
# The mention list is just bookkeeping (the dashboard already filters to
# reminders assigned to the operator), so the actually useful content is
# whatever follows "please follow up on". We strip the prefix to claw back
# screen real estate. If the pattern doesn't match — e.g. a manual
# reminder with custom phrasing — we leave the message untouched.
_SLEUTH_PREFIX_RE = re.compile(
    r"^@\S+(?:\s*,\s*@\S+)*\s*[-–—:]\s*please\s+follow\s+up\s+on\s+",
    flags=re.IGNORECASE,
)

# Slack wraps URLs in angle brackets, optionally with a "|label" suffix.
# Examples: <https://example.com>, <https://example.com|click here>.
# We unwrap so the link reads naturally in a terminal cell, preferring
# the label when present (Slack does the same).
_SLACK_LINK_RE = re.compile(r"<((?:https?|mailto):[^|>]+)(?:\|([^>]+))?>")

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


def unwrap_slack_links(text: str | None) -> str:
    """Replace Slack ``<URL>`` / ``<URL|label>`` markup with plain text."""
    if not text:
        return text or ""

    def _sub(match: re.Match[str]) -> str:
        url = match.group(1)
        label = match.group(2)
        return label if label else url

    return _SLACK_LINK_RE.sub(_sub, text)


def compact_sleuth_reminder(text: str | None) -> str:
    """Compact a raw Sleuth reminder for surfaces with limited width.

    Sleuth-bot reminders have a stable multi-line shape:

        @mentions - please follow up on <URL|this>:
        ><quoted Slack message>

        Key task(s):
        • <bullet derived from the source message>

    The header line is pure boilerplate (the dashboard already filters to
    reminders assigned to the operator), and the URL label is usually the
    uninformative word "this". The actually useful content is on the
    quoted line that follows the header, or — failing that — the first
    bullet in the "Key task(s)" block.

    Pipeline:
      1. ``format_slack_mentions`` — rewrite ``<@UXXX>`` → friendly names.
      2. If the text matches the Sleuth header pattern, drop the header
         and prefer the quoted body line; fall back to the first bullet,
         then to the first non-empty body line, then to the single-line
         post-strip text (covers reminders with no body).
      3. ``unwrap_slack_links`` on whatever we settled on, so
         ``<URL|label>`` reads as plain text (Slack's behaviour: prefer
         the label).

    If the header pattern doesn't match — e.g. a manually-typed reminder
    with custom phrasing — we return the message with mentions + links
    rewritten and the body otherwise untouched, so we never silently
    swallow unfamiliar content.
    """
    if not text:
        return text or ""
    rewritten = format_slack_mentions(text)

    if not _SLEUTH_PREFIX_RE.match(rewritten):
        return unwrap_slack_links(rewritten)

    lines = rewritten.splitlines()
    body = lines[1:] if len(lines) > 1 else []

    # Prefer the quoted source line ("> ...") — it's the most concise
    # restatement of the original Slack message that triggered the reminder.
    for line in body:
        stripped = line.lstrip()
        if stripped.startswith(">"):
            return unwrap_slack_links(stripped.lstrip(">").strip())

    # Fall back to the first "Key task(s)" bullet.
    for line in body:
        stripped = line.lstrip()
        if stripped[:1] in ("•", "-", "*"):
            return unwrap_slack_links(stripped[1:].lstrip())

    # Fall back to the first non-empty body line.
    for line in body:
        if line.strip():
            return unwrap_slack_links(line.strip())

    # No body — strip the header inline and unwrap whatever's left
    # (handles single-line reminders like
    # "@Noel - please follow up on <https://example.com>").
    return unwrap_slack_links(_SLEUTH_PREFIX_RE.sub("", rewritten)).strip()
