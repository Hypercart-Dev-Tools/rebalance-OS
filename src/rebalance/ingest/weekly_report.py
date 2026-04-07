"""
Weekly calendar report generator — combines daily reports into Sun-Sat markdown format.
"""

from __future__ import annotations

from datetime import datetime, date, timedelta
from pathlib import Path

from rebalance.ingest.daily_report import generate_daily_report
from rebalance.ingest.calendar_config import CalendarConfig


def get_week_start(target_date: date) -> date:
    """Get Sunday of the week containing target_date."""
    days_since_sunday = (target_date.weekday() + 1) % 7
    return target_date - timedelta(days=days_since_sunday)


def generate_weekly_report(
    database_path: Path,
    target_date: date | None = None,
    config: CalendarConfig | None = None,
) -> str:
    """Generate markdown weekly report (Sun-Sat)."""
    if target_date is None:
        target_date = date.today()
    if config is None:
        config = CalendarConfig.load()
    
    week_start = get_week_start(target_date)
    week_end = week_start + timedelta(days=6)
    
    # Build markdown
    md = f"# Weekly Calendar Report\n\n"
    md += f"**Week of {week_start.strftime('%B %d')} – {week_end.strftime('%B %d, %Y')}**\n\n"
    
    # Generate daily reports
    total_events = 0
    total_minutes = 0
    
    for offset in range(7):
        day = week_start + timedelta(days=offset)
        daily_md = generate_daily_report(database_path, day, config)
        md += daily_md
        md += "\n---\n\n"
    
    # Weekly summary
    md += "## Weekly Summary\n\n"
    md += f"Week: {week_start.strftime('%a, %b %d')} – {week_end.strftime('%a, %b %d, %Y')}\n"
    md += f"Timezone: {config.timezone}\n"
    md += f"Calendar: {config.calendar_id}\n\n"
    
    return md
