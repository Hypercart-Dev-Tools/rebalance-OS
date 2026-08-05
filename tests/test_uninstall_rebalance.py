"""Tests for scripts/uninstall_rebalance.sh (GH-257).

This is a deletion tool, so the tests that matter most are the ones proving it does NOT
delete: ~/Library/LaunchAgents holds Google, Setapp and Homebrew agents beside rebalance's,
and a uninstaller that matched on label alone could take them out.

Every test runs against a fixture LaunchAgents directory and a fixture template directory, so
nothing here can touch the real machine.
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "uninstall_rebalance.sh"


def _plist(path: Path, program: str) -> None:
    path.write_text(
        "<?xml version='1.0' encoding='UTF-8'?>\n"
        "<plist version='1.0'><dict>"
        f"<key>Label</key><string>{path.stem}</string>"
        f"<key>ProgramArguments</key><array><string>{program}</string></array>"
        "</dict></plist>\n",
        encoding="utf-8",
    )


@pytest.fixture
def sandbox(tmp_path):
    """A fake repo, template dir, and LaunchAgents dir that the script operates on."""
    repo = tmp_path / "repo"
    templates = tmp_path / "templates"
    agents = tmp_path / "LaunchAgents"
    for directory in (repo, templates, agents):
        directory.mkdir()
    (templates / "com.rebalance-os.alpha.plist.template").write_text("x", encoding="utf-8")
    (templates / "com.rebalance-os.bravo.plist.template").write_text("x", encoding="utf-8")
    return repo, templates, agents


def _run(sandbox, *args):
    repo, templates, agents = sandbox
    environment = {
        **os.environ,
        "RB_UNINSTALL_REPO_DIR": str(repo),
        "RB_UNINSTALL_TEMPLATE_DIR": str(templates),
        "RB_UNINSTALL_AGENTS_DIR": str(agents),
    }
    return subprocess.run(
        ["bash", str(SCRIPT), *args], capture_output=True, text=True, env=environment
    )


def test_a_dry_run_changes_nothing(sandbox):
    _repo, _templates, agents = sandbox
    _plist(agents / "com.rebalance-os.alpha.plist", f"{_repo}/scripts/alpha.sh")

    result = _run(sandbox)

    assert result.returncode == 0
    assert (agents / "com.rebalance-os.alpha.plist").exists()  # untouched
    assert "DRY RUN" in result.stdout
    # The past tense is reserved for things that actually happened.
    assert "would be removed" in result.stdout


def test_apply_removes_a_job_this_repo_owns(sandbox):
    repo, _templates, agents = sandbox
    plist = agents / "com.rebalance-os.alpha.plist"
    _plist(plist, f"{repo}/scripts/alpha.sh")

    result = _run(sandbox, "--apply")

    assert result.returncode == 0
    assert not plist.exists()


def test_a_plist_belonging_to_other_software_is_refused(sandbox):
    """The safety property: matching a label is not authority to delete a file."""
    _repo, _templates, agents = sandbox
    foreign = agents / "com.rebalance-os.alpha.plist"
    _plist(foreign, "/Library/Google/GoogleUpdater/updater")

    result = _run(sandbox, "--apply")

    assert foreign.exists(), "a plist not referencing this repo must survive"
    assert "refusing to remove" in result.stdout
    assert result.returncode == 1  # and it must not be reported as a clean uninstall


def test_a_job_that_was_never_installed_is_reported_absent_not_removed(sandbox):
    result = _run(sandbox, "--apply")

    assert result.returncode == 0
    assert "not installed" in result.stdout
    assert "0 removed" in result.stdout


def test_the_run_is_idempotent(sandbox):
    repo, _templates, agents = sandbox
    _plist(agents / "com.rebalance-os.alpha.plist", f"{repo}/scripts/alpha.sh")

    first = _run(sandbox, "--apply")
    second = _run(sandbox, "--apply")

    assert first.returncode == 0 and second.returncode == 0
    assert "1 removed" in first.stdout
    assert "0 removed" in second.stdout  # a second run is a clean no-op


def test_data_is_kept_unless_explicitly_requested(sandbox):
    repo, _templates, _agents = sandbox
    logs = repo / "temp" / "logs"
    logs.mkdir(parents=True)
    (logs / "vault.log").write_text("history", encoding="utf-8")

    _run(sandbox, "--apply")

    # Unloading a job is reversible by re-running its installer; deleting a log history is not,
    # so it must never ride along with a default run.
    assert (logs / "vault.log").exists()


def test_include_data_removes_it(sandbox):
    repo, _templates, _agents = sandbox
    logs = repo / "temp" / "logs"
    logs.mkdir(parents=True)
    (logs / "vault.log").write_text("history", encoding="utf-8")

    result = _run(sandbox, "--apply", "--include-data")

    assert result.returncode == 0
    assert not logs.exists()


def test_a_missing_template_directory_fails_loudly(sandbox, tmp_path):
    """With no templates there is no inventory, and 'nothing to remove' would be a lie."""
    repo, _templates, agents = sandbox
    empty = tmp_path / "no-templates"
    empty.mkdir()
    result = subprocess.run(
        ["bash", str(SCRIPT), "--apply"],
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "RB_UNINSTALL_REPO_DIR": str(repo),
            "RB_UNINSTALL_TEMPLATE_DIR": str(empty),
            "RB_UNINSTALL_AGENTS_DIR": str(agents),
        },
    )

    assert result.returncode == 1
    assert "cannot derive the job list" in result.stdout


def test_an_unknown_option_is_rejected_rather_than_ignored(sandbox):
    result = _run(sandbox, "--delete-everything")

    assert result.returncode == 2
    assert "unknown option" in result.stderr


def test_the_job_list_is_derived_from_templates_not_hardcoded(sandbox):
    """Add a template, and the new job is covered with no edit to the script."""
    repo, templates, agents = sandbox
    (templates / "com.rebalance-os.charlie.plist.template").write_text("x", encoding="utf-8")
    plist = agents / "com.rebalance-os.charlie.plist"
    _plist(plist, f"{repo}/scripts/charlie.sh")

    result = _run(sandbox, "--apply")

    assert result.returncode == 0
    assert not plist.exists()
