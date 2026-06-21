"""
Calendar configuration — per-user settings for event filtering, calendar selection, and timezone.

Config file: temp/calendar_config.json (gitignored, repo root)
Schema:
  {
    "calendar_id": "primary",
    "team_calendars": [
      {"person": "matthew", "calendar_id": "matthew@group.calendar.google.com"}
    ],
    "exclude_titles": ["Check Slack", "Post Daily Timesheet"],
    "aggregator_skip_words": ["wrap", "setup", "test"],
    "timezone": "",
    "hours_format": "decimal",
    "projects": [
      {
        "name": "CreditRegistry",
        "aliases": ["CR", "Credit Registry", "CR CC"]
      }
    ]
  }

Field notes:
  - ``calendar_id``: legacy/compat field — effectively unused. The operator's
    own calendar is ALWAYS synced and stored as "primary" (Google's alias for
    the authenticated user's default calendar) by both the orchestrated refresh
    (index_ops, which hardcodes "primary") and ``calendar-sync`` with no
    override (which canonicalises the default to "primary"). Changing this
    field therefore has no effect on the operator sync. To sync a *different*
    calendar ad-hoc, pass ``calendar-sync --calendar-id <id>`` — those events
    are stored verbatim under that id, kept separate from your "primary" data.
  - ``team_calendars``: list of teammate calendars to ingest. Each entry must
    have ``person`` (short label used in the ``person`` DB column, e.g. "matthew")
    and ``calendar_id`` (the Google Calendar ID, e.g. a group calendar address).
    Teammate rows are stored with ``calendar_id != 'primary'`` and are NEVER
    exported to the pulse repo (P2 privacy default-deny).
  - ``timezone`` accepts any IANA name (e.g. "America/Los_Angeles"). If omitted
    or left as an empty string, the device's local timezone is used (resolved
    via REBALANCE_TZ env var, then /etc/localtime, then UTC fallback).
  - ``hours_format``: "decimal" = 1.75h  |  "hm" = 1h 45m

Legacy field "exclude_keywords" is accepted for backwards compatibility and
mapped to exclude_titles.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rebalance.tz_utils import local_tz

logger = logging.getLogger(__name__)

# __file__ = src/rebalance/ingest/calendar_config.py
# .parent (ingest) .parent (rebalance) .parent (src) .parent (repo root)
DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent.parent / "temp" / "calendar_config.json"
REVIEW_DECISIONS_PATH = Path(__file__).parent.parent.parent.parent / "temp" / "review_decisions.json"

# The operator's own calendar is always stored under this canonical id — the
# Google alias for the authenticated user's default calendar. index_ops and
# refresh_calendar_source normalise the operator's stored rows to it regardless
# of what ``calendar_id`` says in config, so every operator-scoped read MUST
# filter on this constant (not ``config.calendar_id``) for write/read to agree.
# It is also the reserved value a team_calendars entry may not use.
OPERATOR_CALENDAR_ID = "primary"

DEFAULT_CONFIG: dict[str, Any] = {
    "calendar_id": "primary",
    "team_calendars": [],
    "exclude_titles": [
        "Lunch",
        "Break",
        "Admin",
    ],
    "aggregator_skip_words": [],
    "timezone": "",  # empty → resolved to device local timezone at load time
    "projects": [],
    "hours_format": "decimal",
    "snap_gap_minutes": 0,  # 0 = gapless/accurate; any positive value loses time
}


@dataclass
class TeamCalendarEntry:
    """A single teammate's calendar to ingest alongside the operator's own."""
    person: str      # short label stored in the DB ``person`` column (e.g. "matthew")
    calendar_id: str # Google Calendar ID (e.g. "matthew@group.calendar.google.com")


@dataclass
class CalendarProject:
    """Canonical project label and optional calendar aliases."""
    name: str
    aliases: list[str]


@dataclass
class CalendarConfig:
    """Validated calendar configuration."""
    calendar_id: str
    exclude_titles: list[str]
    aggregator_skip_words: list[str]
    timezone: str
    projects: list[CalendarProject]
    hours_format: str  # "decimal" (default) or "hm"
    team_calendars: list[TeamCalendarEntry] = field(default_factory=list)
    # Minutes of gap to leave when snapping an overlapping event's edge.
    # MUST be 0 for accurate time tracking — any positive value discards that
    # many minutes of real time on every resolved overlap (see calendar_snap).
    snap_gap_minutes: int = 0

    @property
    def exclude_keywords(self) -> list[str]:
        """Backwards-compatible alias — returns exclude_titles."""
        return self.exclude_titles

    @staticmethod
    def _load_team_calendars(raw: Any) -> list[TeamCalendarEntry]:
        if not isinstance(raw, list):
            return []
        entries: list[TeamCalendarEntry] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            person = str(item.get("person", "")).strip()
            cal_id = str(item.get("calendar_id", "")).strip()
            if not (person and cal_id):
                continue
            if cal_id.casefold() == OPERATOR_CALENDAR_ID:
                # 'primary' is reserved for the operator's own calendar. A team
                # entry stored under it would be exported off-machine to the
                # pulse repo (export filters calendar_id='primary'), leaking
                # teammate data — the exact P2 privacy invariant we must hold.
                # Drop the entry loudly rather than mislabel teammate rows.
                logger.warning(
                    "ignoring team_calendars entry for person=%r: calendar_id "
                    "%r is reserved for the operator's own calendar and would "
                    "leak teammate events to the pulse repo",
                    person, cal_id,
                )
                continue
            entries.append(TeamCalendarEntry(person=person, calendar_id=cal_id))
        return entries

    @staticmethod
    def _load_projects(raw_projects: Any) -> list[CalendarProject]:
        """Normalize project definitions from config JSON."""
        if not isinstance(raw_projects, list):
            return []

        projects: list[CalendarProject] = []
        for item in raw_projects:
            if not isinstance(item, dict):
                continue

            name = str(item.get("name", "")).strip()
            if not name:
                continue

            aliases_raw = item.get("aliases", [])
            aliases = [
                str(alias).strip()
                for alias in aliases_raw
                if str(alias).strip()
            ] if isinstance(aliases_raw, list) else []

            projects.append(CalendarProject(name=name, aliases=aliases))

        return projects

    @classmethod
    def load(cls, config_path: Path | None = None) -> CalendarConfig:
        """Load config from file, or return defaults if file doesn't exist.

        Backwards compatibility: if the file uses ``exclude_keywords`` (legacy)
        instead of ``exclude_titles``, the value is migrated automatically.
        """
        path = config_path or DEFAULT_CONFIG_PATH

        if path.exists():
            with open(path, "r") as f:
                data = json.load(f)
        else:
            data = dict(DEFAULT_CONFIG)

        hours_fmt = data.get("hours_format", DEFAULT_CONFIG["hours_format"])
        if hours_fmt not in ("decimal", "hm"):
            hours_fmt = "decimal"

        # Legacy migration: exclude_keywords → exclude_titles
        if "exclude_titles" in data:
            exclude_titles = data["exclude_titles"]
        elif "exclude_keywords" in data:
            exclude_titles = data["exclude_keywords"]
        else:
            exclude_titles = DEFAULT_CONFIG["exclude_titles"]

        aggregator_skip_words = data.get(
            "aggregator_skip_words",
            DEFAULT_CONFIG["aggregator_skip_words"],
        )

        return cls(
            calendar_id=data.get("calendar_id", DEFAULT_CONFIG["calendar_id"]),
            team_calendars=cls._load_team_calendars(data.get("team_calendars", [])),
            exclude_titles=exclude_titles,
            aggregator_skip_words=aggregator_skip_words,
            timezone=data.get("timezone") or local_tz().key,
            projects=cls._load_projects(data.get("projects", DEFAULT_CONFIG["projects"])),
            hours_format=hours_fmt,
            snap_gap_minutes=max(0, int(data.get("snap_gap_minutes", 0) or 0)),
        )

    def save(self, config_path: Path | None = None) -> None:
        """Save config to file."""
        path = config_path or DEFAULT_CONFIG_PATH
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w") as f:
            json.dump(
                {
                    "calendar_id": self.calendar_id,
                    "team_calendars": [
                        {"person": tc.person, "calendar_id": tc.calendar_id}
                        for tc in self.team_calendars
                    ],
                    "exclude_titles": self.exclude_titles,
                    "aggregator_skip_words": self.aggregator_skip_words,
                    "timezone": self.timezone,
                    "hours_format": self.hours_format,
                    "snap_gap_minutes": self.snap_gap_minutes,
                    "projects": [
                        {
                            "name": project.name,
                            "aliases": project.aliases,
                        }
                        for project in self.projects
                    ],
                },
                f,
                indent=2,
            )

        print(f"✓ Config saved to {path}")


# ── Signal weights (P2 v0.5 "what next" ranking levers) ──────────────────────
#
# Seeded from the Phase-0 spike. These are the knobs the "what should we work on
# next" synthesis uses to weight signals per-person and per-source, discount
# redundant/vague signals, and gate which teammates have enough calendar history
# for their events to add anything (the per-person additivity check). They live
# alongside the calendar config because the per-person weights and the team
# additivity threshold are keyed off the same roster.


@dataclass
class SignalWeights:
    """Per-person / per-source signal weights and the additivity gate.

    Defaults are the Phase-0 seeds — documented inline so a later re-tune can
    see what each number was reaching for, not just its value.
    """

    # Per-person trust. Matt's calendar is rich (~239 events) so he carries full
    # weight; Jose/Jinhui are sparse (3 / 7 events) so their signal is halved
    # until they accumulate history.
    per_person: dict[str, float] = field(
        default_factory=lambda: {
            "matthew": 1.0,  # Phase-0 seed: rich history, full trust
            "jose": 0.5,     # Phase-0 seed: sparse, halved
            "jinhui": 0.5,   # Phase-0 seed: sparse, halved
        }
    )

    # Per-source trust. Structured/authoritative sources (calendar, github,
    # sleuth) carry full weight; the vault is noisier (~0.7) and email sits in
    # between (~0.8).
    per_source: dict[str, float] = field(
        default_factory=lambda: {
            "calendar": 1.0,  # Phase-0 seed
            "github": 1.0,    # Phase-0 seed
            "sleuth": 1.0,    # Phase-0 seed
            "vault": 0.7,     # Phase-0 seed: noisier free-text
            "email": 0.8,     # Phase-0 seed
        }
    )

    # Multiplier applied to a signal that merely restates one already counted.
    redundancy_penalty: float = 0.5  # Phase-0 seed

    # Multiplier applied to a vague / low-specificity signal.
    vagueness_discount: float = 0.5  # Phase-0 seed

    # The one load-bearing lever — correct for the operator over-weighting their
    # own (owner) signal. Default ON.
    owner_bias_correction: bool = True

    # How sharply a "drop" (a signal disappearing) moves the ranking.
    drop_sensitivity: float = 0.5  # Phase-0 seed

    # Per-person additivity threshold: a teammate needs at least this many
    # calendar events before their events add anything to the synthesis. Matt
    # (~239) passes; Jose (3) / Jinhui (7) fail until they accrue history.
    min_team_events: int = 12  # Phase-0 seed


def load_signal_weights(config_path: Path | None = None) -> SignalWeights:
    """Return seeded :class:`SignalWeights`, overlaying a ``signal_weights``
    block from ``temp/calendar_config.json`` if one is present.

    Mirrors how ``team_calendars`` is loaded: absent file or absent/invalid
    block → seeded defaults. Never raises — a malformed override falls back to
    the seed for that field rather than failing the load.
    """
    weights = SignalWeights()

    path = config_path or DEFAULT_CONFIG_PATH
    if not path.exists():
        return weights

    try:
        with open(path, "r") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return weights

    block = data.get("signal_weights")
    if not isinstance(block, dict):
        return weights

    def _floats(raw: Any, seed: dict[str, float]) -> dict[str, float]:
        if not isinstance(raw, dict):
            return seed
        out = dict(seed)
        for key, value in raw.items():
            try:
                out[str(key)] = float(value)
            except (TypeError, ValueError):
                continue
        return out

    weights.per_person = _floats(block.get("per_person"), weights.per_person)
    weights.per_source = _floats(block.get("per_source"), weights.per_source)

    for fld in (
        "redundancy_penalty",
        "vagueness_discount",
        "drop_sensitivity",
    ):
        if fld in block:
            try:
                setattr(weights, fld, float(block[fld]))
            except (TypeError, ValueError):
                pass

    if "owner_bias_correction" in block:
        weights.owner_bias_correction = bool(block["owner_bias_correction"])

    if "min_team_events" in block:
        try:
            weights.min_team_events = int(block["min_team_events"])
        except (TypeError, ValueError):
            pass

    return weights


def team_persons_passing_additivity(
    event_counts: dict[str, int],
    min_events: int,
) -> list[str]:
    """Return persons whose event count meets the additivity threshold.

    The per-person mini additivity check: a teammate's events only add signal
    once they have at least *min_events* of history. The caller computes the
    counts; this is a pure filter that preserves the roster order of the input
    mapping.
    """
    return [
        person
        for person, count in event_counts.items()
        if count >= min_events
    ]


def should_exclude_event(event_summary: str, exclude_titles: list[str]) -> bool:
    """Check if event summary matches any exclude title (case-insensitive).

    Uses case-insensitive full-title matching, not substring matching, so
    "wrap" in exclude_titles won't catch "Wrap up Countdown Timer".
    """
    summary_lower = event_summary.strip().lower()
    for title in exclude_titles:
        if title.strip().lower() == summary_lower:
            return True
    return False


def filter_events(
    events: list[dict[str, Any]],
    exclude_titles: list[str],
) -> list[dict[str, Any]]:
    """Filter out events whose title exactly matches an exclude entry."""
    return [
        event for event in events
        if not should_exclude_event(event.get("summary", ""), exclude_titles)
    ]


# ── Review decisions persistence ─────────────────────────────────────────────

VALID_DECISION_PREFIXES = ("include", "exclude", "project:")


class InvalidDecisionError(ValueError):
    """Raised when a review decision string doesn't match an accepted format."""


def load_review_decisions(path: Path | None = None) -> dict[str, str]:
    """Load prior review decisions from temp/review_decisions.json.

    Returns {normalized_summary: decision} where decision is one of:
    "include", "exclude", or "project:<name>".
    """
    p = path or REVIEW_DECISIONS_PATH
    if not p.exists():
        return {}
    with open(p, "r") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def save_review_decision(summary: str, decision: str, path: Path | None = None) -> None:
    """Validate and persist a review decision.

    Raises :class:`InvalidDecisionError` if *decision* is not one of
    ``"include"``, ``"exclude"``, or ``"project:<Name>"``.
    """
    if not any(decision.startswith(p) for p in VALID_DECISION_PREFIXES):
        raise InvalidDecisionError(
            f"Invalid decision '{decision}'. Must be 'include', 'exclude', or 'project:<Name>'."
        )
    p = path or REVIEW_DECISIONS_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    decisions = load_review_decisions(p)
    decisions[summary.strip().lower()] = decision
    with open(p, "w") as f:
        json.dump(decisions, f, indent=2)
