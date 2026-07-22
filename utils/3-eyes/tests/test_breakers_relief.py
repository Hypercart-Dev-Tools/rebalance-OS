"""Circuit breakers + pressure-relief valves (GH-195)."""

from __future__ import annotations

import datetime as dt

from three_eyes import breakers, relief


def test_failure_breaker_trips_after_n_consecutive():
    b = breakers.FailureBreaker()
    assert b.is_open("job") is False
    assert b.record("job", ok=False, trip_after=3) is False   # 1
    assert b.record("job", ok=False, trip_after=3) is False   # 2
    assert b.record("job", ok=False, trip_after=3) is True    # 3 -> OPENS
    assert b.is_open("job") is True


def test_success_resets_the_counter():
    b = breakers.FailureBreaker()
    b.record("job", ok=False, trip_after=3)
    b.record("job", ok=False, trip_after=3)
    b.record("job", ok=True, trip_after=3)     # reset
    assert b.record("job", ok=False, trip_after=3) is False   # count restarted at 1
    assert b.is_open("job") is False


def test_trip_after_zero_never_trips():
    b = breakers.FailureBreaker()
    for _ in range(10):
        assert b.record("job", ok=False, trip_after=0) is False
    assert b.is_open("job") is False


def test_manual_pause_and_resume():
    b = breakers.FailureBreaker()
    b.quarantine("job", reason="paused")
    assert b.is_open("job") is True
    # A fresh instance reads the same on-disk state (persistence).
    assert breakers.FailureBreaker().is_open("job") is True
    b.reset("job")
    assert breakers.FailureBreaker().is_open("job") is False


def test_breaker_state_survives_new_instance():
    breakers.FailureBreaker().record("job", ok=False, trip_after=2)
    assert breakers.FailureBreaker().record("job", ok=False, trip_after=2) is True


def test_quiet_hours_same_day_window():
    assert relief.in_quiet_hours("09:00-17:00", dt.datetime(2026, 7, 22, 12, 0)) is True
    assert relief.in_quiet_hours("09:00-17:00", dt.datetime(2026, 7, 22, 8, 0)) is False


def test_quiet_hours_wraps_past_midnight():
    spec = "22:00-07:00 PT"   # trailing tz label tolerated
    assert relief.in_quiet_hours(spec, dt.datetime(2026, 7, 22, 23, 30)) is True
    assert relief.in_quiet_hours(spec, dt.datetime(2026, 7, 22, 3, 0)) is True
    assert relief.in_quiet_hours(spec, dt.datetime(2026, 7, 22, 12, 0)) is False


def test_quiet_hours_none_or_bad_spec():
    assert relief.in_quiet_hours(None) is False
    assert relief.in_quiet_hours("not-a-window") is False


def test_budget_per_run_cap():
    b = relief.Budget("llm", daily_max=100, per_run_max=2)
    assert b.can_spend() is True
    b.spend()
    b.spend()
    assert b.can_spend() is False   # hit per-run cap


def test_budget_daily_cap_persists():
    b1 = relief.Budget("llm", daily_max=2, per_run_max=None)
    b1.spend()
    b1.spend()
    # A new run this same day sees the daily total is exhausted.
    b2 = relief.Budget("llm", daily_max=2, per_run_max=None)
    assert b2.can_spend() is False


def test_backoff_is_exponential_and_capped():
    assert relief.backoff_seconds(0) == 0
    assert relief.backoff_seconds(1, base=60) == 60
    assert relief.backoff_seconds(2, base=60) == 120
    assert relief.backoff_seconds(3, base=60) == 240
    assert relief.backoff_seconds(99, base=60, cap=3600) == 3600
