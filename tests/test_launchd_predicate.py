"""Regression coverage for the launchd health predicate (GH-146, GH-160, GH-278).

`_check_launchd` must not flag a running or just-restarted daemon as broken.
It reads a stubbed `launchctl list` snapshot (`pid \t status \t label`), never
the real machine. The bug these tests pin: a `KeepAlive` daemon restarted via
`launchctl kickstart -k` shows a live PID with the *previous* instance's exit
`-15` (SIGTERM) and used to WARN despite being healthy and serving.

GH-160: a single snapshot cannot distinguish a one-off crash from a genuine
crash loop (a live PID is always live at poll time either way), so
`_check_launchd` persists recent crash-relaunch events across polls under
`log_dir`. The crash-loop tests below drive it across several polls with an
isolated `tmp_path`-backed `log_dir` so that history never leaks between
tests or real `doctor` runs (GH-278).
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from rebalance.doctor import NOTICE, OK, WARN, WARNING, _check_launchd


def _one(snapshot: str, log_dir: Path | None = None):
    checks = _check_launchd(snapshot, log_dir=log_dir)
    assert len(checks) == 1, f"expected exactly one check, got {checks}"
    return checks[0]


def test_running_daemon_with_sigterm_last_exit_is_ok(tmp_path) -> None:
    """The GH-146 case: live PID + last exit -15 (SIGTERM from kickstart -k)."""
    check = _one("41142\t-15\tcom.rebalance-os.pulse-server\n", log_dir=tmp_path / "logs")
    assert check.name == "launchd:pulse-server"
    assert check.status == OK
    assert check.detail == "running"
    assert check.severity == NOTICE


def test_negative_signal_without_live_pid_is_ok(tmp_path) -> None:
    """A negative (signal) status is a clean stop, not a crash — OK even idle.

    Uses a non-``daily-sync`` job: ``daily-sync`` has its own JSON-outcome check
    (GH-146 Root cause A) and does not go through this general predicate.
    """
    check = _one("-\t-15\tcom.rebalance-os.vault-sync\n", log_dir=tmp_path / "logs")
    assert check.status == OK
    assert check.detail == "idle, last run ok"


def test_running_daemon_with_positive_last_exit_is_ok(tmp_path) -> None:
    """A live PID means it is up now, regardless of the prior instance's code."""
    check = _one("50001\t1\tcom.rebalance-os.pulse-web-sync\n", log_dir=tmp_path / "logs")
    assert check.status == OK
    assert check.detail == "running"


def test_crashed_job_positive_exit_no_pid_still_warns(tmp_path) -> None:
    """The genuine failure: no live PID and a positive non-zero exit (non-daily-sync)."""
    check = _one("-\t7\tcom.rebalance-os.vault-sync\n", log_dir=tmp_path / "logs")
    assert check.status == WARN
    assert check.severity == WARNING
    assert check.detail == "last run exited with status 7"


def test_clean_states_are_ok(tmp_path) -> None:
    for snapshot, detail in (
        ("-\t0\tcom.rebalance-os.vault-sync\n", "idle, last run ok"),
        ("-\t-\tcom.rebalance-os.github-sync\n", "idle, last run ok"),
        ("60002\t0\tcom.rebalance-os.pulse-server\n", "running"),
    ):
        check = _one(snapshot, log_dir=tmp_path / "logs")
        assert check.status == OK, snapshot
        assert check.detail == detail, snapshot


def test_crash_looping_daemon_is_flagged_despite_live_pid(tmp_path) -> None:
    """GH-160: a KeepAlive job repeatedly crashing and being relaunched must
    eventually WARN even though every poll catches it mid-live-PID."""
    log_dir = tmp_path / "logs"
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    label = "com.rebalance-os.pulse-server"

    # Poll 1: first-ever observation of this label. A live PID next to a
    # positive last exit is indistinguishable from a one-off crash on its
    # own (this is exactly the GH-146-pinned case) — must stay OK.
    check1 = _check_launchd(f"1000\t1\t{label}\n", log_dir=log_dir, now=base)[0]
    assert check1.status == OK
    assert check1.detail == "running"

    # Poll 2: launchd respawned it under a new PID after another non-zero
    # exit. One crash-relaunch is now on record, but one alone is still not
    # a loop.
    check2 = _check_launchd(
        f"1050\t1\t{label}\n", log_dir=log_dir, now=base + timedelta(minutes=1)
    )[0]
    assert check2.status == OK

    # Poll 3: a second crash-relaunch inside the lookback window — this is a
    # genuine loop and must degrade despite the PID being live right now.
    check3 = _check_launchd(
        f"1103\t1\t{label}\n", log_dir=log_dir, now=base + timedelta(minutes=2)
    )[0]
    assert check3.status == WARN
    assert check3.severity == WARNING
    assert "crash-loop" in check3.detail.lower()


def test_repeated_sigterm_restarts_are_not_mistaken_for_a_crash_loop(tmp_path) -> None:
    """GH-146 must survive GH-160: repeated *clean* SIGTERM restarts (e.g. an
    operator running `kickstart -k` more than once) are still not a crash
    loop — only genuinely non-zero, non-signal exits ever count."""
    log_dir = tmp_path / "logs"
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    label = "com.rebalance-os.pulse-server"

    for minute, pid in enumerate((2000, 2050, 2103, 2140)):
        check = _check_launchd(
            f"{pid}\t-15\t{label}\n", log_dir=log_dir, now=base + timedelta(minutes=minute)
        )[0]
        assert check.status == OK, (pid, check)
        assert check.detail == "running"
