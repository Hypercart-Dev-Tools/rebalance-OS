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

import logging
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

    def as_dict(self) -> dict[str, Any]:
        return {
            "store_path": self.store_path,
            "snapshot_dir": self.snapshot_dir,
            "extracted_count": self.extracted_count,
            "skipped_count": self.skipped_count,
            "list_count": self.list_count,
            "duration_seconds": round(self.duration_seconds, 3),
            "mapping_fallbacks": list(self.mapping_fallbacks),
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
