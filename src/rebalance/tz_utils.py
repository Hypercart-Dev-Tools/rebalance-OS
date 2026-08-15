"""Timezone utilities — single source of truth for local timezone resolution.

DEPRECATED: This module is deprecated in favor of `rebalance.lib.time_ops`.
All helpers are re-exported from `rebalance.lib.time_ops` for backward compatibility.
Do not add new code here; use `rebalance.lib.time_ops` instead.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from rebalance.lib.time_ops import (
    format_local,
    format_relative,
    format_timestamp,
    local_tz,
    parse_date,
    parse_iso,
    parse_utc_iso,
    to_local,
)

__all__ = [
    "ZoneInfo",
    "ZoneInfoNotFoundError",
    "date",
    "datetime",
    "format_local",
    "format_relative",
    "format_timestamp",
    "local_tz",
    "parse_date",
    "parse_iso",
    "parse_utc_iso",
    "timezone",
    "to_local",
]
