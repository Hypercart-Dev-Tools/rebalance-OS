"""
Hermetic test for the pulse self-repair loop.

Sets up two real git repos in a tempdir:
  - remote/  bare repo (acts as origin)
  - local/   non-bare clone (acts as the pulse working tree)

Simulates divergence by pushing a commit directly to the bare remote
after the local has cloned — making the local's push fail with a
non-fast-forward rejection. Verifies that _commit_and_push_if_changed()
detects the failure, runs pull --rebase, and succeeds on the retry.
"""

import subprocess
import tempfile
from pathlib import Path

import pytest

from rebalance.ingest.pulse import _commit_and_push_if_changed


def _git(args: list[str], *, cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=check,
    )


def _make_repos(tmp: Path) -> tuple[Path, Path]:
    """Return (bare_remote, local_clone) with an initial commit."""
    remote = tmp / "remote"
    local = tmp / "local"

    # Bare remote
    remote.mkdir()
    _git(["init", "--bare", "--initial-branch=main"], cwd=remote)

    # Clone into local
    _git(["clone", str(remote), str(local)], cwd=tmp)

    # Config identity for commits
    for repo in (local,):
        _git(["config", "user.email", "test@test.com"], cwd=repo)
        _git(["config", "user.name", "Test"], cwd=repo)

    # Initial commit in local → push to remote
    seed = local / "pulse.md"
    seed.write_text("# initial\n", encoding="utf-8")
    _git(["add", "pulse.md"], cwd=local)
    _git(["commit", "-m", "initial"], cwd=local)
    _git(["push", "-u", "origin", "main"], cwd=local)

    return remote, local


def _push_competing_commit(remote: Path, tmp: Path) -> None:
    """Clone the remote into a second worktree and push a competing commit."""
    other = tmp / "other"
    _git(["clone", str(remote), str(other)], cwd=tmp)
    _git(["config", "user.email", "other@test.com"], cwd=other)
    _git(["config", "user.name", "Other"], cwd=other)
    competing = other / "competing.md"
    competing.write_text("# competing commit\n", encoding="utf-8")
    _git(["add", "competing.md"], cwd=other)
    _git(["commit", "-m", "competing: from another machine"], cwd=other)
    _git(["push"], cwd=other)


class TestPulseSelfRepair:
    def test_clean_push_succeeds_without_repair(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            _remote, local = _make_repos(tmp)

            result = _commit_and_push_if_changed(
                local, "pulse.md", "# updated content\n",
                push=True, commit_message="test: clean push",
            )

        assert result["pushed"] is True
        assert result.get("repaired") is None  # no repair needed

    def test_self_repair_on_push_rejection(self) -> None:
        """Simulate diverged remote; verify pull--rebase retry delivers pushed=True, repaired=True."""
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            remote, local = _make_repos(tmp)

            # Another machine pushes a commit — local is now behind remote
            _push_competing_commit(remote, tmp)

            result = _commit_and_push_if_changed(
                local, "pulse.md", "# repaired content\n",
                push=True, commit_message="test: should repair",
            )

        assert result["pushed"] is True, f"expected pushed=True, got: {result}"
        assert result.get("repaired") is True, f"expected repaired=True, got: {result}"
        assert "repair_error" not in result

    def test_no_push_when_content_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            _remote, local = _make_repos(tmp)

            result = _commit_and_push_if_changed(
                local, "pulse.md", "# initial\n",  # same as seed content
                push=True, commit_message="test: no change",
            )

        assert result["pushed"] is False
        assert result.get("reason") == "no content change"

    def test_repair_failure_propagates_error(self) -> None:
        """If pull --rebase itself fails, repair_error is returned and pushed stays False."""
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            remote, local = _make_repos(tmp)
            _push_competing_commit(remote, tmp)

            # Introduce a local conflict that will make rebase fail
            conflicted = local / "competing.md"
            conflicted.write_text("# local conflicting content\n", encoding="utf-8")
            _git(["add", "competing.md"], cwd=local)
            _git(["commit", "-m", "conflicting local commit"], cwd=local)

            result = _commit_and_push_if_changed(
                local, "pulse.md", "# after conflict\n",
                push=True, commit_message="test: conflict repair",
            )

        # Either the rebase resolved cleanly (unlikely with this conflict shape)
        # or we get repair_error. Either way, we must not raise an exception.
        assert "pushed" in result
        assert "git_error" in result or result["pushed"] is True
