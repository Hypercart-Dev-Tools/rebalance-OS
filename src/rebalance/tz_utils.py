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


def format_local(value: str | datetime | None, fmt: str, *, tz: ZoneInfo | None = None) -> str:
    """Render `value` (a UTC ISO-8601 string, or an already-parsed datetime —
    naive treated as UTC) in local time using the given strftime pattern.

    Returns "" on None/unparseable input so callers choose their own fallback
    text — this is the shared parse-guard-convert-format core that several
    call sites previously reimplemented independently, each with its own
    fallback string. Callers keep their own `fmt` so migrating onto this
    doesn't change any already-correct screen's visible output.
    """
    if value is None:
        return ""
    parsed = value if isinstance(value, datetime) else parse_utc_iso(value)
    if parsed is None:
        return ""
    return to_local(parsed, tz).strftime(fmt)


def format_relative(value: str | datetime | None, *, now: datetime | None = None) -> str:
    """Render `value` as a compact relative age: 'just now' / '5m ago' /
    '3h ago' / '2d ago'. Returns "" on None/unparseable input.

    No timezone conversion needed — a delta between two instants is
    tz-agnostic — so this only depends on `parse_utc_iso`/naive-as-UTC.
    """
    if value is None:
        return ""
    parsed = value if isinstance(value, datetime) else parse_utc_iso(value)
    if parsed is None:
        return ""
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    reference = now or datetime.now(timezone.utc)
    secs = max(0, int((reference - parsed).total_seconds()))
    for label, unit in (("d", 86400), ("h", 3600), ("m", 60)):
        if secs >= unit:
            return f"{secs // unit}{label} ago"
    return "just now"
