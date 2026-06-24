"""Integration tests for the standalone Stickies-to-Obsidian utility."""

from __future__ import annotations

import hashlib
import os
import stat
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "utils"
    / "stickies-to-obsidian"
    / "stickies2obsidian.sh"
)
INSTALL_SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "utils"
    / "stickies-to-obsidian"
    / "install_launch_agent.sh"
)


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _write_textutil_stub(path: Path) -> None:
    _write_executable(
        path,
        textwrap.dedent(
            """\
            #!/usr/bin/env python3
            import sys
            from pathlib import Path

            args = sys.argv[1:]
            if len(args) == 4 and args[:3] == ["-convert", "txt", "-stdout"]:
                print(Path(args[3]).read_text(), end="")
                raise SystemExit(0)
            raise SystemExit(f"unsupported textutil invocation: {args}")
            """
        ),
    )


def _write_date_stub(path: Path) -> None:
    _write_executable(
        path,
        textwrap.dedent(
            """\
            #!/usr/bin/env python3
            import sys

            args = sys.argv[1:]
            if len(args) == 1 and args[0].startswith("+"):
                print("2026-06-04 21:00")
                raise SystemExit(0)
            raise SystemExit(f"unsupported date invocation: {args}")
            """
        ),
    )


class StickiesToObsidianTests(unittest.TestCase):
    def test_install_launch_agent_renders_custom_target_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            bin_dir = home / "bin"
            launch_agents = home / "Library" / "LaunchAgents"
            vault_dir = home / "Vault Root"
            obsidian_file = vault_dir / "Stickies.md"
            state_file = home / ".local" / "stickies.state"
            stickies_dir = home / "Stickies Source"

            bin_dir.mkdir(parents=True)
            launch_agents.mkdir(parents=True)
            vault_dir.mkdir(parents=True)
            stickies_dir.mkdir(parents=True)

            _write_executable(bin_dir / "launchctl", "#!/bin/sh\nexit 0\n")

            run = subprocess.run(
                [
                    "/bin/bash",
                    str(INSTALL_SCRIPT),
                    "--obsidian-file",
                    str(obsidian_file),
                    "--state-file",
                    str(state_file),
                    "--stickies-dir",
                    str(stickies_dir),
                ],
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "HOME": str(home),
                    "PATH": f"{bin_dir}:{os.environ['PATH']}",
                },
            )

            self.assertEqual(run.returncode, 0, msg=run.stderr + run.stdout)
            plist_path = launch_agents / "com.user.stickies2obsidian.plist"
            plist_text = plist_path.read_text()

            self.assertIn(str(SCRIPT), plist_text)
            self.assertIn(str(obsidian_file), plist_text)
            self.assertIn(str(state_file), plist_text)
            self.assertIn(str(stickies_dir), plist_text)
            self.assertIn(f"Target: {obsidian_file}", run.stdout)

    def test_imports_new_notes_and_deduplicates_on_second_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            bin_dir = home / "bin"
            stickies_dir = home / "stickies"
            vault_dir = home / "vault"
            obsidian_file = vault_dir / "Stickies.md"
            state_file = home / ".stickies2obsidian.state"

            bin_dir.mkdir(parents=True)
            stickies_dir.mkdir(parents=True)
            vault_dir.mkdir(parents=True)

            _write_textutil_stub(bin_dir / "textutil")
            _write_date_stub(bin_dir / "date")

            older_note = stickies_dir / "A-OLDER.rtfd"
            newer_note = stickies_dir / "B-NEWER.rtfd"
            malformed_note = stickies_dir / "C-MALFORMED.rtfd"
            older_note.mkdir()
            newer_note.mkdir()
            malformed_note.mkdir()

            (older_note / "TXT.rtf").write_text("Older sticky note\n")
            (newer_note / "TXT.rtf").write_text("Newer sticky note\n")

            os.utime(older_note, (1_717_500_000, 1_717_500_000))
            os.utime(newer_note, (1_717_600_000, 1_717_600_000))

            first = subprocess.run(
                ["/bin/bash", str(SCRIPT)],
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "HOME": str(home),
                    "PATH": f"{bin_dir}:{os.environ['PATH']}",
                    "STICKIES_DIR": str(stickies_dir),
                    "OBSIDIAN_FILE": str(obsidian_file),
                    "STATE_FILE": str(state_file),
                    "VERBOSE": "true",
                },
            )

            self.assertEqual(first.returncode, 0, msg=first.stderr + first.stdout)
            self.assertIn("[stickies2obsidian] 2 imported, 1 skipped.", first.stdout)
            self.assertIn("Skipping malformed note package without TXT.rtf", first.stderr)

            obsidian_text = obsidian_file.read_text()
            older_hash = hashlib.sha256("Older sticky note\n".encode("utf-8")).hexdigest()
            newer_hash = hashlib.sha256("Newer sticky note\n".encode("utf-8")).hexdigest()

            self.assertLess(
                obsidian_text.index("Newer sticky note"),
                obsidian_text.index("Older sticky note"),
            )
            self.assertIn(f"<!-- stickies-hash: {older_hash} -->", obsidian_text)
            self.assertIn(f"<!-- stickies-hash: {newer_hash} -->", obsidian_text)

            state_lines = state_file.read_text().strip().splitlines()
            self.assertEqual(
                state_lines,
                [
                    f"{newer_hash} B-NEWER.rtfd",
                    f"{older_hash} A-OLDER.rtfd",
                ],
            )

            second = subprocess.run(
                ["/bin/bash", str(SCRIPT)],
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "HOME": str(home),
                    "PATH": f"{bin_dir}:{os.environ['PATH']}",
                    "STICKIES_DIR": str(stickies_dir),
                    "OBSIDIAN_FILE": str(obsidian_file),
                    "STATE_FILE": str(state_file),
                    "VERBOSE": "true",
                },
            )

            self.assertEqual(second.returncode, 0, msg=second.stderr + second.stdout)
            self.assertIn("[stickies2obsidian] 0 imported, 3 skipped.", second.stdout)
            self.assertEqual(obsidian_file.read_text(), obsidian_text)
            self.assertEqual(state_file.read_text().strip().splitlines(), state_lines)

    def test_dry_run_prints_blocks_and_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            bin_dir = home / "bin"
            stickies_dir = home / "stickies"
            obsidian_file = home / "vault" / "Stickies.md"
            state_file = home / ".stickies2obsidian.state"

            bin_dir.mkdir(parents=True)
            stickies_dir.mkdir(parents=True)

            _write_textutil_stub(bin_dir / "textutil")
            _write_date_stub(bin_dir / "date")

            note_dir = stickies_dir / "DRY-RUN.rtfd"
            note_dir.mkdir()
            (note_dir / "TXT.rtf").write_text("Preview sticky note\n")

            run = subprocess.run(
                ["/bin/bash", str(SCRIPT)],
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "HOME": str(home),
                    "PATH": f"{bin_dir}:{os.environ['PATH']}",
                    "STICKIES_DIR": str(stickies_dir),
                    "OBSIDIAN_FILE": str(obsidian_file),
                    "STATE_FILE": str(state_file),
                    "DRY_RUN": "true",
                },
            )

            self.assertEqual(run.returncode, 0, msg=run.stderr + run.stdout)
            self.assertIn("Preview sticky note", run.stdout)
            self.assertIn("[stickies2obsidian] 1 imported, 0 skipped.", run.stdout)
            self.assertFalse(obsidian_file.exists())
            self.assertFalse(state_file.exists())


if __name__ == "__main__":
    unittest.main()
