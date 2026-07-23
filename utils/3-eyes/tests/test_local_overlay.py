"""Machine-local registry overlay (GH-195) — jobs.local.d / commands.local.allow.

The overlay is how a cross-repo adoption (absolute machine-specific paths) enters
3-Eyes without leaking those paths into the committed, fleet-portable registry:
runtime loads the overlay (include_local=True), the committed DASHBOARD.md does not.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

from three_eyes import dashboard, registry


def _seed(root: Path, *, committed: dict[str, str], local: dict[str, str] | None = None,
          local_allow: str | None = None) -> Path:
    reg = root / "registry"
    (reg / "jobs.d").mkdir(parents=True)
    (reg / "commands.allow").write_text(
        '[commands.noop]\nexec = "/bin/echo"\nargs = ["ok"]\ndescription = "noop"\n'
    )
    (reg / "routes.toml").write_text('[routes.log-only]\ndescription = "local"\n')
    for name, body in committed.items():
        (reg / "jobs.d" / f"{name}.toml").write_text(textwrap.dedent(body))
    if local:
        (reg / "jobs.local.d").mkdir(parents=True)
        for name, body in local.items():
            (reg / "jobs.local.d" / f"{name}.toml").write_text(textwrap.dedent(body))
    if local_allow is not None:
        (reg / "commands.local.allow").write_text(local_allow)
    return reg


COMMITTED = """\
    id = "alpha"
    command = "noop"
    routes = ["log-only"]
    [schedule.launchd]
    StartInterval = 3600
"""

LOCAL = """\
    id = "zeta-local"
    command = "local-cmd"
    routes = ["log-only"]
    [schedule.launchd]
    StartInterval = 120
"""

LOCAL_ALLOW = '[commands.local-cmd]\nexec = "/bin/echo"\nargs = ["local"]\ndescription = "m"\n'


def test_load_jobs_includes_local_by_default(tmp_path):
    reg = _seed(tmp_path, committed={"alpha": COMMITTED}, local={"zeta": LOCAL})
    ids = {j.id for j in registry.load_jobs(reg)}
    assert ids == {"alpha", "zeta-local"}


def test_load_jobs_can_exclude_local(tmp_path):
    reg = _seed(tmp_path, committed={"alpha": COMMITTED}, local={"zeta": LOCAL})
    ids = {j.id for j in registry.load_jobs(reg, include_local=False)}
    assert ids == {"alpha"}


def test_commands_allow_merges_local_overlay(tmp_path):
    reg = _seed(tmp_path, committed={"alpha": COMMITTED},
                local={"zeta": LOCAL}, local_allow=LOCAL_ALLOW)
    allow = registry.load_commands_allow(reg)
    assert "noop" in allow and "local-cmd" in allow
    assert registry.load_commands_allow(reg, include_local=False).keys() == {"noop"}


def test_local_job_validates_when_its_command_is_in_local_allow(tmp_path):
    reg = _seed(tmp_path, committed={"alpha": COMMITTED},
                local={"zeta": LOCAL}, local_allow=LOCAL_ALLOW)
    assert registry.validate(reg) == []
    # Without the local allowlist, the local job's command is unresolved → a problem,
    # but only when the overlay is in scope. Committed-only view stays clean.
    reg2 = _seed(tmp_path / "b", committed={"alpha": COMMITTED}, local={"zeta": LOCAL})
    assert any("not in commands.allow" in p for p in registry.validate(reg2))
    assert registry.validate(reg2, include_local=False) == []


def test_dashboard_excludes_local_jobs(tmp_path):
    reg = _seed(tmp_path, committed={"alpha": COMMITTED},
                local={"zeta": LOCAL}, local_allow=LOCAL_ALLOW)
    md = dashboard.render(reg)
    assert "alpha" in md
    assert "zeta-local" not in md          # machine-local job never drifts the mirror


def test_dashboard_stable_whether_or_not_local_present(tmp_path):
    a = dashboard.render(_seed(tmp_path / "a", committed={"alpha": COMMITTED}))
    b = dashboard.render(_seed(tmp_path / "b", committed={"alpha": COMMITTED},
                               local={"zeta": LOCAL}, local_allow=LOCAL_ALLOW))
    assert a == b   # identical committed registry → identical dashboard, local or not
