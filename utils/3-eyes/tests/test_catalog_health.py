"""Catalog generation + fleet health (GH-195)."""

from __future__ import annotations

import pytest

from three_eyes import catalog, health, launchd

NOTES = {
    "system_order": ["s1"],
    "system_names": {"s1": "Sys One"},
    "agent": {
        "com.x.managed": {"system": "s1", "status": "managed", "desc": "the managed one"},
        "com.x.adopt": {"system": "s1", "status": "to-adopt", "desc": "adopt me", "priority": 1},
    },
}

OBSERVE = [
    {"label": "com.x.managed", "schedule": "every 1h"},
    {"label": "com.x.adopt", "schedule": "every 2m"},
    {"label": "com.google.foo", "schedule": "every 1h"},   # vendor → ignored
    {"label": "com.x.NEW", "schedule": "daily 09:00"},      # unclassified
]


@pytest.fixture
def fixture_env(monkeypatch, tmp_path):
    monkeypatch.setattr(catalog, "load_notes", lambda: NOTES)
    monkeypatch.setattr(launchd, "observe_existing", lambda: list(OBSERVE))
    monkeypatch.setattr(catalog, "CATALOG", tmp_path / "CATALOG.md")


def test_drift_detects_new_and_ignores_vendor(fixture_env):
    d = catalog.drift()
    assert d["new"] == ["com.x.NEW"]          # unclassified, non-vendor
    assert "com.google.foo" not in d["new"]   # vendor auto-ignored
    assert d["removed"] == []                 # both notes agents present


def test_render_groups_and_flags(fixture_env):
    md = catalog.render()
    assert "Sys One" in md
    assert "com.x.managed" in md and "🟢 managed" in md
    assert "Unclassified" in md and "com.x.NEW" in md      # triage section
    assert "Suggested next adoptions" in md and "com.x.adopt" in md


def test_retired_cactus_agents_are_not_adoption_targets(monkeypatch):
    """Retired incumbents remain curated history, never future adoption work."""
    notes = catalog.load_notes()
    retired = [
        "com.neochro.sentinel-daemon",
        "com.neochro.sentinel-daemon.sleuth-app",
        "com.neochro.needle-router",
        "com.neochro.cactus-serve",
    ]
    monkeypatch.setattr(launchd, "observe_existing",
                        lambda: [{"label": label, "schedule": "retired"} for label in retired])

    rendered = catalog.render(notes)
    for label in retired:
        note = notes["agent"][label]
        assert note["status"] == "observe"
        assert "Retired 2026-07-27" in note["desc"]
        row = next(line for line in rendered.splitlines() if f"`{label}`" in line)
        assert "🎯 to-adopt" not in row
    assert "Suggested next adoptions" not in rendered


def test_check_true_after_write_then_false_on_drift(fixture_env, monkeypatch):
    catalog.write()
    assert catalog.check() is True
    # A new agent appears on the machine -> render changes -> stale.
    monkeypatch.setattr(launchd, "observe_existing",
                        lambda: OBSERVE + [{"label": "com.x.LATER", "schedule": "every 5m"}])
    assert catalog.check() is False


def test_health_scan_counts_and_grades(fixture_env, monkeypatch):
    # (pid, last-exit): "-" pid means not currently running.
    monkeypatch.setattr(health, "_launchctl_list",
                        lambda: {"com.x.managed": ("-", "0"), "com.x.adopt": ("-", "78")})
    r = health.scan()
    assert r["ok"] == 1 and r["failing"] == 1 and r["not_loaded"] == 0
    by = {row["label"]: row for row in r["rows"]}
    assert by["com.x.managed"]["health"] == "ok"
    assert by["com.x.managed"]["breaker"] == "closed"       # managed → breaker overlay
    assert "FAIL" in by["com.x.adopt"]["health"] and "78" in by["com.x.adopt"]["health"]
    assert r["unclassified"] == ["com.x.NEW"]


def test_health_not_loaded(fixture_env, monkeypatch):
    monkeypatch.setattr(health, "_launchctl_list", lambda: {})   # nothing loaded
    r = health.scan()
    assert r["not_loaded"] == 2 and r["ok"] == 0 and r["failing"] == 0
    assert r["launchctl_available"] is True      # empty ≠ unreadable


def test_running_pid_beats_prior_sigterm_exit(fixture_env, monkeypatch):
    """A KeepAlive server restarted with SIGTERM shows PID + exit -15 — it is ALIVE.

    Regression for the GH-146 bug class: the exit-status column describes the
    *previous* instance, so reading it alone calls a running server failing.
    """
    monkeypatch.setattr(health, "_launchctl_list",
                        lambda: {"com.x.managed": ("35845", "-15"), "com.x.adopt": ("-", "0")})
    r = health.scan()
    assert r["failing"] == 0 and r["ok"] == 2
    by = {row["label"]: row for row in r["rows"]}
    assert by["com.x.managed"]["health"] == "ok"
    assert by["com.x.managed"]["running"] is True
    assert by["com.x.managed"]["last_exit"] == "-15"     # retained, but not a verdict
    assert "prior exit -15" in health.format_report(r)   # surfaced, not hidden


def test_unreachable_launchctl_reports_unknown_not_healthy(fixture_env, monkeypatch):
    """A probe that could not run must not return a confident answer."""
    def boom():
        raise health.LaunchctlUnavailable("launchctl list exited 1: no output")
    monkeypatch.setattr(health, "_launchctl_list", boom)
    r = health.scan()
    assert r["launchctl_available"] is False
    assert r["unknown"] == 2
    assert r["ok"] == 0 and r["failing"] == 0 and r["not_loaded"] == 0   # no false verdict
    assert all(row["health"] == "unknown" for row in r["rows"])
    text = health.format_report(r)
    assert "UNKNOWN" in text and "NOT a clean bill of health" in text


def test_launchctl_nonzero_exit_raises_rather_than_returning_empty(monkeypatch):
    """rc!=0 with empty stdout (the sandboxed case) must raise, not read as 'nothing loaded'."""
    class FakeProc:
        returncode, stdout, stderr = 1, "", ""
    monkeypatch.setattr(health.subprocess, "run", lambda *a, **k: FakeProc())
    with pytest.raises(health.LaunchctlUnavailable):
        health._launchctl_list()


def test_launchctl_parses_pid_and_status_columns(monkeypatch):
    class FakeProc:
        returncode = 0
        stdout = "PID\tStatus\tLabel\n35845\t-15\tcom.x.server\n-\t0\tcom.x.batch\n"
        stderr = ""
    monkeypatch.setattr(health.subprocess, "run", lambda *a, **k: FakeProc())
    assert health._launchctl_list() == {"com.x.server": ("35845", "-15"),
                                        "com.x.batch": ("-", "0")}


def test_compact_schedule_formatting():
    assert launchd._fmt_interval(3600) == "every 1h"
    assert launchd._fmt_interval(1800) == "every 30m"
    assert launchd._fmt_interval(120) == "every 2m"
    assert launchd._fmt_calendar({"Hour": 6, "Minute": 30}) == "daily 06:30"
    assert launchd._fmt_calendar([{"Minute": 10}]) == "hourly :10"
    assert launchd._fmt_calendar([{"Hour": 6}, {"Hour": 7}, {"Hour": 8}]) == "3×/day"
