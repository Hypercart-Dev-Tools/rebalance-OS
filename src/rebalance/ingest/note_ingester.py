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

from rebalance.ingest.db import get_connection, ensure_schema
from rebalance.ingest.md_parser import parse_note, ParsedNote


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
# Result type
# ---------------------------------------------------------------------------


@dataclass
class IngestResult:
    total_files: int
    new_files: int
    updated_files: int
    unchanged_files: int
    deleted_files: int
    total_chunks: int
    total_keywords: int
    total_links: int
    elapsed_seconds: float


# ---------------------------------------------------------------------------
# Core ingestion
# ---------------------------------------------------------------------------


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
    conn = get_connection(database_path)
    ensure_schema(conn)

    # Load existing file hashes from DB
    existing = {}
    try:
        rows = conn.execute("SELECT rel_path, content_hash FROM vault_files").fetchall()
        existing = {row["rel_path"]: row["content_hash"] for row in rows}
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
    total_chunks = 0
    total_links = 0

    for rel_path, file_path in disk_files.items():
        content_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()

        if rel_path in existing and existing[rel_path] == content_hash:
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

        # Insert chunks
        for chunk in parsed.chunks:
            chunk_hash = hashlib.sha256(chunk.body.encode("utf-8")).hexdigest()
            conn.execute(
                """INSERT INTO chunks
                   (file_id, chunk_index, heading, heading_level, body, char_count, content_hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (file_id, chunk.chunk_index, chunk.heading, chunk.heading_level,
                 chunk.body, chunk.char_count, chunk_hash),
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

    conn.close()
    elapsed = time.monotonic() - start

    return IngestResult(
        total_files=len(disk_files),
        new_files=new_count,
        updated_files=updated_count,
        unchanged_files=unchanged_count,
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
    # Clear existing keywords
    conn.execute("DELETE FROM keywords")

    # Load all chunks
    rows = conn.execute("SELECT id, body FROM chunks").fetchall()
    if not rows:
        conn.commit()
        return 0

    # Build document frequency
    doc_count = len(rows)
    doc_freq: Counter[str] = Counter()
    chunk_tokens: dict[int, list[str]] = {}

    for row in rows:
        tokens = _tokenize(row["body"])
        chunk_tokens[row["id"]] = tokens
        unique_in_doc = set(tokens)
        for token in unique_in_doc:
            doc_freq[token] += 1

    # Compute TF-IDF and insert top-K per chunk
    total_inserted = 0
    for chunk_id, tokens in chunk_tokens.items():
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

    conn.commit()
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
    conn = get_connection(database_path)
    ensure_schema(conn)

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

    conn.close()

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
