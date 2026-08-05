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



def _template(templates: Path, label: str, args: list[str]) -> Path:
    """Write a real plist template, the way install_common.sh expects to find one.

    The fixture used to write the stub "x". That was fine while ownership was judged from
    paths, and useless once the proof became "does this plist match what our installer would
    have rendered" — the tests have to exercise the real contract.
    """
    body = "".join(f"<string>{a}</string>" for a in args)
    path = templates / f"{label}.plist.template"
    path.write_text(
        "<?xml version='1.0' encoding='UTF-8'?>\n"
        "<plist version='1.0'><dict>"
        f"<key>Label</key><string>{label}</string>"
        f"<key>ProgramArguments</key><array>{body}</array>"
        "</dict></plist>\n",
        encoding="utf-8",
    )
    return path


def _rendered(agents: Path, label: str, repo: Path, args: list[str], *, create: bool = True) -> Path:
    """Write the plist a template would render to, substituting {{REBALANCE_DIR}}/{{PYTHON}}."""
    real = [
        a.replace("{{REBALANCE_DIR}}", str(repo)).replace("{{PYTHON}}", f"{repo}/.venv/bin/python")
        for a in args
    ]
    if create:
        for a in real:
            if a.startswith("/"):
                _touch_executable(a)
    path = agents / f"{label}.plist"
    body = "".join(f"<string>{a}</string>" for a in real)
    path.write_text(
        "<?xml version='1.0' encoding='UTF-8'?>\n"
        "<plist version='1.0'><dict>"
        f"<key>Label</key><string>{label}</string>"
        f"<key>ProgramArguments</key><array>{body}</array>"
        "</dict></plist>\n",
        encoding="utf-8",
    )
    return path


@pytest.fixture
def sandbox(tmp_path):
    """A fake repo, template dir, and LaunchAgents dir that the script operates on."""
    repo = tmp_path / "repo"
    templates = tmp_path / "templates"
    agents = tmp_path / "LaunchAgents"
    for directory in (repo, templates, agents):
        directory.mkdir()
    _template(templates, "com.rebalance-os.alpha", ["{{REBALANCE_DIR}}/scripts/alpha.sh"])
    _template(templates, "com.rebalance-os.bravo", ["{{REBALANCE_DIR}}/scripts/bravo.sh"])
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
    args = ["{{PYTHON}}", "{{REBALANCE_DIR}}/scripts/health_issue_reporter.py", "--close"]
    _template(templates, "com.rebalance-os.health-check", args)
    plist = _rendered(agents, "com.rebalance-os.health-check", repo, args)

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
    args = ["{{REBALANCE_DIR}}/scripts/dashy.sh"]
    _template(templates, "-dashy", args)
    plist = _rendered(agents, "-dashy", repo, args)

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

    # Template and plist both name the alias, so the shapes match; the point is that a
    # symlink resolving INSIDE the repo is still a legitimate job.
    _template(sandbox[1], "com.rebalance-os.alpha", [str(alias)])
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
    # Matching the template is a comparison of contents, so a job whose files are already
    # gone still proves ownership — the orphan case is handled without a flag for template
    # jobs. The flag remains for the ~/bin jobs, which have no template to compare against.
    args = ["{{REBALANCE_DIR}}/scripts/already-deleted.sh"]
    _template(sandbox[1], "com.rebalance-os.alpha", args)
    plist = _rendered(agents, "com.rebalance-os.alpha", repo, args, create=False)

    result = _run(sandbox, "--apply")

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


def test_an_mcp_registration_is_reported_even_though_it_is_not_removed(sandbox):
    """Found by running --apply on a live machine.

    Every launchd job was removed and the tool said "9 removed" — while two
    rebalance.mcp_server processes were still running, one of them for five days. They come
    from the checkout's own .mcp.json, not from launchd. Not removing it is correct (it is
    part of the git checkout). Not MENTIONING it would let the summary read as "rebalance is
    gone from this machine" when it is still running.
    """
    repo, _templates, _agents = sandbox
    (repo / ".mcp.json").write_text(
        '{"mcpServers": {"rebalance": {"command": ".venv/bin/python",'
        ' "args": ["-m", "rebalance.mcp_server"]}}}',
        encoding="utf-8",
    )

    result = _run(sandbox, "--apply")

    assert "other entry points" in result.stdout
    assert ".mcp.json" in result.stdout
    assert result.returncode == 0  # reported, not treated as a failure — it is out of scope


def test_no_mcp_section_when_the_repo_does_not_register_one(sandbox):
    result = _run(sandbox, "--apply")

    assert "other entry points" not in result.stdout


def test_the_word_rebalance_elsewhere_in_mcp_json_is_not_a_registration(sandbox):
    """Same match-anywhere sloppiness the ownership check spent four rounds shedding."""
    repo, _templates, _agents = sandbox
    (repo / ".mcp.json").write_text(
        '{"_comment": "does not talk to rebalance at all",'
        ' "mcpServers": {"other": {"command": "/opt/other", "args": ["--note", "rebalance"]}}}',
        encoding="utf-8",
    )

    result = _run(sandbox, "--apply")

    assert "other entry points" not in result.stdout


def test_an_unreadable_mcp_json_does_not_claim_a_registration(sandbox):
    repo, _templates, _agents = sandbox
    (repo / ".mcp.json").write_text("{ not json", encoding="utf-8")

    result = _run(sandbox, "--apply")

    assert "other entry points" not in result.stdout
    assert result.returncode == 0


def test_matching_processes_are_reported_without_claiming_the_checkout(sandbox, tmp_path):
    """A command line cannot prove which clone a process belongs to, so it must not say so."""
    repo, templates, agents = sandbox
    (repo / ".mcp.json").write_text(
        '{"mcpServers": {"rebalance": {"command": ".venv/bin/python",'
        ' "args": ["-m", "rebalance.mcp_server"]}}}',
        encoding="utf-8",
    )
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    pgrep = fake_bin / "pgrep"
    pgrep.write_text("#!/bin/sh\nprintf '4242\\n4243\\n'\n", encoding="utf-8")
    pgrep.chmod(0o755)

    result = subprocess.run(
        ["bash", str(SCRIPT), "--apply"],
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

    assert "4242 4243" in result.stdout
    assert "Not attributed to this checkout" in result.stdout
    # and no unproven lifecycle claim either (QA r9 Should)
    assert "If hosted by your editor" in result.stdout
    assert result.returncode == 0


def test_our_interpreter_running_a_foreign_script_is_refused(sandbox, tmp_path):
    """QA r9 Blocker: a repo-owned interpreter must not vouch for foreign code.

    Three templates launch {{PYTHON}} — a binary inside the checkout — with their real work in
    argument 1, so a colliding plist could borrow our interpreter to run /opt/foreign.py.
    """
    repo, _templates, agents = sandbox
    _touch_executable(f"{repo}/.venv/bin/python")
    foreign_script = tmp_path / "foreign.py"
    foreign_script.write_text("print('not ours')\n", encoding="utf-8")

    plist = agents / "com.rebalance-os.alpha.plist"
    plist.write_text(
        "<?xml version='1.0' encoding='UTF-8'?>\n"
        "<plist version='1.0'><dict>"
        "<key>ProgramArguments</key><array>"
        f"<string>{repo}/.venv/bin/python</string>"
        f"<string>{foreign_script}</string>"
        "</array></dict></plist>\n",
        encoding="utf-8",
    )

    result = _run(sandbox, "--apply")

    assert plist.exists(), "our interpreter must not confer ownership on foreign code"
    assert result.returncode == 1


def test_inline_code_and_module_invocations_are_refused(sandbox):
    """`-c` and `-m` leave no path to verify, so ownership cannot be proven at all."""
    repo, _templates, agents = sandbox
    _touch_executable(f"{repo}/.venv/bin/python")

    for flag, payload in (("-c", "import os; os.system('rm -rf /')"), ("-m", "http.server")):
        plist = agents / "com.rebalance-os.alpha.plist"
        plist.write_text(
            "<?xml version='1.0' encoding='UTF-8'?>\n"
            "<plist version='1.0'><dict>"
            "<key>ProgramArguments</key><array>"
            f"<string>{repo}/.venv/bin/python</string>"
            f"<string>{flag}</string><string>{payload}</string>"
            "</array></dict></plist>\n",
            encoding="utf-8",
        )
        result = _run(sandbox, "--apply")
        assert plist.exists(), f"{flag} must not be removable"
        assert result.returncode == 1
        plist.unlink()


def test_a_genuine_interpreter_job_with_flags_is_still_removed(sandbox):
    """pulse-warning-watch passes flags after its script; those must not break ownership."""
    repo, templates, agents = sandbox
    args = ["{{PYTHON}}", "{{REBALANCE_DIR}}/scripts/pulse_warning_watch.py",
            "--url", "http://127.0.0.1:8767/"]
    _template(templates, "com.rebalance-os.pulse-warning-watch", args)
    plist = _rendered(agents, "com.rebalance-os.pulse-warning-watch", repo, args)

    result = _run(sandbox, "--apply")

    assert not plist.exists()
    assert result.returncode == 0


def test_a_relative_script_operand_is_refused(sandbox):
    """QA r10 Blocker: realpath() resolves relative paths against OUR cwd, launchd against
    the plist's WorkingDirectory — so a relative operand can look owned and run elsewhere.
    """
    repo, _templates, agents = sandbox
    _touch_executable(f"{repo}/.venv/bin/python")
    (repo / "scripts").mkdir(parents=True, exist_ok=True)
    (repo / "scripts" / "health_issue_reporter.py").write_text("#\n", encoding="utf-8")

    plist = agents / "com.rebalance-os.alpha.plist"
    plist.write_text(
        "<?xml version='1.0' encoding='UTF-8'?>\n"
        "<plist version='1.0'><dict>"
        "<key>ProgramArguments</key><array>"
        f"<string>{repo}/.venv/bin/python</string>"
        "<string>scripts/health_issue_reporter.py</string>"
        "</array>"
        "<key>WorkingDirectory</key><string>/opt/foreign</string>"
        "</dict></plist>\n",
        encoding="utf-8",
    )

    # Run from inside the checkout, the CWD that makes the relative path look owned.
    result = subprocess.run(
        ["bash", str(SCRIPT), "--apply"],
        capture_output=True, text=True, cwd=str(repo),
        env={
            **os.environ,
            "RB_UNINSTALL_REPO_DIR": str(repo),
            "RB_UNINSTALL_TEMPLATE_DIR": str(sandbox[1]),
            "RB_UNINSTALL_AGENTS_DIR": str(agents),
        },
    )

    assert plist.exists()
    assert result.returncode == 1


def test_a_relative_executable_is_refused(sandbox):
    repo, _templates, agents = sandbox
    plist = agents / "com.rebalance-os.alpha.plist"
    _plist(plist, "scripts/alpha.sh", create=False)

    result = _run(sandbox, "--apply")

    assert plist.exists()
    assert result.returncode == 1


def test_a_broken_data_symlink_is_not_called_absent(sandbox, tmp_path):
    """QA r10 Should: same gone-vs-unreadable collapse as the plist case, in --include-data."""
    repo, _templates, _agents = sandbox
    (repo / "temp").mkdir(parents=True, exist_ok=True)
    link = repo / "temp" / "logs"
    link.symlink_to(tmp_path / "vanished")

    result = _run(sandbox, "--apply", "--include-data")

    assert not link.is_symlink(), "the stale link must be removed, not reported absent"
    assert result.returncode == 0


def test_compact_inline_code_and_module_forms_are_refused(sandbox):
    """QA r11 Blocker: python accepts "-cimport os; ..." and "-mhttp.server" compactly.

    An exact `-c`/`-m` match let those through as ordinary flags, leaving the owned
    interpreter as the only checked path — so arbitrary inline code was deletable.
    """
    repo, _templates, agents = sandbox
    _touch_executable(f"{repo}/.venv/bin/python")

    for payload in ("-cimport os; os.system('id')", "-mhttp.server"):
        plist = agents / "com.rebalance-os.alpha.plist"
        plist.write_text(
            "<?xml version='1.0' encoding='UTF-8'?>\n"
            "<plist version='1.0'><dict>"
            "<key>ProgramArguments</key><array>"
            f"<string>{repo}/.venv/bin/python</string>"
            f"<string>{payload}</string>"
            "</array></dict></plist>\n",
            encoding="utf-8",
        )
        result = _run(sandbox, "--apply")
        assert plist.exists(), f"{payload!r} must not be removable"
        assert result.returncode == 1
        plist.unlink()


def test_long_options_after_a_script_are_unaffected(sandbox):
    """--close/--llm-triage must keep working: they begin '--', not '-c'/'-m'."""
    repo, templates, agents = sandbox
    args = ["{{PYTHON}}", "{{REBALANCE_DIR}}/scripts/health_issue_reporter.py",
            "--warn", "--close", "--llm-triage", "--llm-max-per-run", "5"]
    _template(templates, "com.rebalance-os.health-check-triage", args)
    plist = _rendered(agents, "com.rebalance-os.health-check-triage", repo, args)

    result = _run(sandbox, "--apply")

    assert not plist.exists()
    assert result.returncode == 0


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
    args = ["{{REBALANCE_DIR}}/scripts/charlie.sh"]
    _template(templates, "com.rebalance-os.charlie", args)
    plist = _rendered(agents, "com.rebalance-os.charlie", repo, args)

    result = _run(sandbox, "--apply")

    assert result.returncode == 0
    assert not plist.exists()


def test_an_interpreter_option_cannot_smuggle_a_foreign_script(sandbox):
    """QA r12 Blocker: `-X <repo path> /opt/foreign.py` — python consumes the repo path as
    -X's value and runs the foreign script, while a first-non-flag-operand scan validated the
    repo path. Chasing python's grammar lost four rounds running; matching the template shape
    ends the whole class, because this is simply not what our installer would have written.
    """
    repo, templates, agents = sandbox
    args = ["{{PYTHON}}", "{{REBALANCE_DIR}}/scripts/health_issue_reporter.py", "--close"]
    _template(templates, "com.rebalance-os.health-check", args)
    _touch_executable(f"{repo}/.venv/bin/python")

    plist = agents / "com.rebalance-os.health-check.plist"
    plist.write_text(
        "<?xml version='1.0' encoding='UTF-8'?>\n"
        "<plist version='1.0'><dict>"
        "<key>ProgramArguments</key><array>"
        f"<string>{repo}/.venv/bin/python</string>"
        "<string>-X</string>"
        f"<string>{repo}/scripts/health_issue_reporter.py</string>"
        "<string>/opt/foreign.py</string>"
        "</array></dict></plist>\n",
        encoding="utf-8",
    )

    result = _run(sandbox, "--apply")

    assert plist.exists()
    assert result.returncode == 1


def test_a_hand_edited_plist_is_refused_rather_than_assumed(sandbox):
    """A shape we did not write is not a shape we can claim. Refused loudly, not deleted."""
    repo, templates, agents = sandbox
    _template(templates, "com.rebalance-os.alpha", ["{{REBALANCE_DIR}}/scripts/alpha.sh"])
    plist = _rendered(agents, "com.rebalance-os.alpha", repo,
                      ["{{REBALANCE_DIR}}/scripts/alpha.sh", "--extra-flag"])

    result = _run(sandbox, "--apply")

    assert plist.exists()
    assert result.returncode == 1
    assert "does not match" in result.stdout


def test_a_foreign_label_inside_our_filename_is_refused(sandbox):
    """QA r13 Blocker: copying our launch fields while declaring a different Label.

    Every other rendered fixture couples filename and embedded label, so this case could not
    have been caught by them.
    """
    repo, templates, agents = sandbox
    _template(templates, "com.rebalance-os.alpha", ["{{REBALANCE_DIR}}/scripts/alpha.sh"])
    _touch_executable(f"{repo}/scripts/alpha.sh")

    plist = agents / "com.rebalance-os.alpha.plist"
    plist.write_text(
        "<?xml version='1.0' encoding='UTF-8'?>\n"
        "<plist version='1.0'><dict>"
        "<key>Label</key><string>com.foreign.agent</string>"
        "<key>ProgramArguments</key><array>"
        f"<string>{repo}/scripts/alpha.sh</string>"
        "</array></dict></plist>\n",
        encoding="utf-8",
    )

    result = _run(sandbox, "--apply")

    assert plist.exists(), "a foreign Label must not be removable under our filename"
    assert result.returncode == 1


def _plist_with_env(agents, label, repo, args, env):
    body = "".join(f"<string>{a}</string>" for a in args)
    envxml = "".join(f"<key>{k}</key><string>{v}</string>" for k, v in env.items())
    path = agents / f"{label}.plist"
    path.write_text(
        "<?xml version='1.0' encoding='UTF-8'?>\n"
        "<plist version='1.0'><dict>"
        f"<key>Label</key><string>{label}</string>"
        f"<key>ProgramArguments</key><array>{body}</array>"
        f"<key>EnvironmentVariables</key><dict>{envxml}</dict>"
        "</dict></plist>\n",
        encoding="utf-8",
    )
    return path


def test_an_injected_PYTHONPATH_is_refused(sandbox):
    """QA r14 Blocker: the environment can redirect a repo-owned interpreter.

    Exact Label and ProgramArguments, but PYTHONPATH makes our own python import someone
    else's code.
    """
    repo, templates, agents = sandbox
    args = ["{{PYTHON}}", "{{REBALANCE_DIR}}/scripts/health_issue_reporter.py"]
    _template(templates, "com.rebalance-os.health-check", args)
    _touch_executable(f"{repo}/.venv/bin/python")
    _touch_executable(f"{repo}/scripts/health_issue_reporter.py")
    real = [a.replace("{{REBALANCE_DIR}}", str(repo)).replace("{{PYTHON}}", f"{repo}/.venv/bin/python")
            for a in args]

    plist = _plist_with_env(agents, "com.rebalance-os.health-check", repo, real,
                            {"PYTHONPATH": "/opt/attacker"})

    result = _run(sandbox, "--apply")

    assert plist.exists()
    assert result.returncode == 1


def test_loader_hijack_variables_are_refused(sandbox):
    repo, templates, agents = sandbox
    args = ["{{REBALANCE_DIR}}/scripts/alpha.sh"]
    _template(templates, "com.rebalance-os.alpha", args)
    _touch_executable(f"{repo}/scripts/alpha.sh")

    # Matched by family, so a variable nobody enumerated is covered too: PYTHONUSERBASE
    # (QA r15) points at a user-site dir whose sitecustomize.py python imports at startup,
    # and PYTHONNEVERHEARDOFIT stands in for whatever the next list would have missed.
    # Any variable the template did not ship, dangerous-looking or not. Enumerating the
    # dangerous ones was one list behind three rounds running (PYTHONUSERBASE, then BASH_ENV);
    # the set of ways an environment redirects a program does not close, so the rule is
    # "exactly what we rendered".
    for name in ("DYLD_INSERT_LIBRARIES", "LD_PRELOAD", "PATH", "PYTHONUSERBASE",
                 "BASH_ENV", "ENV", "PYTHONNEVERHEARDOFIT", "SOMETHING_NOBODY_LISTED"):
        plist = _plist_with_env(agents, "com.rebalance-os.alpha", repo,
                                [f"{repo}/scripts/alpha.sh"], {name: "/opt/attacker"})
        result = _run(sandbox, "--apply")
        assert plist.exists(), f"{name} must not be removable"
        assert result.returncode == 1
        plist.unlink()


def test_an_environment_variable_we_did_not_render_is_refused_and_named(sandbox):
    """Even a benign-looking one. pulse-sync really carries a hand-added PULSE_PUSH=false, so
    this refuses a real job on the operator's machine — deliberately.

    Three rounds of enumerating dangerous variables were each one behind. The set does not
    close, so the rule is "exactly what we rendered", and the cost is named: a refusal is loud
    and recoverable, a wrong deletion is neither.
    """
    repo, templates, agents = sandbox
    args = ["{{REBALANCE_DIR}}/scripts/alpha.sh"]
    _template(templates, "com.rebalance-os.alpha", args)
    _touch_executable(f"{repo}/scripts/alpha.sh")

    plist = _plist_with_env(agents, "com.rebalance-os.alpha", repo,
                            [f"{repo}/scripts/alpha.sh"], {"PULSE_PUSH": "false"})

    result = _run(sandbox, "--apply")

    assert plist.exists()
    assert result.returncode == 1
    # the refusal must NAME the variable, or the operator cannot act on it
    assert "environment differs: PULSE_PUSH" in result.stdout
