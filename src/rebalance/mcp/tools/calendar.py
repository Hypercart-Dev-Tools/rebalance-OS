from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP, database_path: Path) -> None:
    @mcp.tool()
    def create_calendar_event(
        summary: str,
        start_time: str,
        end_time: str,
        description: str = "",
        location: str = "",
        attendees: list[str] | None = None,
        calendar_id: str = "",
        timezone_name: str = "",
    ) -> dict[str, Any]:
        """
        Create a Google Calendar event using the local OAuth token.

        Args:
            summary: Event title.
            start_time: ISO datetime with timezone offset.
            end_time: ISO datetime with timezone offset.
            description: Optional body text.
            location: Optional location.
            attendees: Optional attendee email list.
            calendar_id: Optional calendar ID. Defaults to the local config calendar.
            timezone_name: Optional IANA timezone name to include in the event payload.
        """
        from rebalance.ingest.calendar import create_calendar_event as calendar_create_event
        from rebalance.ingest.calendar_config import CalendarConfig

        resolved_calendar_id = calendar_id.strip()
        if not resolved_calendar_id:
            resolved_calendar_id = CalendarConfig.load().calendar_id

        result = calendar_create_event(
            calendar_id=resolved_calendar_id,
            summary=summary,
            start_time=start_time,
            end_time=end_time,
            description=description,
            location=location,
            attendees=attendees or [],
            timezone_name=timezone_name.strip() or None,
        )
        return {
            "event_id": result.event_id,
            "html_link": result.html_link,
            "calendar_id": result.calendar_id,
            "summary": result.summary,
            "start_time": result.start_time,
            "end_time": result.end_time,
            "attendees_count": result.attendees_count,
            "status": "created",
        }

    @mcp.tool()
    def review_timesheet(date_str: str = "") -> dict[str, Any]:
        """
        Return unclassified calendar events for a given date that need
        human or agent review.

        These are events that passed the exclude filter but did not match
        any configured project. The agent can recommend classifying them
        under a project, marking as "include" (real work, no project),
        or "exclude" (filler).

        Args:
            date_str: ISO date (YYYY-MM-DD). Defaults to today.

        Returns:
            needs_review: list of {summary, start_time, end_time, duration_minutes}
            available_projects: list of project names for classification
        """
        from datetime import date as date_cls

        from rebalance.ingest.calendar_config import CalendarConfig
        from rebalance.ingest.calendar_helpers import event_duration_minutes
        from rebalance.ingest.daily_report import get_day_data
        from rebalance.ingest.project_classifier import load_project_matchers
        from rebalance.lib.time_ops import parse_date

        config = CalendarConfig.load()
        target = parse_date(date_str) or date_cls.today()
        matchers = load_project_matchers(database_path, config=config)
        day = get_day_data(database_path, target, config, project_matchers=matchers)

        review_items = []
        for event in day.needs_review:
            start_str = event.get("start_time", "")
            end_str = event.get("end_time", "")
            review_items.append({
                "summary": event.get("summary", ""),
                "start_time": start_str,
                "end_time": end_str,
                "duration_minutes": event_duration_minutes(start_str, end_str),
            })

        project_names = [m.name for m in matchers]
        return {
            "date": target.isoformat(),
            "needs_review": review_items,
            "available_projects": project_names,
        }

    @mcp.tool()
    def classify_event(summary: str, decision: str) -> dict[str, Any]:
        """
        Persist a classification decision for an unmatched calendar event.

        After review_timesheet surfaces events, call this to record how
        each one should be handled in future reports.

        Args:
            summary: The event title (exact text from the calendar).
            decision: One of:
              - "include" — real work, keep in reports (no project assignment)
              - "exclude" — filler, remove from future reports
              - "project:<Name>" — assign to a specific project (e.g. "project:Binoid - Bloomz")

        Returns confirmation of the stored decision.
        """
        from rebalance.ingest.calendar_config import InvalidDecisionError, save_review_decision

        try:
            save_review_decision(summary, decision.strip())
        except InvalidDecisionError as e:
            return {"error": str(e)}

        return {
            "summary": summary,
            "decision": decision.strip(),
            "status": "saved",
        }

    @mcp.tool()
    def snap_calendar_edges(
        date_str: str = "",
        days: int = 1,
        calendar_id: str = "",
        timezone_name: str = "",
    ) -> dict[str, Any]:
        """
        Report slightly overlapping calendar events and a clean boundary
        between each overlapping pair.

        Read-only: this tool never modifies your calendar. The calendar is the
        system of record for time tracking, so overlaps are surfaced for you to
        fix directly rather than patched automatically. Skips all-day events
        and clusters of 3+ overlapping events (manual resolution required).

        The suggested boundary is gapless by default (snap_gap_minutes=0 in
        calendar config). A positive snap_gap_minutes leaves an unrecorded gap
        on every overlap and understates tracked time; when set, the result
        includes a `warning`.

        Args:
            date_str: Start date (YYYY-MM-DD). Defaults to today.
            days: Number of consecutive days to process (1-7).
            calendar_id: Calendar ID. Defaults to config calendar.
            timezone_name: IANA timezone. Defaults to config timezone.
        """
        import dataclasses
        from datetime import datetime
        from zoneinfo import ZoneInfo

        from rebalance.ingest.calendar_config import CalendarConfig
        from rebalance.ingest.calendar_snap import snap_edges
        from rebalance.lib.time_ops import parse_date

        if not (1 <= days <= 7):
            return {"error": f"days must be between 1 and 7, got {days}", "status": "error"}

        config = CalendarConfig.load()
        resolved_calendar_id = calendar_id.strip() or config.calendar_id
        resolved_timezone = timezone_name.strip() or config.timezone
        if date_str.strip():
            start_date = parse_date(date_str) or datetime.now(ZoneInfo(resolved_timezone)).date()
        else:
            start_date = datetime.now(ZoneInfo(resolved_timezone)).date()

        result = snap_edges(
            calendar_id=resolved_calendar_id,
            start_date=start_date,
            num_days=days,
            timezone_name=resolved_timezone,
            gap_minutes=config.snap_gap_minutes,
        )
        return dataclasses.asdict(result)
