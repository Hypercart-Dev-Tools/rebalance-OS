#!/usr/bin/env python3
"""Discover local GitHub git checkouts under one or more root folders."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


GITHUB_REMOTE_MARKERS = (
    "github.com:",
    "github.com/",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Find local git repos under the supplied roots and emit one path per line. "
            "By default only repos whose origin remote points at GitHub are returned."
        )
    )
    parser.add_argument(
        "--root",
        action="append",
        default=[],
        metavar="PATH",
        help="Root folder to scan. Repeatable.",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=2,
        help="Maximum directory depth to scan below each root. Default: 2.",
    )
    parser.add_argument(
        "--include-non-github",
        action="store_true",
        help="Include local git repos even if origin is not a GitHub remote.",
    )
    return parser.parse_args()


def git_origin_url(repo_path: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_path), "remote", "get-url", "origin"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def is_github_remote(remote_url: str) -> bool:
    return any(marker in remote_url for marker in GITHUB_REMOTE_MARKERS)


def walk_repo_candidates(root: Path, max_depth: int) -> list[Path]:
    if not root.exists() or not root.is_dir():
        return []

    candidates: list[Path] = []
    stack: list[tuple[Path, int]] = [(root, 0)]

    while stack:
        current, depth = stack.pop()
        if (current / ".git").is_dir():
            candidates.append(current)
            continue
        if depth >= max_depth:
            continue

        try:
            children = sorted(
                child
                for child in current.iterdir()
                if child.is_dir() and not child.name.startswith(".")
            )
        except OSError:
            continue

        for child in reversed(children):
            stack.append((child, depth + 1))

    return candidates


def unique_paths(paths: list[Path]) -> list[Path]:
    unique: list[Path] = []
    for path in sorted(paths, key=lambda value: str(value).lower()):
        if path not in unique:
            unique.append(path)
    return unique


def main() -> int:
    args = parse_args()
    if args.max_depth < 0:
        print("--max-depth must be 0 or greater.", file=sys.stderr)
        return 2

    roots = [Path(item).expanduser() for item in args.root]
    if not roots:
        return 0

    discovered: list[Path] = []
    for root in roots:
        discovered.extend(walk_repo_candidates(root, args.max_depth))

    for repo_path in unique_paths(discovered):
        if args.include_non_github:
            print(repo_path)
            continue

        origin_url = git_origin_url(repo_path)
        if is_github_remote(origin_url):
            print(repo_path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
