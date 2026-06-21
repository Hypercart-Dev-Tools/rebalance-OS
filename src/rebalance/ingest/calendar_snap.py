"""
Google Calendar edge-snapping — detect slightly overlapping timed events and
report a clean boundary between them.

This module is detection/reporting only. It never modifies the calendar: the
calendar is the system of record for time tracking, and writing computed edges
back to it would alter source data. Overlaps are surfaced so a human can fix
them in the calendar directly.

Time-accuracy note:
  When two events overlap, the suggested boundary trims Event 1's end to
  ``Event 2's start - snap_gap_minutes``. ``snap_gap_minutes`` defaults to 0,
  which makes the boundary contiguous (no gap, no time lost). Any positive
  value leaves an unrecorded gap of that many minutes on every resolved
  overlap — i.e. it silently discards real time. Keep it at 0 for accurate
  time calculations; a non-zero value is reported back as a warning.

Rules:
  - Only 2-event overlaps get a suggested boundary. 3+ event clusters are
    skipped and reported for manual cleanup.
  - All-day events are ignored entirely.
  - Operates day-by-day, with a batch mode up to 7 days.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from rebalance.ingest.calendar import (
    CALENDAR_READONLY_SCOPE,
    _build_service,
)
from rebalance.ingest.calendar_helpers import parse_calendar_dt


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class OverlapPair:
    """A detected 2-event overlap where Event 1's end exceeds Event 2's start."""

    event1_id: str
    event1_summary: str
    event1_original_end: str  # ISO datetime
    event1_new_end: str  # ISO datetime (Event2.start - snap_gap_minutes; gapless at 0)
    event2_id: str
    event2_summary: str
    event2_start: str  # ISO datetime
    overlap_minutes: int


@dataclass
class SkippedCluster:
    """A cluster of 3+ overlapping events that was skipped."""

    event_ids: list[str]
    event_summaries: list[str]
    reason: str


@dataclass
class SnapDayResult:
    """Result of processing overlaps for a single day."""

    date: str  # YYYY-MM-DD
    snapped: list[OverlapPair] = field(default_factory=list)
    skipped_clusters: list[SkippedCluster] = field(default_factory=list)
    skipped_allday: int = 0
    total_events_examined: int = 0


@dataclass
class SnapEdgesResult:
    """Aggregate result across all requested days.

    Detection/reporting only — the calendar is never modified.
    """

    days: list[SnapDayResult] = field(default_factory=list)
    total_snapped: int = 0
    total_skipped_clusters: int = 0
    gap_minutes: int = 0
    warning: str = ""
    elapsed_seconds: float = 0.0


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _is_allday_event(event: dict[str, Any]) -> bool:
    """Return True if the event is an all-day event (date-only, no dateTime)."""
    return "dateTime" not in event.get("start", {})


def _detect_overlaps(
    events: list[dict[str, Any]],
    gap_minutes: int = 0,
) -> tuple[list[OverlapPair], list[SkippedCluster], int]:
    """Detect overlapping event pairs from a sorted list of timed events.

    ``gap_minutes`` is the gap left between a resolved pair (Event 1's
    suggested end = Event 2's start - gap_minutes). Defaults to 0 (contiguous,
    no time lost); any positive value discards that many minutes per overlap.

    Returns (overlap_pairs, skipped_clusters, skipped_allday_count).
    """
    # Partition: skip all-day events
    timed: list[dict[str, Any]] = []
    allday_count = 0
    for ev in events:
        if _is_allday_event(ev):
            allday_count += 1
        else:
            timed.append(ev)

    if len(timed) < 2:
        return [], [], allday_count

    # Sort by parsed start time — raw string sort breaks with mixed offsets
    timed.sort(key=lambda e: parse_calendar_dt(e["start"]["dateTime"]))

    # Sweep-line clustering
    clusters: list[list[dict[str, Any]]] = []
    current_cluster = [timed[0]]
    cluster_max_end = parse_calendar_dt(timed[0]["end"]["dateTime"])

    for ev in timed[1:]:
        ev_start = parse_calendar_dt(ev["start"]["dateTime"])
        if ev_start < cluster_max_end:
            # Overlaps with current cluster
            current_cluster.append(ev)
            ev_end = parse_calendar_dt(ev["end"]["dateTime"])
            if ev_end > cluster_max_end:
                cluster_max_end = ev_end
        else:
            # No overlap — finalize current cluster, start new one
            clusters.append(current_cluster)
            current_cluster = [ev]
            cluster_max_end = parse_calendar_dt(ev["end"]["dateTime"])

    clusters.append(current_cluster)

    # Process clusters
    pairs: list[OverlapPair] = []
    skipped: list[SkippedCluster] = []

    for cluster in clusters:
        if len(cluster) == 1:
            continue
        elif len(cluster) == 2:
            ev1, ev2 = cluster
            ev1_end_dt = parse_calendar_dt(ev1["end"]["dateTime"])
            ev2_start_dt = parse_calendar_dt(ev2["start"]["dateTime"])
            ev2_end_dt = parse_calendar_dt(ev2["end"]["dateTime"])

            # Skip contained events — Event 1 fully wraps Event 2.
            # Trimming a 3-hour block to 59 minutes is destructive, not
            # "edge snapping".  Report as a skipped cluster instead.
            if ev1_end_dt >= ev2_end_dt:
                skipped.append(
                    SkippedCluster(
                        event_ids=[ev1["id"], ev2["id"]],
                        event_summaries=[ev1.get("summary", ""), ev2.get("summary", "")],
                        reason="one event fully contains the other — manual resolution required",
                    )
                )
                continue

            new_end_dt = ev2_start_dt - timedelta(minutes=gap_minutes)
            overlap_mins = int((ev1_end_dt - ev2_start_dt).total_seconds() / 60)  # raw-ok: one-off calc

            # Preserve timezone from original event
            original_end_raw = ev1["end"]["dateTime"]
            tz_info = parse_calendar_dt(original_end_raw).tzinfo
            if tz_info:
                new_end_dt = new_end_dt.astimezone(tz_info)

            pairs.append(
                OverlapPair(
                    event1_id=ev1["id"],
                    event1_summary=ev1.get("summary", ""),
                    event1_original_end=ev1["end"]["dateTime"],
                    event1_new_end=new_end_dt.isoformat(),
                    event2_id=ev2["id"],
                    event2_summary=ev2.get("summary", ""),
                    event2_start=ev2["start"]["dateTime"],
                    overlap_minutes=overlap_mins,
                )
            )
        else:
            # 3+ events — skip
            skipped.append(
                SkippedCluster(
                    event_ids=[e["id"] for e in cluster],
                    event_summaries=[e.get("summary", "") for e in cluster],
                    reason=f"{len(cluster)} events overlap in chain — manual resolution required",
                )
            )

    return pairs, skipped, allday_count


def _fetch_day_events(
    service: Any,
    calendar_id: str,
    target_date: date,
    timezone_name: str,
) -> list[dict[str, Any]]:
    """Fetch timed events for a single day directly from Google Calendar API."""
    from zoneinfo import ZoneInfo

    tz = ZoneInfo(timezone_name)
    day_start = datetime.combine(target_date, datetime.min.time(), tzinfo=tz)
    day_end = datetime.combine(target_date + timedelta(days=1), datetime.min.time(), tzinfo=tz)

    all_events: list[dict[str, Any]] = []
    page_token = None
    while True:
        result = (
            service.events()
            .list(
                calendarId=calendar_id,
                timeMin=day_start.isoformat(),
                timeMax=day_end.isoformat(),
                singleEvents=True,
                orderBy="startTime",
                maxResults=250,
                pageToken=page_token,
            )
            .execute()
        )
        all_events.extend(result.get("items", []))
        page_token = result.get("nextPageToken")
        if not page_token:
            break

    return all_events


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def snap_day_edges(
    service: Any,
    calendar_id: str,
    target_date: date,
    timezone_name: str,
    *,
    gap_minutes: int = 0,
) -> SnapDayResult:
    """Detect overlapping edges for a single day (read-only; never patches)."""
    events = _fetch_day_events(service, calendar_id, target_date, timezone_name)
    pairs, skipped, allday_count = _detect_overlaps(events, gap_minutes=gap_minutes)

    return SnapDayResult(
        date=target_date.isoformat(),
        snapped=pairs,
        skipped_clusters=skipped,
        skipped_allday=allday_count,
        total_events_examined=len(events),
    )


def snap_edges(
    *,
    calendar_id: str,
    start_date: date,
    num_days: int = 1,
    timezone_name: str,
    gap_minutes: int = 0,
) -> SnapEdgesResult:
    """Detect overlapping calendar edges across multiple days.

    Detection/reporting only — the calendar is never modified. Overlaps are
    returned for a human to resolve in the calendar directly.

    Args:
        calendar_id: Google Calendar ID.
        start_date: First day to process.
        num_days: Number of consecutive days (1-7).
        timezone_name: IANA timezone for day boundaries.
        gap_minutes: Gap left between a resolved pair. Keep at 0 for accurate
            time tracking; any positive value discards that many minutes per
            overlap and is reported back as a warning.

    Raises:
        ValueError: If num_days is outside 1-7.
    """
    if not 1 <= num_days <= 7:
        raise ValueError(f"num_days must be between 1 and 7, got {num_days}")

    gap_minutes = max(0, int(gap_minutes))

    start = time.monotonic()
    # Read-only by design: this tool reports overlaps, it never writes to the
    # calendar, so it only ever needs read scope.
    service = _build_service(required_scopes=[CALENDAR_READONLY_SCOPE])

    days: list[SnapDayResult] = []
    for offset in range(num_days):
        target = start_date + timedelta(days=offset)
        day_result = snap_day_edges(
            service, calendar_id, target, timezone_name, gap_minutes=gap_minutes
        )
        days.append(day_result)

    warning = ""
    if gap_minutes != 0:
        warning = (
            f"snap_gap_minutes={gap_minutes}: leaves a {gap_minutes}-minute "
            "unrecorded gap on every resolved overlap, which understates tracked "
            "time. Set snap_gap_minutes to 0 for accurate time calculations."
        )

    return SnapEdgesResult(
        days=days,
        total_snapped=sum(len(d.snapped) for d in days),
        total_skipped_clusters=sum(len(d.skipped_clusters) for d in days),
        gap_minutes=gap_minutes,
        warning=warning,
        elapsed_seconds=round(time.monotonic() - start, 2),
    )
