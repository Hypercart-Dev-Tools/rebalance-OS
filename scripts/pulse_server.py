"""
rebalance pulse — local FastAPI server (POC / spike).

Wraps the existing static `web/pulse.html` flow with three endpoints so the
"Refresh" button in the page can actually regenerate the file on demand and
the page can report a real "last generated" timestamp. The launchd
30-minute regenerator stays in place; this server only adds an interactive
on-demand path. The static file remains the canonical render — when the
server is off the file is still openable via file://.

    Start:   uv run python scripts/pulse_server.py
    Open:    http://127.0.0.1:8767/

The server binds to loopback only by default. Do not expose it on a public
interface — there is no auth and /api/refresh runs a subprocess.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel
import uvicorn

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PULSE_HTML = PROJECT_ROOT / "web" / "pulse.html"
PULSE_WEB_PY = PROJECT_ROOT / "scripts" / "pulse_web.py"
# Canonical path shared with pulse_web.py — must stay in sync
ACTIVE_JSON_PATH = PROJECT_ROOT / "temp" / "apple-reminders" / "active.json"
PYTHON = sys.executable

import _bootstrap  # noqa: E402, F401  — puts src/ and scripts/ on sys.path
# _open_bundle_invoker is a private symbol; coupling is intentional and documented here.
# It is the only public-facing invoker for the signed Apple Reminders helper bundle.
# Promote to a public name in apple_reminders_write.py when the module API stabilises.
from rebalance.ingest.apple_reminders_write import _open_bundle_invoker  # noqa: PLC2701
from rebalance.ingest.config import get_apple_reminders_list_name
from pulse_web import (  # noqa: E402
    complete_goal_in_file,
    forget_goal_completion,
    _goal_completion_still_applied,
    remember_goal_completion,
    resolve_goals_path,
    load_goal_history,
    undo_goal_completion_in_file,
)
from rebalance.ingest.apple_reminders_write import (  # noqa: E402
    AppleRemindersWriteError,
    WriteOp,
    apply_reminder_writes,
    build_request,
)
from rebalance.ingest.config import add_figma_file_key, get_figma_file_keys  # noqa: E402
from rebalance.ingest.index_ops import refresh_index  # noqa: E402
from rebalance.paths import resolve_database_path  # noqa: E402

app = FastAPI(title="rebalance pulse (local)", docs_url=None, redoc_url=None)
_FIGMA_KEY_RE = re.compile(r"^[A-Za-z0-9]{8,}$")

# Serve the auth-activity log and Focus 5 view from this always-running server
# too, so their links work without a separate `rebalance serve` process on
# :8787. Reuses the renderers in rebalance.web (no duplication).
from rebalance.web import (  # noqa: E402
    Focus5GoalCompleteRequest,
    Focus5HideRequest,
    focus5_complete_goal as _focus5_complete_goal,
    focus5_goals as _focus5_goals,
    focus5_json as _focus5_json,
    auth_log_page as _auth_log_page,
    auth_log_raw as _auth_log_raw,
    focus5_note as _focus5_note,
    focus5_page as _focus5_page,
    focus5_set_hidden as _focus5_set_hidden,
    sleuth_graph_page as _sleuth_graph_page,
    unhandled_exception_handler as _unhandled_exception_handler,
    whatsnext_page as _whatsnext_page,
    settings_page as _settings_page,
)

# Show the real traceback in-browser on an unhandled error instead of a bare
# "Internal Server Error". Same shared handler the :8787 web app uses. This
# server enforces a loopback bind (see main()), so tracebacks never leave the
# box and gating is unnecessary.
app.state.show_tracebacks = True
app.add_exception_handler(Exception, _unhandled_exception_handler)


@app.get("/auth-log")
def auth_log():
    return _auth_log_page()


@app.get("/auth-log/raw")
def auth_log_raw():
    return _auth_log_raw()


@app.get("/focus-5")
def focus5(refresh: bool = False, view: str = "focus5"):
    # Forward ``view`` so the Focus 5 / Dirty Five toggle works on this surface too
    # (shared renderer in rebalance.web — keeps both /focus-5 surfaces identical).
    return _focus5_page(refresh=refresh, view=view)


@app.get("/focus-5/note")
def focus5_note():
    # Mirror the read-only focus5.md note here too: this is the always-running
    # server, so the Focus 5 Float client gets the note regardless of which local
    # server it points at (keeps both /focus-5 surfaces identical — see web.py).
    return _focus5_note()


@app.get("/focus-5.json")
def focus5_json(view: str = "focus5"):
    # The native/desktop roster fetch. Mirror it on this always-running server so
    # Focus 5 Float loads a live roster without a separate `rebalance serve` on
    # :8787 (shared renderer in rebalance.web — keeps both surfaces identical).
    return _focus5_json(view=view)


@app.get("/focus-5/goals")
def focus5_goals():
    return _focus5_goals()


@app.post("/api/focus5/goals/complete")
def focus5_complete_goal(req: Focus5GoalCompleteRequest, request: Request):
    return _focus5_complete_goal(req, request)


class AppleReminderCompleteRequest(BaseModel):
    reminder_id: str
    title: str | None = None  # carried for the audit trail / readability only


@app.post("/api/apple-reminders/complete")
def apple_reminders_complete(req: AppleReminderCompleteRequest):
    """Complete one Apple Reminder from the dashboard column (Phase 6 dashboard
    write-back; APPLE-REMINDERS-UNIFIED-PLAN.md).

    The ONLY web-surface Apple Reminders write, and it routes through the Phase
    5.1 orchestrator (`apply_reminder_writes`) so the single-writer + audit-table
    discipline is preserved — this layer holds no EventKit/SQLite write code of
    its own. `reconcile=False`: the local `apple_reminders` table re-syncs on the
    next scoped sync (FDA-gated; this loopback server can't hold that grant), so
    the UI greys the row optimistically. A non-2xx here makes the row revert
    rather than falsely show "done".
    """
    reminder_id = (req.reminder_id or "").strip()
    if not reminder_id:
        raise HTTPException(status_code=400, detail="reminder_id is required")

    request = build_request(
        [WriteOp(op="complete", reminder_id=reminder_id)], mode="apply"
    )
    try:
        result = apply_reminder_writes(
            resolve_database_path(), request, reconcile=False
        )
    except AppleRemindersWriteError as exc:
        # Helper missing/unauthorized, scope/confirmation failure, IPC error, …
        raise HTTPException(status_code=502, detail=f"{type(exc).__name__}: {exc}")

    payload = result.as_dict()
    if not result.ok:
        # A per-op error (auth denied, helper rejected) — surface it so the row
        # never falsely shows complete.
        return JSONResponse(payload, status_code=502)
    return payload


@app.post("/api/focus5/hide")
def focus5_hide(req: Focus5HideRequest):
    # The ✕ on a Focus 5 card: hide the repo and re-rank from cache (shared logic
    # in rebalance.web, so this surface matches `rebalance serve`).
    return _focus5_set_hidden(req.repo, hidden=True)


@app.post("/api/focus5/unhide")
def focus5_unhide(req: Focus5HideRequest):
    return _focus5_set_hidden(req.repo, hidden=False)


@app.get("/whats-next")
def whats_next(refresh: bool = False):
    return _whatsnext_page(refresh=refresh)


@app.get("/sleuth-graph")
def sleuth_graph():
    return _sleuth_graph_page()


@app.get("/settings")
def settings():
    return _settings_page()


class ChatRequest(BaseModel):
    query: str
    scope: str = "all"
    top_k: int = 8


class FigmaProjectRequest(BaseModel):
    project: str


def _run_pulse_render(timeout: int = 60) -> subprocess.CompletedProcess[str]:
    if not PULSE_WEB_PY.exists():
        raise HTTPException(status_code=500, detail=f"missing {PULSE_WEB_PY}")
    return subprocess.run(
        [PYTHON, str(PULSE_WEB_PY)],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _extract_figma_file_key(value: str) -> str | None:
    text = (value or "").strip()
    if not text:
        return None
    if _FIGMA_KEY_RE.fullmatch(text):
        return text
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"}:
        return None
    host = parsed.netloc.lower()
    if host not in {"figma.com", "www.figma.com"}:
        return None
    parts = [part for part in parsed.path.split("/") if part]
    for idx, part in enumerate(parts[:-1]):
        if part in {"file", "design", "proto", "board"}:
            candidate = parts[idx + 1].strip()
            if _FIGMA_KEY_RE.fullmatch(candidate):
                return candidate
    return None


@app.post("/api/chat")
def api_chat(req: ChatRequest):
    """Citations-first retrieval for the dashboard 'Ask' search mode.

    Note: the first call lazily loads the embedding model, so it is slow;
    subsequent calls are fast. Loopback-only, no auth (same as the rest).
    """
    from rebalance.chat import chat_with_data
    from rebalance.paths import resolve_database_path
    try:
        result = chat_with_data(
            resolve_database_path(), req.query, scope=req.scope, top_k=req.top_k
        )
        return JSONResponse(result)
    except Exception as exc:  # noqa: BLE001 — surface the error to the UI, don't 500-crash
        return JSONResponse(
            {"error": f"{type(exc).__name__}: {exc}", "citations": [], "query": req.query},
            status_code=500,
        )


@app.get("/")
def index(request: Request):
    if not PULSE_HTML.exists():
        raise HTTPException(
            status_code=503,
            detail=f"pulse.html not generated yet. Run: {PYTHON} {PULSE_WEB_PY}",
        )
    # Conditional GET: an ETag derived from the file's mtime+size lets an unchanged
    # dashboard return 304 (no re-stream) instead of the old blanket no-store. The
    # file is regenerated atomically off-request, so any change bumps mtime -> a new
    # ETag -> the browser refetches; must-revalidate keeps it from serving stale.
    st = PULSE_HTML.stat()
    etag = f'"{int(st.st_mtime)}-{st.st_size}"'
    cache_headers = {"ETag": etag, "Cache-Control": "max-age=0, must-revalidate"}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=cache_headers)
    return FileResponse(
        PULSE_HTML,
        media_type="text/html; charset=utf-8",
        headers=cache_headers,
    )


@app.get("/api/health")
def health():
    if not PULSE_HTML.exists():
        return JSONResponse({"ok": False, "reason": "pulse.html missing"}, status_code=503)
    mtime = datetime.fromtimestamp(PULSE_HTML.stat().st_mtime, tz=timezone.utc)
    age_s = (datetime.now(timezone.utc) - mtime).total_seconds()
    return {
        "ok": True,
        "generated_at": mtime.isoformat(),
        "age_seconds": round(age_s, 1),
    }


@app.post("/api/refresh")
def refresh():
    started = time.perf_counter()

    helper_error = None
    try:
        req_id = uuid.uuid4().hex
        list_name = get_apple_reminders_list_name()
        request = {
            "schema_version": 1,
            "request_id": req_id,
            "mode": "apply",
            "confirm_destructive": False,
            "operations": [{"op": "list-active", "list_name": list_name}]
        }

        response = _open_bundle_invoker(request, timeout_seconds=5.0)
        results = response.get("results") or []
        if not results:
            helper_error = "no results in helper response"
        else:
            first_res = results[0]
            if first_res.get("status") == "ok":
                active_items = json.loads(first_res.get("detail", "[]"))
                ACTIVE_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
                tmp_path = ACTIVE_JSON_PATH.with_suffix(".tmp")
                # Versioned envelope so pulse_web.py can detect schema changes.
                tmp_path.write_text(
                    json.dumps({"schema_version": 1, "items": active_items}),
                    encoding="utf-8",
                )
                tmp_path.replace(ACTIVE_JSON_PATH)
            else:
                helper_error = str(first_res.get("detail", "helper returned error"))
    except Exception as exc:
        helper_error = f"{type(exc).__name__}: {exc}"

    proc = _run_pulse_render(timeout=60)
    duration_ms = round((time.perf_counter() - started) * 1000)
    if proc.returncode != 0:
        return JSONResponse(
            {
                "ok": False,
                "duration_ms": duration_ms,
                "returncode": proc.returncode,
                "stderr": proc.stderr[-2000:],
                "helper_error": helper_error,
            },
            status_code=500,
        )
    mtime = datetime.fromtimestamp(PULSE_HTML.stat().st_mtime, tz=timezone.utc)
    # ok is False when the helper failed even though the render succeeded —
    # the dashboard must surface this, not silently show stale data.
    return {
        "ok": helper_error is None,
        "duration_ms": duration_ms,
        "generated_at": mtime.isoformat(),
        "helper_error": helper_error,
    }


@app.post("/api/figma/projects")
def add_figma_project(req: FigmaProjectRequest):
    raw_value = (req.project or "").strip()
    if not raw_value:
        raise HTTPException(status_code=400, detail="project is required")

    file_key = _extract_figma_file_key(raw_value)
    if not file_key:
        raise HTTPException(
            status_code=400,
            detail="enter a Figma file key or a full figma.com design/file URL",
        )

    added = add_figma_file_key(file_key)
    if not added:
        raise HTTPException(
            status_code=409,
            detail=f"Figma file key already configured: {file_key}",
        )

    sync_ok = True
    sync_error = ""
    figma_result: dict[str, object] = {}
    try:
        result = refresh_index(resolve_database_path(), scope=["figma", "semantic"], dry_run=False)
        figma_result = next(
            (
                row for row in (result.get("results") or [])
                if isinstance(row, dict) and row.get("scope") == "figma"
            ),
            {},
        )
        top_errors = result.get("errors") or []
        scoped_errors = figma_result.get("errors") or []
        scoped_error = str(figma_result.get("error") or "").strip()
        sync_ok = not top_errors and not scoped_errors and not scoped_error
        if scoped_error:
            sync_error = scoped_error
        elif scoped_errors:
            sync_error = "; ".join(
                str(err.get("error") or "").strip()
                for err in scoped_errors
                if isinstance(err, dict) and str(err.get("error") or "").strip()
            ) or "Figma sync reported file-level errors."
        elif top_errors:
            sync_error = "; ".join(str(err) for err in top_errors)
    except Exception as exc:  # noqa: BLE001
        sync_ok = False
        sync_error = f"{type(exc).__name__}: {exc}"

    render_error = ""
    try:
        proc = _run_pulse_render(timeout=60)
        if proc.returncode != 0:
            render_error = proc.stderr[-500:] or f"pulse render failed: {proc.returncode}"
    except Exception as exc:  # noqa: BLE001
        render_error = f"{type(exc).__name__}: {exc}"

    return {
        "ok": True,
        "file_key": file_key,
        "already_present": False,
        "files_configured": len(get_figma_file_keys()),
        "sync_ok": sync_ok,
        "sync_error": sync_error,
        "render_ok": not bool(render_error),
        "render_error": render_error,
        "comments_fetched": int(figma_result.get("comments_fetched") or 0),
        "comments_inserted": int(figma_result.get("comments_inserted") or 0),
        "comments_updated": int(figma_result.get("comments_updated") or 0),
    }


class GoalCompleteRequest(BaseModel):
    title: str


class GoalUndoRequest(BaseModel):
    id: str


def _history_payload(goals_path: Path) -> list[dict[str, str]]:
    items = load_goal_history(goals_path=goals_path)
    now = datetime.now(timezone.utc)
    out: list[dict[str, str]] = []
    for item in items:
        completed_at = item.get("completed_at")
        ago = "just now"
        if isinstance(completed_at, str):
            try:
                dt = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
                secs = max(0, int((now - dt).total_seconds()))
                if secs < 60:
                    ago = f"{secs}s ago"
                elif secs < 3600:
                    ago = f"{secs // 60}m ago"
                elif secs < 86400:
                    ago = f"{secs // 3600}h ago"
                else:
                    ago = f"{secs // 86400}d ago"
            except ValueError:
                ago = "just now"
        out.append({
            "id": str(item.get("id") or ""),
            "title": str(item.get("title") or ""),
            "completed_ago": ago,
        })
    return out


@app.post("/api/goals/complete")
def goals_complete(req: GoalCompleteRequest):
    goals_path = resolve_goals_path()
    if goals_path is None:
        raise HTTPException(
            status_code=503,
            detail="goals path not resolvable (no PULSE_GOALS env and no vault_path in config)",
        )
    if not goals_path.exists():
        raise HTTPException(status_code=404, detail=f"goals file missing: {goals_path}")
    title = (req.title or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="title is required")
    completion = complete_goal_in_file(goals_path, title)
    if not completion:
        # The most useful client-visible reason is that the title no longer
        # matches an unchecked line — file may have been edited since render.
        return JSONResponse(
            {"ok": False, "reason": "not_found", "title": title},
            status_code=404,
        )
    remember_goal_completion(completion)
    # Regenerate the static HTML so a manual reload (or external file:// open)
    # reflects the new state without waiting for the launchd 30-min cycle.
    subprocess.Popen(
        [PYTHON, str(PULSE_WEB_PY)],
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return {
        "ok": True,
        "title": title,
        "history": _history_payload(goals_path),
    }


@app.post("/api/goals/undo")
def goals_undo(req: GoalUndoRequest):
    goals_path = resolve_goals_path()
    if goals_path is None:
        raise HTTPException(
            status_code=503,
            detail="goals path not resolvable (no PULSE_GOALS env and no vault_path in config)",
        )
    if not goals_path.exists():
        raise HTTPException(status_code=404, detail=f"goals file missing: {goals_path}")
    undo_id = (req.id or "").strip()
    if not undo_id:
        raise HTTPException(status_code=400, detail="id is required")

    entries = load_goal_history(goals_path=goals_path)
    entry = next((item for item in entries if item.get("id") == undo_id), None)
    if entry is None:
        return JSONResponse(
            {"ok": False, "reason": "not_found", "id": undo_id},
            status_code=404,
        )

    ok = undo_goal_completion_in_file(goals_path, entry)
    if not ok:
        if not _goal_completion_still_applied(goals_path, entry):
            forget_goal_completion(undo_id)
            subprocess.Popen(
                [PYTHON, str(PULSE_WEB_PY)],
                cwd=str(PROJECT_ROOT),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return {
                "ok": True,
                "id": undo_id,
                "title": str(entry.get("title") or ""),
                "history": _history_payload(goals_path),
                "stale_removed": True,
            }
        return JSONResponse(
            {"ok": False, "reason": "undo_failed", "id": undo_id},
            status_code=409,
        )
    forget_goal_completion(undo_id)
    subprocess.Popen(
        [PYTHON, str(PULSE_WEB_PY)],
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return {
        "ok": True,
        "id": undo_id,
        "title": str(entry.get("title") or ""),
        "history": _history_payload(goals_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Local FastAPI server for rebalance pulse.")
    parser.add_argument("--host", default="127.0.0.1", help="bind host (default: loopback)")
    parser.add_argument("--port", type=int, default=8767)
    parser.add_argument("--reload", action="store_true", help="dev auto-reload")
    args = parser.parse_args()

    if args.host not in ("127.0.0.1", "localhost", "::1"):
        print(
            f"refusing to bind to {args.host!r}: no auth on /api/refresh. "
            "use 127.0.0.1 (default) or front it with a reverse proxy.",
            file=sys.stderr,
        )
        return 2

    uvicorn.run(
        "pulse_server:app" if args.reload else app,
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
