#!/usr/bin/env python3
"""Freshness dashboard spike — read-only view of last-run state per input.

Reads $REBALANCE_DB and classifies each source as
FRESH / WARN / STALE / ALERT / NEVER_RUN. No writes, no history, no auth.

Usage:
    python spike.py                    # terminal table
    python spike.py --json             # machine-readable
    python spike.py --serve            # HTTP on :8765 with auto-refresh
    python spike.py --serve --port N   # custom port
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# (warn, stale, alert) in seconds. Daily cadence → 26h grace, 49h = two misses, 7d = escalate.
DAILY = (26 * 3600, 49 * 3600, 7 * 86400)

# Vector meta tables are (key, value) stores written by the embed step. Reading
# key='last_embed_at' yields an ISO8601 timestamp of the most recent embed run.
# None means the source is structured-only and not vectorized by design.
SOURCES = [
    # (label, table, timestamp_col, count_expr, thresholds, vector_spec)
    # vector_spec = (meta_table, meta_key, thresholds) | None
    ("Obsidian vault",    "vault_files",      "ingested_at",      "COUNT(*)",                       DAILY, ("embedding_meta",        "last_embed_at", DAILY)),
    ("GitHub scan",       "github_activity",  "scanned_at",       "COUNT(DISTINCT repo_full_name)", DAILY, ("github_embedding_meta", "last_embed_at", DAILY)),
    ("Sleuth reminders",  "sleuth_reminders", "last_synced_at",   "COUNT(*)",                       DAILY, None),
    ("Google Calendar",   "calendar_events",  "fetched_at",       "COUNT(*)",                       DAILY, None),
]


@dataclass
class Row:
    label: str
    table: str
    state: str                              # FRESH | WARN | STALE | ALERT | NEVER_RUN
    last_run_utc: str | None
    age_seconds: int | None
    age_human: str
    row_count: int | None
    vector_state: str = "NOT_APPLICABLE"    # + NOT_APPLICABLE for structured-only sources
    last_vectorized_utc: str | None = None
    vector_age_seconds: int | None = None
    vector_age_human: str = "—"
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    v = value.strip()
    if v.endswith("Z"):
        v = v[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(v).astimezone(timezone.utc)
    except ValueError:
        return None


def classify(age_seconds: int | None, thresholds: tuple[int, int, int]) -> str:
    if age_seconds is None:
        return "NEVER_RUN"
    warn, stale, alert = thresholds
    if age_seconds >= alert:
        return "ALERT"
    if age_seconds >= stale:
        return "STALE"
    if age_seconds >= warn:
        return "WARN"
    return "FRESH"


def human_age(seconds: int | None) -> str:
    if seconds is None:
        return "—"
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m"
    if seconds < 86400:
        return f"{seconds / 3600:.1f}h"
    return f"{seconds / 86400:.1f}d"


def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def read_vector_meta(conn: sqlite3.Connection | None,
                     vector_spec: tuple[str, str, tuple[int, int, int]] | None,
                     now: datetime) -> tuple[str, str | None, int | None, str]:
    """Return (vector_state, last_utc, age_seconds, age_human) for one source."""
    if vector_spec is None:
        return "NOT_APPLICABLE", None, None, "—"
    meta_table, meta_key, thresholds = vector_spec
    if conn is None or not table_exists(conn, meta_table):
        return "NEVER_RUN", None, None, "—"
    row = conn.execute(
        f"SELECT value FROM {meta_table} WHERE key = ?", (meta_key,)
    ).fetchone()
    last_dt = parse_iso(row[0]) if row else None
    if last_dt is None:
        return "NEVER_RUN", None, None, "—"
    age = max(int((now - last_dt).total_seconds()), 0)
    return classify(age, thresholds), last_dt.isoformat(), age, human_age(age)


def read_source(conn: sqlite3.Connection | None, label: str, table: str,
                ts_col: str, count_expr: str, thresholds: tuple[int, int, int],
                vector_spec: tuple[str, str, tuple[int, int, int]] | None,
                now: datetime) -> Row:
    vstate, vlast, vage, vage_h = read_vector_meta(conn, vector_spec, now)

    if conn is None:
        return Row(label, table, "NEVER_RUN", None, None, "—", None,
                   vstate, vlast, vage, vage_h, note="DB missing")
    if not table_exists(conn, table):
        return Row(label, table, "NEVER_RUN", None, None, "—", None,
                   vstate, vlast, vage, vage_h, note="table missing")

    row = conn.execute(f"SELECT MAX({ts_col}), {count_expr} FROM {table}").fetchone()
    last_raw, count = row[0], row[1]
    last_dt = parse_iso(last_raw)
    if last_dt is None:
        return Row(label, table, "NEVER_RUN", None, None, "—", count or 0,
                   vstate, vlast, vage, vage_h, note="empty table")

    age = max(int((now - last_dt).total_seconds()), 0)
    return Row(
        label=label,
        table=table,
        state=classify(age, thresholds),
        last_run_utc=last_dt.isoformat(),
        age_seconds=age,
        age_human=human_age(age),
        row_count=count or 0,
        vector_state=vstate,
        last_vectorized_utc=vlast,
        vector_age_seconds=vage,
        vector_age_human=vage_h,
    )


def collect(db_path: Path, now: datetime | None = None) -> list[Row]:
    now = now or datetime.now(timezone.utc)
    conn: sqlite3.Connection | None = None
    try:
        if db_path.exists() and db_path.stat().st_size > 0:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        return [read_source(conn, *s, now=now) for s in SOURCES]
    finally:
        if conn is not None:
            conn.close()


# ── Output renderers ────────────────────────────────────────────────────────
STATE_COLOR = {
    "FRESH":          "\033[92m",  # green
    "WARN":           "\033[93m",  # yellow
    "STALE":          "\033[33m",  # dark yellow
    "ALERT":          "\033[91m",  # red
    "NEVER_RUN":      "\033[90m",  # grey
    "NOT_APPLICABLE": "\033[90m",  # grey (structured-only sources)
}
RESET = "\033[0m"


def _colorize(state: str, width: int, use_color: bool) -> str:
    if use_color:
        return f"{STATE_COLOR.get(state, '')}{state:<{width}}{RESET}"
    return f"{state:<{width}}"


def render_text(rows: list[Row], use_color: bool) -> str:
    header = (f"{'SOURCE':<20} {'INGEST':<10} {'AGE':<7} {'ROWS':>6}  "
              f"{'VECTOR':<14} {'VEC AGE':<8}  NOTE")
    lines = [header, "-" * len(header)]
    for r in rows:
        ingest = _colorize(r.state, 10, use_color)
        vec = _colorize(r.vector_state, 14, use_color)
        rows_s = "—" if r.row_count is None else str(r.row_count)
        lines.append(
            f"{r.label:<20} {ingest} {r.age_human:<7} {rows_s:>6}  "
            f"{vec} {r.vector_age_human:<8}  {r.note}"
        )
    return "\n".join(lines)


def render_json(rows: list[Row]) -> str:
    return json.dumps(
        {"generated_at": datetime.now(timezone.utc).isoformat(), "sources": [r.to_dict() for r in rows]},
        indent=2,
    )


STATE_CSS = {
    "FRESH":          "#1f883d",
    "WARN":           "#bf8700",
    "STALE":          "#9a6700",
    "ALERT":          "#cf222e",
    "NEVER_RUN":      "#6e7781",
    "NOT_APPLICABLE": "#8c959f",
}


def render_html(rows: list[Row], refresh_seconds: int = 30) -> str:
    trs = []
    for r in rows:
        icolor = STATE_CSS.get(r.state, "#6e7781")
        vcolor = STATE_CSS.get(r.vector_state, "#6e7781")
        last_run = r.last_run_utc or "—"
        last_vec = r.last_vectorized_utc or "—"
        rows_s = "—" if r.row_count is None else str(r.row_count)
        trs.append(
            f"<tr>"
            f"<td>{r.label}</td>"
            f"<td><span class='pill' style='background:{icolor}'>{r.state}</span></td>"
            f"<td class='mono'>{last_run}</td>"
            f"<td>{r.age_human}</td>"
            f"<td class='num'>{rows_s}</td>"
            f"<td><span class='pill' style='background:{vcolor}'>{r.vector_state}</span></td>"
            f"<td class='mono'>{last_vec}</td>"
            f"<td>{r.vector_age_human}</td>"
            f"<td class='note'>{r.note}</td>"
            f"</tr>"
        )
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return f"""<!doctype html>
<html><head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="{refresh_seconds}">
<title>rebalance OS — freshness</title>
<style>
  body {{ font: 14px -apple-system, system-ui, sans-serif; padding: 24px; color: #1f2328; }}
  h1 {{ font-size: 18px; margin: 0 0 4px; }}
  .sub {{ color: #656d76; font-size: 12px; margin-bottom: 16px; }}
  table {{ border-collapse: collapse; width: 100%; max-width: 1200px; }}
  th, td {{ text-align: left; padding: 8px 12px; border-bottom: 1px solid #d0d7de; }}
  th {{ font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; color: #656d76; }}
  .mono {{ font-family: ui-monospace, Menlo, monospace; font-size: 12px; }}
  .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .note {{ color: #656d76; font-size: 12px; }}
  .pill {{ color: white; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; white-space: nowrap; }}
</style>
</head><body>
<h1>rebalance OS — freshness</h1>
<div class="sub">Generated {now} · auto-refresh every {refresh_seconds}s · <a href="/status.json">status.json</a></div>
<table>
  <thead><tr>
    <th>Source</th><th>Ingest</th><th>Last run (UTC)</th><th>Age</th><th>Rows</th>
    <th>Vector</th><th>Last vectorized (UTC)</th><th>Vec age</th><th>Note</th>
  </tr></thead>
  <tbody>{''.join(trs)}</tbody>
</table>
</body></html>"""


# ── HTTP server ─────────────────────────────────────────────────────────────
def make_handler(db_path: Path):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # quieter default logging
            sys.stderr.write(f"[{self.log_date_time_string()}] {fmt % args}\n")

        def do_GET(self):
            rows = collect(db_path)
            if self.path == "/status.json":
                body = render_json(rows).encode()
                ctype = "application/json; charset=utf-8"
            elif self.path in ("/", "/index.html"):
                body = render_html(rows).encode()
                ctype = "text/html; charset=utf-8"
            else:
                self.send_response(404)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
    return Handler


def serve(db_path: Path, port: int) -> None:
    httpd = ThreadingHTTPServer(("127.0.0.1", port), make_handler(db_path))
    print(f"rebalance freshness dashboard → http://127.0.0.1:{port}/  (Ctrl-C to stop)",
          file=sys.stderr)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nbye", file=sys.stderr)


def resolve_db() -> Path:
    env = os.environ.get("REBALANCE_DB")
    if env:
        return Path(env).expanduser()
    return Path.cwd() / "rebalance.db"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="rebalance OS freshness dashboard (spike)")
    p.add_argument("--db", type=Path, default=None, help="path to rebalance.db (defaults to $REBALANCE_DB or ./rebalance.db)")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--json", action="store_true", help="emit JSON to stdout")
    mode.add_argument("--serve", action="store_true", help="start HTTP server")
    p.add_argument("--port", type=int, default=8765, help="port for --serve (default 8765)")
    p.add_argument("--no-color", action="store_true", help="disable ANSI color in text output")
    args = p.parse_args(argv)

    db_path = args.db or resolve_db()

    if args.serve:
        serve(db_path, args.port)
        return 0

    rows = collect(db_path)
    if args.json:
        print(render_json(rows))
    else:
        print(f"DB: {db_path}")
        print(render_text(rows, use_color=sys.stdout.isatty() and not args.no_color))
        severity = {"ALERT": 3, "STALE": 2, "WARN": 1}
        exit_code = {"ALERT": 2, "STALE": 1}
        all_states = [r.state for r in rows] + [r.vector_state for r in rows]
        worst = max(all_states, key=lambda s: severity.get(s, 0))
        return exit_code.get(worst, 0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
