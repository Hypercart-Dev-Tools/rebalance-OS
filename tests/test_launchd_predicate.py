"""Regression coverage for the launchd health predicate (GH-146).

`_check_launchd` must not flag a running or just-restarted daemon as broken.
It reads a stubbed `launchctl list` snapshot (`pid \t status \t label`), never
the real machine. The bug these tests pin: a `KeepAlive` daemon restarted via
`launchctl kickstart -k` shows a live PID with the *previous* instance's exit
`-15` (SIGTERM) and used to WARN despite being healthy and serving.
"""

from rebalance.doctor import NOTICE, OK, WARN, WARNING, _check_launchd


def _one(snapshot: str):
    checks = _check_launchd(snapshot)
    assert len(checks) == 1, f"expected exactly one check, got {checks}"
    return checks[0]


def test_running_daemon_with_sigterm_last_exit_is_ok() -> None:
    """The GH-146 case: live PID + last exit -15 (SIGTERM from kickstart -k)."""
    check = _one("41142\t-15\tcom.rebalance-os.pulse-server\n")
    assert check.name == "launchd:pulse-server"
    assert check.status == OK
    assert check.detail == "running"
    assert check.severity == NOTICE


def test_negative_signal_without_live_pid_is_ok() -> None:
    """A negative (signal) status is a clean stop, not a crash — OK even idle."""
    check = _one("-\t-15\tcom.rebalance-os.daily-sync\n")
    assert check.status == OK
    assert check.detail == "idle, last run ok"


def test_running_daemon_with_positive_last_exit_is_ok() -> None:
    """A live PID means it is up now, regardless of the prior instance's code."""
    check = _one("50001\t1\tcom.rebalance-os.pulse-web-sync\n")
    assert check.status == OK
    assert check.detail == "running"


def test_crashed_job_positive_exit_no_pid_still_warns() -> None:
    """The genuine failure: no live PID and a positive non-zero exit."""
    check = _one("-\t7\tcom.rebalance-os.daily-sync\n")
    assert check.status == WARN
    assert check.severity == WARNING
    assert check.detail == "last run exited with status 7"


def test_clean_states_are_ok() -> None:
    for snapshot, detail in (
        ("-\t0\tcom.rebalance-os.vault-sync\n", "idle, last run ok"),
        ("-\t-\tcom.rebalance-os.github-sync\n", "idle, last run ok"),
        ("60002\t0\tcom.rebalance-os.pulse-server\n", "running"),
    ):
        check = _one(snapshot)
        assert check.status == OK, snapshot
        assert check.detail == detail, snapshot
