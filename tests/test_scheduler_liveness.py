"""Regression coverage for scheduler-policy liveness warnings.

Unlike ``test_scheduler_policy``, these tests stub the device-local
``launchctl list`` snapshot.  They deliberately never inspect the machine's
real LaunchAgents.
"""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from rebalance.doctor import WARN, _check_launchd, _check_scheduler_liveness


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
                "Policy notes.",
            ]
        ),
        encoding="utf-8",
    )
    return policy


def test_policy_row_absent_from_stubbed_launchctl_warns_with_installer() -> None:
    """A new policy row is checked without adding it to doctor code."""
    with TemporaryDirectory() as tmp:
        policy = _write_policy(Path(tmp), ["daily-sync", "future-job"])
        with patch(
            "rebalance.doctor._launchctl_list",
            return_value="-\t0\tcom.rebalance-os.daily-sync\n",
        ):
            checks = _check_scheduler_liveness(policy)

    missing = {check.name: check for check in checks}["scheduler:future-job"]
    assert missing.status == WARN
    assert missing.detail == "scheduled job is not loaded on this device"
    assert "scripts/install_future_job_scheduler.sh" in missing.hint
    assert "scheduler:daily-sync" not in {check.name for check in checks}


def test_not_loaded_warning_is_distinct_from_loaded_job_failure() -> None:
    """A registered job with a bad exit code is not reported as missing."""
    launchctl_snapshot = "-\t7\tcom.rebalance-os.daily-sync\n"
    with TemporaryDirectory() as tmp:
        policy = _write_policy(Path(tmp), ["daily-sync"])
        policy_checks = _check_scheduler_liveness(policy, launchctl_snapshot)

    launchd_checks = _check_launchd(launchctl_snapshot)
    assert policy_checks == []
    assert len(launchd_checks) == 1
    assert launchd_checks[0].name == "launchd:daily-sync"
    assert launchd_checks[0].status == WARN
    # GH-146 P2: with no recent structured run to corroborate it, a launchctl exit code is
    # reported as stale/unknown rather than asserted as a current failure. The exit code must
    # still appear in the detail — this test's subject is that a *loaded* failing job surfaces
    # as launchd:<job> and not as a missing-scheduler warning, which the assertions above cover.
    assert "7" in launchd_checks[0].detail
