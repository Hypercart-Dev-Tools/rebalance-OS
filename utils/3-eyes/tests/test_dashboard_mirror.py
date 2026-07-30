"""DASHBOARD.md ≡ registry — the 100%-mirror invariant (GH-195)."""

from __future__ import annotations

import textwrap
from pathlib import Path

from three_eyes import dashboard


def _seed_registry(root: Path, jobs: dict[str, str]) -> Path:
    reg = root / "registry"
    (reg / "jobs.d").mkdir(parents=True)
    (reg / "commands.allow").write_text(
        '[commands.noop]\nexec = "/bin/echo"\nargs = ["ok"]\ndescription = "noop"\n'
    )
    (reg / "routes.toml").write_text('[routes.log-only]\ndescription = "local"\n')
    for name, body in jobs.items():
        (reg / "jobs.d" / f"{name}.toml").write_text(textwrap.dedent(body))
    return reg


ONE_JOB = """\
    id = "alpha"
    command = "noop"
    description = "first"
    routes = ["log-only"]
    [schedule.launchd]
    StartInterval = 3600
"""


def test_render_is_deterministic(tmp_path):
    reg = _seed_registry(tmp_path, {"alpha": ONE_JOB})
    a = dashboard.render(reg)
    b = dashboard.render(reg)
    assert a == b
    assert "alpha" in a


def test_check_passes_after_write(tmp_path):
    reg = _seed_registry(tmp_path, {"alpha": ONE_JOB})
    dash = tmp_path / "DASHBOARD.md"
    dashboard.write(reg, dash)
    assert dashboard.check(reg, dash) is True


def test_check_fails_when_registry_drifts(tmp_path):
    reg = _seed_registry(tmp_path, {"alpha": ONE_JOB})
    dash = tmp_path / "DASHBOARD.md"
    dashboard.write(reg, dash)
    assert dashboard.check(reg, dash) is True

    # Change the registry without regenerating the dashboard -> drift detected.
    (reg / "jobs.d" / "beta.toml").write_text(textwrap.dedent(ONE_JOB).replace("alpha", "beta"))
    assert dashboard.check(reg, dash) is False


def test_fingerprint_changes_with_registry(tmp_path):
    reg = _seed_registry(tmp_path, {"alpha": ONE_JOB})
    first = dashboard.render(reg)
    (reg / "jobs.d" / "beta.toml").write_text(textwrap.dedent(ONE_JOB).replace("alpha", "beta"))
    second = dashboard.render(reg)
    assert first != second   # fingerprint + job row both change


def test_committed_dashboard_is_current():
    """The checked-in DASHBOARD.md must match the checked-in registry."""
    assert dashboard.check() is True, (
        "DASHBOARD.md is stale — run `python -m three_eyes sync-dashboard`"
    )
