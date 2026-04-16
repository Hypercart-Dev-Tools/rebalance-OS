"""
Google Calendar edge-snapping — detect slightly overlapping timed events
and trim Event 1's end to 1 minute before Event 2's start so adjacent
events have clean boundaries.

Rules:
  - Only 2-event overlaps are auto-resolved. 3+ event clusters are
    skipped and reported for manual cleanup.
  - All-day events are ignored entirely.
  - Operates day-by-day, with a batch mode up to 7 days.
  - Dry-run by default; pass apply=True to actually patch Google Calendar.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from rebalance.ingest.calendar import (
    CALENDAR_READONLY_SCOPE,
    CALENDAR_WRITE_SCOPE,
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
    event1_new_end: str  # ISO datetime (Event2.start - 1 minute)
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
    """Aggregate result across all requested days."""

    days: list[SnapDayResult] = field(default_factory=list)
    total_snapped: int = 0
    total_skipped_clusters: int = 0
    applied: bool = False
    elapsed_seconds: float = 0.0


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _is_allday_event(event: dict[str, Any]) -> bool:
    """Return True if the event is an all-day event (date-only, no dateTime)."""
    return "dateTime" not in event.get("start", {})


def _detect_overlaps(
    events: list[dict[str, Any]],
) -> tuple[list[OverlapPair], list[SkippedCluster], int]:
    """Detect overlapping event pairs from a sorted list of timed events.

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

            new_end_dt = ev2_start_dt - timedelta(minutes=1)
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


def _patch_event_end(
    service: Any,
    calendar_id: str,
    event_id: str,
    new_end_iso: str,
    original_end_timezone: str | None = None,
) -> dict[str, Any]:
    """Patch a single event's end time via the Google Calendar API."""
    end_body: dict[str, str] = {"dateTime": new_end_iso}
    if original_end_timezone:
        end_body["timeZone"] = original_end_timezone

    return (
        service.events()
        .patch(
            calendarId=calendar_id,
            eventId=event_id,
            body={"end": end_body},
            sendUpdates="none",
        )
        .execute()
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def snap_day_edges(
    service: Any,
    calendar_id: str,
    target_date: date,
    timezone_name: str,
    *,
    apply: bool = False,
) -> SnapDayResult:
    """Detect and optionally fix overlapping edges for a single day."""
    events = _fetch_day_events(service, calendar_id, target_date, timezone_name)
    pairs, skipped, allday_count = _detect_overlaps(events)

    if apply:
        for pair in pairs:
            # Extract timezone from original event if present
            original_tz = None
            for ev in events:
                if ev["id"] == pair.event1_id:
                    original_tz = ev.get("end", {}).get("timeZone")
                    break

            _patch_event_end(
                service,
                calendar_id,
                pair.event1_id,
                pair.event1_new_end,
                original_end_timezone=original_tz,
            )

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
    apply: bool = False,
) -> SnapEdgesResult:
    """Detect and optionally fix overlapping calendar edges across multiple days.

    Args:
        calendar_id: Google Calendar ID.
        start_date: First day to process.
        num_days: Number of consecutive days (1-7).
        timezone_name: IANA timezone for day boundaries.
        apply: If True, patches Google Calendar. Default is dry-run.

    Raises:
        ValueError: If num_days is outside 1-7.
    """
    if not 1 <= num_days <= 7:
        raise ValueError(f"num_days must be between 1 and 7, got {num_days}")

    start = time.monotonic()
    required_scope = CALENDAR_WRITE_SCOPE if apply else CALENDAR_READONLY_SCOPE
    service = _build_service(required_scopes=[required_scope])

    days: list[SnapDayResult] = []
    for offset in range(num_days):
        target = start_date + timedelta(days=offset)
        day_result = snap_day_edges(
            service, calendar_id, target, timezone_name, apply=apply
        )
        days.append(day_result)

    return SnapEdgesResult(
        days=days,
        total_snapped=sum(len(d.snapped) for d in days),
        total_skipped_clusters=sum(len(d.skipped_clusters) for d in days),
        applied=apply,
        elapsed_seconds=round(time.monotonic() - start, 2),
    )
