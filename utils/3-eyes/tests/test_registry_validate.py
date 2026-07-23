"""Registry integrity — the safe-command allowlist + route/schedule rules (GH-195)."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from three_eyes import registry


def _reg(root: Path, jobs: dict[str, str], allow: str | None = None, routes: str | None = None) -> Path:
    r = root / "registry"
    (r / "jobs.d").mkdir(parents=True)
    (r / "commands.allow").write_text(
        allow if allow is not None
        else '[commands.noop]\nexec = "/bin/echo"\nargs = []\ndescription = "n"\n'
    )
    (r / "routes.toml").write_text(
        routes if routes is not None else '[routes.log-only]\ndescription = "local"\n'
    )
    for name, body in jobs.items():
        (r / "jobs.d" / f"{name}.toml").write_text(textwrap.dedent(body))
    return r


GOOD = """\
    id = "alpha"
    command = "noop"
    routes = ["log-only"]
    [schedule.launchd]
    StartInterval = 3600
"""


def test_valid_registry_has_no_problems(tmp_path):
    assert registry.validate(_reg(tmp_path, {"alpha": GOOD})) == []


def test_command_not_in_allowlist_is_rejected(tmp_path):
    bad = GOOD.replace('command = "noop"', 'command = "rm-rf-slash"')
    problems = registry.validate(_reg(tmp_path, {"alpha": bad}))
    assert any("not in commands.allow" in p for p in problems)


def test_unknown_route_is_rejected(tmp_path):
    bad = GOOD.replace('routes = ["log-only"]', 'routes = ["email-my-boss"]')
    problems = registry.validate(_reg(tmp_path, {"alpha": bad}))
    assert any("unknown route" in p for p in problems)


def test_route_not_configured_is_rejected(tmp_path):
    # gh-issue is a KNOWN route, but routes.toml here doesn't configure it.
    bad = GOOD.replace('routes = ["log-only"]', 'routes = ["gh-issue"]')
    problems = registry.validate(_reg(tmp_path, {"alpha": bad}))
    assert any("not configured in routes.toml" in p for p in problems)


def test_missing_schedule_is_rejected(tmp_path):
    bad = 'id = "alpha"\ncommand = "noop"\nroutes = ["log-only"]\n'
    problems = registry.validate(_reg(tmp_path, {"alpha": bad}))
    assert any("no schedule" in p for p in problems)


def test_duplicate_id_is_rejected(tmp_path):
    other = GOOD  # same id "alpha"
    problems = registry.validate(_reg(tmp_path, {"a": GOOD, "b": other}))
    assert any("duplicate job id" in p for p in problems)


def test_missing_command_key_is_rejected(tmp_path):
    bad = 'id = "alpha"\nroutes = ["log-only"]\n[schedule.launchd]\nStartInterval = 60\n'
    problems = registry.validate(_reg(tmp_path, {"alpha": bad}))
    assert any("missing 'command'" in p for p in problems)


def test_shipped_registry_is_valid():
    """The checked-in (committed-only) registry must itself be valid."""
    assert registry.validate(include_local=False) == []


def test_full_registry_including_local_is_valid():
    """Whatever machine-local overlay exists here must ALSO be self-consistent
    (its jobs' commands resolve in commands.local.allow). No-op where none exists."""
    assert registry.validate(include_local=True) == []


def test_command_allowlist_requires_exec(tmp_path):
    with pytest.raises(registry.RegistryError):
        registry.load_commands_allow(
            _reg(tmp_path, {"alpha": GOOD}, allow='[commands.noop]\ndescription = "no exec"\n')
        )


def test_supersedes_parses_and_defaults_empty(tmp_path):
    """`supersedes` is optional; a string is coerced to a one-element tuple."""
    plain = 'id = "alpha"\ncommand = "noop"\nroutes = ["log-only"]\n[schedule.launchd]\nStartInterval = 60\n'
    one = ('id = "beta"\ncommand = "noop"\nroutes = ["log-only"]\n'
           'supersedes = "com.legacy.one"\n[schedule.launchd]\nStartInterval = 60\n')
    many = ('id = "gamma"\ncommand = "noop"\nroutes = ["log-only"]\n'
            'supersedes = ["com.legacy.a", "com.legacy.b"]\n[schedule.launchd]\nStartInterval = 60\n')
    jobs = {j.id: j for j in registry.load_jobs(
        _reg(tmp_path, {"alpha": plain, "beta": one, "gamma": many}))}
    assert jobs["alpha"].supersedes == ()
    assert jobs["beta"].supersedes == ("com.legacy.one",)
    assert jobs["gamma"].supersedes == ("com.legacy.a", "com.legacy.b")


def test_collector_health_declares_the_incumbents_it_replaces():
    """Guards the real adoption hazard: collector-health and the health-check agents
    both emit GitHub health issues, so the job must name them as superseded."""
    job = {j.id: j for j in registry.load_jobs(include_local=False)}["collector-health"]
    assert set(job.supersedes) == {
        "com.rebalance-os.health-check", "com.rebalance-os.health-check-triage"}


# --- adoption guard: install must never create a second emitter (GH-195) ------ #

def _job(**kw):
    from three_eyes.registry import Job
    base = dict(id="collector-health", command="noop", enabled=True,
                schedule={"launchd": {"StartInterval": 60}}, routes=("log-only",))
    base.update(kw)
    return Job(**base)


def _install_env(monkeypatch, tmp_path, state):
    from three_eyes import config, launchd, registry as reg
    monkeypatch.setattr(config, "three_eyes_active", lambda: True)
    monkeypatch.setattr(reg, "validate", lambda *a, **k: [])
    monkeypatch.setattr(launchd, "launchctl_state", lambda lbl: state)
    monkeypatch.setattr(launchd, "LAUNCH_AGENTS_DIR", tmp_path)
    monkeypatch.setattr(launchd, "render_plist", lambda job: b"<plist/>")
    monkeypatch.setattr(config, "state_dir", lambda: tmp_path)
    monkeypatch.setattr(launchd.subprocess, "run",
                        lambda *a, **k: type("P", (), {"stdout": "501", "returncode": 0})())
    return launchd


def test_install_refuses_while_a_superseded_agent_is_loaded(monkeypatch, tmp_path):
    launchd = _install_env(monkeypatch, tmp_path, "loaded")
    with pytest.raises(registry.RegistryError) as exc:
        launchd.install(_job(supersedes=("com.rebalance-os.health-check",)))
    assert "supersedes" in str(exc.value)
    assert "com.rebalance-os.health-check" in str(exc.value)


def test_install_fails_closed_when_incumbent_state_is_unknown(monkeypatch, tmp_path):
    """An unreadable probe must BLOCK the install, not wave it through."""
    launchd = _install_env(monkeypatch, tmp_path, "unknown")
    with pytest.raises(registry.RegistryError) as exc:
        launchd.install(_job(supersedes=("com.rebalance-os.health-check",)))
    assert "unknown" in str(exc.value)


def test_install_proceeds_once_incumbents_are_retired(monkeypatch, tmp_path):
    launchd = _install_env(monkeypatch, tmp_path, "not-loaded")
    assert launchd.install(_job(supersedes=("com.rebalance-os.health-check",))).exists()


def test_job_without_supersedes_never_probes(monkeypatch, tmp_path):
    launchd = _install_env(monkeypatch, tmp_path, "loaded")   # would block IF probed
    assert launchd.install(_job()).exists()                   # empty supersedes → no probe
