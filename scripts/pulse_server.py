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
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
import uvicorn

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PULSE_HTML = PROJECT_ROOT / "web" / "pulse.html"
PULSE_WEB_PY = PROJECT_ROOT / "scripts" / "pulse_web.py"
PYTHON = sys.executable

sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
from pulse_web import (  # noqa: E402
    complete_goal_in_file,
    forget_goal_completion,
    _goal_completion_still_applied,
    remember_goal_completion,
    resolve_goals_path,
    load_goal_history,
    undo_goal_completion_in_file,
)

app = FastAPI(title="rebalance pulse (local)", docs_url=None, redoc_url=None)

# Serve the auth-activity log and Focus 5 view from this always-running server
# too, so their links work without a separate `rebalance serve` process on
# :8787. Reuses the renderers in rebalance.web (no duplication).
from rebalance.web import (  # noqa: E402
    auth_log_page as _auth_log_page,
    auth_log_raw as _auth_log_raw,
    focus5_page as _focus5_page,
)


@app.get("/auth-log")
def auth_log():
    return _auth_log_page()


@app.get("/auth-log/raw")
def auth_log_raw():
    return _auth_log_raw()


@app.get("/focus-5")
def focus5(refresh: bool = False):
    return _focus5_page(refresh=refresh)


class ChatRequest(BaseModel):
    query: str
    scope: str = "all"
    top_k: int = 8


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
def index():
    if not PULSE_HTML.exists():
        raise HTTPException(
            status_code=503,
            detail=f"pulse.html not generated yet. Run: {PYTHON} {PULSE_WEB_PY}",
        )
    # no-store so the browser always picks up the freshly regenerated file
    return FileResponse(
        PULSE_HTML,
        media_type="text/html; charset=utf-8",
        headers={"Cache-Control": "no-store"},
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
    if not PULSE_WEB_PY.exists():
        raise HTTPException(status_code=500, detail=f"missing {PULSE_WEB_PY}")
    started = time.perf_counter()
    proc = subprocess.run(
        [PYTHON, str(PULSE_WEB_PY)],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )
    duration_ms = round((time.perf_counter() - started) * 1000)
    if proc.returncode != 0:
        return JSONResponse(
            {
                "ok": False,
                "duration_ms": duration_ms,
                "returncode": proc.returncode,
                "stderr": proc.stderr[-2000:],
            },
            status_code=500,
        )
    mtime = datetime.fromtimestamp(PULSE_HTML.stat().st_mtime, tz=timezone.utc)
    return {
        "ok": True,
        "duration_ms": duration_ms,
        "generated_at": mtime.isoformat(),
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
