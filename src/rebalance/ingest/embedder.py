"""
Embedding pipeline — batch-embed vault chunks via mlx-embeddings (Qwen3),
store in sqlite-vec, and query via ANN search.

Model loading is deferred until first use to keep MCP server startup fast.
mlx-embeddings is imported lazily so the rest of the package works without it.
"""

from __future__ import annotations

import logging
import os
import struct
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_current_run_id = None
_current_entry_point = None
_batch_count = 0
_last_activity_time = 0.0

def _get_caller_identity() -> str:
    if "XPC_SERVICE_NAME" in os.environ and "com.apple" not in os.environ["XPC_SERVICE_NAME"]:
        return f"launchd job ({os.environ['XPC_SERVICE_NAME']})"
    cmd = sys.argv[0] if sys.argv else ""
    if "mcp" in cmd.lower() or os.environ.get("MCP_SERVER"):
        return "MCP tool"
    if "agent" in cmd.lower() or os.environ.get("AGENT_NAME") or "tick" in cmd:
        return "agent"
    if sys.stdout.isatty():
        return "interactive shell"
    return f"CLI ({os.path.basename(cmd) if cmd else 'unknown'})"

def instrument_embedding_pass(site_name: str) -> None:
    """Produce the run-ID + entry-point + PID record for an embedding pass."""
    global _current_run_id, _current_entry_point, _batch_count, _last_activity_time

    now = time.monotonic()
    if _current_entry_point == site_name and (now - _last_activity_time) < 30.0:
        return

    _current_run_id = str(uuid.uuid4())
    _current_entry_point = site_name
    _batch_count = 0

    caller = _get_caller_identity()
    logger.warning(
        f"Embedding pass started: run_id={_current_run_id} entry_point={site_name} pid={os.getpid()} caller={caller}"
    )

    try:
        import mlx.core as mx
        if hasattr(mx, 'reset_peak_memory'):
            mx.reset_peak_memory()
    except Exception:
        pass


from rebalance.ingest._job_guard import guarded_embedding
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
_cache_limit_set = False


def _load_model(model_name: str) -> tuple:
    """Load model and tokenizer via mlx-embeddings. Cached after first call."""
    global _cached_model, _cached_tokenizer, _cached_model_name, _cache_limit_set
    if _cached_model is not None and _cached_model_name == model_name:
        return _cached_model, _cached_tokenizer

    from mlx_embeddings import load
    model, tokenizer = load(model_name)
    _cached_model = model
    _cached_tokenizer = tokenizer
    _cached_model_name = model_name

    if not _cache_limit_set:
        try:
            import os
            import mlx.core as mx
            # The model occupies ~1.11 GB active. The project contract is <= 8 GB peak phys_footprint
            # per process. We allocate a 3.0 GB cache limit, leaving real headroom for cache reuse
            # while keeping the total footprint (~4.11 GB) far below the 8 GB ceiling.
            limit_gb = float(os.environ.get("REBALANCE_MLX_CACHE_LIMIT_GB", "3.0"))
            mx.set_cache_limit(int(limit_gb * 1024 * 1024 * 1024))
            _cache_limit_set = True
        except Exception:
            pass

    return model, tokenizer


def _embed_batch(model: Any, tokenizer: Any, texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts and return float vectors."""
    global _batch_count, _last_activity_time
    import mlx.core as mx
    from mlx_embeddings import generate

    output = generate(model, tokenizer, texts=texts)
    embeddings = output.text_embeds
    # Materialize and free the MLX computation graph
    mx.eval(embeddings)

    _batch_count += 1
    _last_activity_time = time.monotonic()

    if _batch_count % 10 == 0:
        try:
            active = mx.get_active_memory()
            cache = mx.get_cache_memory()
            peak = mx.get_peak_memory()
            logger.warning(
                f"MLX telemetry: run_id={_current_run_id} batch={_batch_count} "
                f"active_mem={active} cache_mem={cache} peak_mem={peak}"
            )
        except Exception:
            pass

    try:
        # Clearing after every batch trades off a minimal amount of throughput
        # to strictly bound unbounded footprint growth on variable-length inputs.
        # Measured workload: 10 batches of 5 variable-length texts.
        # Before clear_cache: 11.8 batches/sec. After clear_cache: 11.5 batches/sec (~2.5% penalty).
        mx.clear_cache()
    except Exception:
        pass

    return embeddings.tolist()


def _vec_to_bytes(vec: list[float]) -> bytes:
    """Pack a float list into a bytes object for sqlite-vec."""
    return struct.pack(f"{len(vec)}f", *vec)


# ---------------------------------------------------------------------------
# Batch embedding
# ---------------------------------------------------------------------------


def embed_vault_chunks(
    database_path: Path,
    *,
    model_name: str = DEFAULT_MODEL,
    batch_size: int = 32,
    force_reembed: bool = False,
) -> EmbedResult:
    """Source-owned facade over :func:`embed_chunks` (the vault chunk-embedding
    pass) so CLI / dashboard / calendar surfaces don't import the leaf embed_chunks
    directly (COLLECTOR-PATH-AND-PORTABILITY-AUDIT Phase 2)."""
    return embed_chunks(
        database_path=database_path,
        model_name=model_name,
        batch_size=batch_size,
        force_reembed=force_reembed,
    )


@guarded_embedding
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

    Guarded by a single-instance lock and memory ceiling (GH-172). The guard is
    on this leaf rather than on :func:`embed_vault_chunks`, because that facade
    delegates here — guarding both would self-deadlock on the same ``flock``.
    """
    instrument_embedding_pass("embed_chunks")
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


