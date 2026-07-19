"""Regression coverage for the pulse mirror reconcile step (GH-152).

`reconcile_pulse_mirror` gives `pulse_sync` the `git pull --rebase` it lacked, so
the export mirror tracks origin instead of freezing (which reported live
collectors as stale). These exercise it against real throwaway git repos.
"""

import subprocess
from pathlib import Path

import pytest

from rebalance.ingest.pulse import PulseReconcileError, reconcile_pulse_mirror


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=str(cwd),
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _commit(repo: Path, name: str, content: str) -> None:
    (repo / name).write_text(content)
    _git(repo, "add", name)
    _git(repo, "commit", "-m", f"add {name}")


def _origin_and_clone(tmp: Path) -> tuple[Path, Path, Path]:
    origin = tmp / "origin.git"
    subprocess.run(["git", "init", "--bare", "-b", "main", str(origin)], check=True, capture_output=True)
    seed = tmp / "seed"
    seed.mkdir()
    _git(seed, "init", "-b", "main")
    _commit(seed, "base.txt", "base\n")
    _git(seed, "remote", "add", "origin", str(origin))
    _git(seed, "push", "-u", "origin", "main")
    clone = tmp / "clone"
    subprocess.run(["git", "clone", str(origin), str(clone)], check=True, capture_output=True)
    return origin, seed, clone


def test_not_a_git_repo_raises(tmp_path: Path) -> None:
    with pytest.raises(PulseReconcileError, match="not a git repo"):
        reconcile_pulse_mirror(tmp_path)


def test_pulls_new_origin_commits(tmp_path: Path) -> None:
    _origin, seed, clone = _origin_and_clone(tmp_path)
    _commit(seed, "upstream.txt", "from origin\n")
    _git(seed, "push", "origin", "main")

    reconcile_pulse_mirror(clone)  # no raise

    assert (clone / "upstream.txt").exists()


def test_local_commits_preserved_on_rebase(tmp_path: Path) -> None:
    _origin, seed, clone = _origin_and_clone(tmp_path)
    _commit(clone, "local.txt", "local pulse write\n")  # unpushed local commit
    _commit(seed, "upstream.txt", "from origin\n")
    _git(seed, "push", "origin", "main")

    reconcile_pulse_mirror(clone)

    assert (clone / "upstream.txt").exists()  # origin integrated
    assert (clone / "local.txt").exists()  # local commit replayed on top
    log = _git(clone, "log", "--oneline")
    assert "local.txt" in log and "upstream.txt" in log


def test_conflict_raises_and_leaves_no_lingering_rebase(tmp_path: Path) -> None:
    _origin, seed, clone = _origin_and_clone(tmp_path)
    _commit(clone, "base.txt", "clone edit\n")  # both sides touch base.txt
    _commit(seed, "base.txt", "origin edit\n")
    _git(seed, "push", "origin", "main")

    with pytest.raises(PulseReconcileError, match="pull --rebase failed"):
        reconcile_pulse_mirror(clone)

    # The failed rebase was aborted, so the next run starts clean.
    assert not (clone / ".git" / "rebase-merge").exists()
    assert not (clone / ".git" / "rebase-apply").exists()


def test_rebase_in_progress_defers(tmp_path: Path) -> None:
    _origin, _seed, clone = _origin_and_clone(tmp_path)
    (clone / ".git" / "rebase-merge").mkdir()
    with pytest.raises(PulseReconcileError, match="already in progress"):
        reconcile_pulse_mirror(clone)
