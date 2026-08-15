"""Time, date, and timezone operations.

Canonical home for date/datetime parsing, timezone resolution, relative time,
and operator-facing display formatting.
"""

from __future__ import annotations

import os
import re
from datetime import date, datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def _parse_iso(raw: Any, force_utc: bool = True) -> datetime | None:
    """Parse an ISO 8601 string into a datetime object.

    Handles space separation, trailing 'Z', offsets, and fractional seconds.
    Returns None on empty/malformed inputs or non-string types.

    BEHAVIOUR WIDENED in GH-273: sub-second precision beyond six digits is now
    truncated to six rather than rejected. `datetime.fromisoformat` accepts at
    most microsecond resolution, so a nanosecond timestamp previously returned
    None here. This is the one intentional behaviour change in an otherwise
    behaviour-preserving consolidation — it turns a silent None into a parsed
    value, so any caller that branched on None for such inputs now takes the
    parsed path instead.
    """
    if not raw or not isinstance(raw, str):
        return None
    text = raw.strip().replace("Z", "+00:00")

    parsed = None
    for candidate in (text, text.replace(" ", "T")):
        try:
            parsed = datetime.fromisoformat(candidate)
            break
        except ValueError:
            # Handle timestamps with >6 decimal digits for fractional seconds
            try:
                candidate_trimmed = re.sub(r"(\.\d{6})\d+", r"\1", candidate)
                parsed = datetime.fromisoformat(candidate_trimmed)
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


def parse_iso(raw: Any, force_utc: bool = True) -> datetime | None:
    """Parse an ISO 8601 string into a datetime object.

    Public alias for `_parse_iso`.
    """
    return _parse_iso(raw, force_utc=force_utc)


def parse_utc_iso(value: Any) -> datetime | None:
    """Parse an ISO 8601 string and ensure it is timezone-aware in UTC.

    If the string specifies no timezone, it is assumed to be UTC.
    Returns None on empty input or parse failure.
    """
    return _parse_iso(value, force_utc=True)


def parse_date(raw: Any) -> date | None:
    """Parse a date or ISO datetime string / object into a date.

    Accepts:
    - `datetime.date` or `datetime.datetime` instances
    - ISO 8601 strings (e.g. 'YYYY-MM-DD', 'YYYY-MM-DDTHH:MM:SSZ')

    Returns `date` or `None` on invalid / empty input.
    """
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    if not isinstance(raw, str):
        return None
    raw_str = raw.strip()
    if not raw_str:
        return None
    if len(raw_str) == 10:
        try:
            return date.fromisoformat(raw_str)
        except ValueError:
            pass
    parsed = _parse_iso(raw_str, force_utc=False)
    if parsed is not None:
        return parsed.date()
    try:
        return date.fromisoformat(raw_str[:10])
    except (ValueError, IndexError):
        return None


def _current_time(tz: timezone | ZoneInfo | None = None) -> datetime:
    try:
        import sys
        tz_mod = sys.modules.get("rebalance.tz_utils")
        if tz_mod is not None and hasattr(tz_mod, "datetime") and tz_mod.datetime is not datetime:
            return tz_mod.datetime.now(tz or timezone.utc)
    except Exception:
        pass
    return datetime.now(tz or timezone.utc)


def _now_iso() -> str:
    """Returns the current UTC time as an ISO format string."""
    return _current_time(timezone.utc).isoformat()


def _now() -> str:
    """Alias for _now_iso(). Returns current UTC time as an ISO format string."""
    return _now_iso()


def _now_utc() -> datetime:
    """Returns the current UTC time as a timezone-aware datetime object."""
    return _current_time(timezone.utc)


def now_iso() -> str:
    """Returns the current UTC time as an ISO format string."""
    return _now_iso()


def now() -> str:
    """Alias for now_iso(). Returns current UTC time as an ISO format string."""
    return _now_iso()


def now_utc() -> datetime:
    """Returns the current UTC time as a timezone-aware datetime object."""
    return _now_utc()


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


def format_local(value: str | datetime | None, fmt: str, *, tz: ZoneInfo | None = None) -> str:
    """Render `value` in local time using the given strftime pattern.

    `value` may be a UTC ISO-8601 string, or an already-parsed datetime (naive
    treated as UTC). Returns "" on None/unparseable input so callers choose
    their own fallback text.
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
    reference = now or _current_time(timezone.utc)
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
    Upcoming list, which only ever shows the near future).
    """
    fmt = "%B %-d %-I:%M %p" if month_day else "%Y-%m-%d %-I:%M %p"
    absolute = format_local(value, fmt, tz=tz)
    if not absolute:
        return ""
    if not relative:
        return absolute
    suffix = format_relative(value)
    return f"{absolute} · {suffix}" if suffix else absolute
