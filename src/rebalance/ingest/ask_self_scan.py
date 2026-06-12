"""Device-local discovery of ask_self RAG indexes (spike).

Rebalance knows repos by their GitHub identity (``owner/repo``, derived from
activity / pushes / the project registry). ask_self, by contrast, leaves a
*filesystem* footprint: every repo wired for ask_self has an
``ask_self/ask_self_harness.json`` at its root, and (once built) a SQLite index
whose ``repo_metadata`` row already records the git remote, branch, head SHA,
file/chunk counts, embedding model, and last ingest time.

This collector walks the configured scan roots, detects that footprint, reads
the index's own metadata read-only (never mutating the foreign DB), and records
one row per (device, repo) in ``ask_self_indexes``. The git remote URL is the
bridge: parsing it to ``owner/repo`` lets the dashboard answer "which of my
watched repos have a queryable local brain, and on which machine?".

Design notes
------------
- **Non-destructive.** The ask_self index is opened ``mode=ro`` via a URI
  connection. We only read ``repo_metadata``; we never migrate or write it.
- **Device-aware.** Every row is stamped with :func:`get_device_id` (reused
  from the sync plane) so a future sync step can fan these snapshots across
  machines exactly like calendar/email snapshots do.
- **Honest about "configured but not built".** A repo with a harness but no
  index file is recorded with ``index_built=0`` rather than skipped — that
  distinction is the whole point of an inventory.
"""

from __future__ import annotations

import os
import re
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from rebalance.ingest.db import db_connection, run_migrations
from rebalance.ingest.sync_snapshot import get_device_id

HARNESS_RELPATH = ("ask_self", "ask_self_harness.json")
DEFAULT_MAX_DEPTH = 6

# Directories never worth descending into when hunting for harness files.
# Keeps a full-tree walk cheap; ask_self/ itself is never hidden so pruning
# hidden dirs is safe for discovery.
_PRUNE_DIRS = frozenset({
    "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", "build", "dist", ".next", ".cache",
    "Library", ".Trash", ".npm", ".cargo", "site-packages", ".tox",
    ".gradle", "target", "vendor", ".terraform", "DerivedData", ".git",
})

# remote_url forms we map to owner/repo:
#   https://github.com/Owner/Repo.git
#   git@github.com:Owner/Repo.git
#   ssh://git@github.com/Owner/Repo
_REMOTE_RE = re.compile(
    r"""(?:github\.com[:/])(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/?$""",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class AskSelfIndex:
    """One ask_self-enabled repo discovered on this device."""

    device_id: str
    local_path: str
    repo_full_name: str | None  # owner/repo — the bridge to watched repos
    repo_label: str | None
    repo_kind: str | None
    harness_path: str
    index_db_path: str | None
    index_built: bool
    branch: str | None
    head_sha: str | None
    last_commit_at: str | None
    file_count: int | None
    total_chunks: int | None
    embed_model: str | None
    embed_dim: int | None
    index_size_bytes: int | None
    ingested_at: str | None
    remote_url: str | None


@dataclass(frozen=True)
class AskSelfSyncResult:
    device_id: str
    found: int
    inserted: int
    updated: int
    unchanged: int
    scan_roots: list[str]
    scanned_at: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def derive_repo_full_name(remote_url: str | None) -> str | None:
    """Parse a git remote URL into ``owner/repo`` (original casing), or None."""
    if not remote_url:
        return None
    m = _REMOTE_RE.search(remote_url.strip())
    if not m:
        return None
    return f"{m.group('owner')}/{m.group('repo')}"


def _git_remote_full_name(repo_root: Path) -> str | None:
    """Return ``owner/repo`` from the checkout's ``origin`` remote, or None.

    Authoritative for the current checkout — unlike the harness ``github``
    block, which is frequently copied from a template repo and left stale.
    Best-effort: any git failure (no remote, not a repo) yields None.
    """
    import subprocess
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_root), "remote", "get-url", "origin"],
            capture_output=True, text=True, check=False, timeout=5,
        )
    except Exception:  # noqa: BLE001 — git missing / hung / unreadable repo
        return None
    if proc.returncode != 0:
        return None
    return derive_repo_full_name(proc.stdout.strip())


def _read_json(path: Path) -> dict[str, Any]:
    import json
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — a malformed harness shouldn't abort the sweep
        return {}


def _resolve_index_db_path(repo_root: Path, harness: dict[str, Any]) -> Path | None:
    """Resolve the index SQLite path declared by the harness.

    Honors ``db_path`` (relative to repo root, or absolute) first, then the
    local-only ``db_filename`` convention (``temp/rag/<filename>``).
    """
    db_path = (harness.get("db_path") or "").strip()
    if db_path:
        p = Path(db_path)
        return p if p.is_absolute() else (repo_root / p)
    db_filename = (harness.get("db_filename") or "").strip()
    if db_filename:
        return repo_root / "temp" / "rag" / db_filename
    return None


def read_index_metadata(index_db_path: Path) -> dict[str, Any] | None:
    """Read the single ``repo_metadata`` row from an ask_self index, read-only.

    Returns a column->value dict, or None if the file/table/row is absent.
    Uses a ``mode=ro`` URI connection so we never create, lock-for-write, or
    migrate the foreign database.
    """
    if not index_db_path.is_file():
        return None
    try:
        conn = sqlite3.connect(f"file:{index_db_path}?mode=ro", uri=True)
    except Exception:  # noqa: BLE001
        return None
    try:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM repo_metadata LIMIT 1").fetchone()
        if row is None:
            return None
        return {k: row[k] for k in row.keys()}
    except Exception:  # noqa: BLE001 — older/newer ask_self schema without the table
        return None
    finally:
        conn.close()


def _should_descend(name: str) -> bool:
    if name in _PRUNE_DIRS:
        return False
    # Prune hidden dirs (".git", ".cache", …); ask_self/ is not hidden.
    return not name.startswith(".")


def iter_repo_harnesses(
    roots: list[str] | list[Path],
    *,
    max_depth: int = DEFAULT_MAX_DEPTH,
) -> Iterator[tuple[Path, Path]]:
    """Yield ``(repo_root, harness_path)`` for every ask_self repo under *roots*.

    De-duplicates by resolved repo root so overlapping scan roots don't
    double-count.
    """
    seen: set[Path] = set()
    for raw_root in roots:
        root = Path(raw_root).expanduser()
        if not root.is_dir():
            continue
        base_depth = len(root.resolve().parts)
        for dirpath, dirnames, _filenames in os.walk(root, followlinks=False):
            cur = Path(dirpath)
            if len(cur.resolve().parts) - base_depth >= max_depth:
                dirnames[:] = []
            else:
                dirnames[:] = [d for d in dirnames if _should_descend(d)]

            harness = cur / HARNESS_RELPATH[0] / HARNESS_RELPATH[1]
            if harness.is_file():
                rp = cur.resolve()
                if rp not in seen:
                    seen.add(rp)
                    yield rp, harness


def scan_ask_self_repos(
    roots: list[str] | list[Path],
    *,
    max_depth: int = DEFAULT_MAX_DEPTH,
    device_id: str | None = None,
) -> list[AskSelfIndex]:
    """Walk *roots* and return one :class:`AskSelfIndex` per ask_self repo."""
    dev = device_id or get_device_id()
    out: list[AskSelfIndex] = []
    for repo_root, harness_path in iter_repo_harnesses(roots, max_depth=max_depth):
        harness = _read_json(harness_path)
        index_db = _resolve_index_db_path(repo_root, harness)
        meta = read_index_metadata(index_db) if index_db else None
        built = meta is not None

        # GitHub identity, most→least authoritative:
        #   1. remote_url recorded in the built index (the remote at ingest time)
        #   2. the checkout's live `git remote get-url origin`
        #   3. the harness github.owner/repo — last resort: often a stale copy
        #      from a template repo (observed in the wild during the spike).
        gh = harness.get("github") or {}
        harness_full = None
        if gh.get("owner") and gh.get("repo"):
            harness_full = f"{gh['owner']}/{gh['repo']}"
        remote_url = (meta or {}).get("remote_url")
        repo_full_name = (
            derive_repo_full_name(remote_url)
            or _git_remote_full_name(repo_root)
            or harness_full
        )

        index_size = None
        if index_db and index_db.is_file():
            try:
                index_size = index_db.stat().st_size
            except OSError:
                index_size = None

        out.append(AskSelfIndex(
            device_id=dev,
            local_path=str(repo_root),
            repo_full_name=repo_full_name,
            repo_label=(meta or {}).get("repo_label") or harness.get("repo_label"),
            repo_kind=(meta or {}).get("repo_kind") or harness.get("repo_kind"),
            harness_path=str(harness_path),
            index_db_path=str(index_db) if index_db else None,
            index_built=built,
            branch=(meta or {}).get("branch"),
            head_sha=(meta or {}).get("head_sha"),
            last_commit_at=(meta or {}).get("last_commit_at"),
            file_count=(meta or {}).get("file_count"),
            total_chunks=(meta or {}).get("total_chunks"),
            embed_model=(meta or {}).get("embed_model"),
            embed_dim=(meta or {}).get("embed_dim"),
            index_size_bytes=index_size,
            ingested_at=(meta or {}).get("ingested_at"),
            remote_url=remote_url,
        ))
    return out


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

_COLUMNS = (
    "device_id", "local_path", "repo_full_name", "repo_label", "repo_kind",
    "harness_path", "index_db_path", "index_built", "branch", "head_sha",
    "last_commit_at", "file_count", "total_chunks", "embed_model", "embed_dim",
    "index_size_bytes", "ingested_at", "remote_url", "scanned_at",
)

# Fields whose change makes a row "updated" rather than "unchanged".
_SIGNATURE = ("repo_full_name", "head_sha", "ingested_at", "total_chunks", "index_built")


def sync_ask_self_indexes(
    database_path: Path,
    *,
    roots: list[str] | list[Path] | None = None,
    device_id: str | None = None,
    max_depth: int = DEFAULT_MAX_DEPTH,
) -> AskSelfSyncResult:
    """Scan the device for ask_self repos and upsert them into ``ask_self_indexes``."""
    dev = device_id or get_device_id()
    if roots is None:
        from rebalance.ingest.config import get_repo_scan_roots
        roots = get_repo_scan_roots()
    scanned_at = datetime.now(timezone.utc).isoformat()
    found = scan_ask_self_repos(roots, max_depth=max_depth, device_id=dev)

    inserted = updated = unchanged = 0
    placeholders = ", ".join("?" for _ in _COLUMNS)
    updates = ", ".join(f"{c}=excluded.{c}" for c in _COLUMNS if c not in ("device_id", "local_path"))

    with db_connection(database_path) as conn:
        run_migrations(conn)  # ensure ask_self_indexes exists even on a direct call
        for item in found:
            existing = conn.execute(
                "SELECT repo_full_name, head_sha, ingested_at, total_chunks, index_built "
                "FROM ask_self_indexes WHERE device_id=? AND local_path=?",
                (dev, item.local_path),
            ).fetchone()

            row = {
                **asdict(item),
                "index_built": 1 if item.index_built else 0,
                "scanned_at": scanned_at,
            }
            conn.execute(
                f"INSERT INTO ask_self_indexes ({', '.join(_COLUMNS)}) "
                f"VALUES ({placeholders}) "
                f"ON CONFLICT(device_id, local_path) DO UPDATE SET {updates}",
                tuple(row[c] for c in _COLUMNS),
            )

            if existing is None:
                inserted += 1
            else:
                before = (
                    existing["repo_full_name"], existing["head_sha"],
                    existing["ingested_at"], existing["total_chunks"],
                    bool(existing["index_built"]),
                )
                after = tuple(getattr(item, f) for f in _SIGNATURE)
                updated += 1 if before != after else 0
                unchanged += 1 if before == after else 0
        conn.commit()

    return AskSelfSyncResult(
        device_id=dev,
        found=len(found),
        inserted=inserted,
        updated=updated,
        unchanged=unchanged,
        scan_roots=[str(r) for r in roots],
        scanned_at=scanned_at,
    )


def get_ask_self_indexes(database_path: Path) -> list[dict[str, Any]]:
    """Return all recorded ask_self indexes (defensive against a missing table)."""
    try:
        with db_connection(database_path) as conn:
            rows = conn.execute(
                "SELECT * FROM ask_self_indexes ORDER BY device_id, repo_full_name, local_path"
            ).fetchall()
            return [dict(r) for r in rows]
    except Exception:  # noqa: BLE001 — table absent on a pre-migration DB
        return []


def summarize_ask_self_indexes(database_path: Path) -> dict[str, Any]:
    """Inventory of ask_self repos, each flagged with whether Rebalance watches it.

    This is the join your idea hinges on: ask_self's filesystem inventory
    cross-referenced against the GitHub-identity watched set.
    """
    from rebalance.ingest.index_ops import get_watched_repos

    indexes = get_ask_self_indexes(database_path)
    watched = {r.lower() for r in get_watched_repos(database_path).get("watched", [])}

    enriched: list[dict[str, Any]] = []
    for row in indexes:
        full = (row.get("repo_full_name") or "")
        enriched.append({
            **row,
            "index_built": bool(row.get("index_built")),
            "watched": full.lower() in watched if full else False,
        })

    devices = sorted({r["device_id"] for r in enriched})
    summary: dict[str, Any] = {
        "indexes": enriched,
        "summary": {
            "total": len(enriched),
            "built": sum(1 for r in enriched if r["index_built"]),
            "watched": sum(1 for r in enriched if r["watched"]),
            "devices": devices,
        },
    }
    if not enriched:
        summary["note"] = (
            "No ask_self indexes recorded yet. Run "
            "refresh_index(scope=['ask_self']) to scan this device."
        )
    return summary
