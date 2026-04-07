"""
Daily calendar report generator — creates markdown report with daily totals and project aggregator.

Excludes events by keyword, groups similar tasks, and generates stats.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, date
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from rebalance.ingest.calendar import get_daily_totals, ensure_calendar_schema
from rebalance.ingest.calendar_config import CalendarConfig, filter_events
from rebalance.ingest.db import get_connection


@dataclass
class ProjectGroup:
    """Group of similar event names with combined stats."""
    keyword: str
    count: int
    total_minutes: int
    events: list[str]  # Original event summaries
    
    @property
    def total_hours(self) -> float:
        return self.total_minutes / 60.0


def extract_keywords(text: str, top_n: int = 5) -> list[str]:
    """Extract top N most common words from event name."""
    # Remove common words and split
    words = re.findall(r'\b[a-z]+\b', text.lower())
    # Filter out very short words
    words = [w for w in words if len(w) > 2]
    
    counter = Counter(words)
    return [word for word, _ in counter.most_common(top_n)]


def group_similar_events(
    events: list[dict[str, Any]],
) -> dict[str, ProjectGroup]:
    """Group events by most common keywords (case-insensitive substring matching)."""
    groups: dict[str, ProjectGroup] = {}
    
    for event in events:
        summary = event.get("summary", "")
        start_str = event.get("start_time", "")
        end_str = event.get("end_time", "")
        
        # Calculate duration
        try:
            start_dt = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
            end_dt = datetime.fromisoformat(end_str.replace('Z', '+00:00')) if end_str else start_dt
            minutes = int((end_dt - start_dt).total_seconds() / 60)
        except Exception:
            minutes = 0
        
        # Extract top keywords
        keywords = extract_keywords(summary)
        
        # Group by first keyword (or use full summary if no keywords)
        group_key = keywords[0] if keywords else summary[:20]
        
        if group_key not in groups:
            groups[group_key] = ProjectGroup(
                keyword=group_key,
                count=0,
                total_minutes=0,
                events=[],
            )
        
        groups[group_key].count += 1
        groups[group_key].total_minutes += minutes
        groups[group_key].events.append(summary)
    
    return groups


def generate_daily_report(
    database_path: Path,
    target_date: date,
    config: CalendarConfig,
) -> str:
    """Generate markdown report for a single day."""
    conn = get_connection(database_path)
    ensure_calendar_schema(conn)
    
    # Get all events for this day
    date_str = target_date.isoformat()
    rows = conn.execute(
        """SELECT summary, start_time, end_time
           FROM calendar_events
           WHERE DATE(start_time) = ?
           ORDER BY start_time ASC""",
        (date_str,),
    ).fetchall()
    conn.close()
    
    events = [
        {
            "summary": row["summary"],
            "start_time": row["start_time"],
            "end_time": row["end_time"],
        }
        for row in rows
    ]
    
    # Filter excluded events
    filtered_events = filter_events(events, config.exclude_keywords)
    
    # Calculate totals
    total_minutes = sum(
        int((datetime.fromisoformat(e["end_time"].replace('Z', '+00:00')) -
             datetime.fromisoformat(e["start_time"].replace('Z', '+00:00'))
            ).total_seconds() / 60)
        for e in filtered_events
        if e.get("end_time")
    )
    
    # Group similar events
    groups = group_similar_events(filtered_events)
    sorted_groups = sorted(groups.items(), key=lambda x: x[1].total_minutes, reverse=True)
    
    # Build markdown
    day_name = target_date.strftime("%A")
    md = f"## {day_name}, {target_date.strftime('%B %d, %Y')}\n\n"
    
    # Daily summary
    hours = int(total_minutes / 60)
    mins = total_minutes % 60
    duration_str = f"{hours}h {mins}m" if hours > 0 else f"{mins}m"
    md += f"**Total:** {len(filtered_events)} events, {duration_str}\n\n"
    
    # Event list
    if filtered_events:
        md += "### Events (Excluded items removed)\n\n"
        for event in filtered_events:
            try:
                start_dt = datetime.fromisoformat(event["start_time"].replace('Z', '+00:00'))
                tz = ZoneInfo(config.timezone)
                local_time = start_dt.astimezone(tz)
                time_str = local_time.strftime("%I:%M %p").lstrip('0')
            except Exception:
                time_str = "—"
            md += f"- {time_str} — {event['summary']}\n"
        md += "\n"
    
    # Project aggregator
    if groups:
        md += "### Project Aggregator (Similar Tasks)\n\n"
        for group_key, group in sorted_groups:
            group_hours = int(group.total_minutes / 60)
            group_mins = group.total_minutes % 60
            group_duration = f"{group_hours}h {group_mins}m" if group_hours > 0 else f"{group_mins}m"
            md += f"- **{group_key.title()}**: {group.count} events, {group_duration}\n"
        md += "\n"
    
    return md
