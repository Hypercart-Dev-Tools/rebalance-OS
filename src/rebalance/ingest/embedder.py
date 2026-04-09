"""
Embedding pipeline — batch-embed vault chunks via mlx-embeddings (Qwen3),
store in sqlite-vec, and query via ANN search.

Model loading is deferred until first use to keep MCP server startup fast.
mlx-embeddings is imported lazily so the rest of the package works without it.
"""

from __future__ import annotations

import json
import struct
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rebalance.ingest.db import db_connection, ensure_schema

DEFAULT_MODEL = "Qwen/Qwen3-Embedding-0.6B"
EMBEDDING_DIM = 1024


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class EmbedResult:
    total_chunks: int
    embedded_chunks: int
    skipped_unchanged: int
    model_name: str
    embedding_dim: int
    elapsed_seconds: float


# ---------------------------------------------------------------------------
# Model loading (lazy)
# ---------------------------------------------------------------------------


_cached_model = None
_cached_tokenizer = None
_cached_model_name = None


def _load_model(model_name: str) -> tuple:
    """Load model and tokenizer via mlx-embeddings. Cached after first call."""
    global _cached_model, _cached_tokenizer, _cached_model_name
    if _cached_model is not None and _cached_model_name == model_name:
        return _cached_model, _cached_tokenizer

    from mlx_embeddings import load
    model, tokenizer = load(model_name)
    _cached_model = model
    _cached_tokenizer = tokenizer
    _cached_model_name = model_name
    return model, tokenizer


def _embed_batch(model: Any, tokenizer: Any, texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts and return float vectors."""
    import mlx.core as mx
    from mlx_embeddings import generate

    output = generate(model, tokenizer, texts=texts)
    embeddings = output.text_embeds
    # Materialize and free the MLX computation graph
    mx.eval(embeddings)
    return embeddings.tolist()


def _vec_to_bytes(vec: list[float]) -> bytes:
    """Pack a float list into a bytes object for sqlite-vec."""
    return struct.pack(f"{len(vec)}f", *vec)


# ---------------------------------------------------------------------------
# Batch embedding
# ---------------------------------------------------------------------------


def embed_chunks(
    database_path: Path,
    *,
    model_name: str = DEFAULT_MODEL,
    batch_size: int = 32,
    force_reembed: bool = False,
) -> EmbedResult:
    """Batch-embed all chunks that need embedding.

    Detects model version changes via embedding_meta and triggers full re-embed
    if the model name changed.
    """
    start = time.monotonic()

    with db_connection(database_path, ensure_schema) as conn:
        # Check for model version change
        stored_model = None
        try:
            row = conn.execute(
                "SELECT value FROM embedding_meta WHERE key = 'model_name'"
            ).fetchone()
            if row:
                stored_model = row["value"]
        except Exception:
            pass

        if stored_model and stored_model != model_name:
            force_reembed = True

        # Find chunks needing embedding
        if force_reembed:
            # Clear all embeddings and re-embed everything
            conn.execute("DELETE FROM embeddings")
            conn.commit()
            rows = conn.execute("SELECT id, body FROM chunks").fetchall()
        else:
            # Only embed chunks not already in the embeddings table
            rows = conn.execute("""
                SELECT c.id, c.body
                FROM chunks c
                LEFT JOIN embeddings e ON e.chunk_id = c.id
                WHERE e.chunk_id IS NULL
            """).fetchall()

        total_chunks_in_db = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        skipped = total_chunks_in_db - len(rows)

        if not rows:
            return EmbedResult(
                total_chunks=total_chunks_in_db,
                embedded_chunks=0,
                skipped_unchanged=skipped,
                model_name=model_name,
                embedding_dim=EMBEDDING_DIM,
                elapsed_seconds=round(time.monotonic() - start, 2),
            )

        # Load model
        model, tokenizer = _load_model(model_name)

        # Batch embed
        embedded_count = 0
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i + batch_size]
            texts = [row["body"][:2000] for row in batch]  # truncate very long chunks
            chunk_ids = [row["id"] for row in batch]

            vectors = _embed_batch(model, tokenizer, texts)

            for chunk_id, vec in zip(chunk_ids, vectors):
                conn.execute(
                    "INSERT OR REPLACE INTO embeddings (chunk_id, embedding) VALUES (?, ?)",
                    (chunk_id, _vec_to_bytes(vec)),
                )
                embedded_count += 1

            conn.commit()

        # Update embedding_meta
        now_iso = datetime.now(timezone.utc).isoformat()
        for key, value in [
            ("model_name", model_name),
            ("embedding_dim", str(EMBEDDING_DIM)),
            ("last_embed_at", now_iso),
        ]:
            conn.execute(
                "INSERT OR REPLACE INTO embedding_meta (key, value) VALUES (?, ?)",
                (key, value),
            )
        conn.commit()

    return EmbedResult(
        total_chunks=total_chunks_in_db,
        embedded_chunks=embedded_count,
        skipped_unchanged=skipped,
        model_name=model_name,
        embedding_dim=EMBEDDING_DIM,
        elapsed_seconds=round(time.monotonic() - start, 2),
    )


# ---------------------------------------------------------------------------
# Semantic query
# ---------------------------------------------------------------------------


def query_similar(
    database_path: Path,
    query_text: str,
    *,
    model_name: str = DEFAULT_MODEL,
    top_k: int = 10,
) -> list[dict[str, Any]]:
    """Embed query text and run ANN search via sqlite-vec.

    Returns ranked results with file path, heading, body preview, and score.
    """
    model, tokenizer = _load_model(model_name)
    vectors = _embed_batch(model, tokenizer, [query_text])
    query_vec = _vec_to_bytes(vectors[0])

    with db_connection(database_path, ensure_schema) as conn:
        results = conn.execute(
            """
            SELECT
                e.chunk_id,
                e.distance,
                c.heading,
                SUBSTR(c.body, 1, 300) AS body_preview,
                c.char_count,
                vf.rel_path,
                vf.title,
                vf.tags_json
            FROM embeddings e
            JOIN chunks c ON c.id = e.chunk_id
            JOIN vault_files vf ON vf.id = c.file_id
            WHERE e.embedding MATCH ? AND e.k = ?
            ORDER BY e.distance
            """,
            (query_vec, top_k),
        ).fetchall()

    return [
        {
            "chunk_id": row["chunk_id"],
            "file_path": row["rel_path"],
            "title": row["title"],
            "heading": row["heading"],
            "body_preview": row["body_preview"],
            "similarity_score": round(1.0 - row["distance"], 4),  # distance → similarity
            "char_count": row["char_count"],
            "tags": json.loads(row["tags_json"]) if row["tags_json"] else [],
        }
        for row in results
    ]
