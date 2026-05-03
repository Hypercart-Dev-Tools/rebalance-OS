"""
FastAPI entry point for the rebalance-os web dashboard.

Run locally:
    GITHUB_TOKEN=$(gh auth token) REBALANCE_WEB_DB=/tmp/rbos-web.db \
        uvicorn rebalance.web.app:app --reload --port 2030

Routes:
    GET  /                  — single-page HTML dashboard
    GET  /api/activity      — JSON feed (?since=24h | 7d | ISO)
    POST /api/refresh       — trigger an immediate ingest cycle
    GET  /api/health        — health snapshot for uptime checks
"""

from __future__ import annotations

import asyncio
import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from rebalance.web import sources
from rebalance.web.feed import build_feed
from rebalance.web.ingest_loop import IngestState, loop_forever, run_once


def _resolve_db_path() -> Path:
    raw = os.environ.get("REBALANCE_WEB_DB") or os.environ.get("REBALANCE_DB")
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".rebalance" / "web.db"


def _resolve_mirror_path() -> Path | None:
    raw = os.environ.get("REBALANCE_PULSE_MIRROR")
    if not raw:
        return None
    return Path(raw).expanduser()


DB_PATH = _resolve_db_path()
MIRROR_PATH = _resolve_mirror_path()
PACKAGE_DIR = Path(__file__).parent
INGEST_STATE = IngestState()

_basic = HTTPBasic(auto_error=False)
_BASIC_USER = os.environ.get("BASIC_AUTH_USER")
_BASIC_PASS = os.environ.get("BASIC_AUTH_PASS")


def _check_basic_auth(creds: HTTPBasicCredentials | None = Depends(_basic)) -> None:
    if not _BASIC_USER or not _BASIC_PASS:
        return
    if creds is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="basic auth required",
            headers={"WWW-Authenticate": "Basic"},
        )
    user_ok = secrets.compare_digest(creds.username, _BASIC_USER)
    pass_ok = secrets.compare_digest(creds.password, _BASIC_PASS)
    if not (user_ok and pass_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    task: asyncio.Task | None = None
    if os.environ.get("REBALANCE_WEB_DISABLE_LOOP") != "1":
        task = asyncio.create_task(loop_forever(DB_PATH, INGEST_STATE))
    try:
        yield
    finally:
        if task is not None:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass


app = FastAPI(title="rebalance-os activity dashboard", lifespan=lifespan)
templates = Jinja2Templates(directory=str(PACKAGE_DIR / "templates"))
app.mount(
    "/static",
    StaticFiles(directory=str(PACKAGE_DIR / "static")),
    name="static",
)


@app.get("/", response_class=HTMLResponse)
def index(request: Request, _: None = Depends(_check_basic_auth)) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "auto_refresh_ms": int(os.environ.get("REBALANCE_WEB_AUTO_REFRESH_MS", "600000")),
        },
    )


@app.get("/api/activity")
def api_activity(
    since: str = "24h",
    _: None = Depends(_check_basic_auth),
) -> JSONResponse:
    rows = build_feed(DB_PATH, MIRROR_PATH, since)
    return JSONResponse(
        {
            "since": since,
            "count": len(rows),
            "rows": rows,
            "ingest": {
                "last_started_at": INGEST_STATE.last_started_at,
                "last_finished_at": INGEST_STATE.last_finished_at,
                "last_error": INGEST_STATE.last_error,
                "in_flight": INGEST_STATE.in_flight,
                "watched_repos": INGEST_STATE.last_repos,
            },
        }
    )


@app.post("/api/refresh")
async def api_refresh(_: None = Depends(_check_basic_auth)) -> JSONResponse:
    if INGEST_STATE.in_flight:
        return JSONResponse(
            {"ok": False, "reason": "ingest already in flight",
             "started_at": INGEST_STATE.last_started_at},
            status_code=409,
        )
    summary = await asyncio.to_thread(run_once, DB_PATH, INGEST_STATE)
    return JSONResponse({"ok": "error" not in summary, "summary": summary})


@app.get("/api/health")
def api_health(_: None = Depends(_check_basic_auth)) -> JSONResponse:
    info = sources.health(DB_PATH, MIRROR_PATH)
    info["ingest"] = {
        "cycles_completed": INGEST_STATE.cycles_completed,
        "last_started_at": INGEST_STATE.last_started_at,
        "last_finished_at": INGEST_STATE.last_finished_at,
        "in_flight": INGEST_STATE.in_flight,
        "last_error": INGEST_STATE.last_error,
        "watched_repos": INGEST_STATE.last_repos,
    }
    return JSONResponse(info)
