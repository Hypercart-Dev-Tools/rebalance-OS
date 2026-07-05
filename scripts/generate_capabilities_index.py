#!/usr/bin/env python3
"""Render capabilities/INDEX.md from capabilities/manifest.yaml."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml


REQUIRED_FIELDS = (
    "id",
    "owner",
    "skills",
    "commands",
    "hooks",
    "executables",
    "requires",
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = PROJECT_ROOT / "capabilities" / "manifest.yaml"
DEFAULT_OUTPUT = PROJECT_ROOT / "capabilities" / "INDEX.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def load_manifest(path: Path) -> list[dict[str, Any]]:
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a top-level YAML list")

    entries: list[dict[str, Any]] = []
    for index, entry in enumerate(data, start=1):
        if not isinstance(entry, dict):
            raise ValueError(f"{path} entry #{index} must be a mapping")

        missing = [field for field in REQUIRED_FIELDS if field not in entry]
        if missing:
            raise ValueError(f"{path} entry #{index} is missing fields: {', '.join(missing)}")

        for field in REQUIRED_FIELDS:
            value = entry[field]
            if field in {"id", "owner"}:
                if not isinstance(value, str) or not value:
                    raise ValueError(f"{path} entry #{index} field '{field}' must be a non-empty string")
            else:
                if not isinstance(value, list):
                    raise ValueError(f"{path} entry #{index} field '{field}' must be a list")
                if not all(isinstance(item, str) and item for item in value):
                    raise ValueError(
                        f"{path} entry #{index} field '{field}' must contain only non-empty strings"
                    )
        entries.append(entry)

    return entries


def _format_items(items: list[str]) -> str:
    if not items:
        return "\u2014"
    return "<br>".join(f"`{item}`" for item in items)


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def render_index(entries: list[dict[str, Any]], manifest_path: Path) -> str:
    manifest_display = _display_path(manifest_path)
    lines = [
        "# Capabilities Index",
        "",
        "> Generated from `capabilities/manifest.yaml` by `scripts/generate_capabilities_index.py`.",
        "> Read-only reference. Edit the manifest, then regenerate this file.",
        "",
        "| Bundle | Owner | Skills | Commands | Hooks | Executables | Requires |",
        "|---|---|---|---|---|---|---|",
    ]

    for entry in entries:
        lines.append(
            "| {id} | {owner} | {skills} | {commands} | {hooks} | {executables} | {requires} |".format(
                id=f"`{entry['id']}`",
                owner=entry["owner"],
                skills=_format_items(entry["skills"]),
                commands=_format_items(entry["commands"]),
                hooks=_format_items(entry["hooks"]),
                executables=_format_items(entry["executables"]),
                requires=_format_items(entry["requires"]),
            )
        )

    lines.extend(
        [
            "",
            "Manifest source: [{}]({}).".format(manifest_display, manifest_display),
            "",
        ]
    )
    return "\n".join(lines)


def generate(manifest_path: Path, output_path: Path) -> str:
    entries = load_manifest(manifest_path)
    rendered = render_index(entries, manifest_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered)
    return rendered


def main() -> int:
    args = parse_args()
    generate(args.manifest.resolve(), args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
