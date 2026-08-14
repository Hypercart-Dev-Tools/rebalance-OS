import subprocess
from pathlib import Path

def _git(repo_path: Path, *args: str, timeout: float = 30.0) -> str | None:
    """Run git in *repo_path* and return stdout. Returns None if it fails."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_path), *args],
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except subprocess.TimeoutExpired:
        return None
