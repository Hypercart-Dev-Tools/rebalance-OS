from datetime import datetime, timezone

def _parse_iso(value: str | None) -> datetime | None:
    if not value: return None
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return None

def _now_iso() -> str:
    """Returns the current UTC time as an ISO format string."""
    return datetime.now(timezone.utc).isoformat()

def _now() -> str:
    """Alias for _now_iso(). Returns current UTC time as an ISO format string."""
    return _now_iso()

def _now_utc() -> datetime:
    """Returns the current UTC time as a timezone-aware datetime object."""
    return datetime.now(timezone.utc)
