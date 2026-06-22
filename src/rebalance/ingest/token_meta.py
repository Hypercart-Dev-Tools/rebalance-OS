"""Per-token sidecar metadata — when each credential was first added + its lifetime.

The auth log (``auth_log.py``) is an append-only *event stream*, good for
cadence. This is the complementary *keyed record*: for each distinct token
**value** — identified by a truncated SHA-256 fingerprint, so the raw token is
never stored — it remembers when that token was first added, when it was last
(re)set, how many times, and its kind. That makes "how long has the *current*
token lived?" and "is this a new token?" answerable, which is exactly what you
need to spot a PAT that keeps dying every few days.

Stored as JSON at ``temp/logs/token_meta.json`` (gitignored). All writes are
best-effort — metadata must never break a credential write.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rebalance.tz_utils import parse_utc_iso


def _meta_path() -> Path:
    """Return the token-metadata sidecar path, creating its dir if needed.

    Shares the auth log's ``temp/logs`` home (this is the keyed sidecar to that
    event stream) and the same ``REBALANCE_AUTH_LOG_DIR`` seam, so tests and
    sandboxed runs redirect both together — see tests/conftest.py, which keeps
    the suite from polluting the repo's real token_meta.json.
    """
    override = os.environ.get("REBALANCE_AUTH_LOG_DIR")
    if override:
        log_dir = Path(override)
    else:
        from rebalance.paths import resolve_project_root
        log_dir = resolve_project_root(Path(__file__)) / "temp" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "token_meta.json"


def fingerprint(token: str) -> str:
    """Stable, non-reversible id for a token value (never stores the raw token)."""
    return hashlib.sha256(token.strip().encode("utf-8")).hexdigest()[:12]


def _load() -> dict[str, Any]:
    path = _meta_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8")) or {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save(data: dict[str, Any]) -> None:
    try:
        _meta_path().write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    except OSError:
        pass  # never let metadata break the caller


def record_token_set(
    service: str, token: str, *, kind: str = "", source: str = "manual"
) -> dict[str, Any]:
    """Record that *token* was added for *service*.

    Preserves ``first_added_at`` when the same token value was seen before
    (re-set / re-persist); only ``last_set_at`` and ``set_count`` advance.
    A genuinely new token value starts a fresh record with ``first_added_at`` now.
    Returns the (updated) record.
    """
    if not token:
        return {}
    data = _load()
    svc = data.setdefault(service, {"current": None, "tokens": {}})
    fp = fingerprint(token)
    now = datetime.now(timezone.utc).isoformat()
    rec = svc["tokens"].get(fp)
    if rec is None:
        rec = {
            "fingerprint": fp,
            "kind": kind,
            "source": source,
            "first_added_at": now,
            "last_set_at": now,
            "set_count": 1,
        }
    else:
        rec["last_set_at"] = now
        rec["set_count"] = int(rec.get("set_count", 0)) + 1
        if kind:
            rec["kind"] = kind
    svc["tokens"][fp] = rec
    svc["current"] = fp
    _save(data)
    return rec


def current_token_meta(service: str) -> dict[str, Any] | None:
    """Metadata for the *current* token of *service* (without needing its value)."""
    svc = _load().get(service) or {}
    fp = svc.get("current")
    return (svc.get("tokens") or {}).get(fp) if fp else None


def age_text(iso_ts: str | None, *, now: datetime | None = None) -> str:
    """Compact age like ``6d`` / ``3.2h`` for a stored ISO timestamp; '' if unknown."""
    dt = parse_utc_iso(iso_ts)  # handles trailing-Z + naive→UTC; None on bad/empty
    if dt is None:
        return ""
    now = now or datetime.now(timezone.utc)
    secs = max((now - dt).total_seconds(), 0.0)
    return f"{secs / 86400:.0f}d" if secs >= 86400 else f"{secs / 3600:.1f}h"
