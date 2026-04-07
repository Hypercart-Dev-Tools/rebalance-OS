"""
Calendar configuration — per-user settings for event filtering, calendar selection, and timezone.

Config file: temp/calendar_config.json (gitignored, repo root)
Schema:
  {
    "calendar_id": "c_dih7iped3im5sescansv8uqab8@group.calendar.google.com",
    "exclude_keywords": ["Check Slack", "Lunch", "Start Day earlier", "Start to wind-down"],
    "timezone": "America/Los_Angeles"
  }
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent / "temp" / "calendar_config.json"

DEFAULT_CONFIG = {
    "calendar_id": "c_dih7iped3im5sescansv8uqab8@group.calendar.google.com",
    "exclude_keywords": [
        "Check Slack",
        "Lunch",
        "Start Day earlier",
        "Start to wind-down",
    ],
    "timezone": "America/Los_Angeles",
}


@dataclass
class CalendarConfig:
    """Validated calendar configuration."""
    calendar_id: str
    exclude_keywords: list[str]
    timezone: str

    @classmethod
    def load(cls, config_path: Path | None = None) -> CalendarConfig:
        """Load config from file, or return defaults if file doesn't exist."""
        path = config_path or DEFAULT_CONFIG_PATH
        
        if path.exists():
            with open(path, "r") as f:
                data = json.load(f)
        else:
            data = DEFAULT_CONFIG
        
        return cls(
            calendar_id=data.get("calendar_id", DEFAULT_CONFIG["calendar_id"]),
            exclude_keywords=data.get("exclude_keywords", DEFAULT_CONFIG["exclude_keywords"]),
            timezone=data.get("timezone", DEFAULT_CONFIG["timezone"]),
        )
    
    def save(self, config_path: Path | None = None) -> None:
        """Save config to file."""
        path = config_path or DEFAULT_CONFIG_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, "w") as f:
            json.dump(
                {
                    "calendar_id": self.calendar_id,
                    "exclude_keywords": self.exclude_keywords,
                    "timezone": self.timezone,
                },
                f,
                indent=2,
            )
        
        print(f"✓ Config saved to {path}")


def should_exclude_event(event_summary: str, exclude_keywords: list[str]) -> bool:
    """Check if event summary contains any exclude keywords (case-insensitive)."""
    summary_lower = event_summary.lower()
    for keyword in exclude_keywords:
        if keyword.lower() in summary_lower:
            return True
    return False


def filter_events(
    events: list[dict[str, Any]],
    exclude_keywords: list[str],
) -> list[dict[str, Any]]:
    """Filter out events with excluded keywords."""
    return [
        event for event in events
        if not should_exclude_event(event.get("summary", ""), exclude_keywords)
    ]
