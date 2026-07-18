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


def format_timestamp(
    value: str | datetime | None,
    *,
    relative: bool = False,
    month_day: bool = False,
    tz: ZoneInfo | None = None,
) -> str:
    """Render an absolute local timestamp, with relative age only ever as a suffix.

    Absolute output is the anchor (`YYYY-MM-DD h:mm AM/PM`); when
    ``relative=True`` the existing compact relative helper is appended as
    ``" · <relative>"``. Returns ``""`` when the absolute anchor cannot be
    rendered, so callers never emit a bare relative with no timestamp.

    ``month_day=True`` selects the year-less calendar variant — `July 19 11:00 AM`
    — for surfaces where the year is implied by context (the calendar module's
    Upcoming list, which only ever shows the near future). It is a variant of this
    one helper rather than an inline strftime at the call site, so every timestamp
    on the dashboard still resolves through a single formatter.
    """
    fmt = "%B %-d %-I:%M %p" if month_day else "%Y-%m-%d %-I:%M %p"
    absolute = format_local(value, fmt, tz=tz)
    if not absolute:
        return ""
    if not relative:
        return absolute
    suffix = format_relative(value)
    return f"{absolute} · {suffix}" if suffix else absolute
