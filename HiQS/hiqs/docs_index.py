"""Projection and delta embedding for HiQS docs.

This module owns raw -> `docs` projection and delta vector embedding into `docs_vec`.
It is the SOLE writer to the `docs` table (§5 rule 1).
"""

from __future__ import annotations

import array
from collections.abc import Mapping
import hashlib
import os
import platform
import resource
import sqlite3
import time
from typing import Any, Iterable

from hiqs.plugins import Doc, Source, SyncReport, discover_sources


def get_embed_text(title: str, body: str) -> str:
    """Return the exact text payload passed to the encoder."""
    return f"{title}\n{body}" if title else body


def compute_content_hash(title: str, body: str) -> str:
    """Compute sha256 content hash of the document embedding payload."""
    text = get_embed_text(title, body)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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


def _encode_texts(embedder: Any, texts: list[str]) -> Any:
    """Encode texts using exclusively the `.encode()` method of the embedder object."""
    encode_fn = getattr(embedder, "encode", None)
    if callable(encode_fn):
        return encode_fn(texts)
    raise TypeError(f"Embedder must have an encode method, got {type(embedder)}")


def _matches_unit(unit: str, doc_id: str, source_name: str, doc_unit_map: dict[str, str]) -> bool:
    """Check if doc_id belongs to unit."""
    if doc_id in doc_unit_map:
        return doc_unit_map[doc_id] == unit
    if doc_id == unit:
        return True
    if doc_id.startswith(f"{source_name}:{unit}:"):
        return True
    if doc_id.startswith(f"{unit}:"):
        return True
    return False


def project_docs(
    connection: sqlite3.Connection,
    sources: Iterable[Source] | None = None,
    model_name: str = "all-MiniLM-L6-v2",
    embedder: Any | None = None,
    reports: Mapping[str, SyncReport] | None = None,
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

    existing_global_docs: dict[str, set[str]] = {}
    for doc_id, src_name in connection.execute("SELECT id, source FROM docs").fetchall():
        existing_global_docs.setdefault(doc_id, set()).add(src_name)

    for doc_id, src_set in existing_global_docs.items():
        if len(src_set) > 1:
            sources_str = ", ".join(sorted(src_set))
            raise ValueError(
                f"Existing database contains duplicate doc ID '{doc_id}' across multiple sources ({sources_str})"
            )

    seen_in_batch: dict[str, str] = {}

    docs_to_embed: list[Doc] = []
    inserts: list[tuple[str, str, str, str, str, str, str, str]] = []
    updates: list[tuple[str, str, str, str, str, str, str, str]] = []
    prunes: list[tuple[str, str]] = []

    invalidated_vec_doc_ids: list[str] = []

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

        report = reports.get(source.name) if reports else None
        attested_units = set(report.units_ok) if report and report.units_ok else set()

        doc_unit_map: dict[str, str] = {}
        scanned_doc_ids_by_unit: dict[str, set[str]] = {}

        for doc in source_docs:
            if doc.source != source.name:
                raise ValueError(
                    f"Doc source '{doc.source}' does not match Source name '{source.name}' for doc '{doc.id}'"
                )

            if doc.id in seen_in_batch:
                prev_source = seen_in_batch[doc.id]
                if prev_source != source.name:
                    raise ValueError(
                        f"Duplicate doc ID '{doc.id}' found across sources '{prev_source}' and '{source.name}'"
                    )
                else:
                    raise ValueError(
                        f"Duplicate doc ID '{doc.id}' found multiple times in source '{source.name}'"
                    )
            seen_in_batch[doc.id] = source.name

            if doc.id in existing_global_docs and source.name not in existing_global_docs[doc.id]:
                other_src = next(iter(existing_global_docs[doc.id]))
                raise ValueError(
                    f"Doc ID '{doc.id}' from source '{source.name}' collides with existing doc from source '{other_src}'"
                )

            unit = doc.unit if doc.unit else doc.id
            doc_unit_map[doc.id] = unit
            scanned_doc_ids_by_unit.setdefault(unit, set()).add(doc.id)

            new_tuple = (doc.title, doc.body, doc.url, doc.ts, doc.project, doc.author)

            if doc.id not in existing_map:
                inserts.append(
                    (source.name, doc.id, doc.title, doc.body, doc.url, doc.ts, doc.project, doc.author)
                )
                counts["inserted"] += 1
                docs_to_embed.append(doc)
            else:
                old_tuple = existing_map[doc.id]
                old_title, old_body = old_tuple[0], old_tuple[1]

                if new_tuple != old_tuple:
                    updates.append(
                        (doc.title, doc.body, doc.url, doc.ts, doc.project, doc.author, source.name, doc.id)
                    )
                    counts["updated"] += 1
                    # Delta embedding keyed by content hash
                    new_hash = compute_content_hash(doc.title, doc.body)
                    old_hash = compute_content_hash(old_title, old_body)
                    if new_hash != old_hash or doc.id not in existing_vec_ids:
                        docs_to_embed.append(doc)
                    if new_hash != old_hash:
                        invalidated_vec_doc_ids.append(doc.id)
                else:
                    counts["unchanged"] += 1
                    if doc.id not in existing_vec_ids:
                        docs_to_embed.append(doc)

        # Within-unit reconciliation for docs and docs_vec (§5 rule 2)
        if attested_units:
            to_prune: list[str] = []
            for existing_id in existing_map:
                for unit in attested_units:
                    if _matches_unit(unit, existing_id, source.name, doc_unit_map):
                        if existing_id not in scanned_doc_ids_by_unit.get(unit, set()):
                            to_prune.append(existing_id)
                        break

            for doc_id in to_prune:
                prunes.append((source.name, doc_id))
            counts["pruned"] += len(to_prune)

    # Delta embedding before DB mutations so failures leave DB state unchanged
    embed_ms: float = 0.0
    vec_data: list[tuple[str, str, int, bytes]] = []
    if docs_to_embed:
        if embedder is None:
            embedder = get_default_embedder(model_name)

        texts = [get_embed_text(d.title, d.body) for d in docs_to_embed]
        t0 = time.perf_counter()
        raw_vectors = _encode_texts(embedder, texts)
        t1 = time.perf_counter()
        embed_ms = round((t1 - t0) * 1000, 2)

        if raw_vectors is None or not hasattr(raw_vectors, "__len__"):
            raise ValueError("Encoder result is not a valid sequence")

        if len(raw_vectors) != len(docs_to_embed):
            raise ValueError(
                f"Encoder returned {len(raw_vectors)} vectors, expected {len(docs_to_embed)}"
            )

        for doc, vec in zip(docs_to_embed, raw_vectors):
            dim, blob = serialize_vector(vec)
            if dim == 0:
                raise ValueError(f"Encoder returned empty vector for doc '{doc.id}'")
            vec_data.append((doc.id, model_name, dim, blob))

    # Single atomic transaction for all DB mutations
    with connection:
        if inserts:
            connection.executemany(
                "INSERT INTO docs (source, id, title, body, url, ts, project, author) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                inserts,
            )
        if updates:
            connection.executemany(
                "UPDATE docs SET title = ?, body = ?, url = ?, ts = ?, project = ?, author = ? WHERE source = ? AND id = ?",
                updates,
            )
        if prunes:
            connection.executemany(
                "DELETE FROM docs WHERE source = ? AND id = ?",
                prunes,
            )
            connection.executemany(
                "DELETE FROM docs_vec WHERE doc_id = ?",
                [(p[1],) for p in prunes],
            )
        if invalidated_vec_doc_ids:
            connection.executemany(
                "DELETE FROM docs_vec WHERE doc_id = ?",
                [(did,) for did in invalidated_vec_doc_ids],
            )
        if vec_data:
            connection.executemany(
                "INSERT OR REPLACE INTO docs_vec (doc_id, model, dim, vec) VALUES (?, ?, ?, ?)",
                vec_data,
            )
        connection.execute("DELETE FROM docs_vec WHERE doc_id NOT IN (SELECT id FROM docs)")

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
