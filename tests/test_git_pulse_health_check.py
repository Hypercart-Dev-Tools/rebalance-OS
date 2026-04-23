"""Integration tests for the git-pulse health-check CLI."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "experimental"
    / "git-pulse"
    / "health-check.py"
)


def _git(repo: Path, *args: str, env_override: dict | None = None) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "test",
        "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_COMMITTER_NAME": "test",
        "GIT_COMMITTER_EMAIL": "test@example.com",
    }
    if env_override:
        env.update(env_override)
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
        env=env,
    )


class HealthCheckCliTests(unittest.TestCase):
    def _prepare_sync_repo(self) -> Path:
        tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(tmpdir.cleanup)
        sync = Path(tmpdir.name) / "sync"
        sync.mkdir()
        _git(sync.parent, "init", str(sync), "--initial-branch=main", "--quiet")
        devices_dir = sync / "devices"
        devices_dir.mkdir()
        return sync

    def _write_device(
        self,
        sync: Path,
        device_id: str,
        display: str,
        *,
        extra_yaml: str = "",
        pulse_rows: str = "",
    ) -> None:
        (sync / "devices" / f"{device_id}.yaml").write_text(
            textwrap.dedent(
                f"""\
                schema_version: 2
                device_id: "{device_id}"
                device_name: "{display}"
                pulse_file: "pulse-{device_id}.md"
                {extra_yaml}\
                """
            )
        )
        (sync / f"pulse-{device_id}.md").write_text(
            textwrap.dedent(
                f"""\
                # {display}
                {pulse_rows}"""
            )
        )

    def _commit_at(self, sync: Path, message: str, when_utc: datetime, paths: list[str]) -> None:
        iso = when_utc.strftime("%Y-%m-%dT%H:%M:%S +0000")
        _git(sync, "add", *paths)
        _git(
            sync,
            "commit",
            "-m",
            message,
            "--quiet",
            env_override={
                "GIT_AUTHOR_DATE": iso,
                "GIT_COMMITTER_DATE": iso,
            },
        )

    def _run_health(self, sync: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--sync-repo-dir",
                str(sync),
                *args,
            ],
            capture_output=True,
            text=True,
        )

    def test_alive_device_exits_zero(self) -> None:
        sync = self._prepare_sync_repo()
        self._write_device(sync, "alpha", "Alpha Mac")
        recent = datetime.now(timezone.utc) - timedelta(hours=1)
        self._commit_at(
            sync, "recent alpha commit", recent, ["devices/alpha.yaml", "pulse-alpha.md"]
        )
        result = self._run_health(sync)
        self.assertEqual(result.returncode, 0, msg=result.stderr + result.stdout)
        self.assertIn("ALIVE", result.stdout)
        self.assertIn("Alpha Mac", result.stdout)

    def test_stale_device_exits_one(self) -> None:
        sync = self._prepare_sync_repo()
        self._write_device(sync, "beta", "Beta Mac")
        stale = datetime.now(timezone.utc) - timedelta(hours=6)
        self._commit_at(
            sync, "stale beta commit", stale, ["devices/beta.yaml", "pulse-beta.md"]
        )
        result = self._run_health(sync, "--warn-hours", "3", "--alert-hours", "24")
        self.assertEqual(result.returncode, 1, msg=result.stderr + result.stdout)
        self.assertIn("STALE", result.stdout)

    def test_recent_metadata_heartbeat_keeps_quiet_device_alive(self) -> None:
        sync = self._prepare_sync_repo()
        old_commit = datetime.now(timezone.utc) - timedelta(hours=12)
        recent_scan = datetime.now(timezone.utc) - timedelta(minutes=20)
        self._write_device(
            sync,
            "quiet",
            "Quiet Mac",
            pulse_rows=(
                f'{int(old_commit.timestamp())}\t{old_commit.strftime("%Y-%m-%dT%H:%M:%SZ")}'
                "\trebalance-OS\tmain\tdeadbee\tEarlier local commit\n"
            ),
        )
        self._commit_at(
            sync,
            "quiet pulse seed",
            old_commit,
            ["devices/quiet.yaml", "pulse-quiet.md"],
        )
        (sync / "devices" / "quiet.yaml").write_text(
            textwrap.dedent(
                f"""\
                schema_version: 2
                device_id: "quiet"
                device_name: "Quiet Mac"
                pulse_file: "pulse-quiet.md"
                last_scan_epoch: "{int(recent_scan.timestamp())}"
                last_scan_utc: "{recent_scan.strftime("%Y-%m-%dT%H:%M:%SZ")}"
                """
            )
        )
        self._commit_at(
            sync,
            "quiet metadata heartbeat",
            recent_scan,
            ["devices/quiet.yaml"],
        )
        result = self._run_health(sync, "--warn-hours", "3", "--alert-hours", "24")
        self.assertEqual(result.returncode, 0, msg=result.stderr + result.stdout)
        self.assertIn("ALIVE", result.stdout)
        self.assertIn("Quiet Mac", result.stdout)
        self.assertIn("last pulse update", result.stdout)
        self.assertIn("last local commit", result.stdout)

    def test_alert_device_exits_two(self) -> None:
        sync = self._prepare_sync_repo()
        self._write_device(sync, "gamma", "Gamma Mac")
        ancient = datetime.now(timezone.utc) - timedelta(days=5)
        self._commit_at(
            sync,
            "ancient gamma commit",
            ancient,
            ["devices/gamma.yaml", "pulse-gamma.md"],
        )
        result = self._run_health(sync, "--warn-hours", "3", "--alert-hours", "24")
        self.assertEqual(result.returncode, 2, msg=result.stderr + result.stdout)
        self.assertIn("ALERT", result.stdout)

    def test_metadata_without_pulse_file_is_flagged(self) -> None:
        sync = self._prepare_sync_repo()
        # Metadata exists but pulse file is missing on disk
        (sync / "devices" / "delta.yaml").write_text(
            textwrap.dedent(
                """\
                schema_version: 2
                device_id: "delta"
                device_name: "Delta Mac"
                pulse_file: "pulse-delta.md"
                """
            )
        )
        # And at least one alive device so the overall exit handling still runs
        self._write_device(sync, "alpha", "Alpha Mac")
        self._commit_at(
            sync,
            "seed",
            datetime.now(timezone.utc) - timedelta(hours=1),
            ["devices/alpha.yaml", "pulse-alpha.md", "devices/delta.yaml"],
        )
        result = self._run_health(sync)
        self.assertIn("Delta Mac", result.stdout)
        self.assertIn("pulse-delta.md missing on disk", result.stdout)

    def test_missing_heartbeat_falls_back_to_pulse_pushes(self) -> None:
        sync = self._prepare_sync_repo()
        self._write_device(sync, "legacy", "Legacy Mac")
        stale = datetime.now(timezone.utc) - timedelta(hours=6)
        self._commit_at(
            sync,
            "legacy pulse commit",
            stale,
            ["devices/legacy.yaml", "pulse-legacy.md"],
        )
        result = self._run_health(sync, "--warn-hours", "3", "--alert-hours", "24")
        self.assertEqual(result.returncode, 1, msg=result.stderr + result.stdout)
        self.assertIn("heartbeat unavailable; using pulse-file pushes", result.stdout)


if __name__ == "__main__":
    unittest.main()
