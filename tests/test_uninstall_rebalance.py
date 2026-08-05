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


def _touch_executable(program: str) -> None:
    """Create the binary a fixture plist claims to launch.

    Ownership now requires the executable to exist, so a fixture that skips this would pass
    for the wrong reason — refused because the file is missing rather than because the
    ownership logic worked. Only paths under a temp dir are created; system paths are left be.
    """
    target = Path(program)
    if target.exists():
        return
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("#!/bin/sh\n", encoding="utf-8")
        target.chmod(0o755)
    except OSError:
        # A system path the test never intended to create (/opt/..., /Library/...). Leaving it
        # absent is fine there — those fixtures assert refusal either way.
        pass


def _plist(path: Path, program: str, *, create: bool = True) -> None:
    if create:
        _touch_executable(program)
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


def test_a_plist_that_only_MENTIONS_our_path_is_refused(sandbox):
    """QA r1 Blocker 1: a substring match over the raw XML is deletion-by-mention.

    A foreign job that writes its logs into our tree, or names us in a comment, is not ours.
    Ownership has to be about what the job LAUNCHES.
    """
    repo, _templates, agents = sandbox
    foreign = agents / "com.rebalance-os.alpha.plist"
    foreign.write_text(
        "<?xml version='1.0' encoding='UTF-8'?>\n"
        f"<!-- integrates with {repo} -->\n"
        "<plist version='1.0'><dict>"
        "<key>ProgramArguments</key><array><string>/opt/other/tool</string></array>"
        f"<key>StandardOutPath</key><string>{repo}/temp/logs/other.log</string>"
        "</dict></plist>\n",
        encoding="utf-8",
    )

    _touch_executable("/opt/other/tool")
    result = _run(sandbox, "--apply")

    assert foreign.exists()
    assert result.returncode == 1
    assert "refusing to remove" in result.stdout


def test_a_sibling_directory_sharing_our_prefix_is_refused(sandbox):
    """QA r1 Blocker 1: `<repo>-archive/tool` must not pass as `<repo>`.

    Without a trailing-slash path boundary, any sibling directory whose name merely starts
    with ours is treated as inside ours.
    """
    repo, _templates, agents = sandbox
    foreign = agents / "com.rebalance-os.alpha.plist"
    _plist(foreign, f"{repo}-archive/scripts/alpha.sh")

    result = _run(sandbox, "--apply")

    assert foreign.exists()
    assert result.returncode == 1


def test_a_non_template_job_is_matched_exactly_not_by_prefix(sandbox, tmp_path, monkeypatch):
    """QA r1 Blocker 2: `~/bin/git-pulse` is a prefix of `~/bin/git-pulse-evil`."""
    repo, templates, agents = sandbox
    home = tmp_path / "home"
    (home / "bin").mkdir(parents=True)
    evil = agents / "com.user.git-pulse.plist"
    _plist(evil, f"{home}/bin/git-pulse-evil")

    result = subprocess.run(
        ["bash", str(SCRIPT), "--apply"],
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "HOME": str(home),
            "RB_UNINSTALL_REPO_DIR": str(repo),
            "RB_UNINSTALL_TEMPLATE_DIR": str(templates),
            "RB_UNINSTALL_AGENTS_DIR": str(agents),
        },
    )

    assert evil.exists(), "a prefix match must not authorise deleting a different binary's job"
    assert result.returncode == 1


def test_a_genuine_non_template_job_is_still_removed(sandbox, tmp_path):
    """The exact-match tightening must not refuse the jobs that really are ours."""
    repo, templates, agents = sandbox
    home = tmp_path / "home"
    (home / "bin").mkdir(parents=True)
    ours = agents / "com.user.git-pulse.plist"
    _plist(ours, f"{home}/bin/git-pulse")

    result = subprocess.run(
        ["bash", str(SCRIPT), "--apply"],
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "HOME": str(home),
            "RB_UNINSTALL_REPO_DIR": str(repo),
            "RB_UNINSTALL_TEMPLATE_DIR": str(templates),
            "RB_UNINSTALL_AGENTS_DIR": str(agents),
        },
    )

    assert not ours.exists()
    assert result.returncode == 0


def test_a_foreign_Program_cannot_be_laundered_by_a_repo_path_in_ProgramArguments(sandbox):
    """QA r2 Blocker 2: launchd runs `Program` when it is set; ProgramArguments[0] is argv[0].

    Accepting whichever key happened to match let a plist park one of our paths in
    ProgramArguments purely to satisfy the check while actually launching something else.
    """
    repo, _templates, agents = sandbox
    spoof = agents / "com.rebalance-os.alpha.plist"
    spoof.write_text(
        "<?xml version='1.0' encoding='UTF-8'?>\n"
        "<plist version='1.0'><dict>"
        "<key>Program</key><string>/opt/evil/tool</string>"
        f"<key>ProgramArguments</key><array><string>{repo}/scripts/alpha.sh</string></array>"
        "</dict></plist>\n",
        encoding="utf-8",
    )

    result = _run(sandbox, "--apply")

    assert spoof.exists()
    assert result.returncode == 1


def test_an_interpreter_backed_job_inside_the_repo_is_recognised(sandbox):
    """health-check et al. launch {{PYTHON}} = <repo>/.venv/bin/python with a script argument.

    The strict executable check must not refuse these — that would leave a partial uninstall.
    """
    repo, templates, agents = sandbox
    (templates / "com.rebalance-os.health-check.plist.template").write_text("x", encoding="utf-8")
    _touch_executable(f"{repo}/.venv/bin/python")
    plist = agents / "com.rebalance-os.health-check.plist"
    plist.write_text(
        "<?xml version='1.0' encoding='UTF-8'?>\n"
        "<plist version='1.0'><dict>"
        "<key>ProgramArguments</key><array>"
        f"<string>{repo}/.venv/bin/python</string>"
        f"<string>{repo}/scripts/health_issue_reporter.py</string>"
        "<string>--close</string>"
        "</array></dict></plist>\n",
        encoding="utf-8",
    )

    result = _run(sandbox, "--apply")

    assert not plist.exists()
    assert result.returncode == 0


def test_a_foreign_interpreter_running_our_script_is_refused(sandbox):
    """A system python invoking one of our files does not make the JOB ours.

    Accepting it would restore deletion-by-mention: any plist could claim ownership by naming
    a file of ours as an argument.
    """
    repo, _templates, agents = sandbox
    plist = agents / "com.rebalance-os.alpha.plist"
    plist.write_text(
        "<?xml version='1.0' encoding='UTF-8'?>\n"
        "<plist version='1.0'><dict>"
        "<key>ProgramArguments</key><array>"
        "<string>/usr/bin/python3</string>"
        f"<string>{repo}/scripts/alpha.py</string>"
        "</array></dict></plist>\n",
        encoding="utf-8",
    )

    result = _run(sandbox, "--apply")

    assert plist.exists()
    assert result.returncode == 1


def test_a_failing_security_command_is_not_reported_as_success(sandbox, tmp_path):
    """QA r2 Blocker 3: a locked keychain left the secret in place and still exited 0."""
    repo, templates, agents = sandbox
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    # Exit 1 = an operational failure (authorisation denied), NOT 44 ("item not found").
    security = fake_bin / "security"
    security.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    security.chmod(0o755)

    result = subprocess.run(
        ["bash", str(SCRIPT), "--apply", "--include-secrets"],
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "PATH": f"{fake_bin}:{os.environ['PATH']}",
            "RB_UNINSTALL_REPO_DIR": str(repo),
            "RB_UNINSTALL_TEMPLATE_DIR": str(templates),
            "RB_UNINSTALL_AGENTS_DIR": str(agents),
        },
    )

    assert result.returncode == 1
    assert "may still be present" in result.stdout


def test_no_secrets_left_behind_exits_clean(sandbox, tmp_path):
    """Exit 44 is 'item not found', which is how a successful sweep legitimately ends."""
    repo, templates, agents = sandbox
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    security = fake_bin / "security"
    security.write_text("#!/bin/sh\nexit 44\n", encoding="utf-8")
    security.chmod(0o755)

    result = subprocess.run(
        ["bash", str(SCRIPT), "--apply", "--include-secrets"],
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "PATH": f"{fake_bin}:{os.environ['PATH']}",
            "RB_UNINSTALL_REPO_DIR": str(repo),
            "RB_UNINSTALL_TEMPLATE_DIR": str(templates),
            "RB_UNINSTALL_AGENTS_DIR": str(agents),
        },
    )

    assert result.returncode == 0


def test_a_plist_whose_name_begins_with_a_dash_is_still_deleted(sandbox):
    """Without `--`, rm reads a leading-dash filename as options."""
    repo, templates, agents = sandbox
    (templates / "-dashy.plist.template").write_text("x", encoding="utf-8")
    plist = agents / "-dashy.plist"
    _plist(plist, f"{repo}/scripts/dashy.sh")

    result = _run(sandbox, "--apply")

    assert not plist.exists()
    assert result.returncode == 0


def test_a_symlink_out_of_the_repo_does_not_confer_ownership(sandbox, tmp_path):
    """QA r3 Blocker: the spelling of a path is not what runs.

    A symlink parked inside the checkout can look owned and execute something else entirely.
    """
    repo, _templates, agents = sandbox
    foreign_tool = tmp_path / "foreign-tool"
    foreign_tool.write_text("#!/bin/sh\n", encoding="utf-8")
    (repo / "bin").mkdir(parents=True, exist_ok=True)
    decoy = repo / "bin" / "owned-looking"
    decoy.symlink_to(foreign_tool)

    plist = agents / "com.rebalance-os.alpha.plist"
    _plist(plist, str(decoy))

    result = _run(sandbox, "--apply")

    assert plist.exists(), "a symlink escaping the repo must not confer ownership"
    assert result.returncode == 1


def test_a_symlink_that_stays_inside_the_repo_still_confers_ownership(sandbox):
    """Resolving symlinks must not break a checkout that legitimately uses one internally."""
    repo, _templates, agents = sandbox
    (repo / "scripts").mkdir(parents=True, exist_ok=True)
    real = repo / "scripts" / "alpha.sh"
    real.write_text("#!/bin/sh\n", encoding="utf-8")
    real.chmod(0o755)  # ownership now requires a genuinely launchable file
    link = repo / "bin"
    link.mkdir(exist_ok=True)
    alias = link / "alpha"
    alias.symlink_to(real)

    plist = agents / "com.rebalance-os.alpha.plist"
    _plist(plist, str(alias))

    result = _run(sandbox, "--apply")

    assert not plist.exists()
    assert result.returncode == 0


def test_a_path_that_never_existed_is_not_proof_of_ownership(sandbox):
    """QA r4 Blocker: realpath normalises a string whether or not anything is there.

    A colliding foreign plist naming a path under the checkout that has never existed was
    being deleted on the strength of its spelling alone.
    """
    repo, _templates, agents = sandbox
    foreign = agents / "com.rebalance-os.alpha.plist"
    _plist(foreign, f"{repo}/not-ours/never-existed", create=False)

    result = _run(sandbox, "--apply")

    assert foreign.exists()
    assert result.returncode == 1
    assert "--include-orphans" in result.stdout  # and the operator is told the way forward


def test_an_absent_exact_marker_is_also_refused(sandbox, tmp_path):
    """Same hole, non-template branch: the ~/bin binary must exist to prove anything."""
    repo, templates, agents = sandbox
    home = tmp_path / "home"
    (home / "bin").mkdir(parents=True)
    plist = agents / "com.user.git-pulse.plist"
    _plist(plist, f"{home}/bin/git-pulse", create=False)

    result = subprocess.run(
        ["bash", str(SCRIPT), "--apply"],
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "HOME": str(home),
            "RB_UNINSTALL_REPO_DIR": str(repo),
            "RB_UNINSTALL_TEMPLATE_DIR": str(templates),
            "RB_UNINSTALL_AGENTS_DIR": str(agents),
        },
    )

    assert plist.exists()
    assert result.returncode == 1


def test_include_orphans_cleans_up_a_job_whose_executable_is_gone(sandbox):
    """The half-removed-checkout case an uninstaller exists for — but asked for explicitly."""
    repo, _templates, agents = sandbox
    plist = agents / "com.rebalance-os.alpha.plist"
    _plist(plist, f"{repo}/scripts/already-deleted.sh", create=False)

    result = _run(sandbox, "--apply", "--include-orphans")

    assert not plist.exists()
    assert result.returncode == 0


def test_include_orphans_still_refuses_a_foreign_job(sandbox):
    """The orphan flag relaxes the existence proof, never the ownership boundary."""
    repo, _templates, agents = sandbox
    foreign = agents / "com.rebalance-os.alpha.plist"
    _plist(foreign, f"{repo}-archive/scripts/alpha.sh", create=False)

    result = _run(sandbox, "--apply", "--include-orphans")

    assert foreign.exists()
    assert result.returncode == 1


def test_a_directory_under_the_repo_is_not_an_executable(sandbox):
    """QA r5 Blocker: `$REBALANCE_DIR/scripts` exists and is under the repo, but launchd

    could never launch it. Existence is not the proof — a real executable file is.
    """
    repo, _templates, agents = sandbox
    (repo / "scripts").mkdir(parents=True, exist_ok=True)
    foreign = agents / "com.rebalance-os.alpha.plist"
    _plist(foreign, f"{repo}/scripts", create=False)

    result = _run(sandbox, "--apply")

    assert foreign.exists()
    assert result.returncode == 1


def test_a_directory_is_refused_for_the_exact_marker_too(sandbox, tmp_path):
    repo, templates, agents = sandbox
    home = tmp_path / "home"
    (home / "bin" / "git-pulse").mkdir(parents=True)  # a directory where a binary belongs
    plist = agents / "com.user.git-pulse.plist"
    _plist(plist, f"{home}/bin/git-pulse", create=False)

    result = subprocess.run(
        ["bash", str(SCRIPT), "--apply"],
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "HOME": str(home),
            "RB_UNINSTALL_REPO_DIR": str(repo),
            "RB_UNINSTALL_TEMPLATE_DIR": str(templates),
            "RB_UNINSTALL_AGENTS_DIR": str(agents),
        },
    )

    assert plist.exists()
    assert result.returncode == 1


def test_include_orphans_does_not_excuse_an_existing_non_executable(sandbox):
    """The orphan flag forgives an ABSENT file, never a present unlaunchable one."""
    repo, _templates, agents = sandbox
    (repo / "scripts").mkdir(parents=True, exist_ok=True)
    foreign = agents / "com.rebalance-os.alpha.plist"
    _plist(foreign, f"{repo}/scripts", create=False)

    result = _run(sandbox, "--apply", "--include-orphans")

    assert foreign.exists()
    assert result.returncode == 1


def test_a_non_executable_regular_file_is_also_refused(sandbox):
    """A data file under the repo is not something launchd runs."""
    repo, _templates, agents = sandbox
    (repo / "scripts").mkdir(parents=True, exist_ok=True)
    data = repo / "scripts" / "notes.txt"
    data.write_text("not a program", encoding="utf-8")
    data.chmod(0o644)
    foreign = agents / "com.rebalance-os.alpha.plist"
    _plist(foreign, str(data), create=False)

    result = _run(sandbox, "--apply")

    assert foreign.exists()
    assert result.returncode == 1


def test_a_broken_plist_symlink_is_not_reported_as_absent(sandbox, tmp_path):
    """QA r6: `-f` is false for a broken link, so it read as "not installed" and exited 0.

    "Absent" and "present but unreadable" are different states; collapsing them into the
    reassuring one leaves a stale entry behind under a clean exit code.
    """
    _repo, _templates, agents = sandbox
    link = agents / "com.rebalance-os.alpha.plist"
    link.symlink_to(tmp_path / "gone-away.plist")

    result = _run(sandbox, "--apply")

    assert link.is_symlink()
    assert result.returncode == 1
    assert "not installed" not in result.stdout.split("com.rebalance-os.alpha")[1][:40]


def test_an_unparseable_plist_fails_closed(sandbox):
    """A file we cannot read is a file we cannot prove is ours."""
    _repo, _templates, agents = sandbox
    junk = agents / "com.rebalance-os.alpha.plist"
    junk.write_text("this is not a plist at all", encoding="utf-8")

    result = _run(sandbox, "--apply")

    assert junk.exists()
    assert result.returncode == 1


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
