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
from pulse_web import complete_goal_in_file, resolve_goals_path  # noqa: E402

app = FastAPI(title="rebalance pulse (local)", docs_url=None, redoc_url=None)


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
    ok = complete_goal_in_file(goals_path, title)
    if not ok:
        # The most useful client-visible reason is that the title no longer
        # matches an unchecked line — file may have been edited since render.
        return JSONResponse(
            {"ok": False, "reason": "not_found", "title": title},
            status_code=404,
        )
    # Regenerate the static HTML so a manual reload (or external file:// open)
    # reflects the new state without waiting for the launchd 30-min cycle.
    subprocess.Popen(
        [PYTHON, str(PULSE_WEB_PY)],
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return {"ok": True, "title": title}


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
