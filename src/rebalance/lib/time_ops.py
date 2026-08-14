from datetime import datetime, timezone

from typing import Any

def _parse_iso(raw: Any, force_utc: bool = True) -> datetime | None:
    if not raw or not isinstance(raw, str):
        return None
    text = raw.strip().replace("Z", "+00:00")
    
    parsed = None
    for candidate in (text, text.replace(" ", "T")):
        try:
            parsed = datetime.fromisoformat(candidate)
            break
        except ValueError:
            continue
            
    if not parsed:
        return None
        
    if force_utc:
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return parsed

def _now_iso() -> str:
    """Returns the current UTC time as an ISO format string."""
    return datetime.now(timezone.utc).isoformat()

def _now() -> str:
    """Alias for _now_iso(). Returns current UTC time as an ISO format string."""
    return _now_iso()

def _now_utc() -> datetime:
    """Returns the current UTC time as a timezone-aware datetime object."""
    return datetime.now(timezone.utc)
