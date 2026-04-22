"""Integration tests for the experimental team-recap CLI."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


RECAP_SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experimental"
    / "git-pulse"
    / "team-recap.py"
)


class TeamRecapCliTests(unittest.TestCase):
    def _run_recap(
        self, home: Path, *args: str
    ) -> subprocess.CompletedProcess[str]:
        env = {**os.environ, "HOME": str(home)}
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
        (sync_repo / "team-pulses").mkdir(parents=True)
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

    def test_auto_name_writes_monthly_team_recap(self) -> None:
        home, sync_repo = self._prepare_home()
        pulses_dir = sync_repo / "team-pulses"

        (pulses_dir / "octo-hello.tsv").write_text(
            textwrap.dedent(
                """\
                local_day\tlocal_time\tutc_time\tauthor_login\tauthor_name\trepo\tbranch\tshort_sha\tsubject\tkind\tpr_number
                2026-04-19\t09:00 UTC\t2026-04-19T09:00:00Z\talice\tAlice Smith\tocto/hello\t(default)\t1111111\tfeat: add widget\tcommit\t
                2026-04-20\t10:00 UTC\t2026-04-20T10:00:00Z\talice\tAlice Smith\tocto/hello\t(default)\t2222222\tfix: handle edge case\tcommit\t
                2026-04-20\t11:00 UTC\t2026-04-20T11:00:00Z\talice\tAlice Smith\tocto/hello\tfeature/widget\t\tAdd widget\tpr\t42
                2026-04-19\t12:00 UTC\t2026-04-19T12:00:00Z\tbob\tBob Jones\tocto/hello\t(default)\t3333333\tchore: bump deps\tcommit\t
                """
            )
        )

        result = self._run_recap(home)
        self.assertEqual(result.returncode, 0, msg=result.stderr)

        expected_path = sync_repo / "team-reports" / "2026-04-20-PARTIAL.md"
        self.assertIn(f"wrote: {expected_path}", result.stdout)
        self.assertTrue(expected_path.exists())

        output = expected_path.read_text()
        self.assertIn("# Git Pulse Team Recap", output)
        self.assertIn("AGENT INSTRUCTIONS", output)
        self.assertIn("## Summary", output)
        self.assertIn("- Window: `2026-04-19` to `2026-04-20` (2 active days)", output)
        self.assertIn("- Repos covered: octo/hello", output)
        self.assertIn("- Contributors: 2 — @alice, @bob", output)
        self.assertIn("- Commits: 3 · PRs: 1", output)
        self.assertIn("<!-- TLDR:", output)
        self.assertIn("## By Contributor", output)
        self.assertIn("### @alice (Alice Smith)", output)
        self.assertIn("### @bob (Bob Jones)", output)
        self.assertIn("<!-- FOCUS:", output)
        self.assertIn("**Activity by repo:**", output)
        self.assertIn("**PRs (1):**", output)
        self.assertIn("#42", output)
        self.assertIn("## Observations", output)
        self.assertIn("<!-- OBSERVATIONS:", output)
        self.assertIn("## Appendix", output)
        self.assertIn("### Source TSVs", output)
        self.assertIn("### Contributors Table", output)
        self.assertIn("### Repos Table", output)
        self.assertIn("### Daily Activity", output)
        self.assertIn("### Recent Activity", output)
        self.assertIn("### Exceptions", output)

    def test_output_option_writes_single_file(self) -> None:
        home, sync_repo = self._prepare_home()
        pulses_dir = sync_repo / "team-pulses"
        output_file = home / "reports" / "team-recap.md"
        output_file.parent.mkdir(parents=True)

        (pulses_dir / "octo-hello.tsv").write_text(
            textwrap.dedent(
                """\
                local_day\tlocal_time\tutc_time\tauthor_login\tauthor_name\trepo\tbranch\tshort_sha\tsubject\tkind\tpr_number
                2026-04-20\t10:00 UTC\t2026-04-20T10:00:00Z\talice\tAlice\tocto/hello\t(default)\t1111111\tfeat: thing\tcommit\t
                """
            )
        )

        result = self._run_recap(home, "--output", str(output_file))
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertTrue(output_file.exists())
        self.assertEqual(result.stdout, output_file.read_text())
        self.assertIn("## Summary", result.stdout)

    def test_splits_multi_month_window(self) -> None:
        home, sync_repo = self._prepare_home()
        pulses_dir = sync_repo / "team-pulses"

        (pulses_dir / "octo-hello.tsv").write_text(
            textwrap.dedent(
                """\
                local_day\tlocal_time\tutc_time\tauthor_login\tauthor_name\trepo\tbranch\tshort_sha\tsubject\tkind\tpr_number
                2026-02-15\t09:00 UTC\t2026-02-15T09:00:00Z\talice\tAlice\tocto/hello\t(default)\t1111111\tFeb entry\tcommit\t
                2026-03-10\t09:00 UTC\t2026-03-10T09:00:00Z\tbob\tBob\tocto/hello\t(default)\t2222222\tMar entry\tcommit\t
                """
            )
        )

        result = self._run_recap(home)
        self.assertEqual(result.returncode, 0, msg=result.stderr)

        feb = sync_repo / "team-reports" / "2026-02-15-PARTIAL.md"
        mar = sync_repo / "team-reports" / "2026-03-10-PARTIAL.md"
        self.assertTrue(feb.exists())
        self.assertTrue(mar.exists())
        self.assertIn("Feb entry", feb.read_text())
        self.assertNotIn("Mar entry", feb.read_text())
        self.assertIn("Mar entry", mar.read_text())
        self.assertNotIn("Feb entry", mar.read_text())


if __name__ == "__main__":
    unittest.main()
