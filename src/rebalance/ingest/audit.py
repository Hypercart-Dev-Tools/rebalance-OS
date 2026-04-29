"""Structured audit logging for destructive local operator actions."""

from __future__ import annotations

import getpass
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AUDIT_LOG_PATH = Path(__file__).parent.parent.parent.parent / "logs" / "agent-audit.json"


def _load_entries(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def append_audit_entry(action: str, target: str, **details: Any) -> dict[str, Any]:
    """Append one JSON audit record to the local audit log."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user": getpass.getuser(),
        "action": action,
        "target": target,
        **details,
    }
    AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    entries = _load_entries(AUDIT_LOG_PATH)
    entries.append(entry)
    AUDIT_LOG_PATH.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
    return entry
