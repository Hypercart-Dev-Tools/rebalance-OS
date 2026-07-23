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
