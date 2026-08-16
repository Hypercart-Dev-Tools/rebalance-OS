"""Shared read/write helpers for the operator's ``0. Goals.md`` file."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from uuid import uuid4
from rebalance.lib.time_ops import now_iso

CHECKBOX_RE = re.compile(r"^\s*-\s*\[(?P<mark>[ xX])\]\s*(?P<title>.*)$")


def parse_goals(path: Path, limit: int | None = 3) -> list[dict[str, Any]]:
    """Parse unchecked checklist items into ``{title, description, line_index}``.

    Format:
        - [ ] Title line
        Optional description spanning until blank line or next checkbox.
    """
    if not path.exists():
        return []
    items: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line_index, raw in enumerate(path.read_text(encoding="utf-8").splitlines()):
        if not raw.strip():
            continue
        m = CHECKBOX_RE.match(raw)
        if m:
            if current is not None:
                items.append(current)
            is_done = m.group("mark").lower() == "x"
            if is_done:
                current = None
            else:
                current = {
                    "done": False,
                    "title": m.group("title").strip(),
                    "description": "",
                    "line_index": line_index,
                }
            continue
        if current is None:
            continue
        current["description"] = (current["description"] + " " + raw.strip()).strip()
    if current is not None:
        items.append(current)
    return items if limit is None else items[:limit]


def goal_file_exists(path: Path) -> bool:
    return path.is_file()


def _candidate_indexes(total: int, preferred: int | None) -> list[int]:
    indexes: list[int] = []
    if preferred is not None and 0 <= preferred < total:
        indexes.append(preferred)
    indexes.extend(i for i in range(total) if i not in indexes)
    return indexes


def _rewrite_open_goal_line(raw: str) -> str:
    ending = ""
    if raw.endswith("\r\n"):
        ending = "\r\n"
    elif raw.endswith("\n"):
        ending = "\n"
    body = raw[: -len(ending)] if ending else raw
    return body.replace("[ ]", "[x]", 1) + ending


def complete_goal_in_file(
    path: Path,
    title: str,
    *,
    line_index: int | None = None,
) -> dict[str, Any] | None:
    """Mark one unchecked checkbox line complete in place.

    When ``line_index`` is provided, that exact line is tried first; if the file
    shifted underneath us, the function falls back to the first unchecked line
    with the same stripped title. Write is atomic (tmp + replace).
    """
    if not path.exists():
        return None
    target = title.strip()
    if not target:
        return None
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    record: dict[str, Any] | None = None
    for index in _candidate_indexes(len(lines), line_index):
        raw = lines[index]
        m = CHECKBOX_RE.match(raw.rstrip("\n"))
        if not m or m.group("mark").lower() == "x":
            continue
        if m.group("title").strip() != target:
            continue
        updated = _rewrite_open_goal_line(raw)
        lines[index] = updated
        record = {
            "id": uuid4().hex,
            "title": target,
            "goals_path": str(path.expanduser().resolve()),
            "line_index": index,
            "before_line": raw,
            "after_line": updated,
            "completed_at": now_iso(),
        }
        break
    if record is None:
        return None
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text("".join(lines), encoding="utf-8")
    tmp.replace(path)
    return record


def goal_completion_still_applied(path: Path, entry: dict[str, Any]) -> bool:
    """Return True when the completion record still matches a checked line."""
    if not path.exists():
        return False
    title = str(entry.get("title") or "").strip()
    after_line = str(entry.get("after_line") or "")
    if not title:
        return False

    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    line_index = entry.get("line_index")
    if isinstance(line_index, int) and 0 <= line_index < len(lines):
        raw = lines[line_index]
        m = CHECKBOX_RE.match(raw.rstrip("\n"))
        if m and m.group("mark").lower() == "x" and m.group("title").strip() == title:
            if not after_line or raw == after_line:
                return True

    for raw in lines:
        m = CHECKBOX_RE.match(raw.rstrip("\n"))
        if not m or m.group("mark").lower() != "x":
            continue
        if m.group("title").strip() != title:
            continue
        if not after_line or raw == after_line:
            return True
    return False


def undo_goal_completion_in_file(path: Path, entry: dict[str, Any]) -> bool:
    """Revert one completion record back to an unchecked checkbox."""
    if not path.exists():
        return False
    before_line = str(entry.get("before_line") or "")
    after_line = str(entry.get("after_line") or "")
    title = str(entry.get("title") or "").strip()
    if not before_line or not title:
        return False

    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    candidate_indexes = _candidate_indexes(len(lines), entry.get("line_index"))

    for index in candidate_indexes:
        raw = lines[index]
        m = CHECKBOX_RE.match(raw.rstrip("\n"))
        if not m or m.group("mark").lower() != "x":
            continue
        if m.group("title").strip() != title:
            continue
        if after_line and raw != after_line and index == entry.get("line_index"):
            continue
        lines[index] = before_line
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text("".join(lines), encoding="utf-8")
        tmp.replace(path)
        return True
    return False
