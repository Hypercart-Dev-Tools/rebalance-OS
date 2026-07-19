"""Exit semantics for the daily scheduler wrapper (GH-146)."""

import contextlib
import io
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "daily_sync.sh"


def _embedded_python() -> str:
    """Return the Python payload executed by the shell wrapper."""
    script = SCRIPT.read_text()
    start = 'if "$PYTHON" - <<\'PY\' >> "$LOG_FILE" 2>&1\n'
    return script.split(start, 1)[1].split("\nPY\nthen", 1)[0]


def _run_refresh_payload(payload: dict) -> tuple[int, dict]:
    """Run the wrapper's Python payload with refresh_index replaced by a fixture."""
    rebalance = types.ModuleType("rebalance")
    ingest = types.ModuleType("rebalance.ingest")
    index_ops = types.ModuleType("rebalance.ingest.index_ops")
    paths = types.ModuleType("rebalance.paths")
    index_ops.refresh_index = lambda _db_path: payload
    paths.resolve_database_path = lambda: "/tmp/rebalance.db"
    modules = {
        "rebalance": rebalance,
        "rebalance.ingest": ingest,
        "rebalance.ingest.index_ops": index_ops,
        "rebalance.paths": paths,
    }
    output = io.StringIO()
    with patch.dict(sys.modules, modules), contextlib.redirect_stdout(output):
        with unittest.TestCase().assertRaises(SystemExit) as raised:
            exec(compile(_embedded_python(), str(SCRIPT), "exec"), {})

    lines = output.getvalue().splitlines()
    json_start = next(index for index, line in enumerate(lines) if line == "{")
    return raised.exception.code, json.loads("\n".join(lines[json_start:]))


class DailySyncExitTests(unittest.TestCase):
    def test_transient_only_errors_exit_zero_and_preserve_errors(self) -> None:
        payload = {
            "errors": [{"scope": "calendar", "error": "request timed out"}],
            "results": [{"scope": "github", "commits": 3}],
        }

        exit_code, result = _run_refresh_payload(payload)

        self.assertEqual(exit_code, 0)
        self.assertEqual(result["sync_outcome"], "degraded")
        self.assertEqual(result["errors"], payload["errors"])

    def test_github_rate_limit_payload_exits_zero(self) -> None:
        payload = {
            "errors": [{"scope": "github", "error": "Rate limited fetching /user"}],
            "results": [{"scope": "vault", "notes": 12}],
        }

        exit_code, result = _run_refresh_payload(payload)

        self.assertEqual(exit_code, 0)
        self.assertEqual(result["sync_outcome"], "degraded")

    def test_fatal_error_exits_one(self) -> None:
        payload = {
            "errors": [{"scope": "migrations", "error": "unable to open database file"}],
            "results": [],
        }

        exit_code, result = _run_refresh_payload(payload)

        self.assertEqual(exit_code, 1)
        self.assertEqual(result["sync_outcome"], "fatal")

    def test_clean_run_exits_zero(self) -> None:
        exit_code, result = _run_refresh_payload({"errors": [], "results": [{"scope": "vault"}]})

        self.assertEqual(exit_code, 0)
        self.assertEqual(result["sync_outcome"], "complete")


if __name__ == "__main__":
    unittest.main()
