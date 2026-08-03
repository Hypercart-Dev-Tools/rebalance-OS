"""Projection and delta embedding for HiQS docs.

This module owns raw -> `docs` projection and delta vector embedding into `docs_vec`.
It is the SOLE writer to the `docs` table (§5 rule 1).
"""

from __future__ import annotations

import array
import os
import platform
import resource
import sqlite3
import time
from typing import Any, Iterable

from hiqs.plugins import Doc, Source, SyncReport, discover_sources


def get_peak_rss_mb() -> float:
    """Return peak RSS in megabytes."""
    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if platform.system() == "Darwin":
        return round(usage / (1024 * 1024), 2)
    return round(usage / 1024, 2)


def serialize_vector(vec: Iterable[float]) -> tuple[int, bytes]:
    """Serialize a float vector into (dim, blob)."""
    arr = array.array("f", vec)
    return len(arr), arr.tobytes()


def deserialize_vector(blob: bytes) -> list[float]:
    """Deserialize a float vector blob into a list of floats."""
    arr = array.array("f")
    arr.frombytes(blob)
    return arr.tolist()


def get_default_embedder(model_name: str = "all-MiniLM-L6-v2") -> Any:
    """Load SentenceTransformer model instance for the given model_name."""
    try:
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer(model_name)
    except ImportError as err:
        raise RuntimeError(f"sentence-transformers is required for embedding: {err}") from err


def _encode_texts(embedder: Any, texts: list[str]) -> list[list[float]] | Any:
    """Encode texts using either an encoder object with an `.encode()` method or a callable."""
    if hasattr(type(embedder), "encode"):
        return embedder.encode(texts)
    if callable(embedder):
        return embedder(texts)
    if hasattr(embedder, "encode"):
        return embedder.encode(texts)
    raise TypeError(f"Embedder must be callable or have an encode method, got {type(embedder)}")


def project_docs(
    connection: sqlite3.Connection,
    sources: Iterable[Source] | None = None,
    model_name: str = "all-MiniLM-L6-v2",
    embedder: Any | None = None,
) -> SyncReport:
    """Project raw source documents into the unified `docs` table and delta-embed vectors into `docs_vec`.

    This function is the SOLE writer to the `docs` table (§5 rule 1).
    """
    if sources is None:
        sources = discover_sources()

    counts = {
        "inserted": 0,
        "updated": 0,
        "unchanged": 0,
        "skipped": 0,
        "rejected": 0,
        "pruned": 0,
    }
    errors: list[str] = []

    t0 = time.perf_counter()
    docs_to_embed: list[Doc] = []

    for source in sources:
        if source.docs is None:
            continue

        try:
            source_docs = list(source.docs(connection))
        except Exception as err:
            errors.append(f"Error fetching docs for source '{source.name}': {err}")
            continue

        existing_rows = connection.execute(
            "SELECT id, title, body, url, ts, project, author FROM docs WHERE source = ?",
            (source.name,),
        ).fetchall()
        existing_map = {row[0]: row[1:] for row in existing_rows}

        existing_vec_ids = {
            r[0]
            for r in connection.execute(
                "SELECT doc_id FROM docs_vec WHERE model = ?", (model_name,)
            ).fetchall()
        }

        scanned_doc_ids: set[str] = set()

        with connection:
            for doc in source_docs:
                scanned_doc_ids.add(doc.id)
                new_tuple = (doc.title, doc.body, doc.url, doc.ts, doc.project, doc.author)

                if doc.id not in existing_map:
                    connection.execute(
                        "INSERT INTO docs (source, id, title, body, url, ts, project, author) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (doc.source, doc.id, doc.title, doc.body, doc.url, doc.ts, doc.project, doc.author),
                    )
                    counts["inserted"] += 1
                    docs_to_embed.append(doc)
                else:
                    old_tuple = existing_map[doc.id]
                    if new_tuple != old_tuple:
                        connection.execute(
                            "UPDATE docs SET title = ?, body = ?, url = ?, ts = ?, project = ?, author = ? WHERE source = ? AND id = ?",
                            (doc.title, doc.body, doc.url, doc.ts, doc.project, doc.author, doc.source, doc.id),
                        )
                        counts["updated"] += 1
                        docs_to_embed.append(doc)
                    else:
                        counts["unchanged"] += 1
                        if doc.id not in existing_vec_ids:
                            docs_to_embed.append(doc)

            # Within-unit reconciliation for docs and docs_vec (§5 rule 2)
            to_prune = [doc_id for doc_id in existing_map if doc_id not in scanned_doc_ids]
            if to_prune:
                connection.executemany(
                    "DELETE FROM docs WHERE source = ? AND id = ?",
                    [(source.name, doc_id) for doc_id in to_prune],
                )
                connection.executemany(
                    "DELETE FROM docs_vec WHERE doc_id = ?",
                    [(doc_id,) for doc_id in to_prune],
                )
                counts["pruned"] += len(to_prune)

    # Prune orphaned vectors if any exist
    with connection:
        connection.execute("DELETE FROM docs_vec WHERE doc_id NOT IN (SELECT id FROM docs)")

    # Delta embedding
    if docs_to_embed:
        if embedder is None:
            embedder = get_default_embedder(model_name)

        texts = [f"{d.title}\n{d.body}" if d.title else d.body for d in docs_to_embed]
        raw_vectors = _encode_texts(embedder, texts)

        with connection:
            for doc, vec in zip(docs_to_embed, raw_vectors):
                dim, blob = serialize_vector(vec)
                connection.execute(
                    "INSERT OR REPLACE INTO docs_vec (doc_id, model, dim, vec) VALUES (?, ?, ?, ?)",
                    (doc.id, model_name, dim, blob),
                )

    t1 = time.perf_counter()
    embed_ms = round((t1 - t0) * 1000, 2)
    peak_rss_mb = get_peak_rss_mb()

    meta = {"embed_ms": embed_ms, "peak_rss_mb": peak_rss_mb}
    return SyncReport(counts=counts, errors=errors, meta=meta)


def get_doc_vector(
    connection: sqlite3.Connection, doc_id: str, model_name: str = "all-MiniLM-L6-v2"
) -> tuple[int, list[float]] | None:
    """Retrieve vector (dim, vec_list) for doc_id and model_name from docs_vec table."""
    row = connection.execute(
        "SELECT dim, vec FROM docs_vec WHERE doc_id = ? AND model = ?",
        (doc_id, model_name),
    ).fetchone()
    if row is None:
        return None
    dim, blob = row
    return dim, deserialize_vector(blob)
