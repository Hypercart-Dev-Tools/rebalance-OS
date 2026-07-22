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


def test_check_true_after_write_then_false_on_drift(fixture_env, monkeypatch):
    catalog.write()
    assert catalog.check() is True
    # A new agent appears on the machine -> render changes -> stale.
    monkeypatch.setattr(launchd, "observe_existing",
                        lambda: OBSERVE + [{"label": "com.x.LATER", "schedule": "every 5m"}])
    assert catalog.check() is False


def test_health_scan_counts_and_grades(fixture_env, monkeypatch):
    monkeypatch.setattr(health, "_launchctl_list",
                        lambda: {"com.x.managed": "0", "com.x.adopt": "78"})
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


def test_compact_schedule_formatting():
    assert launchd._fmt_interval(3600) == "every 1h"
    assert launchd._fmt_interval(1800) == "every 30m"
    assert launchd._fmt_interval(120) == "every 2m"
    assert launchd._fmt_calendar({"Hour": 6, "Minute": 30}) == "daily 06:30"
    assert launchd._fmt_calendar([{"Minute": 10}]) == "hourly :10"
    assert launchd._fmt_calendar([{"Hour": 6}, {"Hour": 7}, {"Hour": 8}]) == "3×/day"
