"""
Timezone utilities — single source of truth for local timezone resolution.

Priority for device timezone: REBALANCE_TZ env var > /etc/localtime symlink > UTC fallback.

All stored timestamps in SQLite are UTC ISO 8601 TEXT. These helpers are only
for operator-facing display (terminal dashboard, pulse, reports).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def local_tz() -> ZoneInfo:
    """Return the device's local timezone as a ZoneInfo.

    Resolution order:
    1. REBALANCE_TZ environment variable (explicit operator override)
    2. /etc/localtime symlink (macOS / Linux system timezone)
    3. UTC fallback
    """
    name = os.environ.get("REBALANCE_TZ")

    if not name:
        try:
            lt = os.readlink("/etc/localtime")
            if "zoneinfo/" in lt:
                name = lt.split("zoneinfo/")[-1]
        except OSError:
            pass

    if name:
        try:
            return ZoneInfo(name)
        except ZoneInfoNotFoundError:
            pass

    return ZoneInfo("UTC")


def to_local(dt: datetime, tz: ZoneInfo | None = None) -> datetime:
    """Convert *dt* to local timezone, defaulting to local_tz().

    Treats naive datetimes as UTC (consistent with all storage conventions).
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(tz or local_tz())


def parse_utc_iso(value: str | None) -> datetime | None:
    """Parse an ISO 8601 string; assumes UTC if tzinfo is absent.

    Handles both trailing-Z (GitHub/Sleuth APIs) and +HH:MM offset forms.
    Returns None on empty input or parse failure.
    """
    if not value:
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed
