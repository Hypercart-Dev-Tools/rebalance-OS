"""Pressure-relief valves for 3-Eyes (GH-195).

Circuit breakers stop a *broken* job. Relief valves stop a *healthy* system from
overwhelming the machine or an external API:

  * **Budgets** — daily and per-run caps on expensive calls (the classifier /
    any API), mirroring the ``health_issue_reporter`` ``--llm-daily-limit`` /
    ``--llm-max-per-run`` pattern. Counters reset at local midnight.
  * **Quiet hours** — a window (e.g. ``22:00-07:00``) during which jobs skip,
    so nothing fires while the operator sleeps.
  * **Backoff** — exponential delay hint after repeated failure.

State (daily counters) lives as JSON in the state dir, keyed by local date so a
new day starts fresh without a cron sweep.
"""

from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path
from typing import Any

from . import breakers, config


def _state_path() -> Path:
    return config.state_dir() / "budgets.json"


def _load() -> dict[str, Any]:
    try:
        return json.loads(_state_path().read_text())
    except (OSError, ValueError):
        return {}


def _today(now: _dt.datetime | None = None) -> str:
    return (now or _dt.datetime.now()).strftime("%Y-%m-%d")


def _prune_old_days(state: dict[str, Any], day: str) -> None:
    """Drop day-buckets older than ``day`` so the file cannot grow unbounded.

    Keys are ``YYYY-MM-DD`` date strings; any well-formed date strictly before
    today is stale. Non-date keys (defensive) are left untouched.
    """
    for key in list(state.keys()):
        try:
            _dt.date.fromisoformat(key)
        except ValueError:
            continue
        if key < day:
            state.pop(key, None)


class Budget:
    """Daily + per-run spend caps for one expenditure kind (e.g. ``llm``)."""

    def __init__(self, kind: str, daily_max: int | None, per_run_max: int | None) -> None:
        self.kind = kind
        self.daily_max = daily_max
        self.per_run_max = per_run_max
        self._run_spent = 0

    def _daily_spent(self, day: str) -> int:
        state = _load()
        return int(state.get(day, {}).get(self.kind, 0))

    def remaining_today(self, now: _dt.datetime | None = None) -> int | None:
        if self.daily_max is None:
            return None
        return max(0, self.daily_max - self._daily_spent(_today(now)))

    def can_spend(self, now: _dt.datetime | None = None) -> bool:
        if self.per_run_max is not None and self._run_spent >= self.per_run_max:
            return False
        remaining = self.remaining_today(now)
        return remaining is None or remaining > 0

    def spend(self, n: int = 1, now: _dt.datetime | None = None) -> None:
        """Record ``n`` units spent today (and this run), flock-guarded."""
        self._run_spent += n
        day = _today(now)
        with breakers._locked("budgets"):
            state = _load()
            bucket = state.setdefault(day, {})
            bucket[self.kind] = int(bucket.get(self.kind, 0)) + n
            _prune_old_days(state, day)
            breakers._atomic_write(_state_path(), state)

    def reserve(self, n: int = 1, now: _dt.datetime | None = None) -> bool:
        """Atomically check-and-spend under lock (GH-195 review B3/S6).

        Returns True and records the spend if within both caps, else False and
        records nothing. This is what the classify path must call BEFORE reaching
        the model, so the daily/per-run caps are actually enforced rather than
        merely declared.
        """
        if self.per_run_max is not None and self._run_spent >= self.per_run_max:
            return False
        day = _today(now)
        with breakers._locked("budgets"):
            state = _load()
            spent = int(state.get(day, {}).get(self.kind, 0))
            if self.daily_max is not None and spent + n > self.daily_max:
                return False
            bucket = state.setdefault(day, {})
            bucket[self.kind] = spent + n
            _prune_old_days(state, day)
            breakers._atomic_write(_state_path(), state)
        self._run_spent += n
        return True


def _parse_hhmm(text: str) -> int | None:
    text = text.strip()
    if ":" not in text:
        return None
    hh, _, mm = text.partition(":")
    try:
        return int(hh) * 60 + int(mm)
    except ValueError:
        return None


def in_quiet_hours(spec: str | None, now: _dt.datetime | None = None) -> bool:
    """True when ``now`` falls inside a ``HH:MM-HH:MM`` quiet window.

    A trailing timezone label (e.g. ``22:00-07:00 PT``) is accepted and ignored —
    the comparison is against local wall-clock, which is what launchd/cron fire on.
    Windows that wrap past midnight (start > end) are handled.
    """
    if not spec:
        return False
    body = spec.split()[0] if " " in spec else spec  # drop trailing "PT" etc.
    if "-" not in body:
        return False
    start_s, _, end_s = body.partition("-")
    start = _parse_hhmm(start_s)
    end = _parse_hhmm(end_s)
    if start is None or end is None:
        return False
    now = now or _dt.datetime.now()
    minute = now.hour * 60 + now.minute
    if start == end:
        return False
    if start < end:
        return start <= minute < end
    # wraps past midnight
    return minute >= start or minute < end


def backoff_seconds(consecutive_failures: int, base: int = 60, cap: int = 3600) -> int:
    """Exponential backoff hint: base * 2**(n-1), capped. 0 when no failures."""
    if consecutive_failures <= 0:
        return 0
    return min(cap, base * (2 ** (consecutive_failures - 1)))


def budget_for(job, kind: str = "llm") -> Budget:
    """Build a :class:`Budget` from a job's ``[relief]`` table."""
    relief = getattr(job, "relief", {}) or {}
    return Budget(
        kind,
        daily_max=relief.get("llm_daily_max"),
        per_run_max=relief.get("llm_per_run_max"),
    )
