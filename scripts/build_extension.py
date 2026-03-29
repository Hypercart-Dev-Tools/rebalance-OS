"""
Build script for rebalance OS desktop extension (.mcpb).

Assembles the extension directory structure:
  build/extension/
    manifest.json
    server/
      mcp_server.py     (thin entry point)
      lib/
        rebalance/      (copied from src/rebalance/)
        <pip deps>      (installed via pip --target)

Then packages it as a .mcpb (ZIP) file.

Usage:
    python scripts/build_extension.py

Output:
    dist/rebalance-os-<version>.mcpb
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
BUILD_DIR = ROOT / "build" / "extension"
DIST_DIR = ROOT / "dist"
SERVER_DIR = BUILD_DIR / "server"
LIB_DIR = SERVER_DIR / "lib"


def clean() -> None:
    """Remove previous build artifacts."""
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    BUILD_DIR.mkdir(parents=True)
    DIST_DIR.mkdir(parents=True, exist_ok=True)


def copy_manifest() -> str:
    """Copy manifest.json to build dir and return the version."""
    src = ROOT / "manifest.json"
    shutil.copy2(src, BUILD_DIR / "manifest.json")
    manifest = json.loads(src.read_text())
    return manifest.get("version", "0.0.0")


def copy_server_entry() -> None:
    """Copy the thin entry point."""
    SERVER_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "server" / "mcp_server.py", SERVER_DIR / "mcp_server.py")


def copy_source() -> None:
    """Copy src/rebalance/ into server/lib/rebalance/."""
    src = ROOT / "src" / "rebalance"
    dest = LIB_DIR / "rebalance"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)
    print(f"  Copied {src} -> {dest}")


def install_deps() -> None:
    """Install pip dependencies into server/lib/ (no scripts, no metadata bloat)."""
    # Read dependencies from pyproject.toml
    pyproject = ROOT / "pyproject.toml"
    # Use pip to install into target dir
    # We install the core deps (not optional embeddings — those are large and
    # need Apple Silicon wheels, so we install them separately)
    print("  Installing core dependencies...")
    subprocess.run(
        [
            sys.executable, "-m", "pip", "install",
            "--target", str(LIB_DIR),
            "--no-user",
            "--no-cache-dir",
            "--quiet",
            "typer>=0.12.0",
            "pydantic>=2.8.0",
            "PyYAML>=6.0.1",
            "questionary>=2.0.1",
            "mcp>=1.0.0",
            "sqlite-vec>=0.1.6",
            "google-api-python-client>=2.0.0",
            "google-auth-oauthlib>=1.0.0",
        ],
        check=True,
    )

    # Install mlx-embeddings and mlx-lm (Apple Silicon only)
    print("  Installing MLX dependencies (Apple Silicon)...")
    subprocess.run(
        [
            sys.executable, "-m", "pip", "install",
            "--target", str(LIB_DIR),
            "--no-user",
            "--no-cache-dir",
            "--quiet",
            "mlx-embeddings>=0.1.0",
            "mlx-lm>=0.20.0",
        ],
        check=True,
    )


def cleanup_lib() -> None:
    """Remove unnecessary files from lib/ to reduce size."""
    # Remove dist-info directories
    for dist_info in LIB_DIR.glob("*.dist-info"):
        shutil.rmtree(dist_info)
    # Remove __pycache__
    for pycache in LIB_DIR.rglob("__pycache__"):
        shutil.rmtree(pycache)
    # Remove .pyc files
    for pyc in LIB_DIR.rglob("*.pyc"):
        pyc.unlink()

    total_size = sum(f.stat().st_size for f in LIB_DIR.rglob("*") if f.is_file())
    print(f"  lib/ size after cleanup: {total_size / 1024 / 1024:.1f} MB")


def package(version: str) -> Path:
    """Create .mcpb (ZIP) archive."""
    output_name = f"rebalance-os-{version}"
    output_path = DIST_DIR / output_name
    # shutil.make_archive adds the extension
    archive = shutil.make_archive(
        str(output_path),
        "zip",
        root_dir=BUILD_DIR.parent,
        base_dir="extension",
    )
    # Rename .zip to .mcpb
    mcpb_path = Path(archive).with_suffix(".mcpb")
    Path(archive).rename(mcpb_path)
    return mcpb_path


def main() -> None:
    print("Building rebalance OS desktop extension...")
    print()

    print("[1/6] Cleaning build directory...")
    clean()

    print("[2/6] Copying manifest.json...")
    version = copy_manifest()
    print(f"  Version: {version}")

    print("[3/6] Copying server entry point...")
    copy_server_entry()

    print("[4/6] Copying source code...")
    copy_source()

    print("[5/6] Installing dependencies into lib/...")
    install_deps()
    cleanup_lib()

    print("[6/6] Packaging .mcpb...")
    mcpb_path = package(version)
    size_mb = mcpb_path.stat().st_size / 1024 / 1024
    print(f"  Created: {mcpb_path} ({size_mb:.1f} MB)")
    print()
    print("Done! Drag the .mcpb file into Claude Desktop -> Settings -> Extensions")


if __name__ == "__main__":
    main()
