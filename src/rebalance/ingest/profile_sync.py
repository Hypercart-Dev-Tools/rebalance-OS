"""
Profile a daily_sync log to surface slow repos.

The launchd-driven daily_sync.sh dumps a JSON document into
``temp/logs/daily_sync_YYYY-MM-DD.log``. The live dashboard also appends
GitHub-only refresh records to ``temp/logs/github_refresh_YYYY-MM-DD.log``.
This module finds the latest supported timing log, extracts the JSON
(resilient to surrounding shell output and even to truncated/multi-run
logs), and renders a Rich table showing per-repo timings for the GitHub
scope.

The parser is deliberately defensive: it never raises on a shape change.
If a key it expected is missing or renamed, it surfaces what it could
find and quietly skips what it couldn't, so a small upstream change in
``index_ops`` doesn't break ``rebalance profile-sync``.
"""

from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table
from rich.text import Text


# Keep this aligned with the dashboard palette so the two surfaces feel
# like one product. Standalone (small) copy rather than reaching into
# scripts/dashboard.py to keep the import graph trivial.
_PALETTE = {
    "fg":        "#e8e6e3",
    "fg_muted":  "#a8a29c",
    "fg_dim":    "#6c6660",
    "accent":    "#e8b86a",
    "ok":        "#7fb069",
    "warn":      "#e8b86a",
    "danger":    "#d65f5f",
    "border":    "#262a31",
}


# ---------------------------------------------------------------------------
# Resilient log parsing
# ---------------------------------------------------------------------------


_LOG_GLOBS = ("daily_sync_*.log", "github_refresh_*.log")


def _find_most_recent_log(log_dir: Path) -> Path | None:
    """Return the most recently modified supported sync profile log or None."""
    if not log_dir.exists():
        return None
    candidates: list[Path] = []
    for pattern in _LOG_GLOBS:
        candidates.extend(log_dir.glob(pattern))
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def _extract_last_json(text: str) -> dict[str, Any] | None:
    """Walk *text* for valid JSON objects, returning the last one.

    Robust to surrounding shell prefixes, ``tqdm`` progress bars on the
    same line as the JSON, and even multi-run log files (it keeps
    advancing past each successful decode and only the final blob
    survives). Returns ``None`` if no parseable JSON object is found.
    """
    decoder = json.JSONDecoder()
    last_obj: dict[str, Any] | None = None
    i = 0
    length = len(text)
    while i < length:
        # Find the next candidate object opening.
        j = text.find("{", i)
        if j < 0:
            break
        try:
            obj, end = decoder.raw_decode(text, j)
        except json.JSONDecodeError:
            i = j + 1
            continue
        if isinstance(obj, dict):
            last_obj = obj
        i = end
    return last_obj


def parse_daily_sync_log(log_path: Path) -> dict[str, Any] | None:
    """Read *log_path* and return the last JSON object embedded in it."""
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    return _extract_last_json(text)


# ---------------------------------------------------------------------------
# Defensive accessors — every shape lookup goes through these so a renamed
# key surfaces as "—" instead of crashing the command.
# ---------------------------------------------------------------------------


def _coerce_seconds(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _unwrap_refresh_result(data: dict[str, Any]) -> dict[str, Any]:
    """Return the refresh_index result from daily or dashboard log shapes."""
    result = data.get("result")
    if isinstance(result, dict):
        return result
    return data


def _extract_github_artifacts(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Pull the per-repo timing rows from a parsed daily_sync JSON.

    Walks ``results[]`` looking for the github scope and returns its
    ``artifact_sync`` list (or ``[]``). Dashboard refresh logs wrap the
    refresh result as ``{"source": "dashboard", "result": ...}``, so unwrap
    that shape first. Tolerant of:
      - ``results`` missing or non-list
      - github scope absent
      - ``artifact_sync`` renamed/missing → returns []
      - rows that aren't dicts → filtered out
    """
    data = _unwrap_refresh_result(data)
    results = data.get("results")
    if not isinstance(results, list):
        return []
    for entry in results:
        if not isinstance(entry, dict):
            continue
        if entry.get("scope") != "github":
            continue
        rows = entry.get("artifact_sync") or entry.get("repos") or []
        if not isinstance(rows, list):
            return []
        return [r for r in rows if isinstance(r, dict)]
    return []


def _format_seconds(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    if seconds < 60:
        return f"{seconds:.1f}s"
    return f"{seconds / 60:.1f}m"


def _format_pct(seconds: float | None, total: float) -> str:
    if seconds is None or total <= 0:
        return "—"
    return f"{seconds * 100 / total:.1f}%"


def _format_log_age(log_path: Path) -> str:
    try:
        mtime = _dt.datetime.fromtimestamp(
            log_path.stat().st_mtime, tz=_dt.timezone.utc
        )
    except OSError:
        return "?"
    delta = _dt.datetime.now(_dt.timezone.utc) - mtime
    secs = int(delta.total_seconds())
    if secs < 60:
        return f"{secs}s ago"
    if secs < 3600:
        return f"{secs // 60}m ago"
    if secs < 86400:
        return f"{secs // 3600}h ago"
    return f"{secs // 86400}d ago"


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def render_profile_sync(
    *,
    project_root: Path,
    log_override: Path | None = None,
    top_n: int | None = None,
    console: Console | None = None,
) -> int:
    """Render the GitHub sync timings table. Returns a process exit code.

    0  — rendered something
    1  — log directory / log file missing
    2  — log existed but couldn't be parsed
    3  — log parsed but had no github scope
    """
    out = console or Console()
    log_dir = project_root / "temp" / "logs"

    log_path = log_override
    if log_path is None:
        log_path = _find_most_recent_log(log_dir)
        if log_path is None:
            out.print(
                Text(
                    f"No daily_sync_*.log or github_refresh_*.log files found in {log_dir}.",
                    style=_PALETTE["danger"],
                )
            )
            out.print(
                Text(
                    "Run: rebalance, press [r], then use rebalance profile-sync after it completes.",
                    style=_PALETTE["fg_muted"],
                )
            )
            return 1
    elif not log_path.exists():
        out.print(Text(f"Log file not found: {log_path}", style=_PALETTE["danger"]))
        return 1

    data = parse_daily_sync_log(log_path)
    if data is None:
        out.print(
            Text(
                f"Could not extract JSON from {log_path.name}. "
                f"The sync may have crashed before writing a result block.",
                style=_PALETTE["danger"],
            )
        )
        return 2

    rows = _extract_github_artifacts(data)
    if not rows:
        out.print(
            Text(
                f"{log_path.name} parsed cleanly but contains no github "
                "artifact_sync block (scope may not have run, or schema changed).",
                style=_PALETTE["warn"],
            )
        )
        # Still useful: print top-level errors if any.
        errs = data.get("errors")
        if errs:
            out.print(Text(f"errors: {errs!r}", style=_PALETTE["fg_muted"]))
        return 3

    timings: list[tuple[str, float | None, dict[str, Any]]] = []
    for r in rows:
        repo = (r.get("repo") or r.get("repo_full_name") or "?").strip()
        elapsed = _coerce_seconds(r.get("elapsed_seconds"))
        timings.append((repo, elapsed, r))

    timings.sort(
        key=lambda t: (t[1] if isinstance(t[1], float) else -1.0),
        reverse=True,
    )
    if top_n is not None and top_n > 0:
        timings = timings[:top_n]

    total = sum(t[1] for t in timings if isinstance(t[1], float))
    refresh_result = _unwrap_refresh_result(data)
    overall_run_seconds = _coerce_seconds(refresh_result.get("elapsed_seconds")) or 0.0
    log_age = _format_log_age(log_path)

    # Header
    out.print()
    out.print(
        Text.assemble(
            ("●", _PALETTE["accent"]),
            (" github sync timings", f"bold {_PALETTE['fg']}"),
            ("  ·  ", _PALETTE["fg_dim"]),
            (log_path.name, _PALETTE["fg_muted"]),
            ("  ·  ", _PALETTE["fg_dim"]),
            (log_age, _PALETTE["fg_muted"]),
        )
    )

    table = Table(
        show_header=True,
        header_style=f"bold {_PALETTE['accent']}",
        border_style=_PALETTE["border"],
        pad_edge=False,
    )
    table.add_column("repo", style=_PALETTE["fg"], overflow="fold")
    table.add_column("elapsed", justify="right")
    table.add_column("% of github", justify="right")
    table.add_column("issues", justify="right", style=_PALETTE["fg_muted"])
    table.add_column("prs", justify="right", style=_PALETTE["fg_muted"])
    table.add_column("commits", justify="right", style=_PALETTE["fg_muted"])
    table.add_column("comments", justify="right", style=_PALETTE["fg_muted"])
    table.add_column("docs", justify="right", style=_PALETTE["fg_muted"])

    for repo, elapsed, raw in timings:
        # Shade the elapsed column by magnitude so the eye lands on the
        # outliers without needing to scan the percentage column.
        if elapsed is None:
            elapsed_style = _PALETTE["fg_dim"]
        elif elapsed >= 120:
            elapsed_style = _PALETTE["danger"]
        elif elapsed >= 30:
            elapsed_style = _PALETTE["warn"]
        else:
            elapsed_style = _PALETTE["ok"]

        table.add_row(
            repo,
            Text(_format_seconds(elapsed), style=elapsed_style),
            _format_pct(elapsed, total),
            str(raw.get("issues") if raw.get("issues") is not None else "—"),
            str(raw.get("prs") if raw.get("prs") is not None else "—"),
            str(raw.get("commits") if raw.get("commits") is not None else "—"),
            str(raw.get("comments") if raw.get("comments") is not None else "—"),
            str(raw.get("docs_built") if raw.get("docs_built") is not None else "—"),
        )

    out.print(table)

    # Footer summary
    summary = Text()
    summary.append("github total: ", style=_PALETTE["fg_muted"])
    summary.append(_format_seconds(total), style=f"bold {_PALETTE['fg']}")
    summary.append("   run total: ", style=_PALETTE["fg_muted"])
    summary.append(_format_seconds(overall_run_seconds), style=_PALETTE["fg_muted"])
    if total > 0 and overall_run_seconds > 0:
        share = total * 100 / overall_run_seconds
        summary.append(f"  ({share:.1f}% of run)", style=_PALETTE["fg_muted"])
    out.print(summary)
    out.print()

    return 0
