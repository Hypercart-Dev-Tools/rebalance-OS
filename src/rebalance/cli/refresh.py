"""`rebalance refresh` — the full refresh pipeline the launchd jobs collectively run.

Extracted from the cli monolith (Phase 5). Registers on the shared Typer `app`.

The heavy lifting is already delegated to ``ingest.index_ops.refresh_index`` (step
1); the remaining pipeline (web/pulse.html mirror, markdown pulse publish) plus
status rendering are CLI concerns. The repeated per-step timing/try-except/record
boilerplate is factored into ``_timed_step`` so each step is a small thunk.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any
from collections.abc import Callable

import typer

from rebalance.cli._core import app, _PROJECT_ROOT
from rebalance.paths import resolve_database_path


def _timed_step(name: str, fn: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    """Run *fn*, timing it, and return its step record.

    *fn* returns a dict of result fields (may set ``ok``; defaults to True) or
    raises. On exception, an error record (``ok=False`` + the exception text)
    is returned instead. ``name`` and ``elapsed_seconds`` are filled here.
    """
    started = time.monotonic()
    try:
        fields = fn()
    except Exception as exc:  # noqa: BLE001 — one step failing must not abort the rest
        return {
            "name": name,
            "ok": False,
            "elapsed_seconds": round(time.monotonic() - started, 2),
            "errors": [f"{type(exc).__name__}: {exc}"],
        }
    record: dict[str, Any] = {
        "name": name,
        "ok": fields.get("ok", True),
        "elapsed_seconds": round(time.monotonic() - started, 2),
    }
    record.update(fields)
    return record


@app.command("refresh")
def refresh_cmd(
    publish: bool = typer.Option(
        True,
        "--publish/--no-publish",
        help="Render the markdown pulse and push to the configured private repo "
             "(gated on content change). Use --no-publish to skip the remote push.",
    ),
    pulse_web: bool = typer.Option(
        True,
        "--pulse-web/--no-pulse-web",
        help="Regenerate the local web/pulse.html mirror.",
    ),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON instead of a status table."),
    database: Path | None = typer.Option(
        None,
        "--database",
        "-d",
        help="Override the resolved REBALANCE_DB path for this run.",
    ),
) -> None:
    """Run the full refresh pipeline that the four launchd jobs collectively do.

    Steps, each independently guarded so one failure does not abort the rest:

    1. ``refresh_index()`` (default recipe) — all raw sources (vault, github incl.
       pushed-repo auto-discovery, calendar, sleuth, email) plus the follow-on
       stages (code, semantic, sync). ``scope=["all"]`` alone is raw sources only.
    2. Regenerate ``web/pulse.html`` from the now-fresh DB (atomic
       tmp+replace; same renderer the 30-min launchd job uses).
    3. Render the markdown pulse and push it to your private pulse repo,
       gated on content change. Skip with ``--no-publish``.
    """
    import json as _json

    from rebalance.ingest.index_ops import refresh_index

    db_path = resolve_database_path(database)
    started = time.monotonic()

    summary: dict[str, Any] = {"database": str(db_path), "steps": []}

    # ---- Step 1: refresh_index(all) ----
    def _step_refresh_index() -> dict[str, Any]:
        index_result = refresh_index(db_path)  # default recipe: raw sources + code/semantic/sync
        return {
            "ok": not bool(index_result.get("errors")),
            "errors": index_result.get("errors") or [],
            "result": index_result,
        }

    summary["steps"].append(_timed_step("refresh_index", _step_refresh_index))

    # ---- Step 2: web/pulse.html ----
    def _step_pulse_web() -> dict[str, Any]:
        from rebalance.ingest.config import get_vault_path
        # pulse_web.py lives in scripts/, not in the package. Import via path.
        import importlib.util as _importlib_util
        pulse_web_path = _PROJECT_ROOT / "scripts" / "pulse_web.py"
        spec = _importlib_util.spec_from_file_location("rebalance_pulse_web", pulse_web_path)
        assert spec and spec.loader, f"could not load {pulse_web_path}"
        mod = _importlib_util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        vault_path = get_vault_path()
        goals_path = (Path(vault_path) / "0. Goals.md") if vault_path else None
        out_path = _PROJECT_ROOT / "web" / "pulse.html"
        if goals_path and goals_path.exists():
            mod.write_page(out_path, goals_path=goals_path, vault_path=Path(vault_path) if vault_path else None, refresh_seconds=30)
            return {"ok": True, "output_path": str(out_path)}
        return {
            "ok": False,
            "errors": [f"goals file not found: {goals_path}"] if goals_path else ["vault_path not configured"],
        }

    if pulse_web:
        summary["steps"].append(_timed_step("pulse_web", _step_pulse_web))
    else:
        summary["steps"].append({"name": "pulse_web", "ok": True, "skipped": True})

    # ---- Step 3: publish_pulse (markdown → private repo) ----
    def _step_publish() -> dict[str, Any]:
        from rebalance.ingest.pulse import publish_pulse as _publish_pulse
        publish_result = _publish_pulse(db_path, dry_run=False, push=True)
        record: dict[str, Any] = {
            "ok": bool(publish_result.get("ok", True)) and not publish_result.get("error"),
            "result": publish_result,
        }
        if publish_result.get("error"):
            record["errors"] = [publish_result["error"]]
        return record

    if publish:
        summary["steps"].append(_timed_step("publish_pulse", _step_publish))
    else:
        summary["steps"].append({"name": "publish_pulse", "ok": True, "skipped": True})

    summary["total_elapsed_seconds"] = round(time.monotonic() - started, 2)
    summary["ok"] = all(s.get("ok", False) for s in summary["steps"])

    if json_output:
        typer.echo(_json.dumps(summary, indent=2, default=str))
        raise typer.Exit(0 if summary["ok"] else 1)

    # Human-readable rendering
    from rich.console import Console
    from rich.table import Table

    console = Console()
    console.print(
        f"[bold]rebalance refresh[/bold] · db=[dim]{db_path}[/dim] · "
        f"{summary['total_elapsed_seconds']}s total"
    )
    table = Table(show_header=True, header_style="bold")
    table.add_column("step", no_wrap=True)
    table.add_column("status", no_wrap=True, justify="center", width=8)
    table.add_column("elapsed", no_wrap=True, justify="right")
    table.add_column("notes", overflow="fold")
    for step in summary["steps"]:
        name = step["name"]
        if step.get("skipped"):
            table.add_row(name, "[dim]skip[/dim]", "-", "[dim]disabled by flag[/dim]")
            continue
        ok = step.get("ok")
        status = "[green]✓[/green]" if ok else "[red]✗[/red]"
        elapsed = f"{step.get('elapsed_seconds', 0):.2f}s"
        notes_parts: list[str] = []
        if step.get("errors"):
            notes_parts.append("[red]" + "; ".join(str(e) for e in step["errors"]) + "[/red]")
        result = step.get("result") or {}
        if name == "refresh_index" and isinstance(result, dict):
            scope_results = result.get("results") or []
            scope_names = sorted(
                {(r.get("scope") or "?") for r in scope_results if isinstance(r, dict)}
            )
            scope_summary = ", ".join(scope_names) if scope_names else "(no scopes)"
            notes_parts.append(f"scopes: {scope_summary}")
        if name == "pulse_web" and step.get("output_path"):
            notes_parts.append(step["output_path"])
        if name == "publish_pulse" and isinstance(result, dict):
            git = result.get("git") or {}
            if git.get("committed"):
                notes_parts.append(f"committed{' + pushed' if git.get('pushed') else ''}")
            elif git.get("unchanged"):
                notes_parts.append("no content change → no commit")
        table.add_row(name, status, elapsed, " · ".join(notes_parts) if notes_parts else "")
    console.print(table)
    raise typer.Exit(0 if summary["ok"] else 1)
