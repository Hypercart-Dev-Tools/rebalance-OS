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
import re
import sqlite3
import sys
import time
from typing import Any, Iterable

from hiqs.plugins import Doc, Source, SyncReport, discover_sources


_FENCED_CODE_BLOCK_RE = re.compile(r"(?:^|\n)```[^\n]*\n.*?(?:\n```|\Z)", re.DOTALL)
_URL_RE = re.compile(r"https?://[^\s<>()]+")
_GITHUB_URL_RE = re.compile(
    r"https?://github\.com/(?P<repo>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)/(?:issues/(?P<issue>\d+)|pull/(?P<pull>\d+))(?=$|[/?#\s<>)\],.?!;:])",
    re.IGNORECASE,
)
_GITHUB_SHORTHAND_RE = re.compile(
    r"(?<![\w./-])(?P<repo>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)#(?P<number>\d+)\b"
)
_BARE_GITHUB_REF_RE = re.compile(r"(?<![\w/#])#(?P<number>\d+)\b")
_NEWSLETTER_ISSUE_RE = re.compile(r"^\s+of\s+(?:the\s+)?newsletter\b", re.IGNORECASE)


def _literal_github_references(body: str, repo_context: str) -> set[tuple[str, str | None, int]]:
    """Extract literal GitHub references, excluding fenced code and URL fragments."""
    text = _FENCED_CODE_BLOCK_RE.sub("\n", body)
    references: set[tuple[str, str | None, int]] = set()

    for match in _GITHUB_URL_RE.finditer(text):
        repo = match.group("repo")
        if match.group("issue"):
            references.add((repo, "issue", int(match.group("issue"))))
        else:
            references.add((repo, "pull_request", int(match.group("pull"))))

    text_without_urls = _URL_RE.sub(" ", text)
    for match in _GITHUB_SHORTHAND_RE.finditer(text_without_urls):
        references.add((match.group("repo"), None, int(match.group("number"))))

    if repo_context:
        for match in _BARE_GITHUB_REF_RE.finditer(text_without_urls):
            if _NEWSLETTER_ISSUE_RE.match(text_without_urls[match.end() :]):
                continue
            references.add((repo_context, None, int(match.group("number"))))

    return references


def _resolved_github_references(
    connection: sqlite3.Connection, doc: Doc
) -> set[tuple[str, str, int]]:
    """Resolve only literal references to existing GitHub rows; never create placeholders."""
    resolved: set[tuple[str, str, int]] = set()
    for repo, explicit_type, number in _literal_github_references(doc.body, doc.project):
        if explicit_type is None:
            rows = connection.execute(
                "SELECT type FROM github_items WHERE repo = ? AND number = ?",
                (repo, number),
            ).fetchall()
        else:
            rows = connection.execute(
                "SELECT type FROM github_items WHERE repo = ? AND type = ? AND number = ?",
                (repo, explicit_type, number),
            ).fetchall()
        resolved.update((repo, row[0], number) for row in rows)
    return resolved


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
    """Load a SentenceTransformer, preferring local weights and never downloading silently.

    The plain `SentenceTransformer(model_name)` call this replaces fetched weights from the
    network with no announcement: an unattended run would stall for minutes on a cold cache
    with nothing in the log explaining why, and a test would hang (observed 2026-08-03).
    The eval runner already carries the offline-first fix as `get_offline_embedder`; this is
    the same fix at the second site that needed it — L23's lesson is precisely that a fix
    applied in one module does not protect the next one written.
    """
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as err:
        raise RuntimeError(f"sentence-transformers is required for embedding: {err}") from err

    try:
        return SentenceTransformer(model_name, local_files_only=True)
    except Exception:
        # Downloading is legitimate on a cold cache — it just may never be silent.
        print(
            f"hiqs: embedding model {model_name!r} is not cached locally; downloading now "
            "(one time, ~90 MB). An unattended run should pre-warm the cache instead.",
            file=sys.stderr,
            flush=True,
        )
        return SentenceTransformer(model_name)


EMBED_BATCH_SIZE = int(os.environ.get("HIQS_EMBED_BATCH", "64"))


def _encode_texts(embedder: Any, texts: list[str], batch_size: int = EMBED_BATCH_SIZE) -> Any:
    """Encode texts through `.encode()` in bounded batches.

    Unbounded until 2026-08-03, when one `.encode()` call over 1,833 chunks with
    Qwen3-Embedding-0.6B reached 14.32 GiB and was stopped only by MPS's own watermark.
    Nothing in HiQS limited it; the smaller default model had merely been hiding the
    absence of a ceiling. That is GH-172's mechanism — unbounded embedding memory —
    reproduced inside the clean room, and BOUNDED (§18.3) exists to forbid exactly it.

    Note the trap in torch's own advice: the MPS error suggests
    PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.0 to lift the limit, "may cause system failure".
    Raising the ceiling is how the original incident ended in a kernel panic. The fix is
    to need less, not to be allowed more.
    """
    encode_fn = getattr(embedder, "encode", None)
    if not callable(encode_fn):
        raise TypeError(f"Embedder must have an encode method, got {type(embedder)}")
    if batch_size < 1:
        raise ValueError("embedding batch size must be at least 1")

    if len(texts) <= batch_size:
        return encode_fn(texts)

    vectors: list[Any] = []
    for start in range(0, len(texts), batch_size):
        vectors.extend(encode_fn(texts[start : start + batch_size]))
    return vectors


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
    connection.execute(
        "CREATE TABLE IF NOT EXISTS doc_units (doc_id TEXT PRIMARY KEY, unit TEXT NOT NULL)"
    )

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
    doc_units_to_upsert: list[tuple[str, str]] = []
    desired_refs_by_doc: dict[tuple[str, str], set[tuple[str, str, int]]] = {}

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

        existing_units_rows = connection.execute(
            "SELECT doc_id, unit FROM doc_units WHERE doc_id IN (SELECT id FROM docs WHERE source = ?)",
            (source.name,),
        ).fetchall()
        existing_doc_units = {r[0]: r[1] for r in existing_units_rows}

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

            unit = doc.unit
            doc_unit_map[doc.id] = unit
            if unit:
                scanned_doc_ids_by_unit.setdefault(unit, set()).add(doc.id)
            doc_units_to_upsert.append((doc.id, unit))
            desired_refs_by_doc[(source.name, doc.id)] = _resolved_github_references(
                connection, doc
            )

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
                existing_unit = doc_unit_map.get(existing_id)
                if existing_unit is None:
                    existing_unit = existing_doc_units.get(existing_id)
                if existing_unit and existing_unit in attested_units:
                    if existing_id not in scanned_doc_ids_by_unit.get(existing_unit, set()):
                        to_prune.append(existing_id)

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
        if doc_units_to_upsert:
            connection.executemany(
                "INSERT OR REPLACE INTO doc_units (doc_id, unit) VALUES (?, ?)",
                doc_units_to_upsert,
            )
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
        refs_to_insert: list[tuple[str, str, str, str, int]] = []
        refs_to_delete: list[tuple[str, str, str, str, int]] = []
        for (doc_source, doc_id), desired_refs in desired_refs_by_doc.items():
            existing_refs = {
                (row[0], row[1], row[2])
                for row in connection.execute(
                    "SELECT repo, type, number FROM doc_github_refs WHERE doc_source = ? AND doc_id = ?",
                    (doc_source, doc_id),
                ).fetchall()
            }
            refs_to_insert.extend(
                (doc_source, doc_id, repo, item_type, number)
                for repo, item_type, number in desired_refs - existing_refs
            )
            refs_to_delete.extend(
                (doc_source, doc_id, repo, item_type, number)
                for repo, item_type, number in existing_refs - desired_refs
            )
        if refs_to_delete:
            connection.executemany(
                "DELETE FROM doc_github_refs WHERE doc_source = ? AND doc_id = ? AND repo = ? AND type = ? AND number = ?",
                refs_to_delete,
            )
        if refs_to_insert:
            connection.executemany(
                "INSERT INTO doc_github_refs(doc_source, doc_id, repo, type, number) VALUES (?, ?, ?, ?, ?)",
                refs_to_insert,
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
            connection.executemany(
                "DELETE FROM doc_units WHERE doc_id = ?",
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
        connection.execute("DELETE FROM doc_units WHERE doc_id NOT IN (SELECT id FROM docs)")

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


def get_linked_github_items(
    connection: sqlite3.Connection, doc_id: str
) -> list[tuple[str, str, int, str, str]]:
    """Return GitHub items literally linked from one projected document, without ranking them."""
    return connection.execute(
        """
        SELECT item.repo, item.type, item.number, item.title, item.url
        FROM doc_github_refs AS ref
        JOIN github_items AS item
          ON item.repo = ref.repo AND item.type = ref.type AND item.number = ref.number
        WHERE ref.doc_id = ?
        ORDER BY item.repo, item.type, item.number
        """,
        (doc_id,),
    ).fetchall()
