"""Integration tests for the experimental git-pulse collector."""

from __future__ import annotations

import os
import stat
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


COLLECT_SCRIPT = Path(__file__).resolve().parents[1] / "experimental" / "git-pulse" / "collect.sh"


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _write_date_stub(path: Path) -> None:
    _write_executable(
        path,
        textwrap.dedent(
            """\
            #!/usr/bin/env python3
            import sys
            from datetime import datetime, timezone

            args = sys.argv[1:]

            if args == ["+%s"]:
                print("1776750000")
                raise SystemExit(0)

            if args == ["+%Z"]:
                print("PDT")
                raise SystemExit(0)

            if args == ["+%z"]:
                print("-0700")
                raise SystemExit(0)

            if len(args) == 3 and args[0] == "-r" and args[2] == "+%Y-%m-%dT%H:%M:%SZ":
                dt = datetime.fromtimestamp(int(args[1]), tz=timezone.utc)
                print(dt.strftime("%Y-%m-%dT%H:%M:%SZ"))
                raise SystemExit(0)

            if len(args) == 5 and args[0] == "-j" and args[1] == "-f" and args[4] == "+%s":
                dt = datetime.strptime(args[3], "%Y-%m-%dT%H:%M:%S%z")
                print(int(dt.timestamp()))
                raise SystemExit(0)

            raise SystemExit(f"unsupported date invocation: {args}")
            """
        ),
    )


def _write_scutil_stub(path: Path) -> None:
    _write_executable(
        path,
        textwrap.dedent(
            """\
            #!/bin/sh
            if [ "$1" = "--get" ] && [ "$2" = "ComputerName" ]; then
              printf '%s\n' "Noel's MacBook Pro 14"
              exit 0
            fi
            exit 1
            """
        ),
    )


def _write_git_stub(
    path: Path,
    local_repo: Path,
    sync_repo: Path,
    *,
    diff_cached_exit_code: int = 1,
    unborn_repos: tuple[Path, ...] = (),
) -> None:
    _write_executable(
        path,
        textwrap.dedent(
            f"""\
            #!/usr/bin/env python3
            import sys
            from pathlib import Path

            local_repo = {str(local_repo)!r}
            sync_repo = {str(sync_repo)!r}
            unborn_repos = {tuple(str(repo) for repo in unborn_repos)!r}
            args = sys.argv[1:]

            if len(args) >= 3 and args[0] == "-C":
                repo_path = args[1]
                repo_args = args[2:]

                if repo_args[:3] == ["rev-parse", "--verify", "HEAD"]:
                    if repo_path in unborn_repos:
                        raise SystemExit(128)
                    if repo_path in {{local_repo, sync_repo}}:
                        print("deadbeef")
                        raise SystemExit(0)

                if repo_path == local_repo and repo_args[:2] == ["log", "-g"]:
                    print("HEAD@{{2026-04-20T14:32:15-07:00}}\\t1234567890abcdef\\tcommit:\\tMigrated local commit")
                    raise SystemExit(0)

                if repo_path == local_repo and repo_args[:2] == ["branch", "--contains"]:
                    print("main")
                    raise SystemExit(0)

                if repo_path == sync_repo and repo_args[:2] == ["rev-parse", "--verify"]:
                    print("deadbeef")
                    raise SystemExit(0)

                if repo_path == sync_repo and repo_args[:2] == ["pull", "--quiet"]:
                    raise SystemExit(0)

            if args[:3] == ["add", "-A", "--"]:
                raise SystemExit(0)

            if args[:2] == ["add", "--"]:
                raise SystemExit(0)

            if args[:2] == ["diff", "--cached"]:
                raise SystemExit({diff_cached_exit_code})

            if args and args[0] == "commit":
                raise SystemExit(0)

            if args[:2] == ["rev-parse", "--abbrev-ref"]:
                print("origin/main")
                raise SystemExit(0)

            if args and args[0] == "push":
                raise SystemExit(0)

            raise SystemExit(f"unsupported git invocation: {{args}}")
            """
        ),
    )


class GitPulseCollectCliTests(unittest.TestCase):
    def test_collect_backfill_skips_rows_already_present_in_pulse_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            bin_dir = home / "bin"
            config_dir = home / ".config" / "git-pulse"
            sync_repo = config_dir / "repo"
            devices_dir = sync_repo / "devices"
            local_repo = home / "code" / "sample-repo"

            bin_dir.mkdir(parents=True)
            devices_dir.mkdir(parents=True)
            (sync_repo / ".git").mkdir()
            (local_repo / ".git").mkdir(parents=True)

            _write_date_stub(bin_dir / "date")
            _write_scutil_stub(bin_dir / "scutil")
            _write_git_stub(
                bin_dir / "git",
                local_repo,
                sync_repo,
                diff_cached_exit_code=0,
            )

            (config_dir / "config.sh").write_text(
                textwrap.dedent(
                    f"""\
                    repos=("{local_repo}")
                    sync_repo_dir="{sync_repo}"
                    device_id="noels-macbook-pro-14"
                    device_name="Noel's MacBook Pro 14"
                    hostname="Noel's MacBook Pro 14"
                    """
                )
            )
            (config_dir / "last-run").write_text("0\n")

            (devices_dir / "noels-macbook-pro-14.yaml").write_text(
                textwrap.dedent(
                    """\
                    schema_version: 2
                    device_id: "noels-macbook-pro-14"
                    device_name: "Noel's MacBook Pro 14"
                    hostname: "Noel's MacBook Pro 14"
                    host_tag: "Noels-MacBook-Pro-14"
                    timezone_name: "PDT"
                    utc_offset: "-0700"
                    pulse_file: "pulse-noels-macbook-pro-14.md"
                    """
                )
            )
            (sync_repo / "pulse-noels-macbook-pro-14.md").write_text(
                textwrap.dedent(
                    """\
                    # Git pulse — Noel's MacBook Pro 14

                    <!-- Append-only chronological log. Tab-separated columns:
                         epoch_utc \t timestamp_utc \t repo \t branch \t short-sha \t subject
                         device_id: noels-macbook-pro-14
                         canonical time: UTC
                         Oldest at top; newest at bottom. Grep-friendly; not meant for pretty rendering. -->

                    1776720735\t2026-04-20T21:32:15Z\tsample-repo\tmain\t1234567\tMigrated local commit
                    """
                )
            )

            subprocess.run(
                ["/bin/bash", str(COLLECT_SCRIPT)],
                check=True,
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "HOME": str(home),
                    "PATH": f"{bin_dir}:{os.environ['PATH']}",
                },
            )

            pulse_text = (sync_repo / "pulse-noels-macbook-pro-14.md").read_text()

        self.assertEqual(pulse_text.count("Migrated local commit"), 1)

    def test_collect_skips_unborn_repo_without_failing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            bin_dir = home / "bin"
            config_dir = home / ".config" / "git-pulse"
            sync_repo = config_dir / "repo"
            devices_dir = sync_repo / "devices"
            local_repo = home / "code" / "sample-repo"
            unborn_repo = home / "code" / "empty-repo"

            bin_dir.mkdir(parents=True)
            devices_dir.mkdir(parents=True)
            (sync_repo / ".git").mkdir()
            (local_repo / ".git").mkdir(parents=True)
            (unborn_repo / ".git").mkdir(parents=True)

            _write_date_stub(bin_dir / "date")
            _write_scutil_stub(bin_dir / "scutil")
            _write_git_stub(
                bin_dir / "git",
                local_repo,
                sync_repo,
                unborn_repos=(unborn_repo,),
            )

            (config_dir / "config.sh").write_text(
                textwrap.dedent(
                    f"""\
                    repos=("{local_repo}" "{unborn_repo}")
                    sync_repo_dir="{sync_repo}"
                    device_id="noels-macbook-pro-14"
                    device_name="Noel's MacBook Pro 14"
                    hostname="Noel's MacBook Pro 14"
                    """
                )
            )
            (config_dir / "last-run").write_text("0\n")

            result = subprocess.run(
                ["/bin/bash", str(COLLECT_SCRIPT)],
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "HOME": str(home),
                    "PATH": f"{bin_dir}:{os.environ['PATH']}",
                },
            )

            pulse_text = (sync_repo / "pulse-noels-macbook-pro-14.md").read_text()

        self.assertEqual(result.returncode, 0, msg=result.stderr + result.stdout)
        self.assertIn(f"Skipping {unborn_repo}: no commits yet", result.stderr)
        self.assertIn("Migrated local commit", pulse_text)

    def test_collect_self_migrates_legacy_slugged_device_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            bin_dir = home / "bin"
            config_dir = home / ".config" / "git-pulse"
            sync_repo = config_dir / "repo"
            devices_dir = sync_repo / "devices"
            local_repo = home / "code" / "sample-repo"

            bin_dir.mkdir(parents=True)
            devices_dir.mkdir(parents=True)
            (sync_repo / ".git").mkdir()
            (local_repo / ".git").mkdir(parents=True)

            _write_date_stub(bin_dir / "date")
            _write_scutil_stub(bin_dir / "scutil")
            _write_git_stub(bin_dir / "git", local_repo, sync_repo)

            (config_dir / "config.sh").write_text(
                textwrap.dedent(
                    f"""\
                    repos=("{local_repo}")
                    sync_repo_dir="{sync_repo}"
                    device_id="noel-s-macbook-pro-14"
                    device_name="Noel's MacBook Pro 14"
                    hostname="Noel's MacBook Pro 14"
                    """
                )
            )
            (config_dir / "last-run").write_text("0\n")

            (devices_dir / "noel-s-macbook-pro-14.yaml").write_text(
                textwrap.dedent(
                    """\
                    schema_version: 1
                    device_id: "noel-s-macbook-pro-14"
                    device_name: "Noel's MacBook Pro 14"
                    hostname: "Noel's MacBook Pro 14"
                    host_tag: "Noel-s-MacBook-Pro-14"
                    timezone_name: "PDT"
                    utc_offset: "-0700"
                    pulse_file: "pulse-noel-s-macbook-pro-14.md"
                    """
                )
            )
            (sync_repo / "pulse-noel-s-macbook-pro-14.md").write_text(
                textwrap.dedent(
                    """\
                    # Git pulse — Noel's MacBook Pro 14

                    <!-- Append-only chronological log. Tab-separated columns:
                         epoch_utc \t timestamp_utc \t repo \t branch \t short-sha \t subject
                         device_id: noel-s-macbook-pro-14
                         canonical time: UTC
                         Oldest at top; newest at bottom. Grep-friendly; not meant for pretty rendering. -->

                    """
                )
            )

            subprocess.run(
                ["/bin/bash", str(COLLECT_SCRIPT)],
                check=True,
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "HOME": str(home),
                    "PATH": f"{bin_dir}:{os.environ['PATH']}",
                },
            )

            config_text = (config_dir / "config.sh").read_text()
            new_metadata = (devices_dir / "noels-macbook-pro-14.yaml").read_text()
            new_pulse = (sync_repo / "pulse-noels-macbook-pro-14.md").read_text()

        self.assertIn('device_id="noels-macbook-pro-14"', config_text)
        self.assertNotIn('device_id="noel-s-macbook-pro-14"', config_text)
        self.assertIn('device_id: "noels-macbook-pro-14"', new_metadata)
        self.assertIn('pulse_file: "pulse-noels-macbook-pro-14.md"', new_metadata)
        self.assertIn("device_id: noels-macbook-pro-14", new_pulse)
        self.assertIn("Migrated local commit", new_pulse)
        self.assertFalse((devices_dir / "noel-s-macbook-pro-14.yaml").exists())
        self.assertFalse((sync_repo / "pulse-noel-s-macbook-pro-14.md").exists())


if __name__ == "__main__":
    unittest.main()
