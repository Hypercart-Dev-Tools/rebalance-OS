"""Integration tests for the experimental git-pulse installer."""

from __future__ import annotations

import os
import stat
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


INSTALL_SCRIPT = (
    Path(__file__).resolve().parents[1] / "experimental" / "git-pulse" / "install.sh"
)


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _git(repo: Path, *args: str, env_override: dict[str, str] | None = None) -> None:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "test",
        "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_COMMITTER_NAME": "test",
        "GIT_COMMITTER_EMAIL": "test@example.com",
    }
    if env_override:
        env.update(env_override)
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )


class GitPulseInstallCliTests(unittest.TestCase):
    def test_install_discovers_local_github_repos_and_updates_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            path_bin = home / "path-bin"
            launch_agents = home / "Library" / "LaunchAgents"
            config_dir = home / ".config" / "git-pulse"
            sync_repo = config_dir / "repo"
            roots_dir = home / "Documents" / "GH Repos"
            github_repo = roots_dir / "alpha"
            non_github_repo = roots_dir / "beta"

            path_bin.mkdir(parents=True)
            launch_agents.mkdir(parents=True)
            sync_repo.mkdir(parents=True)
            roots_dir.mkdir(parents=True)

            _write_executable(
                path_bin / "launchctl",
                "#!/bin/sh\nexit 0\n",
            )

            _git(sync_repo.parent, "init", str(sync_repo), "--initial-branch=main", "--quiet")
            _git(roots_dir, "init", str(github_repo), "--initial-branch=main", "--quiet")
            _git(roots_dir, "init", str(non_github_repo), "--initial-branch=main", "--quiet")
            _git(github_repo, "remote", "add", "origin", "git@github.com:example/alpha.git")
            _git(non_github_repo, "remote", "add", "origin", "git@gitlab.com:example/beta.git")

            (config_dir / "config.sh").write_text(
                textwrap.dedent(
                    f"""\
                    repos=()
                    repo_roots=("{roots_dir}")
                    repo_discovery_mode="append"
                    sync_repo_dir="{sync_repo}"
                    device_id="test-device"
                    device_name="Test Device"
                    hostname="Test Device"
                    """
                )
            )

            subprocess.run(
                ["/bin/bash", str(INSTALL_SCRIPT)],
                check=True,
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "HOME": str(home),
                    "PATH": f"{path_bin}:{os.environ['PATH']}",
                },
            )

            config_text = (config_dir / "config.sh").read_text()

        self.assertIn(str(github_repo), config_text)
        self.assertNotIn(str(non_github_repo), config_text)

    def test_copy_mode_installs_working_health_launcher_with_shared_module(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            path_bin = home / "path-bin"
            launch_agents = home / "Library" / "LaunchAgents"
            config_dir = home / ".config" / "git-pulse"
            sync_repo = config_dir / "repo"
            devices_dir = sync_repo / "devices"

            path_bin.mkdir(parents=True)
            launch_agents.mkdir(parents=True)
            devices_dir.mkdir(parents=True)

            _write_executable(
                path_bin / "launchctl",
                "#!/bin/sh\nexit 0\n",
            )

            _git(sync_repo.parent, "init", str(sync_repo), "--initial-branch=main", "--quiet")

            (config_dir / "config.sh").write_text(
                textwrap.dedent(
                    f"""\
                    repos=()
                    sync_repo_dir="{sync_repo}"
                    device_id="test-device"
                    device_name="Test Device"
                    hostname="Test Device"
                    """
                )
            )

            (devices_dir / "test-device.yaml").write_text(
                textwrap.dedent(
                    """\
                    schema_version: 2
                    device_id: "test-device"
                    device_name: "Test Device"
                    pulse_file: "pulse-test-device.md"
                    """
                )
            )
            (sync_repo / "pulse-test-device.md").write_text("# Test Device\n")
            _git(sync_repo, "add", "devices/test-device.yaml", "pulse-test-device.md")
            _git(sync_repo, "commit", "-m", "seed", "--quiet")

            install = subprocess.run(
                ["/bin/bash", str(INSTALL_SCRIPT)],
                check=True,
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "HOME": str(home),
                    "PATH": f"{path_bin}:{os.environ['PATH']}",
                },
            )

            self.assertIn("Health install:", install.stdout)
            self.assertTrue((home / "bin" / "git-pulse-health").exists())
            self.assertTrue((home / "bin" / "pulse_common.py").exists())
            self.assertTrue((home / "bin" / "EXEC-SUMMARY.md").exists())
            self.assertTrue((home / "bin" / "TEAM-EXEC-SUMMARY.md").exists())

            health = subprocess.run(
                [
                    str(home / "bin" / "git-pulse-health"),
                    "--sync-repo-dir",
                    str(sync_repo),
                    "--warn-hours",
                    "999",
                    "--alert-hours",
                    "1999",
                ],
                capture_output=True,
                text=True,
                env={**os.environ, "HOME": str(home)},
            )

            self.assertEqual(health.returncode, 0, msg=health.stderr + health.stdout)
            self.assertIn("Test Device", health.stdout)


if __name__ == "__main__":
    unittest.main()
