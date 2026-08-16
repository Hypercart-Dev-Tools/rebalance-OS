"""
Vault ingestion orchestrator — walks vault, detects changes via content hash,
parses markdown, inserts files/chunks/keywords/links into SQLite.

Note: vault notes may contain sensitive content (API keys, credentials).
This module stores raw chunk text in SQLite. This is acceptable for a local-only
tool. Do not log chunk content.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import time
from datetime import date, datetime as _dt
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from rebalance.ingest.db import db_connection, ensure_schema, ensure_semantic_schema
from rebalance.ingest.md_parser import parse_note
from rebalance.ingest.semantic_index import sync_vault_documents


def _json_default(obj: Any) -> Any:
    """Handle non-serializable types from YAML frontmatter (date, datetime, etc.)."""
    if isinstance(obj, (date, _dt)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

DEFAULT_EXCLUDES = [".obsidian/*", ".trash/*", "node_modules/*", ".git/*", ".venv/*", "*/.venv/*"]

# Top-100 English stopwords for TF-IDF filtering
_STOPWORDS = frozenset(
    "a about above after again against all am an and any are aren't as at be because "
    "been before being below between both but by can can't cannot could couldn't did "
    "didn't do does doesn't doing don't down during each few for from further get got "
    "had hadn't has hasn't have haven't having he her here hers herself him himself his "
    "how i if in into is isn't it its itself just let me more most my myself no nor not "
    "now of off on once only or other our ours ourselves out over own s same she should "
    "shouldn't so some such t than that the their theirs them themselves then there "
    "these they this those through to too under until up us very was wasn't we were "
    "weren't what when where which while who whom why will with won't would you your "
    "yours yourself yourselves".split()
)

_WORD_RE = re.compile(r"[a-zA-Z]{2,}")

# ---------------------------------------------------------------------------
# Secret redaction — applied to every chunk body before storage/embedding.
# Patterns cover the most common accidentally-committed credential formats.
# Add new patterns here; they take effect on the next vault ingest.
# ---------------------------------------------------------------------------

_SECRET_PATTERNS = re.compile(
    r'sk-ant-[A-Za-z0-9\-_]{20,}'   # Anthropic sk-ant-
    r'|sk-[A-Za-z0-9]{20,}'          # OpenAI / generic sk-
    r'|ghp_[A-Za-z0-9]{35,}'         # GitHub PAT (36 chars typical)
    r'|gho_[A-Za-z0-9]{35,}'         # GitHub OAuth token
    r'|github_pat_[A-Za-z0-9_]{20,}' # GitHub fine-grained PAT
    r'|AIza[A-Za-z0-9\-_]{35,}'      # Google API key (39 chars total)
    r'|AKIA[A-Za-z0-9]{16}'          # AWS access key ID (exactly 20 chars)
    r'|xoxb-[0-9]+-[A-Za-z0-9\-]+'  # Slack bot token
    r'|xoxp-[0-9]+-[A-Za-z0-9\-]+'  # Slack user token
    r'|ya29\.[A-Za-z0-9\-_]{20,}'   # Google OAuth access token
)


def _redact_secrets(text: str) -> str:
    """Replace known secret patterns with a placeholder before indexing."""
    return _SECRET_PATTERNS.sub("[REDACTED]", text)


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class IngestResult:
    total_files: int
    new_files: int
    updated_files: int
    unchanged_files: int
    touched_files: int  # content unchanged but on-disk mtime changed; last_modified refreshed
    deleted_files: int
    total_chunks: int
    total_keywords: int
    total_links: int
    elapsed_seconds: float


# ---------------------------------------------------------------------------
# Core ingestion
# ---------------------------------------------------------------------------


def ingest_notes_command(
    vault_path: Path,
    database_path: Path,
    *,
    exclude_patterns: list[str] | None = None,
    dry_run: bool = False,
) -> IngestResult:
    """Source-owned 1:1 wrapper over :func:`ingest_vault` so CLI / dashboard /
    calendar surfaces don't import the leaf ingest_vault directly
    (COLLECTOR-PATH-AND-PORTABILITY-AUDIT Phase 2)."""
    return ingest_vault(
        vault_path=vault_path,
        database_path=database_path,
        exclude_patterns=exclude_patterns,
        dry_run=dry_run,
    )


def ingest_vault(
    vault_path: Path,
    database_path: Path,
    *,
    exclude_patterns: list[str] | None = None,
    dry_run: bool = False,
) -> IngestResult:
    """Full vault ingest with hash-based delta updates.

    Walks vault for .md files, skips unchanged (by SHA-256), re-ingests changed,
    removes deleted. Then computes TF-IDF keywords across all chunks.
    """
    start = time.monotonic()
    excludes = exclude_patterns or DEFAULT_EXCLUDES

    with db_connection(database_path, ensure_schema) as conn:
        # Load existing (content_hash, last_modified) per file. We track the
        # mtime so we can refresh ``last_modified`` on no-op edits — opening
        # a note in Obsidian and saving it without changing bytes still
        # signals "you touched this," and the dashboard should reflect that.
        existing: dict[str, tuple[str, str | None]] = {}
        try:
            rows = conn.execute(
                "SELECT rel_path, content_hash, last_modified FROM vault_files"
            ).fetchall()
            existing = {
                row["rel_path"]: (row["content_hash"], row["last_modified"])
                for row in rows
            }
        except Exception:
            pass

        # Walk vault
        disk_files: dict[str, Path] = {}
        for md_path in vault_path.rglob("*.md"):
            rel = str(md_path.relative_to(vault_path))
            if any(fnmatch(rel, pat) for pat in excludes):
                continue
            disk_files[rel] = md_path

        new_count = 0
        updated_count = 0
        unchanged_count = 0
        touched_count = 0
        total_chunks = 0
        total_links = 0

        for rel_path, file_path in disk_files.items():
            content_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()

            existing_hash, existing_mtime = existing.get(rel_path, (None, None))
            if existing_hash == content_hash:
                # Content unchanged — but if on-disk mtime moved forward,
                # refresh the stored last_modified so "vault edits" surfaces
                # the touch. Cheap UPDATE; no chunk/embedding work.
                disk_mtime_iso = datetime.fromtimestamp(
                    file_path.stat().st_mtime, tz=timezone.utc
                ).isoformat()
                if not dry_run and disk_mtime_iso != (existing_mtime or ""):
                    conn.execute(
                        "UPDATE vault_files SET last_modified = ? WHERE rel_path = ?",
                        (disk_mtime_iso, rel_path),
                    )
                    touched_count += 1
                else:
                    unchanged_count += 1
                continue

            if dry_run:
                if rel_path in existing:
                    updated_count += 1
                else:
                    new_count += 1
                continue

            # Parse the note
            parsed = parse_note(file_path, vault_path)

            # Delete old data if exists (CASCADE handles chunks, keywords, links)
            conn.execute("DELETE FROM vault_files WHERE rel_path = ?", (rel_path,))

            # Insert file
            stat = file_path.stat()
            now_iso = datetime.now(timezone.utc).isoformat()
            mtime_iso = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()

            conn.execute(
                """INSERT INTO vault_files
                   (rel_path, title, content_hash, frontmatter_json, tags_json,
                    ingested_at, file_size_bytes, last_modified)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    rel_path,
                    parsed.title,
                    parsed.content_hash,
                    json.dumps(parsed.frontmatter, default=_json_default),
                    json.dumps(parsed.tags),
                    now_iso,
                    stat.st_size,
                    mtime_iso,
                ),
            )
            file_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

            # Insert chunks — redact secrets before storage and embedding
            for chunk in parsed.chunks:
                safe_body = _redact_secrets(chunk.body)
                chunk_hash = hashlib.sha256(safe_body.encode("utf-8")).hexdigest()
                conn.execute(
                    """INSERT INTO chunks
                       (file_id, chunk_index, heading, heading_level, body, char_count, content_hash)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (file_id, chunk.chunk_index, chunk.heading, chunk.heading_level,
                     safe_body, chunk.char_count, chunk_hash),
                )
                total_chunks += 1

            # Insert links
            for target, link_type in parsed.wikilinks:
                try:
                    conn.execute(
                        """INSERT OR IGNORE INTO links
                           (source_file_id, target_title, link_type)
                           VALUES (?, ?, ?)""",
                        (file_id, target, link_type),
                    )
                    total_links += 1
                except Exception:
                    pass

            if rel_path in existing:
                updated_count += 1
            else:
                new_count += 1

        # Remove files that no longer exist on disk
        deleted_count = 0
        if not dry_run:
            for rel_path in existing:
                if rel_path not in disk_files:
                    conn.execute("DELETE FROM vault_files WHERE rel_path = ?", (rel_path,))
                    deleted_count += 1

        conn.commit()

        # Compute TF-IDF keywords
        total_keywords = 0
        if not dry_run and (new_count > 0 or updated_count > 0 or deleted_count > 0):
            total_keywords = _compute_tfidf_keywords(conn)

        if not dry_run:
            semantic_rows = conn.execute(
                "SELECT COUNT(*) FROM semantic_documents WHERE source_type = 'vault'"
            ).fetchone()[0] if conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='semantic_documents'"
            ).fetchone() else 0
            if new_count > 0 or updated_count > 0 or deleted_count > 0 or (
                semantic_rows == 0 and existing
            ):
                ensure_semantic_schema(conn)
                sync_vault_documents(conn)
                conn.commit()

    elapsed = time.monotonic() - start

    return IngestResult(
        total_files=len(disk_files),
        new_files=new_count,
        updated_files=updated_count,
        unchanged_files=unchanged_count,
        touched_files=touched_count,
        deleted_files=deleted_count,
        total_chunks=total_chunks,
        total_keywords=total_keywords,
        total_links=total_links,
        elapsed_seconds=round(elapsed, 2),
    )


# ---------------------------------------------------------------------------
# TF-IDF keyword extraction
# ---------------------------------------------------------------------------


def _tokenize(text: str) -> list[str]:
    """Lowercase word tokens, filtered by stopwords and minimum length."""
    return [
        w.lower()
        for w in _WORD_RE.findall(text)
        if w.lower() not in _STOPWORDS and len(w) >= 3
    ]


def _compute_tfidf_keywords(conn: Any, top_k: int = 10) -> int:
    """Compute TF-IDF scores across all chunks, insert top-K keywords per chunk."""
    # Clear existing keywords and commit immediately to release the write lock
    conn.execute("DELETE FROM keywords")
    conn.commit()

    doc_count = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    if doc_count == 0:
        return 0

    BATCH_SIZE = 1000
    doc_freq: Counter[str] = Counter()

    # Pass 1: Build document frequency in batches
    offset = 0
    while True:
        rows = conn.execute("SELECT body FROM chunks LIMIT ? OFFSET ?", (BATCH_SIZE, offset)).fetchall()
        if not rows:
            break
        for row in rows:
            unique_in_doc = set(_tokenize(row["body"]))
            for token in unique_in_doc:
                doc_freq[token] += 1
        offset += BATCH_SIZE

    # Pass 2: Compute TF-IDF and insert in batches
    total_inserted = 0
    offset = 0
    while True:
        # Re-fetch chunks in batches
        rows = conn.execute("SELECT id, body FROM chunks LIMIT ? OFFSET ?", (BATCH_SIZE, offset)).fetchall()
        if not rows:
            break

        for row in rows:
            chunk_id = row["id"]
            tokens = _tokenize(row["body"])
            if not tokens:
                continue

            tf = Counter(tokens)
            max_tf = max(tf.values())
            scores: dict[str, float] = {}
            for word, count in tf.items():
                # Augmented TF * IDF
                tf_score = 0.5 + 0.5 * (count / max_tf)
                idf = math.log(doc_count / (1 + doc_freq.get(word, 0)))
                scores[word] = tf_score * idf

            # Top-K by score
            top = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
            for keyword, score in top:
                conn.execute(
                    "INSERT OR IGNORE INTO keywords (chunk_id, keyword, tf_idf_score) VALUES (?, ?, ?)",
                    (chunk_id, keyword, round(score, 4)),
                )
                total_inserted += 1

        # Commit after each batch to keep transaction sizes small and release locks (Fixing #222)
        conn.commit()
        offset += BATCH_SIZE

    return total_inserted


# ---------------------------------------------------------------------------
# Keyword search (used by search_vault MCP tool)
# ---------------------------------------------------------------------------


def search_by_keyword(
    database_path: Path,
    keyword: str,
    *,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Full-text keyword search over vault chunks via the keywords table.

    Returns ranked results with file path, heading, body preview, and TF-IDF score.
    """
    with db_connection(database_path, ensure_schema) as conn:
        results = conn.execute(
            """
            SELECT
                k.keyword,
                k.tf_idf_score,
                c.heading,
                SUBSTR(c.body, 1, 300) AS body_preview,
                c.char_count,
                vf.rel_path,
                vf.title,
                vf.tags_json
            FROM keywords k
            JOIN chunks c ON c.id = k.chunk_id
            JOIN vault_files vf ON vf.id = c.file_id
            WHERE k.keyword = ?
            ORDER BY k.tf_idf_score DESC
            LIMIT ?
            """,
            (keyword.lower(), limit),
        ).fetchall()

    return [
        {
            "file_path": row["rel_path"],
            "title": row["title"],
            "heading": row["heading"],
            "body_preview": row["body_preview"],
            "keyword_score": row["tf_idf_score"],
            "char_count": row["char_count"],
            "tags": json.loads(row["tags_json"]) if row["tags_json"] else [],
        }
        for row in results
    ]
