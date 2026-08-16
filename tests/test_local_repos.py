"""Tests for local checkout discovery (ingest/local_repos.py, Phase 6.1).

Builds real throwaway git repos (with a local bare 'remote') so unpushed
counts and origin parsing are exercised genuinely — no network, no mocks of
git itself.
"""

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rebalance.ingest.local_repos import (
    LocalRepo,
    parse_github_full_name,
    scan_local_repos,
    unpushed_work,
    walk_repo_candidates,
)


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True, capture_output=True,
        env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
             "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
             "PATH": "/usr/bin:/bin"},
    )


def _make_repo(root: Path, name: str, *, origin: str | None, commits_after_push: int = 0):
    repo = root / name
    repo.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    (repo / "f.txt").write_text("1")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "c1")
    if origin:
        bare = root / f"{name}-remote.git"
        subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True, capture_output=True)
        _git(repo, "remote", "add", "origin", str(bare))
        _git(repo, "push", "-q", "-u", "origin", "main")
        # Point origin at a GitHub-shaped URL AFTER pushing, so full_name
        # parses while upstream tracking still works against the local bare.
        _git(repo, "remote", "set-url", "origin", origin)
        _git(repo, "config", "remote.origin.fetch", "+refs/heads/*:refs/remotes/origin/*")
    for i in range(commits_after_push):
        (repo / "f.txt").write_text(f"x{i}")
        _git(repo, "add", ".")
        _git(repo, "commit", "-q", "-m", f"local-{i}")
    return repo


class ParseFullNameTests(unittest.TestCase):
    def test_ssh_and_https_and_trailing_git(self):
        self.assertEqual(parse_github_full_name("git@github.com:acme/site.git"), "acme/site")
        self.assertEqual(parse_github_full_name("https://github.com/acme/site"), "acme/site")
        self.assertEqual(parse_github_full_name("https://github.com/acme/site.git/"), "acme/site")
        self.assertIsNone(parse_github_full_name("https://gitlab.com/acme/site"))
        self.assertIsNone(parse_github_full_name(""))


class ScanTests(unittest.TestCase):
    def test_scan_finds_repos_counts_unpushed_and_filters_non_github(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_repo(root, "pushed", origin="git@github.com:acme/pushed.git")
            _make_repo(root, "ahead", origin="git@github.com:acme/ahead.git", commits_after_push=2)
            _make_repo(root, "no-origin", origin=None)
            (root / "not-a-repo").mkdir()

            repos = scan_local_repos([str(root)])
            by_name = {r.full_name: r for r in repos}

            self.assertEqual(set(by_name), {"acme/pushed", "acme/ahead"})  # github_only drops no-origin
            self.assertEqual(by_name["acme/pushed"].unpushed_commits, 0)
            self.assertEqual(by_name["acme/ahead"].unpushed_commits, 2)
            self.assertEqual(by_name["acme/ahead"].branch, "main")

            stale = unpushed_work(repos)
            self.assertEqual([r.full_name for r in stale], ["acme/ahead"])

    def test_no_upstream_counts_as_unpushed_work(self):
        repo = LocalRepo(
            path=Path("/x"), origin_url="git@github.com:a/b.git",
            full_name="a/b", branch="main", unpushed_commits=None,
        )
        self.assertEqual(unpushed_work([repo]), [repo])

    def test_no_roots_configured_means_scanning_off(self):
        with patch("rebalance.ingest.config.get_local_repo_roots", return_value=[]):
            self.assertEqual(scan_local_repos(), [])

    def test_walk_respects_max_depth(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            deep = root / "a" / "b" / "c" / "repo"
            deep.mkdir(parents=True)
            (deep / ".git").mkdir()
            self.assertEqual(walk_repo_candidates(root, max_depth=2), [])
            self.assertEqual(walk_repo_candidates(root, max_depth=4), [deep])


class DiscoveryIntegrationTests(unittest.TestCase):
    def test_local_candidates_carry_local_scan_provenance(self):
        from rebalance.ingest.preflight import discover_candidates

        fake = LocalRepo(
            path=Path("/Users/op/GH/forgotten"),
            origin_url="git@github.com:acme/forgotten.git",
            full_name="acme/forgotten", branch="main", unpushed_commits=3,
        )
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault"
            vault.mkdir()
            with patch("rebalance.ingest.preflight.scan_local_repos", return_value=[fake]):
                discovery = discover_candidates(
                    vault_path=vault,
                    registry_path=vault / "Projects" / "00-project-registry.md",
                    github_token=None,  # remote discovery off; local still runs
                )
        candidates = discovery.potential_projects
        local = [c for c in candidates if c["provenance"] == "local-scan"]
        self.assertEqual(len(local), 1)
        self.assertEqual(local[0]["name"], "acme/forgotten")
        self.assertIn("3 unpushed commit(s) on main", local[0]["summary"])
        self.assertEqual(local[0]["repos"], ["acme/forgotten"])


if __name__ == "__main__":
    unittest.main()


class DetachedHeadTests(unittest.TestCase):
    def test_detached_head_is_not_flagged_as_unpushed(self):
        # Review finding: detached HEAD can't have an upstream by definition —
        # flagging it is noise, not signal.
        detached = LocalRepo(
            path=Path("/x"), origin_url="git@github.com:a/b.git",
            full_name="a/b", branch="HEAD", unpushed_commits=None,
        )
        named_no_upstream = LocalRepo(
            path=Path("/y"), origin_url="git@github.com:a/c.git",
            full_name="a/c", branch="feat/x", unpushed_commits=None,
        )
        self.assertEqual(unpushed_work([detached, named_no_upstream]), [named_no_upstream])
