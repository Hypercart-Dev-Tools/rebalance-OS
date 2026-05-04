"""Tests for GitHub sync profile log parsing."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from rich.console import Console

from rebalance.ingest.profile_sync import (
    _extract_github_artifacts,
    _find_most_recent_log,
    render_profile_sync,
)


def _refresh_result(repo: str, elapsed: float) -> dict[str, object]:
    return {
        "elapsed_seconds": elapsed + 1,
        "results": [
            {
                "scope": "github",
                "artifact_sync": [
                    {
                        "repo": repo,
                        "elapsed_seconds": elapsed,
                        "issues": 1,
                        "prs": 0,
                        "commits": 0,
                        "comments": 0,
                        "docs_built": 1,
                    }
                ],
            }
        ],
        "errors": [],
    }


class ProfileSyncTests(unittest.TestCase):
    def test_dashboard_refresh_log_shape_unwraps_to_github_artifacts(self) -> None:
        data = {
            "logged_at": "2026-05-04T18:00:00+00:00",
            "source": "dashboard",
            "result": _refresh_result("example/slow", 42.5),
        }

        rows = _extract_github_artifacts(data)

        self.assertEqual(rows[0]["repo"], "example/slow")
        self.assertEqual(rows[0]["elapsed_seconds"], 42.5)

    def test_latest_log_includes_dashboard_github_refresh_logs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir)
            daily = log_dir / "daily_sync_2026-05-04.log"
            dashboard = log_dir / "github_refresh_2026-05-04.log"
            daily.write_text(json.dumps(_refresh_result("example/daily", 3.0)), encoding="utf-8")
            dashboard.write_text(
                json.dumps({"source": "dashboard", "result": _refresh_result("example/dashboard", 9.0)}),
                encoding="utf-8",
            )
            os.utime(daily, (1_000_000_000, 1_000_000_000))
            os.utime(dashboard, (1_000_000_010, 1_000_000_010))

            self.assertEqual(_find_most_recent_log(log_dir), dashboard)

    def test_render_profile_sync_reads_dashboard_refresh_log(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            log_dir = root / "temp" / "logs"
            log_dir.mkdir(parents=True)
            (log_dir / "github_refresh_2026-05-04.log").write_text(
                json.dumps({"source": "dashboard", "result": _refresh_result("example/dashboard", 9.0)}),
                encoding="utf-8",
            )
            console = Console(record=True, width=120)

            exit_code = render_profile_sync(project_root=root, console=console)

            self.assertEqual(exit_code, 0)
            output = console.export_text()
            self.assertIn("example/dashboard", output)
            self.assertIn("9.0s", output)


if __name__ == "__main__":
    unittest.main()
