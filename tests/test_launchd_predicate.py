"""Regression coverage for the launchd health predicate (GH-146, GH-160).

`_check_launchd` must not flag a running or just-restarted daemon as broken,
but must detect a crash-looping KeepAlive job even when its current PID is live.
It reads a stubbed `launchctl list` snapshot (`pid \t status \t label`), never
the real machine. GH-146: a KeepAlive daemon restarted via `launchctl kickstart
-k` shows a live PID with exit -15 (SIGTERM) — must stay OK. GH-160: a live PID
with a positive non-zero exit is crash-looping — must WARN, not OK.
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
    """A negative (signal) status is a clean stop, not a crash — OK even idle.

    Uses a non-``daily-sync`` job: ``daily-sync`` has its own JSON-outcome check
    (GH-146 Root cause A) and does not go through this general predicate.
    """
    check = _one("-\t-15\tcom.rebalance-os.vault-sync\n")
    assert check.status == OK
    assert check.detail == "idle, last run ok"


def test_crash_looping_keepalive_warns() -> None:
    """GH-160 regression: live PID + positive exit = KeepAlive crash-loop; must WARN."""
    check = _one("50001\t1\tcom.rebalance-os.pulse-web-sync\n")
    assert check.status == WARN
    assert check.detail == "crash-looping: KeepAlive relaunched after exit 1"


def test_crashed_job_positive_exit_no_pid_still_warns() -> None:
    """The genuine failure: no live PID and a positive non-zero exit (non-daily-sync)."""
    check = _one("-\t7\tcom.rebalance-os.vault-sync\n")
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
