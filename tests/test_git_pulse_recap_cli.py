"""Integration tests for the experimental git-pulse recap CLI."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


RECAP_SCRIPT = Path(__file__).resolve().parents[1] / "experimental" / "git-pulse" / "recap.py"


class GitPulseRecapCliTests(unittest.TestCase):
    def _run_recap(self, home: Path, *args: str) -> subprocess.CompletedProcess[str]:
        env = {
            **os.environ,
            "HOME": str(home),
        }
        return subprocess.run(
            [sys.executable, str(RECAP_SCRIPT), *args],
            capture_output=True,
            text=True,
            env=env,
        )

    def _prepare_home(self) -> tuple[Path, Path]:
        tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(tmpdir.cleanup)

        home = Path(tmpdir.name)
        config_dir = home / ".config" / "git-pulse"
        sync_repo = config_dir / "repo"

        (sync_repo / "reports").mkdir(parents=True)
        (sync_repo / ".git").mkdir()
        (config_dir / "config.sh").write_text(
            textwrap.dedent(
                f"""\
                repos=()
                sync_repo_dir="{sync_repo}"
                """
            )
        )

        return home, sync_repo

    def test_no_input_args_reads_reports_and_emits_markdown_recap(self) -> None:
        home, sync_repo = self._prepare_home()
        reports_dir = sync_repo / "reports"
        devices_dir = sync_repo / "devices"
        devices_dir.mkdir()

        (reports_dir / "alpha.tsv").write_text(
            textwrap.dedent(
                """\
                local_day\tlocal_time\tutc_time\tdevice_id\tdevice_name\trepo\tbranch\tshort_sha\tsubject
                2026-04-19\t09:00 UTC\t2026-04-19T16:00:00Z\tdev-a\tAlpha Mac\trepo-one\tmain\t1111111\tAlpha start
                2026-04-20\t10:00 UTC\t2026-04-20T17:00:00Z\tdev-a\tAlpha Mac\trepo-two\tfeature\t2222222\tAlpha feature
                """
            )
        )
        (reports_dir / "beta.tsv").write_text(
            textwrap.dedent(
                """\
                local_day\tlocal_time\tutc_time\tdevice_id\tdevice_name\trepo\tbranch\tshort_sha\tsubject
                2026-04-19\t09:00 UTC\t2026-04-19T16:00:00Z\tdev-a\tAlpha Mac\trepo-one\tmain\t1111111\tAlpha start
                2026-04-19\t08:30 UTC\t2026-04-19T15:30:00Z\tdev-b\tBeta Mac\trepo-one\trelease\t4444444\tBeta prep
                2026-04-20\t11:00 UTC\t2026-04-20T18:00:00Z\tdev-b\tBeta Mac\trepo-one\tmain\t3333333\tBeta follow-up
                """
            )
        )
        (reports_dir / "ignore.txt").write_text("not tsv\n")
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
        (devices_dir / "dev-c.yaml").write_text(
            textwrap.dedent(
                """\
                schema_version: 1
                device_id: "dev-c"
                device_name: "Gamma Mac"
                pulse_file: "pulse-dev-c.md"
                """
            )
        )
        (sync_repo / "pulse-dev-a.md").write_text("# alpha\n")
        (sync_repo / "pulse-dev-b.md").write_text("# beta\n")

        result = self._run_recap(home)

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        expected_path = sync_repo / "reports" / "2026-04-20-PARTIAL.md"
        self.assertIn(f"wrote: {expected_path}", result.stdout)
        self.assertTrue(expected_path.exists())

        output = expected_path.read_text()
        self.assertIn("# Git Pulse Executive Recap", output)
        self.assertIn("AGENT INSTRUCTIONS", output)
        self.assertIn("## Summary", output)
        self.assertIn("- Window: `2026-04-19` to `2026-04-20` (2 active days)", output)
        self.assertIn("- Repos covered: repo-one | repo-two", output)
        self.assertIn("- Commits: 4 across 2 repos from 2 machines", output)
        self.assertIn("<!-- TLDR:", output)
        self.assertIn("## By Repo", output)
        self.assertIn("### `repo-one`", output)
        self.assertIn("### `repo-two`", output)
        self.assertIn("<!-- FOCUS:", output)
        self.assertIn("**Commit themes:**", output)
        self.assertIn("## Observations", output)
        self.assertIn("<!-- OBSERVATIONS:", output)
        self.assertIn("## Appendix", output)
        self.assertIn("### Source Reports", output)
        self.assertIn("### Coverage", output)
        self.assertIn("### Machines Table", output)
        self.assertIn("### Repos Table", output)
        self.assertIn("### Cross-Machine Repos", output)
        self.assertIn("### Daily Activity", output)
        self.assertIn("### Recent Activity", output)
        self.assertIn("### Exceptions", output)
        self.assertIn("alpha.tsv", output)
        self.assertIn("beta.tsv", output)
        self.assertIn("Alpha Mac", output)
        self.assertIn("Beta Mac", output)
        self.assertIn("Gamma Mac", output)
        self.assertIn("repo-one", output)
        self.assertIn("repo-two", output)
        self.assertIn("Alpha feature", output)
        self.assertIn("Beta follow-up", output)
        self.assertIn("no rows in supplied reports", output)
        self.assertIn("missing `pulse-dev-c.md`", output)

    def test_auto_name_full_calendar_month(self) -> None:
        home, sync_repo = self._prepare_home()
        reports_dir = sync_repo / "reports"

        (reports_dir / "alpha.tsv").write_text(
            textwrap.dedent(
                """\
                local_day\tlocal_time\tutc_time\tdevice_id\tdevice_name\trepo\tbranch\tshort_sha\tsubject
                2026-02-01\t09:00 UTC\t2026-02-01T09:00:00Z\tdev-a\tAlpha Mac\trepo-one\tmain\t1111111\tFirst of Feb
                2026-02-15\t10:00 UTC\t2026-02-15T10:00:00Z\tdev-a\tAlpha Mac\trepo-one\tmain\t2222222\tMid Feb
                2026-02-28\t20:00 UTC\t2026-02-28T20:00:00Z\tdev-a\tAlpha Mac\trepo-one\tmain\t3333333\tLast of Feb
                """
            )
        )

        result = self._run_recap(home)

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        expected_path = sync_repo / "reports" / "2026-02-FEB.md"
        self.assertIn(f"wrote: {expected_path}", result.stdout)
        self.assertTrue(expected_path.exists())

    def test_auto_name_splits_multi_month_window(self) -> None:
        home, sync_repo = self._prepare_home()
        reports_dir = sync_repo / "reports"

        (reports_dir / "alpha.tsv").write_text(
            textwrap.dedent(
                """\
                local_day\tlocal_time\tutc_time\tdevice_id\tdevice_name\trepo\tbranch\tshort_sha\tsubject
                2026-02-15\t09:00 UTC\t2026-02-15T09:00:00Z\tdev-a\tAlpha Mac\trepo-one\tmain\t1111111\tFeb entry
                2026-03-10\t09:00 UTC\t2026-03-10T09:00:00Z\tdev-a\tAlpha Mac\trepo-one\tmain\t2222222\tMar entry
                """
            )
        )

        result = self._run_recap(home)

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        feb_path = sync_repo / "reports" / "2026-02-15-PARTIAL.md"
        mar_path = sync_repo / "reports" / "2026-03-10-PARTIAL.md"
        self.assertIn(f"wrote: {feb_path}", result.stdout)
        self.assertIn(f"wrote: {mar_path}", result.stdout)
        self.assertTrue(feb_path.exists())
        self.assertTrue(mar_path.exists())

        feb = feb_path.read_text()
        mar = mar_path.read_text()
        self.assertIn("Feb entry", feb)
        self.assertNotIn("Mar entry", feb)
        self.assertIn("Mar entry", mar)
        self.assertNotIn("Feb entry", mar)

    def test_output_option_writes_markdown_to_file(self) -> None:
        home, sync_repo = self._prepare_home()
        reports_dir = sync_repo / "reports"
        output_file = home / "reports" / "recap.md"
        output_file.parent.mkdir(parents=True)

        (reports_dir / "alpha.tsv").write_text(
            textwrap.dedent(
                """\
                local_day\tlocal_time\tutc_time\tdevice_id\tdevice_name\trepo\tbranch\tshort_sha\tsubject
                2026-04-20\t10:00 UTC\t2026-04-20T17:00:00Z\tdev-a\tAlpha Mac\trepo-one\tmain\t1111111\tAlpha start
                """
            )
        )

        result = self._run_recap(home, "--output", str(output_file))

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertTrue(output_file.exists())
        self.assertEqual(result.stdout, output_file.read_text())
        output = result.stdout
        self.assertIn("## Summary", output)
        self.assertIn("- Raw rows: 1", output)
        self.assertIn("- Unique rows: 1", output)
        self.assertIn("- Window: `2026-04-20` to `2026-04-20` (1 active days)", output)


if __name__ == "__main__":
    unittest.main()
