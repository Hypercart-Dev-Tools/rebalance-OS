"""Unit tests for ``scripts/build_status.py``.

Exercises the pure helpers (CI color, commit-title extraction, row builder,
device-pulse reader). Network-touching code is not tested here — the GH
Action's actual run is the integration test.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "build_status.py"


def _load_build_status_module():
    sys.path.insert(0, str(REPO_ROOT / "src"))
    spec = importlib.util.spec_from_file_location("build_status", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bs = _load_build_status_module()


class CiColorTests(unittest.TestCase):
    def test_success_is_green(self) -> None:
        self.assertEqual(bs._ci_color("completed", "success"), "green")

    def test_failure_is_red(self) -> None:
        self.assertEqual(bs._ci_color("completed", "failure"), "red")
        self.assertEqual(bs._ci_color("completed", "timed_out"), "red")
        self.assertEqual(bs._ci_color("completed", "cancelled"), "red")

    def test_in_progress_is_yellow(self) -> None:
        self.assertEqual(bs._ci_color("in_progress", None), "yellow")
        self.assertEqual(bs._ci_color("queued", None), "yellow")

    def test_unknown_is_grey(self) -> None:
        self.assertEqual(bs._ci_color(None, None), "grey")


class CommitTitleTests(unittest.TestCase):
    def test_strips_to_first_line(self) -> None:
        self.assertEqual(bs._commit_title("first line\n\nbody"), "first line")

    def test_truncates_long_titles(self) -> None:
        long = "x" * 300
        self.assertEqual(len(bs._commit_title(long)), 200)

    def test_handles_none(self) -> None:
        self.assertEqual(bs._commit_title(None), "")
        self.assertEqual(bs._commit_title(""), "")


class IndexRunsBySha(unittest.TestCase):
    def test_keeps_most_recent_per_sha(self) -> None:
        runs = [
            {"head_sha": "a", "created_at": "2026-05-01T00:00:00Z", "id": 1},
            {"head_sha": "a", "created_at": "2026-05-02T00:00:00Z", "id": 2},
            {"head_sha": "b", "created_at": "2026-05-01T00:00:00Z", "id": 3},
        ]
        idx = bs._index_runs_by_sha(runs)
        self.assertEqual(idx["a"]["id"], 2)
        self.assertEqual(idx["b"]["id"], 3)


class BuildRowsTests(unittest.TestCase):
    def test_commit_joined_with_workflow_run(self) -> None:
        commits = [
            {
                "sha": "abc1234",
                "html_url": "https://github.com/o/r/commit/abc1234",
                "commit": {
                    "message": "Refactor handler",
                    "author": {"date": "2026-05-02T10:00:00Z", "name": "Noel"},
                },
                "author": {"login": "noelsaw"},
                "committer": {"login": "noelsaw"},
            }
        ]
        runs = [
            {
                "head_sha": "abc1234",
                "head_branch": "claude/abc",
                "status": "completed",
                "conclusion": "success",
                "html_url": "https://github.com/o/r/actions/runs/1",
                "name": "ci",
                "event": "push",
                "created_at": "2026-05-02T10:05:00Z",
                "actor": {"login": "noelsaw"},
            }
        ]
        rows = bs.build_rows("o/r", commits, [], runs, "2026-04-25T00:00:00Z")
        commit_row = next(r for r in rows if r["kind"] == "commit")
        self.assertEqual(commit_row["source_tag"], "claude-cloud")
        self.assertEqual(commit_row["ci"]["color"], "green")
        self.assertEqual(commit_row["branch"], "claude/abc")

    def test_pr_classified_via_branch(self) -> None:
        pulls = [
            {
                "number": 7,
                "title": "Add dashboard",
                "state": "closed",
                "merged_at": "2026-05-02T09:00:00Z",
                "updated_at": "2026-05-02T09:00:00Z",
                "html_url": "https://github.com/o/r/pull/7",
                "head": {"ref": "claude/dashboard"},
                "user": {"login": "noelsaw"},
            }
        ]
        rows = bs.build_rows("o/r", [], pulls, [], "2026-04-25T00:00:00Z")
        pr = next(r for r in rows if r["kind"] == "pr_merged")
        self.assertEqual(pr["source_tag"], "claude-cloud")
        self.assertEqual(pr["title"], "#7 Add dashboard")

    def test_workflow_row_source_tag(self) -> None:
        runs = [
            {
                "head_sha": "deadbee",
                "head_branch": "codex/refactor",
                "status": "completed",
                "conclusion": "failure",
                "html_url": "https://github.com/o/r/actions/runs/2",
                "name": "ci",
                "event": "push",
                "created_at": "2026-05-02T11:00:00Z",
                "actor": {"login": "chatgpt-codex-connector[bot]"},
            }
        ]
        rows = bs.build_rows("o/r", [], [], runs, "2026-04-25T00:00:00Z")
        wf = next(r for r in rows if r["kind"] == "workflow_run")
        self.assertEqual(wf["source_tag"], "codex-cloud")
        self.assertEqual(wf["ci"]["color"], "red")

    def test_pr_outside_window_is_dropped(self) -> None:
        pulls = [
            {
                "number": 1,
                "title": "Old",
                "state": "open",
                "updated_at": "2026-01-01T00:00:00Z",
                "created_at": "2026-01-01T00:00:00Z",
                "html_url": "https://github.com/o/r/pull/1",
                "head": {"ref": "feat"},
                "user": {"login": "noelsaw"},
            }
        ]
        rows = bs.build_rows("o/r", [], pulls, [], "2026-04-25T00:00:00Z")
        self.assertEqual(rows, [])


class DevicePulseTests(unittest.TestCase):
    def test_reads_recent_lines_only(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            mirror = Path(td)
            now = datetime.now(timezone.utc)
            recent = now - timedelta(minutes=5)
            old = now - timedelta(days=10)
            (mirror / "pulse-mac-studio.md").write_text(
                "# header\n"
                f"{int(recent.timestamp())}\t{recent.isoformat()}\to/r\tmain\tabc\tFix\n"
                f"{int(old.timestamp())}\t{old.isoformat()}\to/r\tmain\tdef\tStale\n",
                encoding="utf-8",
            )
            results = bs.read_device_pulses(mirror, now - timedelta(hours=1))
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["device"], "mac-studio")

    def test_missing_dir_returns_empty(self) -> None:
        self.assertEqual(
            bs.read_device_pulses(Path("/nonexistent-xyz"),
                                  datetime.now(timezone.utc)),
            [],
        )


class LocalSessionRowsTests(unittest.TestCase):
    def test_local_session_rows_are_tagged_local_vscode(self) -> None:
        rows = bs.build_local_session_rows(
            [{"when": "2026-05-02T10:00:00Z", "device": "mac-studio",
              "repo": "o/r", "branch": "main", "subject": "wip"}]
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source_tag"], "local-vscode")
        self.assertEqual(rows[0]["actor"], "mac-studio")


if __name__ == "__main__":
    unittest.main()
