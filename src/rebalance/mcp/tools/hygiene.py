from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

# project root: src/rebalance/mcp/tools/hygiene.py → 5 levels up
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent


def register(mcp: FastMCP, database_path: Path) -> None:
    @mcp.tool()
    def audit_modules(
        init: bool = False,
        commits_window: int = 20,
        include_uncommitted: bool = False,
    ) -> dict[str, Any]:
        """
        Audit ingest collectors, render modules, and scheduled-job infrastructure
        against ARCHITECTURE.md and CHANGELOG.md.

        Three checks run on every invocation:
          1. ARCHITECTURE.md mention check — every Python module in ingest/ and
             scripts/ (minus IGNORED_FILES) is mentioned somewhere in
             ARCHITECTURE.md.
          2. CHANGELOG.md historical-mention check — same, against any past
             version section.
          3. Recent-commit coverage — last `commits_window` commits since the
             latest version's date have their touched .py/.sh/.plist files
             reflected in that version's CHANGELOG section.

        Pre-existing gaps (#1 and #2) can be silenced via a baseline lockfile
        at scripts/audit_modules.lock; the audit then fails only on NEW drift.
        Re-snapshot the baseline after a doc backfill by calling with init=True.

        Returns the script's stable JSON schema (audit_version=1):
          {
            "audit_version": 1,
            "passed": bool,
            "exit_code": int,         # 0 pass, 1 new drift, 2 cannot run
            "summary": str,
            "candidate_modules_count": int,
            "checks": {
              "ignored_files_valid": {...},
              "architecture_md":     {"new_misses": [...], "silenced_by_baseline": [...], "resolved_in_lockfile": [...]},
              "changelog_md":        {... same shape ...},
              "recent_commits":      {"commits_examined": int, "version_section_checked": str,
                                      "version_date": str, "missing_from_changelog": [...]}
            },
            "next_steps": [str, ...]  # actionable guidance for an orchestrating agent
          }

        Args:
            init: Snapshot current ARCHITECTURE.md and CHANGELOG.md misses as
                the baseline lockfile and exit. Use after a deliberate doc
                backfill to re-zero the audit.
            commits_window: How many recent commits to check against the latest
                CHANGELOG version (default: 20). Bounded by the version date —
                older commits already documented under prior versions are
                excluded automatically.
            include_uncommitted: Pre-commit preview. When True, also flag
                working-tree changes (modified or untracked audit-worthy files)
                that aren't in the latest CHANGELOG section. Useful for an agent
                doing a "would this commit pass the audit?" check before staging.
        """
        import json as _json
        import subprocess
        import sys as _sys

        script_path = _PROJECT_ROOT / "scripts" / "audit_modules.py"

        cmd = [_sys.executable, str(script_path), "--json", "--commits", str(commits_window)]
        if init:
            cmd.append("--init")
        if include_uncommitted:
            cmd.append("--include-uncommitted")

        try:
            proc = subprocess.run(
                cmd,
                cwd=_PROJECT_ROOT,
                capture_output=True,
                text=True,
                timeout=60,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
            return {
                "audit_version": 1,
                "passed": False,
                "exit_code": 2,
                "summary": f"audit_modules subprocess failed: {exc}",
                "error": str(exc),
            }

        if not proc.stdout.strip():
            return {
                "audit_version": 1,
                "passed": False,
                "exit_code": proc.returncode if proc.returncode is not None else 2,
                "summary": "audit_modules produced no output",
                "stderr": proc.stderr,
            }
        try:
            return _json.loads(proc.stdout)
        except _json.JSONDecodeError as exc:
            return {
                "audit_version": 1,
                "passed": False,
                "exit_code": 2,
                "summary": f"audit_modules returned invalid JSON: {exc}",
                "stdout": proc.stdout,
                "stderr": proc.stderr,
            }
