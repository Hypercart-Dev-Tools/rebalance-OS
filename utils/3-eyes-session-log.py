#!/usr/bin/env python3
"""Stop hook: append a per-interaction summary to temp/3-eyes.log.

Claude Code fires the Stop hook when the assistant finishes a turn, handing us
JSON on stdin that includes `transcript_path`. We read the transcript, take the
user's request and the assistant's closing text (which is where the findings
live), and append one block to the log.

Contract: never break the session. Any failure exits 0 silently.
"""

import json
import os
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = REPO_ROOT / "temp" / "3-eyes.log"
STATE_PATH = REPO_ROOT / "temp" / ".3-eyes-log.state"

# Generous caps — the point is a readable record, not a full transcript copy.
MAX_REQUEST = 2000
MAX_OUTCOME = 8000


def clip(text, limit):
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + f"\n… [truncated, {len(text) - limit} more chars]"


def block_text(content):
    """Flatten a message's content into plain text, dropping tool plumbing."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text", ""))
    return "\n".join(parts)


def is_real_user_turn(entry):
    """True for a typed prompt — not a tool result, hook echo, or meta line."""
    if entry.get("type") != "user" or entry.get("isMeta"):
        return False
    content = entry.get("message", {}).get("content")
    if isinstance(content, list):
        # A turn carrying tool_result blocks is the harness replying, not the user.
        if any(
            isinstance(b, dict) and b.get("type") == "tool_result" for b in content
        ):
            return False
    text = block_text(content).strip()
    if not text:
        return False
    # System-injected wrappers we don't want as "the request".
    if text.startswith("<") and "system-reminder" in text[:200]:
        return False
    return True


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    transcript_path = payload.get("transcript_path")
    if not transcript_path or not os.path.exists(transcript_path):
        return 0

    entries = []
    with open(transcript_path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except Exception:
                continue

    request = ""
    outcome = ""
    outcome_uuid = ""

    # Final assistant text, walking backwards past tool-only turns.
    for entry in reversed(entries):
        if entry.get("type") == "assistant":
            text = block_text(entry.get("message", {}).get("content")).strip()
            if text:
                outcome = text
                outcome_uuid = entry.get("uuid", "")
                break

    for entry in reversed(entries):
        if is_real_user_turn(entry):
            request = block_text(entry.get("message", {}).get("content"))
            break

    if not outcome and not request:
        return 0

    # Stop also fires on /clear, resume, and compact. Skip if nothing new.
    if outcome_uuid:
        try:
            if STATE_PATH.read_text(encoding="utf-8").strip() == outcome_uuid:
                return 0
        except Exception:
            pass

    stamp = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    session = (payload.get("session_id") or "unknown")[:8]
    cwd = payload.get("cwd") or ""
    device = socket.gethostname() or "unknown-device"

    record = (
        f"\n=== {stamp} | device {device} | session {session} | cwd {cwd} ===\n"
        f"REQUEST:\n{clip(request, MAX_REQUEST) or '(none captured)'}\n\n"
        f"OUTCOME:\n{clip(outcome, MAX_OUTCOME) or '(none captured)'}\n"
    )

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(record)

    if outcome_uuid:
        try:
            STATE_PATH.write_text(outcome_uuid, encoding="utf-8")
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
