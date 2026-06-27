"""
Apple Reminders extractor — read-only, snapshot-based ingest of the local
macOS Reminders store.

This is a LOCAL READ-ONLY source. It never opens a handle on Apple's live
store: it file-copies the SQLite triplet (``.sqlite`` + ``-wal`` + ``-shm``)
into a temp working folder and reads the copy with ``mode=ro``. Nothing here
mutates Apple's database under any code path — that is the load-bearing safety
invariant for the whole Apple Reminders integration (see
PROJECT/2-WORKING/APPLE-REMINDERS-UNIFIED-PLAN.md).

Scope (Phase 1): discover the active store, snapshot it, dynamically map the
Core Data schema, and emit normalized :class:`AppleReminder` records. It does
NOT upsert into a rebalance-managed table — collector registration and storage
are Phase 2, kept deliberately separate so the read path can be verified in
isolation.

Schema reality (REMCD / CloudKit store, macOS 2024+):

* Reminders live in ``ZREMCDREMINDER``; lists in ``ZREMCDBASELIST``.
* ``ZCKIDENTIFIER`` is a stable UUID string present on every row — used as the
  reminder id rather than decoding the raw ``ZIDENTIFIER`` UUID blob.
* Timestamps are Core Data "seconds since 2001-01-01 UTC" — add
  :data:`CORE_DATA_EPOCH_OFFSET` to convert to a Unix timestamp.
* ``ZNOTES`` is empty on modern stores; notes moved into the zlib-compressed
  ``ZNOTESDOCUMENT`` attributed-string blob. We do a bounded best-effort decode
  and record a mapping fallback; full-fidelity note parsing is deferred.
* Sections (``ZREMCDBASESECTION``) are not a direct FK on the reminder; the
  reminder→section membership is encoded in a per-list blob. Section names are
  therefore best-effort/None for now (no section rows in the reference store).

Column access is dynamic: we resolve the actual columns of the reminder table
and only select the ones that exist, so an OS update that drops or renames an
optional column degrades gracefully instead of raising. A missing *required*
table/column (the reminder table itself, ``ZTITLE``, or ``ZCKIDENTIFIER``)
raises :class:`AppleRemindersSchemaError` with the specific missing symbol.
"""

from __future__ import annotations

import hashlib
import json
import logging
import platform
import re
import shutil
import sqlite3
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Seconds between the Unix epoch (1970-01-01) and the Core Data / NSDate
# reference date (2001-01-01), both UTC. Core Data TIMESTAMP columns store
# seconds since 2001; add this to get a Unix timestamp.
CORE_DATA_EPOCH_OFFSET = 978307200

# Known roots for the macOS Reminders store, most-current first. The active
# store is one of several ``Data-*.sqlite`` account stores under here.
APPLE_REMINDERS_STORE_ROOTS: tuple[str, ...] = (
    "~/Library/Group Containers/group.com.apple.reminders/Container_v1/Stores",
)

# Candidate reminder/list table names, current schema first then legacy. The
# resolver picks whichever exists so we don't hardcode one schema generation.
_REMINDER_TABLE_CANDIDATES = ("ZREMCDREMINDER", "ZREMINDER")
_LIST_TABLE_CANDIDATES = ("ZREMCDBASELIST", "ZREMINDERLIST")

# Hashtag in a title/notes string: '#' at a word boundary (start-of-string or
# after whitespace — NOT after a '/' so URL fragments like ".../#inbox/x" don't
# match), then a tag that STARTS WITH A LETTER. The leading-letter rule rejects
# the common false positives in real data: suite numbers (#225), invoice numbers
# (#110695), and ticket ids (#3365707608). This is still best-effort — full tag
# fidelity lives in the title-document blob / resolution token map, which we do
# not parse here; tested against the live store, this matches the real tags.
_HASHTAG_RE = re.compile(r"(?:^|(?<=\s))#([A-Za-z][\w-]*)")

# ASCII printable-run extractor for the best-effort notes-document decode. ASCII
# only on purpose: the high-byte range yields latin-1 mojibake from the binary
# archive rather than real text.
_PRINTABLE_RUN_RE = re.compile(rb"[\x20-\x7e]{4,}")


class AppleRemindersError(Exception):
    """Base class for Apple Reminders extraction failures."""


class AppleRemindersAccessError(AppleRemindersError):
    """The Reminders store directory is missing or unreadable.

    On macOS an unreadable store almost always means the host process lacks
    Full Disk Access (TCC). The message carries the actionable remediation."""


class AppleRemindersSchemaError(AppleRemindersError):
    """A required table or column is absent — the schema drifted.

    Names the specific missing symbol so an operator can triage an OS upgrade
    that changed the Core Data schema."""


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AppleReminder:
    """One normalized reminder. Matches the plan's data contract."""

    reminder_id: str
    title: str
    notes: str | None
    is_completed: bool
    due_at: datetime | None
    completed_at: datetime | None
    list_name: str | None
    section_name: str | None
    tags: tuple[str, ...]
    parent_reminder_id: str | None
    sort_hint: float | None
    created_at: datetime | None
    updated_at: datetime | None
    raw_payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class AppleRemindersExtractResult:
    """Summary of one extraction run (for logging / freshness reporting)."""

    store_path: str
    snapshot_dir: str
    extracted_count: int
    skipped_count: int
    list_count: int
    duration_seconds: float
    mapping_fallbacks: tuple[str, ...] = ()
    schema_fingerprint: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "store_path": self.store_path,
            "snapshot_dir": self.snapshot_dir,
            "extracted_count": self.extracted_count,
            "skipped_count": self.skipped_count,
            "list_count": self.list_count,
            "duration_seconds": round(self.duration_seconds, 3),
            "mapping_fallbacks": list(self.mapping_fallbacks),
            "schema_fingerprint": self.schema_fingerprint,
        }


# ---------------------------------------------------------------------------
# Conversion helpers
# ---------------------------------------------------------------------------


def core_data_timestamp(value: Any) -> datetime | None:
    """Convert a Core Data TIMESTAMP (seconds since 2001-01-01 UTC) to an
    aware UTC datetime. Returns None for NULL / non-numeric values."""
    if value is None:
        return None
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(seconds + CORE_DATA_EPOCH_OFFSET, tz=timezone.utc)


def parse_hashtags(*texts: str | None) -> tuple[str, ...]:
    """Extract unique ``#hashtags`` from the given text(s), order-preserving."""
    seen: dict[str, None] = {}
    for text in texts:
        if not text:
            continue
        for match in _HASHTAG_RE.findall(text):
            seen.setdefault(match, None)
    return tuple(seen)


def _decode_notes_document(blob: bytes) -> str | None:
    """Best-effort text recovery from a ``ZNOTESDOCUMENT`` blob.

    The blob is a zlib-compressed archived attributed string (the text is often
    UTF-16 inside a binary plist). Full fidelity requires parsing the archive;
    here we inflate and pull ASCII printable runs as a best-effort recovery.

    Crucially, we return None rather than emit mojibake: if the recovered text
    isn't substantially letters (i.e. we only pulled archive framing bytes, not
    real words), we treat the note as unrecoverable here and defer it. Better an
    honest None than a garbage note."""
    try:
        raw = zlib.decompress(blob)
    except (zlib.error, TypeError):
        return None
    runs = _PRINTABLE_RUN_RE.findall(raw)
    if not runs:
        return None
    text = " ".join(r.decode("ascii", errors="ignore").strip() for r in runs).strip()
    if not text:
        return None
    # Reject framing/garbage: require a real word and a majority-letter result.
    letters = sum(c.isalpha() for c in text)
    if letters < 3 or letters / len(text) < 0.5:
        return None
    return text


# ---------------------------------------------------------------------------
# Schema resolution (dynamic — no hardcoded Z_ENT assumptions)
# ---------------------------------------------------------------------------


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def compute_schema_fingerprint(db_path: Path) -> dict[str, Any]:
    """Lightweight fingerprint of the store schema, for upgrade-drift triage.

    Captures the macOS/sqlite versions, the resolved table names, and a short
    hash of the reminder table's column set. A change in ``columns_sha`` across
    runs is the cheapest signal that a macOS update reshaped the Core Data
    schema. Best-effort — never raises; returns ``{}`` on any failure."""
    fp: dict[str, Any] = {
        "macos": platform.mac_ver()[0] or "",
        "sqlite": sqlite3.sqlite_version,
    }
    try:
        conn = _open_ro(db_path)
    except sqlite3.Error:
        return fp
    try:
        reminder_table = _resolve_table(conn, _REMINDER_TABLE_CANDIDATES)
        list_table = _resolve_table(conn, _LIST_TABLE_CANDIDATES)
        fp["reminder_table"] = reminder_table
        fp["list_table"] = list_table
        if reminder_table:
            cols = sorted(_table_columns(conn, reminder_table))
            fp["reminder_column_count"] = len(cols)
            fp["columns_sha"] = hashlib.sha256(
                ",".join(cols).encode("utf-8")
            ).hexdigest()[:12]
    except sqlite3.Error:
        pass
    finally:
        conn.close()
    return fp


def _resolve_table(conn: sqlite3.Connection, candidates: tuple[str, ...]) -> str | None:
    present = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    for name in candidates:
        if name in present:
            return name
    return None


# ---------------------------------------------------------------------------
# Discovery + snapshot (never touches the live store beyond a file copy)
# ---------------------------------------------------------------------------


def discover_stores_dir() -> Path:
    """Return the first existing, readable Reminders store directory.

    Raises :class:`AppleRemindersAccessError` if none can be listed — the
    common cause is the host process lacking Full Disk Access."""
    tried: list[str] = []
    for root in APPLE_REMINDERS_STORE_ROOTS:
        path = Path(root).expanduser()
        tried.append(str(path))
        if not path.is_dir():
            continue
        try:
            # Probe readability — TCC denial surfaces here, not at is_dir().
            next(path.iterdir(), None)
        except PermissionError:
            raise AppleRemindersAccessError(
                f"Reminders store dir is not readable: {path}. Grant Full Disk "
                f"Access to the host process (System Settings -> Privacy & "
                f"Security -> Full Disk Access) and restart it."
            )
        except OSError:
            continue
        return path
    raise AppleRemindersAccessError(
        "No readable Reminders store directory found. Tried: " + ", ".join(tried)
    )


def snapshot_stores(stores_dir: Path, dest: Path) -> list[Path]:
    """Copy every ``Data-*.sqlite`` triplet into ``dest``; return copy paths.

    Copies ``.sqlite`` plus its ``-wal`` and ``-shm`` siblings so the snapshot
    is self-consistent. This is the only contact with the live store — a read
    file-copy, never an open handle."""
    dest.mkdir(parents=True, exist_ok=True)
    copied: list[Path] = []
    for src in sorted(stores_dir.glob("Data-*.sqlite")):
        target = dest / src.name
        shutil.copy2(src, target)
        for suffix in ("-wal", "-shm"):
            sidecar = src.with_name(src.name + suffix)
            if sidecar.exists():
                shutil.copy2(sidecar, dest / sidecar.name)
        copied.append(target)
    if not copied:
        raise AppleRemindersAccessError(
            f"No Data-*.sqlite stores found under {stores_dir}"
        )
    return copied


def _open_ro(path: Path) -> sqlite3.Connection:
    """Open a snapshot copy strictly read-only (belt-and-suspenders; we only
    ever read, but mode=ro makes an accidental write impossible)."""
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _count_reminders(path: Path) -> int:
    try:
        conn = _open_ro(path)
    except sqlite3.OperationalError:
        return 0
    try:
        table = _resolve_table(conn, _REMINDER_TABLE_CANDIDATES)
        if table is None:
            return 0
        return int(conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0])
    except sqlite3.Error:
        return 0
    finally:
        conn.close()


def pick_active_store(snapshot_paths: list[Path]) -> Path:
    """Pick the account store with the most reminders.

    Reminders keeps one store per account; secondary/stale accounts hold zero
    rows. Counting rather than guessing by file size or mtime is deterministic
    and robust to which account was most recently touched."""
    ranked = sorted(snapshot_paths, key=_count_reminders, reverse=True)
    best = ranked[0]
    if _count_reminders(best) == 0:
        raise AppleRemindersSchemaError(
            "No store contains any reminders (empty or unrecognized schema)"
        )
    return best


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

# Optional reminder columns we map when present. reminder_id (ZCKIDENTIFIER)
# and title (ZTITLE) are required and validated separately.
_OPTIONAL_REMINDER_COLUMNS = (
    "ZNOTES",
    "ZNOTESDOCUMENT",
    "ZCOMPLETED",
    "ZDUEDATE",
    "ZCOMPLETIONDATE",
    "ZCREATIONDATE",
    "ZLASTMODIFIEDDATE",
    "ZLIST",
    "ZPARENTREMINDER",
    "ZCKPARENTREMINDERIDENTIFIER",
    "ZICSDISPLAYORDER",
    "ZMARKEDFORDELETION",
    "Z_PK",
)


def extract_reminders(
    db_path: Path,
) -> tuple[list[AppleReminder], int, list[str]]:
    """Extract normalized reminders from a snapshot store (read-only).

    Returns ``(reminders, skipped_count, mapping_fallbacks)``. Rows marked for
    deletion or missing a stable id/title are skipped (counted, not silently
    dropped). All column access is guarded by what the schema actually has."""
    conn = _open_ro(db_path)
    try:
        reminder_table = _resolve_table(conn, _REMINDER_TABLE_CANDIDATES)
        if reminder_table is None:
            raise AppleRemindersSchemaError(
                f"No reminder table found (looked for {_REMINDER_TABLE_CANDIDATES})"
            )
        cols = _table_columns(conn, reminder_table)
        for required in ("ZTITLE", "ZCKIDENTIFIER"):
            if required not in cols:
                raise AppleRemindersSchemaError(
                    f"{reminder_table} missing required column {required}"
                )

        fallbacks: list[str] = []
        present_optional = [c for c in _OPTIONAL_REMINDER_COLUMNS if c in cols]
        for missing in (c for c in _OPTIONAL_REMINDER_COLUMNS if c not in cols):
            fallbacks.append(f"missing_optional_column:{missing}")

        # Build the list-name lookup if both the table and the FK are available.
        list_names: dict[int, str] = {}
        list_table = _resolve_table(conn, _LIST_TABLE_CANDIDATES)
        if list_table is not None and "ZLIST" in cols:
            list_cols = _table_columns(conn, list_table)
            name_col = "ZNAME" if "ZNAME" in list_cols else None
            if name_col:
                for row in conn.execute(
                    f"SELECT Z_PK, {name_col} FROM {list_table}"
                ):
                    if row[1] is not None:
                        list_names[int(row[0])] = str(row[1])
            else:
                fallbacks.append(f"missing_list_name_column:{list_table}")
        elif "ZLIST" in cols:
            fallbacks.append("missing_list_table")

        select_cols = ["ZTITLE", "ZCKIDENTIFIER", *present_optional]
        rows = conn.execute(
            f"SELECT {', '.join(select_cols)} FROM {reminder_table}"
        ).fetchall()
    finally:
        conn.close()

    # First pass: map ZPARENTREMINDER (a local Z_PK) to the parent's stable id.
    pk_to_ckid: dict[int, str] = {}
    if "Z_PK" in cols:
        for row in rows:
            pk = row["Z_PK"]
            ckid = row["ZCKIDENTIFIER"]
            if pk is not None and ckid:
                pk_to_ckid[int(pk)] = str(ckid)

    reminders: list[AppleReminder] = []
    skipped = 0
    notes_recovered = 0
    notes_deferred = 0
    for row in rows:
        keys = row.keys()

        def col(name: str) -> Any:
            return row[name] if name in keys else None

        if col("ZMARKEDFORDELETION"):
            skipped += 1
            continue
        ckid = col("ZCKIDENTIFIER")
        title = col("ZTITLE")
        if not ckid or title is None:
            skipped += 1
            continue

        notes = col("ZNOTES")
        notes = str(notes) if notes else None
        if notes is None and col("ZNOTESDOCUMENT"):
            notes = _decode_notes_document(col("ZNOTESDOCUMENT"))
            if notes is None:
                notes_deferred += 1
            else:
                notes_recovered += 1

        parent_id: str | None = None
        parent_pk = col("ZPARENTREMINDER")
        if parent_pk is not None:
            parent_id = pk_to_ckid.get(int(parent_pk))
        if parent_id is None:
            parent_id = col("ZCKPARENTREMINDERIDENTIFIER") or None

        list_pk = col("ZLIST")
        list_name = list_names.get(int(list_pk)) if list_pk is not None else None

        sort_hint = col("ZICSDISPLAYORDER")
        reminders.append(
            AppleReminder(
                reminder_id=str(ckid),
                title=str(title),
                notes=notes,
                is_completed=bool(col("ZCOMPLETED")),
                due_at=core_data_timestamp(col("ZDUEDATE")),
                completed_at=core_data_timestamp(col("ZCOMPLETIONDATE")),
                list_name=list_name,
                section_name=None,  # membership lives in a per-list blob; deferred
                tags=parse_hashtags(title, notes),
                parent_reminder_id=parent_id,
                sort_hint=float(sort_hint) if sort_hint is not None else None,
                created_at=core_data_timestamp(col("ZCREATIONDATE")),
                updated_at=core_data_timestamp(col("ZLASTMODIFIEDDATE")),
                raw_payload={
                    "z_pk": col("Z_PK"),
                    "list_pk": list_pk,
                    "table": reminder_table,
                },
            )
        )

    if notes_recovered:
        fallbacks.append(f"notes_decoded_from_document_blob:lossy({notes_recovered})")
    if notes_deferred:
        fallbacks.append(f"notes_in_document_blob:deferred({notes_deferred})")
    return reminders, skipped, fallbacks


# ---------------------------------------------------------------------------
# Public pipeline
# ---------------------------------------------------------------------------


def extract_apple_reminders(
    *,
    snapshot_dir: Path | None = None,
) -> tuple[AppleRemindersExtractResult, list[AppleReminder]]:
    """Run the full read-only pipeline: discover -> snapshot -> pick -> extract.

    Returns the run summary and the normalized records. Does NOT persist to any
    rebalance table — storage is Phase 2. ``snapshot_dir`` defaults to
    ``temp/apple-reminders`` under the current working directory."""
    import time

    started = time.monotonic()
    stores_dir = discover_stores_dir()
    dest = snapshot_dir or (Path.cwd() / "temp" / "apple-reminders")
    snapshots = snapshot_stores(stores_dir, dest)
    active = pick_active_store(snapshots)
    reminders, skipped, fallbacks = extract_reminders(active)
    fingerprint = compute_schema_fingerprint(active)

    # Count distinct non-null list names actually referenced.
    list_count = len({r.list_name for r in reminders if r.list_name})
    duration = time.monotonic() - started

    result = AppleRemindersExtractResult(
        store_path=str(active),
        snapshot_dir=str(dest),
        extracted_count=len(reminders),
        skipped_count=skipped,
        list_count=list_count,
        duration_seconds=duration,
        mapping_fallbacks=tuple(fallbacks),
        schema_fingerprint=fingerprint,
    )
    # Log counts only — never reminder titles/notes (privacy).
    logger.info(
        "apple_reminders extract: %d reminders, %d skipped, %d lists, "
        "%.3fs, fallbacks=%s",
        result.extracted_count,
        result.skipped_count,
        result.list_count,
        result.duration_seconds,
        list(result.mapping_fallbacks),
    )
    return result, reminders


# ---------------------------------------------------------------------------
# Storage + sync (Phase 2) — list-scoped upsert into the apple_reminders table.
# The extract_* functions above stay pure readers; this section is the only
# writer, and the list filter is applied here at the storage boundary.
# ---------------------------------------------------------------------------


@dataclass
class AppleRemindersSyncResult:
    """Summary of one list-scoped sync into the apple_reminders table."""

    list_name: str
    store_path: str
    snapshot_dir: str
    scoped_count: int
    active_count: int
    inserted_count: int
    updated_count: int
    unchanged_count: int
    retired_count: int
    duration_seconds: float
    mapping_fallbacks: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "list_name": self.list_name,
            "store_path": self.store_path,
            "snapshot_dir": self.snapshot_dir,
            "scoped_count": self.scoped_count,
            "active_count": self.active_count,
            "inserted_count": self.inserted_count,
            "updated_count": self.updated_count,
            "unchanged_count": self.unchanged_count,
            "retired_count": self.retired_count,
            "duration_seconds": round(self.duration_seconds, 3),
            "mapping_fallbacks": list(self.mapping_fallbacks),
        }


def ensure_apple_reminders_schema(conn: sqlite3.Connection) -> None:
    """Create the apple_reminders table and indexes if absent."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS apple_reminders (
            reminder_id        TEXT PRIMARY KEY,
            list_name          TEXT,
            title              TEXT NOT NULL,
            notes              TEXT,
            is_completed       INTEGER NOT NULL,
            due_at             TEXT,
            completed_at       TEXT,
            section_name       TEXT,
            tags_json          TEXT NOT NULL,
            parent_reminder_id TEXT,
            sort_hint          REAL,
            created_at         TEXT,
            updated_at         TEXT,
            raw_payload_json   TEXT NOT NULL,
            is_active          INTEGER NOT NULL,
            first_seen_at      TEXT NOT NULL,
            last_seen_at       TEXT NOT NULL,
            last_synced_at     TEXT NOT NULL
        )
        """
    )
    # Source-level metadata (key/value): schema fingerprint + last-sync drift
    # signal, read cheaply by `doctor` / `get_index_status` to surface schema
    # drift after a macOS upgrade without re-reading the live store.
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS apple_reminders_sync_meta (
            key   TEXT PRIMARY KEY,
            value TEXT
        )
        """
    )
    # is_completed index: the in-scope (default) list is mostly completed history,
    # so Phase 3 must filter to active fast.
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_apple_reminders_completed "
        "ON apple_reminders(is_completed)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_apple_reminders_active "
        "ON apple_reminders(is_active)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_apple_reminders_list "
        "ON apple_reminders(list_name)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_apple_reminders_parent "
        "ON apple_reminders(parent_reminder_id)"
    )
    conn.commit()


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt is not None else None


# Fields compared to decide insert vs update vs unchanged (everything content-
# bearing; excludes the *_seen_at / *_synced_at bookkeeping timestamps).
_SYNC_UPDATE_FIELDS = (
    "list_name",
    "title",
    "notes",
    "is_completed",
    "due_at",
    "completed_at",
    "section_name",
    "tags_json",
    "parent_reminder_id",
    "sort_hint",
    "created_at",
    "updated_at",
    "raw_payload_json",
    "is_active",
)


def _sync_row_values(r: AppleReminder) -> dict[str, Any]:
    return {
        "list_name": r.list_name,
        "title": r.title,
        "notes": r.notes,
        "is_completed": 1 if r.is_completed else 0,
        "due_at": _iso(r.due_at),
        "completed_at": _iso(r.completed_at),
        "section_name": r.section_name,
        "tags_json": json.dumps(list(r.tags), ensure_ascii=False),
        "parent_reminder_id": r.parent_reminder_id,
        "sort_hint": r.sort_hint,
        "created_at": _iso(r.created_at),
        "updated_at": _iso(r.updated_at),
        "raw_payload_json": json.dumps(r.raw_payload, ensure_ascii=False, default=str),
        "is_active": 1,
    }


def _sync_row_differs(existing: sqlite3.Row, desired: dict[str, Any]) -> bool:
    return any(existing[f] != desired[f] for f in _SYNC_UPDATE_FIELDS)


def upsert_apple_reminders(
    database_path: Path,
    reminders: list[AppleReminder],
    *,
    list_name: str,
    now_iso: str | None = None,
    meta: dict[str, str] | None = None,
) -> dict[str, int]:
    """Upsert ``reminders`` (already scoped to ``list_name``) and reconcile.

    Rows present in the DB but absent from this batch are **retired** (is_active
    flips to 0) rather than deleted, preserving the audit trail — same discipline
    as the Sleuth source. Idempotent: re-running an unchanged batch only bumps
    last_seen/last_synced. ``meta`` key/value pairs (schema fingerprint, drift
    signal) are persisted in the same transaction. Returns counts."""
    now = now_iso or datetime.now(timezone.utc).isoformat()
    inserted = updated = unchanged = 0

    from rebalance.ingest.db import db_connection

    with db_connection(database_path, ensure_apple_reminders_schema) as conn:
        for r in reminders:
            desired = _sync_row_values(r)
            row = conn.execute(
                f"SELECT {', '.join(_SYNC_UPDATE_FIELDS)} "
                f"FROM apple_reminders WHERE reminder_id = ?",
                (r.reminder_id,),
            ).fetchone()

            if row is None:
                cols = ["reminder_id", *_SYNC_UPDATE_FIELDS,
                        "first_seen_at", "last_seen_at", "last_synced_at"]
                placeholders = ", ".join("?" * len(cols))
                conn.execute(
                    f"INSERT INTO apple_reminders ({', '.join(cols)}) "
                    f"VALUES ({placeholders})",
                    (r.reminder_id, *[desired[f] for f in _SYNC_UPDATE_FIELDS],
                     now, now, now),
                )
                inserted += 1
            elif _sync_row_differs(row, desired):
                set_clause = ", ".join(f"{f} = ?" for f in _SYNC_UPDATE_FIELDS)
                conn.execute(
                    f"UPDATE apple_reminders SET {set_clause}, "
                    f"last_seen_at = ?, last_synced_at = ? WHERE reminder_id = ?",
                    (*[desired[f] for f in _SYNC_UPDATE_FIELDS], now, now, r.reminder_id),
                )
                updated += 1
            else:
                conn.execute(
                    "UPDATE apple_reminders SET last_seen_at = ?, last_synced_at = ? "
                    "WHERE reminder_id = ?",
                    (now, now, r.reminder_id),
                )
                unchanged += 1

        # Reconcile disappearances: a reminder that was deleted in Apple (or fell
        # out of the configured list) is retired locally, never hard-deleted.
        seen_ids = [r.reminder_id for r in reminders]
        if seen_ids:
            placeholders = ",".join("?" * len(seen_ids))
            cur = conn.execute(
                f"UPDATE apple_reminders SET is_active = 0, last_synced_at = ? "
                f"WHERE is_active = 1 AND reminder_id NOT IN ({placeholders})",
                (now, *seen_ids),
            )
        else:
            cur = conn.execute(
                "UPDATE apple_reminders SET is_active = 0, last_synced_at = ? "
                "WHERE is_active = 1",
                (now,),
            )
        retired = cur.rowcount or 0

        if meta:
            conn.executemany(
                "INSERT INTO apple_reminders_sync_meta (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                list(meta.items()),
            )
        conn.commit()

    return {
        "inserted": inserted,
        "updated": updated,
        "unchanged": unchanged,
        "retired": retired,
    }


# Mapping fallbacks that signal genuine schema DRIFT (columns/tables that
# vanished) — distinct from expected deferrals like notes-in-blob.
_DRIFT_FALLBACK_PREFIX = "missing_"


def _drift_fallbacks(fallbacks: tuple[str, ...] | list[str]) -> list[str]:
    return [f for f in fallbacks if f.startswith(_DRIFT_FALLBACK_PREFIX)]


def get_apple_reminders_meta(database_path: Path) -> dict[str, Any]:
    """Read the source meta (fingerprint, drift signal, last sync). ``{}`` if the
    source has never synced. JSON values are decoded; scalars pass through."""
    if not Path(database_path).exists():
        return {}
    conn = sqlite3.connect(f"file:{database_path}?mode=ro", uri=True)
    try:
        try:
            rows = conn.execute(
                "SELECT key, value FROM apple_reminders_sync_meta"
            ).fetchall()
        except sqlite3.OperationalError:
            return {}
    finally:
        conn.close()
    out: dict[str, Any] = {}
    for key, value in rows:
        try:
            out[key] = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            out[key] = value
    return out


def apple_reminders_health(database_path: Path) -> dict[str, Any]:
    """Cheap, DB-only health verdict for the apple_reminders source.

    Reads the persisted meta (no live-store access, so it works on any host).
    ``status`` is one of: ``never_synced`` (opt-in source not enabled),
    ``drift`` (schema columns/tables went missing on the last sync — names the
    symbols + remediation), or ``ok``."""
    meta = get_apple_reminders_meta(database_path)
    last_sync_at = meta.get("last_sync_at")
    if not last_sync_at:
        return {"status": "never_synced", "message": "apple_reminders never synced"}

    drift = meta.get("drift_fallbacks") or []
    fingerprint = meta.get("schema_fingerprint") or {}
    if drift:
        return {
            "status": "drift",
            "last_sync_at": last_sync_at,
            "drift_fallbacks": drift,
            "schema_fingerprint": fingerprint,
            "message": "Reminders schema drift — missing: " + ", ".join(drift),
            "remediation": (
                "A macOS update likely reshaped the Core Data schema. Review the "
                "field mapping in apple_reminders.py against the live store; the "
                "extractor degrades gracefully but affected fields are now null."
            ),
        }
    return {
        "status": "ok",
        "last_sync_at": last_sync_at,
        "schema_fingerprint": fingerprint,
        "message": "ok",
    }


def sync_apple_reminders(
    database_path: Path,
    *,
    list_name: str | None = None,
    snapshot_dir: Path | None = None,
) -> AppleRemindersSyncResult:
    """Source-owned entry point: read the local store (read-only), filter to the
    configured list, and upsert into apple_reminders.

    This is the single path the collector / CLI / MCP call — no user surface
    touches the leaf extractor or upsert directly. ``list_name`` defaults to the
    configured list (``"Reminders"``)."""
    import time

    if list_name is None:
        from rebalance.ingest.config import get_apple_reminders_list_name
        list_name = get_apple_reminders_list_name()

    started = time.monotonic()
    extract_result, reminders = extract_apple_reminders(snapshot_dir=snapshot_dir)
    scoped = [r for r in reminders if r.list_name == list_name]

    # Persist hardening signals (fingerprint + drift) in the sync transaction so
    # doctor / status can warn on schema drift without touching the live store.
    drift = _drift_fallbacks(extract_result.mapping_fallbacks)
    now_iso = datetime.now(timezone.utc).isoformat()
    meta = {
        "last_sync_at": now_iso,
        "schema_fingerprint": json.dumps(extract_result.schema_fingerprint),
        "drift_fallbacks": json.dumps(drift),
        "all_fallbacks": json.dumps(list(extract_result.mapping_fallbacks)),
    }
    counts = upsert_apple_reminders(
        database_path, scoped, list_name=list_name, now_iso=now_iso, meta=meta
    )
    active_count = sum(1 for r in scoped if not r.is_completed)
    if drift:
        logger.warning("apple_reminders SCHEMA DRIFT — missing: %s", ", ".join(drift))

    result = AppleRemindersSyncResult(
        list_name=list_name,
        store_path=extract_result.store_path,
        snapshot_dir=extract_result.snapshot_dir,
        scoped_count=len(scoped),
        active_count=active_count,
        inserted_count=counts["inserted"],
        updated_count=counts["updated"],
        unchanged_count=counts["unchanged"],
        retired_count=counts["retired"],
        duration_seconds=time.monotonic() - started,
        mapping_fallbacks=extract_result.mapping_fallbacks,
    )
    fp = extract_result.schema_fingerprint
    logger.info(
        "apple_reminders sync: list=%r scoped=%d active=%d "
        "(ins=%d upd=%d unch=%d retired=%d) %.3fs "
        "[fingerprint macos=%s sqlite=%s cols=%s/%s]",
        result.list_name, result.scoped_count, result.active_count,
        result.inserted_count, result.updated_count, result.unchanged_count,
        result.retired_count, result.duration_seconds,
        fp.get("macos"), fp.get("sqlite"),
        fp.get("reminder_column_count"), fp.get("columns_sha"),
    )
    return result


# ---------------------------------------------------------------------------
# Read surface (Phase 3) — query the synced apple_reminders table.
# Read path is pure sqlite3 (no macOS / private-framework dependency), so it
# works on any host that has the rebalance DB, not just the capture machine.
# ---------------------------------------------------------------------------

_ORDER_BY_COLUMNS = {
    "due": ("due_at", "ASC"),
    "created": ("created_at", "DESC"),
    "updated": ("updated_at", "DESC"),
    "title": ("title", "ASC"),
}


def _as_iso(value: datetime | str | None) -> str | None:
    if value is None:
        return None
    return value.isoformat() if isinstance(value, datetime) else str(value)


def list_apple_reminders(
    database_path: Path,
    *,
    include_completed: bool = False,
    include_retired: bool = False,
    list_name: str | None = None,
    has_due: bool | None = None,
    due_before: datetime | str | None = None,
    due_after: datetime | str | None = None,
    order_by: str = "due",
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Read reminders from the synced ``apple_reminders`` table.

    Safe-by-default: returns only **active, non-completed** reminders unless asked
    otherwise — the configured (default) list is mostly completed history, so a
    naive read would flood callers. Pass ``include_completed=True`` /
    ``include_retired=True`` to widen.

    Filters: ``list_name``; ``has_due`` (True=only dated, False=only undated);
    ``due_before`` / ``due_after`` (datetime or ISO string, compared as UTC ISO).
    ``order_by`` ∈ {due, created, updated, title}. Returns plain dicts with
    ``tags`` already parsed from JSON. Empty/absent table → ``[]`` (never raises
    on a not-yet-synced source)."""
    if order_by not in _ORDER_BY_COLUMNS:
        raise ValueError(
            f"order_by must be one of {sorted(_ORDER_BY_COLUMNS)}, got {order_by!r}"
        )
    if not Path(database_path).exists():
        return []  # DB never created (source never synced) — mode=ro would error

    where: list[str] = []
    params: list[Any] = []
    if not include_retired:
        where.append("is_active = 1")
    if not include_completed:
        where.append("is_completed = 0")
    if list_name is not None:
        where.append("list_name = ?")
        params.append(list_name)
    if has_due is True:
        where.append("due_at IS NOT NULL")
    elif has_due is False:
        where.append("due_at IS NULL")
    if due_before is not None:
        where.append("due_at IS NOT NULL AND due_at < ?")
        params.append(_as_iso(due_before))
    if due_after is not None:
        where.append("due_at IS NOT NULL AND due_at > ?")
        params.append(_as_iso(due_after))

    col, direction = _ORDER_BY_COLUMNS[order_by]
    # NULLs last regardless of direction, so undated items don't crowd the top.
    order_sql = f"({col} IS NULL), {col} {direction}"
    sql = "SELECT * FROM apple_reminders"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += f" ORDER BY {order_sql}"
    if limit is not None:
        sql += " LIMIT ?"
        params.append(int(limit))

    conn = sqlite3.connect(f"file:{database_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        try:
            rows = conn.execute(sql, params).fetchall()
        except sqlite3.OperationalError:
            return []  # table not created yet (source never synced)
    finally:
        conn.close()

    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        try:
            d["tags"] = json.loads(d.pop("tags_json") or "[]")
        except (json.JSONDecodeError, KeyError):
            d["tags"] = []
        d["is_completed"] = bool(d["is_completed"])
        d["is_active"] = bool(d["is_active"])
        out.append(d)
    return out
