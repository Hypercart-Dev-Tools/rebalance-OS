import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from hiqs import __main__ as cli


HIQS_ROOT = Path(__file__).resolve().parents[1]


def run_hiqs(tmp_path, *arguments):
    environment = os.environ.copy()
    environment["HOME"] = str(tmp_path)
    return subprocess.run(
        [sys.executable, "-m", "hiqs", *arguments],
        cwd=HIQS_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_help_lists_the_six_stable_subcommands(tmp_path):
    result = run_hiqs(tmp_path, "--help")

    assert result.returncode == 0
    for command in ("refresh", "status", "search", "ask", "serve", "auth"):
        assert command in result.stdout


@pytest.mark.parametrize("arguments", [(), ("--json",)])
def test_status_on_an_empty_database_emits_the_shared_json_shape(tmp_path, arguments):
    result = run_hiqs(tmp_path, "status", *arguments)

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert set(payload) == {"sources", "row_counts", "last_errors", "search", "ranking"}
    assert payload["sources"] == {}
    assert payload["search"] == {"mode": "unknown", "model": None, "quality": "unknown"}
    assert payload["ranking"] == {"quality": "unknown"}


@pytest.mark.parametrize(
    ("arguments", "phase"),
    [
        # refresh and search were here until 2026-08-03; both are implemented now, so
        # asserting they fail would pin a stub that no longer exists. Retiring the row is
        # part of implementing the command — the same retire-the-forward-declaration duty
        # the strict xfail contracts carry.
        (("ask", "what now?"), "Phase 3"),
        (("serve",), "Phase 4"),
        (("auth", "calendar"), "Phase 4"),
    ],
)
def test_skeleton_commands_fail_clearly_until_their_implementation_phase(tmp_path, arguments, phase):
    result = run_hiqs(tmp_path, *arguments)

    assert result.returncode != 0
    assert phase in result.stderr
    assert "Traceback" not in result.stderr


def test_invalid_bounded_options_are_rejected_before_the_unimplemented_command_runs(capsys):
    with pytest.raises(SystemExit) as error:
        cli.main(["search", "status", "--limit", "0"])

    assert error.value.code == 2
    assert "must be at least 1" in capsys.readouterr().err
