import subprocess
from pathlib import Path

def _git(repo_path: Path, *args: str) -> str | None:
    """Run git in *repo_path* and return stdout. Returns None if it fails."""
    result = subprocess.run(
        ["git", "-C", str(repo_path), *args],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else None
