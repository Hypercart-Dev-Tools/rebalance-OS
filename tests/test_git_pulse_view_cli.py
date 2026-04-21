"""Integration tests for the experimental git-pulse viewer."""

from __future__ import annotations

import os
import stat
import subprocess
import tempfile
import textwrap
import unittest
from datetime import datetime, timezone
from pathlib import Path


VIEW_SCRIPT = Path(__file__).resolve().parents[1] / "experimental" / "git-pulse" / "view.sh"


def _epoch(value: str) -> int:
    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())


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
            from datetime import date, datetime, timedelta, timezone

            fixed_today = date(2026, 4, 20)
            args = sys.argv[1:]

            if args == ["+%Y-%m-%d"]:
                print(fixed_today.strftime("%Y-%m-%d"))
                raise SystemExit(0)

            if len(args) == 2 and args[0].startswith("-v-") and args[0].endswith("d") and args[1].startswith("+"):
                offset_days = int(args[0][3:-1])
                target = fixed_today - timedelta(days=offset_days)
                print(target.strftime(args[1][1:]))
                raise SystemExit(0)

            if len(args) == 3 and args[0] == "-r" and args[2].startswith("+"):
                dt = datetime.fromtimestamp(int(args[1]), tz=timezone.utc)
                print(dt.strftime(args[2][1:]))
                raise SystemExit(0)

            if len(args) == 5 and args[0] == "-j" and args[1] == "-f" and args[4] == "+%s":
                dt = datetime.strptime(args[3], "%Y-%m-%dT%H:%M:%S%z")
                print(int(dt.timestamp()))
                raise SystemExit(0)

            raise SystemExit(f"unsupported date invocation: {args}")
            """
        ),
    )


def _write_git_stub(path: Path, repo_path: Path) -> None:
    _write_executable(
        path,
        textwrap.dedent(
            f"""\
            #!/usr/bin/env python3
            import sys

            repo_path = {str(repo_path)!r}
            args = sys.argv[1:]

            if len(args) >= 3 and args[0] == "-C" and args[1] == repo_path:
                repo_args = args[2:]
                if repo_args[:2] == ["log", "-g"]:
                    print("HEAD@{{2026-04-19T15:30:00-07:00}}\\t1234567890abcdef\\tcommit:\\tUnsynced local commit")
                    raise SystemExit(0)
                if repo_args[:2] == ["branch", "--contains"]:
                    print("main")
                    raise SystemExit(0)

            raise SystemExit(f"unsupported git invocation: {{args}}")
            """
        ),
    )


class GitPulseViewCliTests(unittest.TestCase):
    def _run_view(self, *args: str) -> list[str]:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            bin_dir = home / "bin"
            config_dir = home / ".config" / "git-pulse"
            sync_repo = config_dir / "repo"
            devices_dir = sync_repo / "devices"

            bin_dir.mkdir(parents=True)
            devices_dir.mkdir(parents=True)
            (sync_repo / ".git").mkdir()

            _write_date_stub(bin_dir / "date")
            (config_dir / "config.sh").write_text(
                textwrap.dedent(
                    f"""\
                    repos=()
                    sync_repo_dir="{sync_repo}"
                    """
                )
            )

            (devices_dir / "dev-a.yaml").write_text(
                textwrap.dedent(
                    """\
                    schema_version: 1
                    device_id: "dev-a"
                    device_name: "Alpha Mac"
                    pulse_file: "pulse-dev-a.md"
                    """
                )
            )
            (devices_dir / "dev-b.yaml").write_text(
                textwrap.dedent(
                    """\
                    schema_version: 1
                    device_id: "dev-b"
                    device_name: "Beta Mac"
                    pulse_file: "pulse-dev-b.md"
                    """
                )
            )

            (sync_repo / "pulse-dev-a.md").write_text(
                textwrap.dedent(
                    f"""\
                    # Git pulse — Alpha Mac

                    {_epoch("2026-04-07T12:00:00Z")}	2026-04-07T12:00:00Z	rebalance-OS	main	aaaa111	Start 14-day window
                    {_epoch("2026-04-20T17:05:57Z")}	2026-04-20T17:05:57Z	rebalance-OS	main	bbbb222	Newest visible commit
                    """
                )
            )
            (sync_repo / "pulse-dev-b.md").write_text(
                textwrap.dedent(
                    f"""\
                    # Git pulse — Beta Mac

                    {_epoch("2026-04-06T23:59:59Z")}	2026-04-06T23:59:59Z	other-repo	main	cccc333	Outside 14-day window
                    """
                )
            )

            result = subprocess.run(
                ["/bin/bash", str(VIEW_SCRIPT), *args],
                check=True,
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "HOME": str(home),
                    "PATH": f"{bin_dir}:{os.environ['PATH']}",
                },
            )
            return result.stdout.splitlines()

    def test_days_output_is_flat_tsv_with_header(self) -> None:
        lines = self._run_view("--days", "14")

        self.assertEqual(
            lines[0],
            "local_day\tlocal_time\tutc_time\tdevice_id\tdevice_name\trepo\tbranch\tshort_sha\tsubject",
        )
        self.assertEqual(len(lines), 3)
        self.assertEqual(
            lines[1],
            "2026-04-07\t12:00 UTC\t2026-04-07T12:00:00Z\tdev-a\tAlpha Mac\trebalance-OS\tmain\taaaa111\tStart 14-day window",
        )
        self.assertEqual(
            lines[2],
            "2026-04-20\t17:05 UTC\t2026-04-20T17:05:57Z\tdev-a\tAlpha Mac\trebalance-OS\tmain\tbbbb222\tNewest visible commit",
        )

    def test_days_and_date_are_mutually_exclusive(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            bin_dir = home / "bin"
            config_dir = home / ".config" / "git-pulse"
            sync_repo = config_dir / "repo"
            devices_dir = sync_repo / "devices"

            bin_dir.mkdir(parents=True)
            devices_dir.mkdir(parents=True)
            (sync_repo / ".git").mkdir()

            _write_date_stub(bin_dir / "date")
            (config_dir / "config.sh").write_text(f'repos=()\nsync_repo_dir="{sync_repo}"\n')

            result = subprocess.run(
                ["/bin/bash", str(VIEW_SCRIPT), "--date", "2026-04-20", "--days", "14"],
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "HOME": str(home),
                    "PATH": f"{bin_dir}:{os.environ['PATH']}",
                },
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Use either --date or --days", result.stderr)

    def test_include_local_unsynced_writes_combined_output_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            bin_dir = home / "bin"
            config_dir = home / ".config" / "git-pulse"
            sync_repo = config_dir / "repo"
            devices_dir = sync_repo / "devices"
            local_repo = home / "code" / "sample-repo"
            output_file = home / "reports" / "combined.tsv"

            bin_dir.mkdir(parents=True)
            devices_dir.mkdir(parents=True)
            (sync_repo / ".git").mkdir()
            (local_repo / ".git").mkdir(parents=True)

            _write_date_stub(bin_dir / "date")
            _write_git_stub(bin_dir / "git", local_repo)
            (config_dir / "config.sh").write_text(
                textwrap.dedent(
                    f"""\
                    repos=("{local_repo}")
                    sync_repo_dir="{sync_repo}"
                    device_id="local-dev"
                    device_name="Local Mac"
                    hostname="local-mac"
                    """
                )
            )

            (devices_dir / "dev-a.yaml").write_text(
                textwrap.dedent(
                    """\
                    schema_version: 1
                    device_id: "dev-a"
                    device_name: "Alpha Mac"
                    pulse_file: "pulse-dev-a.md"
                    """
                )
            )
            (sync_repo / "pulse-dev-a.md").write_text(
                textwrap.dedent(
                    f"""\
                    # Git pulse — Alpha Mac

                    {_epoch("2026-04-20T17:05:57Z")}	2026-04-20T17:05:57Z	rebalance-OS	main	bbbb222	Synced peer commit
                    """
                )
            )

            result = subprocess.run(
                [
                    "/bin/bash",
                    str(VIEW_SCRIPT),
                    "--days",
                    "14",
                    "--include-local-unsynced",
                    "--output",
                    str(output_file),
                ],
                check=True,
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "HOME": str(home),
                    "PATH": f"{bin_dir}:{os.environ['PATH']}",
                },
            )

            output_lines = result.stdout.splitlines()
            saved_lines = output_file.read_text().splitlines()

        self.assertEqual(output_lines, saved_lines)
        self.assertEqual(
            output_lines[0],
            "local_day\tlocal_time\tutc_time\tdevice_id\tdevice_name\trepo\tbranch\tshort_sha\tsubject",
        )
        self.assertEqual(len(output_lines), 3)
        self.assertIn(
            "2026-04-19\t22:30 UTC\t2026-04-19T22:30:00Z\tlocal-dev\tLocal Mac\tsample-repo\tmain\t1234567\tUnsynced local commit",
            output_lines,
        )
        self.assertIn(
            "2026-04-20\t17:05 UTC\t2026-04-20T17:05:57Z\tdev-a\tAlpha Mac\trebalance-OS\tmain\tbbbb222\tSynced peer commit",
            output_lines,
        )


if __name__ == "__main__":
    unittest.main()
