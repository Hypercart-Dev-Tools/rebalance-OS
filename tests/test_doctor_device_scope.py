"""Regression coverage for device-owned doctor checks."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from rebalance.doctor import (
    OK,
    WARN,
    _check_pulse_collectors,
    _check_scheduler_liveness,
)
from rebalance.ingest.pulse_health import CollectorHealth


def _health(device_id: str, *, age_hours: float, state: str = "STALE") -> CollectorHealth:
    health = CollectorHealth(
        device_id=device_id,
        device_name=device_id,
        last_scan_utc=None,
    )
    health.age_hours = age_hours
    health.state = state
    return health


def _write_policy(directory: Path, jobs: list[str]) -> Path:
    rows = "\n".join(
        f"| `{job}` | hourly | `scripts/{job}.sh` | work | — | output |"
        for job in jobs
    )
    policy = directory / "SCHEDULER.md"
    policy.write_text(
        "\n".join(
            [
                "# Scheduler Policy",
                "",
                "| Job (label suffix) | Cadence | Wrapper | Work | Prerequisites | Outputs |",
                "|---|---|---|---|---|---|",
                rows,
                "",
            ]
        ),
        encoding="utf-8",
    )
    return policy


def test_foreign_pulse_collector_is_informational_not_a_warning() -> None:
    health = _health("noels-mbp-16-m1-pro", age_hours=48, state="ALERT")
    with patch("rebalance.ingest.pulse_health.read_collector_health", return_value=[health]):
        checks = _check_pulse_collectors(current_device_id="noels-mac-studio")

    assert checks[0].status == OK  # the foreign-device assertion
    assert "not applicable" in checks[0].detail


def test_stale_collector_still_warns_on_its_own_device() -> None:
    health = _health("noels-mbp-16-m1-pro", age_hours=25, state="ALERT")
    with patch("rebalance.ingest.pulse_health.read_collector_health", return_value=[health]):
        checks = _check_pulse_collectors(current_device_id="noels-mbp-16-m1-pro")

    assert checks[0].status == WARN


def test_intermittent_laptop_window_differs_from_always_on_collector() -> None:
    laptop = _health("noels-macbook-pro-14", age_hours=7)
    workstation = _health("noels-mac-studio", age_hours=7)
    with patch(
        "rebalance.ingest.pulse_health.read_collector_health",
        return_value=[laptop, workstation],
    ):
        laptop_check = _check_pulse_collectors(current_device_id="noels-macbook-pro-14")[0]
        workstation_check = _check_pulse_collectors(current_device_id="noels-mac-studio")[1]

    assert laptop_check.status == OK
    assert "intermittent-device window 24h" in laptop_check.detail
    assert workstation_check.status == WARN


def test_unscoped_scheduler_job_keeps_existing_missing_job_warning() -> None:
    with TemporaryDirectory() as tmp:
        policy = _write_policy(Path(tmp), ["future-job"])
        checks = _check_scheduler_liveness(
            policy,
            "",
            current_device_id="noels-mac-studio",
        )

    assert checks[0].status == WARN
