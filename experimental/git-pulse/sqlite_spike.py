#!/usr/bin/env python3
"""Phase 0 spike: ingest git-pulse raw artifacts into SQLite and probe retrieval.

This script is deliberately minimal. It exists to inform the Phase 1 design
before we commit to a real ingest pipeline. It:

  1. Resolves the raw sync folder via the existing git-pulse config contract
  2. Parses pulse-*.md and combined TSV reports into commit_observations
  3. Parses devices/*.yaml into a devices table
  4. Deduplicates using the contract from P1-SQLITE.md
  5. Runs a handful of representative SQL queries
  6. Probes FTS5 and sqlite-vec availability
  7. Prints a findings block ready to paste into P1-SQLITE.md

Not run automatically. Invoke with `python experimental/git-pulse/sqlite_spike.py`.
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from pulse_common import load_sync_repo_dir


DEFAULT_DB_PATH = (
    Path.home()
    / "Library"
    / "Application Support"
    / "git-pulse"
    / "history.sqlite"
)


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS devices (
    device_id TEXT PRIMARY KEY,
    device_name TEXT,
    hostname TEXT,
    timezone_name TEXT,
    utc_offset TEXT,
    pulse_file TEXT
);

CREATE TABLE IF NOT EXISTS commit_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT,
    author_login TEXT,
    repo TEXT NOT NULL,
    branch TEXT,
    short_sha TEXT,
    subject TEXT,
    epoch_utc INTEGER,
    timestamp_utc TEXT,
    source_tz_offset_minutes INTEGER,
    source_tz_name TEXT,
    local_day TEXT,
    local_time TEXT,
    source_type TEXT NOT NULL,
    source_file TEXT,
    source_line INTEGER,
    kind TEXT NOT NULL DEFAULT 'commit',
    pr_number TEXT,
    dedupe_key TEXT NOT NULL UNIQUE
);

CREATE INDEX IF NOT EXISTS idx_obs_timestamp ON commit_observations(timestamp_utc);
CREATE INDEX IF NOT EXISTS idx_obs_device ON commit_observations(device_id);
CREATE INDEX IF NOT EXISTS idx_obs_repo ON commit_observations(repo);
CREATE INDEX IF NOT EXISTS idx_obs_short_sha ON commit_observations(short_sha);

CREATE TABLE IF NOT EXISTS ingest_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at_utc TEXT,
    completed_at_utc TEXT,
    source_root TEXT,
    rows_read INTEGER,
    rows_inserted INTEGER,
    duplicates_skipped INTEGER,
    malformed_skipped INTEGER
);
"""


TSV_HEADER = [
    "local_day",
    "local_time",
    "utc_time",
    "device_id",
    "device_name",
    "repo",
    "branch",
    "short_sha",
    "subject",
]


def resolve_db_path() -> Path:
    override = os.environ.get("GIT_PULSE_DB_PATH")
    if override:
        return Path(override).expanduser()
    return DEFAULT_DB_PATH


def resolve_sync_repo_dir() -> Path:
    config_dir = Path(
        os.environ.get("GIT_PULSE_CONFIG_DIR")
        or os.environ.get("GIT_HISTORY_CONFIG_DIR")
        or Path.home() / ".config" / "git-pulse"
    )
    sync_repo_dir = load_sync_repo_dir(config_dir / "config.sh", config_dir)
    if sync_repo_dir is None:
        raise SystemExit(
            "Could not resolve sync_repo_dir from ~/.config/git-pulse/config.sh"
        )
    return sync_repo_dir


def yaml_value(path: Path, key: str) -> str:
    prefix = f"{key}: "
    for raw_line in path.read_text().splitlines():
        if not raw_line.startswith(prefix):
            continue
        value = raw_line[len(prefix):].strip()
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        return value.replace('\\"', '"').replace("\\\\", "\\")
    return ""


def parse_devices(sync_repo_dir: Path) -> list[dict]:
    devices_dir = sync_repo_dir / "devices"
    if not devices_dir.is_dir():
        return []
    rows = []
    for path in sorted(devices_dir.glob("*.yaml")):
        device_id = yaml_value(path, "device_id")
        if not device_id:
            continue
        rows.append(
            {
                "device_id": device_id,
                "device_name": yaml_value(path, "device_name") or device_id,
                "hostname": yaml_value(path, "hostname"),
                "timezone_name": yaml_value(path, "timezone_name"),
                "utc_offset": yaml_value(path, "utc_offset"),
                "pulse_file": yaml_value(path, "pulse_file"),
            }
        )
    return rows


def infer_device_id_from_pulse_filename(path: Path) -> str:
    name = path.name
    if name.startswith("pulse-") and name.endswith(".md"):
        return name[len("pulse-") : -len(".md")]
    return ""


def parse_pulse_file(path: Path) -> list[dict]:
    """Parse a pulse-*.md file into observation dicts.

    Format: 6-column TSV (epoch, timestamp_utc, repo, branch, short_sha, subject)
    after the HTML comment header block.
    """
    device_id = infer_device_id_from_pulse_filename(path)
    rows: list[dict] = []
    in_header_comment = False
    for lineno, raw_line in enumerate(path.read_text().splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("<!--"):
            in_header_comment = True
            if stripped.endswith("-->"):
                in_header_comment = False
            continue
        if in_header_comment:
            if stripped.endswith("-->"):
                in_header_comment = False
            continue
        parts = raw_line.split("\t")
        if len(parts) != 6:
            continue
        epoch_s, ts_utc, repo, branch, short_sha, subject = parts
        try:
            epoch = int(epoch_s)
        except ValueError:
            continue
        rows.append(
            {
                "device_id": device_id,
                "repo": repo,
                "branch": branch,
                "short_sha": short_sha,
                "subject": subject,
                "epoch_utc": epoch,
                "timestamp_utc": ts_utc,
                "source_type": "pulse",
                "source_file": str(path),
                "source_line": lineno,
                "kind": "commit",
            }
        )
    return rows


def parse_combined_tsv(path: Path) -> list[dict]:
    rows: list[dict] = []
    for lineno, raw_line in enumerate(path.read_text().splitlines(), start=1):
        if not raw_line.strip():
            continue
        if raw_line == "\t".join(TSV_HEADER):
            continue
        parts = raw_line.split("\t")
        if len(parts) != len(TSV_HEADER):
            continue
        (
            local_day,
            local_time,
            utc_time,
            device_id,
            _device_name,
            repo,
            branch,
            short_sha,
            subject,
        ) = parts
        rows.append(
            {
                "device_id": device_id,
                "repo": repo,
                "branch": branch,
                "short_sha": short_sha,
                "subject": subject,
                "timestamp_utc": utc_time,
                "local_day": local_day,
                "local_time": local_time,
                "source_type": "reports_tsv",
                "source_file": str(path),
                "source_line": lineno,
                "kind": "commit",
            }
        )
    return rows


def compute_dedupe_key(row: dict) -> str:
    device_segment = (row.get("device_id") or "").strip().lower()
    if not device_segment:
        device_segment = f"team:{row.get('source_type', 'unknown')}"
    segments = [
        device_segment,
        (row.get("repo") or "").strip().lower(),
        (row.get("short_sha") or "").strip().lower(),
        (row.get("timestamp_utc") or "").strip(),
        row.get("kind", "commit"),
        (row.get("pr_number") or "-").strip(),
    ]
    return hashlib.sha1("|".join(segments).encode("utf-8")).hexdigest()


def ingest(
    conn: sqlite3.Connection, devices: list[dict], rows: list[dict]
) -> tuple[int, int, int]:
    conn.execute("BEGIN")
    for d in devices:
        conn.execute(
            """
            INSERT INTO devices(device_id, device_name, hostname, timezone_name, utc_offset, pulse_file)
            VALUES(:device_id, :device_name, :hostname, :timezone_name, :utc_offset, :pulse_file)
            ON CONFLICT(device_id) DO UPDATE SET
              device_name = excluded.device_name,
              hostname = excluded.hostname,
              timezone_name = excluded.timezone_name,
              utc_offset = excluded.utc_offset,
              pulse_file = excluded.pulse_file
            """,
            d,
        )

    inserted = 0
    duplicates = 0
    malformed = 0
    for row in rows:
        if not row.get("short_sha") or not row.get("timestamp_utc"):
            malformed += 1
            continue
        row.setdefault("kind", "commit")
        row.setdefault("pr_number", None)
        row.setdefault("author_login", None)
        row.setdefault("epoch_utc", None)
        row.setdefault("source_tz_offset_minutes", None)
        row.setdefault("source_tz_name", None)
        row.setdefault("local_day", None)
        row.setdefault("local_time", None)
        row["dedupe_key"] = compute_dedupe_key(row)
        try:
            conn.execute(
                """
                INSERT INTO commit_observations(
                    device_id, author_login, repo, branch, short_sha, subject,
                    epoch_utc, timestamp_utc, source_tz_offset_minutes,
                    source_tz_name, local_day, local_time, source_type,
                    source_file, source_line, kind, pr_number, dedupe_key
                ) VALUES (
                    :device_id, :author_login, :repo, :branch, :short_sha, :subject,
                    :epoch_utc, :timestamp_utc, :source_tz_offset_minutes,
                    :source_tz_name, :local_day, :local_time, :source_type,
                    :source_file, :source_line, :kind, :pr_number, :dedupe_key
                )
                """,
                row,
            )
            inserted += 1
        except sqlite3.IntegrityError:
            duplicates += 1
    conn.execute("COMMIT")
    return inserted, duplicates, malformed


def log_ingest_run(
    conn: sqlite3.Connection,
    *,
    started: str,
    completed: str,
    source_root: str,
    rows_read: int,
    rows_inserted: int,
    duplicates: int,
    malformed: int,
) -> None:
    conn.execute(
        """
        INSERT INTO ingest_runs(started_at_utc, completed_at_utc, source_root,
                                rows_read, rows_inserted, duplicates_skipped, malformed_skipped)
        VALUES(?, ?, ?, ?, ?, ?, ?)
        """,
        (
            started,
            completed,
            source_root,
            rows_read,
            rows_inserted,
            duplicates,
            malformed,
        ),
    )
    conn.commit()


def probe_fts5(conn: sqlite3.Connection) -> str:
    try:
        conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS _fts_probe USING fts5(x)")
        conn.execute("DROP TABLE _fts_probe")
        return "available"
    except sqlite3.OperationalError as exc:
        return f"unavailable: {exc}"


def probe_sqlite_vec(conn: sqlite3.Connection) -> str:
    try:
        conn.enable_load_extension(True)
    except (AttributeError, sqlite3.NotSupportedError) as exc:
        return f"enable_load_extension unavailable: {exc}"
    try:
        import sqlite_vec  # noqa: WPS433  (stdlib-style import late is fine)
        sqlite_vec.load(conn)
        row = conn.execute("SELECT vec_version()").fetchone()
        return f"available (vec_version={row[0]})"
    except Exception as exc:  # noqa: BLE001
        return f"unavailable: {type(exc).__name__}: {exc}"
    finally:
        try:
            conn.enable_load_extension(False)
        except Exception:  # noqa: BLE001
            pass


def run_queries(conn: sqlite3.Connection) -> list[tuple[str, list]]:
    qs = [
        (
            "count by source_type",
            "SELECT source_type, COUNT(*) FROM commit_observations GROUP BY source_type ORDER BY COUNT(*) DESC",
        ),
        (
            "last commit per repo",
            "SELECT repo, MAX(timestamp_utc), COUNT(*) FROM commit_observations GROUP BY repo ORDER BY MAX(timestamp_utc) DESC",
        ),
        (
            "observations per device",
            "SELECT COALESCE(device_id, '(none)'), COUNT(*) FROM commit_observations GROUP BY device_id ORDER BY COUNT(*) DESC",
        ),
        (
            "same short_sha seen by multiple sources",
            """
            SELECT repo, short_sha, COUNT(DISTINCT source_type) AS sources, GROUP_CONCAT(DISTINCT source_type)
            FROM commit_observations
            GROUP BY repo, short_sha
            HAVING sources > 1
            ORDER BY sources DESC
            LIMIT 10
            """,
        ),
        (
            "device alias candidates (pulse_file vs device_id mismatch)",
            """
            SELECT device_id, pulse_file
            FROM devices
            WHERE pulse_file IS NOT NULL
              AND pulse_file != ''
              AND pulse_file != ('pulse-' || device_id || '.md')
            """,
        ),
    ]
    results = []
    for label, sql in qs:
        rows = conn.execute(sql).fetchall()
        results.append((label, rows))
    return results


def main() -> int:
    print("=== git-pulse SQLite spike ===")
    sync_repo_dir = resolve_sync_repo_dir()
    print(f"sync_repo_dir: {sync_repo_dir}")

    db_path = resolve_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    # Fresh spike: drop any prior scratch DB so results are reproducible
    if db_path.exists():
        db_path.unlink()
    print(f"db_path: {db_path}")

    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA_SQL)

    print(f"\nfts5 probe: {probe_fts5(conn)}")
    print(f"sqlite-vec probe: {probe_sqlite_vec(conn)}")

    # Collect inputs
    devices = parse_devices(sync_repo_dir)
    print(f"\ndevices parsed: {len(devices)}")

    all_rows: list[dict] = []
    pulse_files = sorted(sync_repo_dir.glob("pulse-*.md"))
    for pf in pulse_files:
        parsed = parse_pulse_file(pf)
        print(f"  {pf.name}: {len(parsed)} rows")
        all_rows.extend(parsed)

    reports_dir = sync_repo_dir / "reports"
    tsv_files = sorted(reports_dir.glob("*.tsv")) if reports_dir.is_dir() else []
    for tf in tsv_files:
        parsed = parse_combined_tsv(tf)
        print(f"  reports/{tf.name}: {len(parsed)} rows")
        all_rows.extend(parsed)

    # Ingest
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    t0 = time.perf_counter()
    inserted, duplicates, malformed = ingest(conn, devices, all_rows)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    completed = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    log_ingest_run(
        conn,
        started=started,
        completed=completed,
        source_root=str(sync_repo_dir),
        rows_read=len(all_rows),
        rows_inserted=inserted,
        duplicates=duplicates,
        malformed=malformed,
    )
    print(
        f"\ningest: rows_read={len(all_rows)} inserted={inserted} "
        f"duplicates={duplicates} malformed={malformed} "
        f"elapsed_ms={elapsed_ms:.1f}"
    )
    print(f"db size: {db_path.stat().st_size} bytes")

    # Queries
    print("\n=== representative queries ===")
    for label, rows in run_queries(conn):
        print(f"\n# {label}")
        if not rows:
            print("  (no rows)")
            continue
        for row in rows:
            print(f"  {row}")

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
