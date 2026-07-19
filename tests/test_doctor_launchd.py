"""Regression coverage for launchd health based on daily-sync's run JSON."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from rebalance.doctor import OK, WARN, _check_launchd


NOW = datetime(2026, 7, 18, 12, tzinfo=timezone.utc)
DAILY_SYNC_STATUS_ONE = "-\t1\tcom.rebalance-os.daily-sync\n"


def _write_daily_result(
    log_dir: Path, outcome: str | None, *, age: timedelta = timedelta(minutes=10)
) -> Path:
    log_dir.mkdir()
    log_path = log_dir / "daily_sync_2026-07-18.log"
    payload = {"results": []}
    if outcome is not None:
        payload["sync_outcome"] = outcome
    log_path.write_text("daily wrapper output\n" + json.dumps(payload), encoding="utf-8")
    modified = (NOW - age).timestamp()
    os.utime(log_path, (modified, modified))
    return log_path


def _daily_check(tmp_path: Path, outcome: str | None, *, age: timedelta = timedelta(minutes=10)):
    log_dir = tmp_path / "logs"
    _write_daily_result(log_dir, outcome, age=age)
    return _check_launchd(DAILY_SYNC_STATUS_ONE, log_dir=log_dir, now=NOW)[0]


def test_recent_success_supersedes_sticky_launchctl_failure(tmp_path: Path) -> None:
    check = _daily_check(tmp_path, "complete")

    assert check.status == OK  # Regression: a recent success must clear status 1.
    assert "completed" in check.detail
    assert "stale" in check.detail


def test_recent_degraded_run_is_distinct_from_failure(tmp_path: Path) -> None:
    check = _daily_check(tmp_path, "degraded")

    assert check.status == OK
    assert "degraded" in check.detail
    assert "failed" not in check.detail


def test_recent_fatal_run_warns(tmp_path: Path) -> None:
    check = _daily_check(tmp_path, "fatal")

    assert check.status == WARN
    assert "failed fatally" in check.detail


def test_missing_recent_run_is_stale_unknown_not_current_failure(tmp_path: Path) -> None:
    check = _daily_check(tmp_path, "complete", age=timedelta(hours=49))

    assert check.status == WARN
    assert "stale/unknown" in check.detail
    assert "last run exited" not in check.detail


def test_job_without_structured_result_keeps_launchctl_behavior(tmp_path: Path) -> None:
    checks = _check_launchd(
        "-\t1\tcom.rebalance-os.github-sync\n", log_dir=tmp_path / "logs", now=NOW
    )

    assert checks[0].status == WARN
    assert checks[0].detail == "last run exited with status 1"


def test_unrecognised_daily_log_keeps_legacy_launchctl_behavior(tmp_path: Path) -> None:
    check = _daily_check(tmp_path, None)

    assert check.status == WARN
    assert check.detail == "last run exited with status 1"
