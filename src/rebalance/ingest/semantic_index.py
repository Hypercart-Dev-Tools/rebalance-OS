"""Unified semantic document index across vault and GitHub sources."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from rebalance.ingest.config import get_github_ignored_repos, normalize_github_repo_name
from rebalance.ingest.db import (
    db_connection,
    ensure_github_schema,
    ensure_schema,
    ensure_semantic_schema,
    run_migrations,
)
from rebalance.ingest._job_guard import guarded_embedding
from rebalance.ingest.db import semantic as sem
from rebalance.ingest.embedder import (
    DEFAULT_MODEL as DEFAULT_EMBED_MODEL,
    EMBEDDING_DIM,
    _embed_batch,
    _load_model,
    _vec_to_bytes,
)

logger = logging.getLogger(__name__)

EmbedTexts = Callable[[list[str], str], list[list[float]]]


@dataclass
class SemanticBackfillResult:
    source_types: tuple[str, ...]
    total_documents: int
    inserted_count: int
    updated_count: int
    unchanged_count: int
    deleted_count: int
    elapsed_seconds: float


@dataclass
class SemanticEmbedResult:
    total_docs: int
    embedded_docs: int
    skipped_unchanged: int
    model_name: str
    embedding_dim: int
    elapsed_seconds: float


@dataclass
class SemanticDoc:
    """One source-agnostic semantic document yielded by a registry provider.

    A SourceModule's ``semantic_docs(conn)`` provider yields these; the
    flag-gated provider path in :func:`backfill_semantic_documents` maps each
    onto :func:`upsert_document`. This keeps new sources off the legacy
    if-ladder.
    """

    source_pk: str
    doc_kind: str
    title: str
    body: str
    metadata: dict
    created_at: str
    updated_at: str


def _default_embed_texts(texts: list[str], model_name: str) -> list[list[float]]:
    model, tokenizer = _load_model(model_name)
    return _embed_batch(model, tokenizer, texts)


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


from rebalance.lib.json_ops import _json_dumps

# ---------------------------------------------------------------------------
# Shared retrieval contracts — exported so callers never re-derive them.
# ---------------------------------------------------------------------------

# The canonical set of source names that constitute "work artifacts" in the
# unified semantic index. Used by chat_with_data and any surface that needs to
# express the product concept of "all ingested work".
WORK_SOURCES: tuple[str, ...] = ("vault", "github", "email")


def scope_to_sources(scope: str) -> list[str]:
    """Map a product scope alias to semantic source_type values.

    Canonical scope vocabulary:
      "work"  → ingested work artifacts (vault, github, email)
      "code"  → federated code/docs corpus (ask_self)
      "all"   → both work and code

    Callers must NOT define their own scope→sources mapping; import this.
    """
    if scope == "work":
        return list(WORK_SOURCES)
    if scope == "code":
        return ["code"]
    return [*WORK_SOURCES, "code"]  # "all"


def normalize_sources(source_types: Iterable[str] | None) -> tuple[str, ...]:
    """Validate and deduplicate a raw source-type list against the legal set.

    Returns a tuple of accepted source_type strings. Raises ``ValueError`` for
    any unrecognised value. Callers that need CLI-friendly errors should catch
    ``ValueError`` and re-raise in a surface-appropriate form.

    This is the canonical owner of the semantic source vocabulary. CLI and MCP
    wrappers must delegate here instead of maintaining their own allowed sets.
    """
    if source_types is None:
        return WORK_SOURCES
    normalized = []
    for value in source_types:
        item = value.strip().lower()
        if not item:
            continue
        if item == "all":
            return WORK_SOURCES
        # The legal set is exactly what the runtime ``semantic`` stage
        # processes: derive it from the single source of truth
        # (``_all_semantic_sources()``) so CLI validation can never drift from
        # the stage. That set is the if-ladder sources (vault/github/email/code)
        # plus any collector exposing a ``semantic_docs`` provider (e.g.
        # ``figma``); calendar/sleuth are intentionally absent because the stage
        # does not project them into the semantic index. Lazy/function-local
        # import avoids an import cycle (index_ops imports SemanticDoc here).
        from rebalance.ingest.index_ops import _all_semantic_sources
        legal = set(_all_semantic_sources())
        if item not in legal:
            raise ValueError(f"Unsupported source type: {value!r}")
        if item not in normalized:
            normalized.append(item)
    return tuple(normalized)


# Keep the private name alive so any internal caller not yet migrated still
# works — remove after all call sites are updated.
_normalize_sources = normalize_sources


def upsert_document(
    conn: Any,
    *,
    source_type: str,
    source_table: str,
    source_pk: str,
    doc_kind: str,
    title: str,
    body: str,
    metadata: dict[str, Any] | None,
    created_at: str,
    updated_at: str,
) -> tuple[int, str]:
    """Insert or update one semantic document row.

    Returns ``(doc_id, state)`` where state is one of ``inserted``, ``updated``,
    or ``unchanged``.
    """
    metadata_json = _json_dumps(metadata or {})
    content_hash = _content_hash(body)
    existing = sem.find_semantic_document(conn, source_type, source_pk)

    if existing is None:
        doc_id = sem.insert_semantic_document(
            conn,
            source_type=source_type,
            source_table=source_table,
            source_pk=source_pk,
            doc_kind=doc_kind,
            title=title,
            body=body,
            content_hash=content_hash,
            metadata_json=metadata_json,
            created_at=created_at,
            updated_at=updated_at,
        )
        return doc_id, "inserted"

    has_changed = any(
        [
            existing["source_table"] != source_table,
            existing["doc_kind"] != doc_kind,
            (existing["title"] or "") != title,
            existing["body"] != body,
            existing["content_hash"] != content_hash,
            (existing["metadata_json"] or "{}") != metadata_json,
            (existing["updated_at"] or "") != updated_at,
        ]
    )
    if not has_changed:
        return int(existing["id"]), "unchanged"

    sem.update_semantic_document(
        conn,
        int(existing["id"]),
        source_table=source_table,
        doc_kind=doc_kind,
        title=title,
        body=body,
        content_hash=content_hash,
        metadata_json=metadata_json,
        updated_at=updated_at,
    )
    return int(existing["id"]), "updated"


def _delete_missing_docs(
    conn: Any,
    *,
    source_type: str,
    seen_source_pks: set[str],
    source_pk_prefix: str = "",
) -> int:
    rows = sem.semantic_documents_for_source(
        conn, source_type, source_pk_prefix=source_pk_prefix
    )

    to_delete = [int(row["id"]) for row in rows if row["source_pk"] not in seen_source_pks]
    if not to_delete:
        return 0

    sem.delete_semantic_documents(conn, to_delete)
    return len(to_delete)


def sync_vault_documents(conn: Any) -> dict[str, int]:
    """Backfill semantic documents from the current ``chunks`` table."""
    ensure_semantic_schema(conn)
    rows = sem.vault_chunks_for_semantic(conn)

    inserted = updated = unchanged = 0
    seen_source_pks: set[str] = set()
    for row in rows:
        source_pk = str(row["id"])
        seen_source_pks.add(source_pk)
        _, state = upsert_document(
            conn,
            source_type="vault",
            source_table="chunks",
            source_pk=source_pk,
            doc_kind="chunk",
            title=row["title"] or row["rel_path"],
            body=row["body"],
            metadata={
                "file_id": row["file_id"],
                "file_path": row["rel_path"],
                "heading": row["heading"] or "",
                "heading_level": row["heading_level"],
                "chunk_index": row["chunk_index"],
                "char_count": row["char_count"],
                "tags": json.loads(row["tags_json"]) if row["tags_json"] else [],
            },
            created_at=row["ingested_at"],
            updated_at=row["last_modified"] or row["ingested_at"],
        )
        if state == "inserted":
            inserted += 1
        elif state == "updated":
            updated += 1
        else:
            unchanged += 1

    deleted = _delete_missing_docs(conn, source_type="vault", seen_source_pks=seen_source_pks)
    return {
        "total": len(rows),
        "inserted": inserted,
        "updated": updated,
        "unchanged": unchanged,
        "deleted": deleted,
    }


def sync_github_documents(conn: Any, *, repo_full_name: str = "") -> dict[str, int]:
    """Backfill semantic documents from ``github_documents``."""
    ensure_semantic_schema(conn)
    ignored_repos = set(get_github_ignored_repos())
    normalized_repo = normalize_github_repo_name(repo_full_name) if repo_full_name.strip() else ""
    if normalized_repo and normalized_repo in ignored_repos:
        return {"total": 0, "inserted": 0, "updated": 0, "unchanged": 0, "deleted": 0}

    rows = sem.github_documents_for_semantic(
        conn, normalized_repo=normalized_repo, ignored_repos=ignored_repos
    )

    inserted = updated = unchanged = skipped = 0
    seen_source_pks: set[str] = set()
    for row in rows:
        source_pk = row["source_key"]
        try:
            _, state = upsert_document(
                conn,
                source_type="github",
                source_table="github_documents",
                source_pk=source_pk,
                doc_kind=row["doc_type"],
                title=row["title"] or "",
                body=row["body"],
                metadata={
                    "repo_full_name": row["repo_full_name"],
                    "item_type": row["github_source_type"],
                    "source_number": row["source_number"],
                    "state": row["state"] or "",
                    "milestone_title": row["milestone_title"] or "",
                    "labels": json.loads(row["labels_json"]) if row["labels_json"] else [],
                    "review_decision": row["review_decision"] or "",
                    "check_status": row["check_status"] or "",
                    "html_url": row["html_url"] or "",
                },
                created_at=row["fetched_at"],
                updated_at=row["updated_at"] or row["fetched_at"],
            )
        except Exception as exc:
            # GH-167: one malformed github_documents row (bad JSON in
            # labels_json, a constraint violation, etc.) must not abort the
            # rest of this repo's projection — skip it, log why, and keep
            # going so every other row still lands in the semantic index.
            skipped += 1
            logger.warning(
                "sync_github_documents: skipping malformed row source_key=%r "
                "repo=%r doc_type=%r: %s",
                source_pk,
                row["repo_full_name"],
                row["doc_type"],
                exc,
            )
            continue
        # Only mark a row "seen" once it's actually landed in the semantic
        # index — a skipped row must stay eligible for reconciliation on the
        # next run instead of being treated as intentionally deleted.
        seen_source_pks.add(source_pk)
        if state == "inserted":
            inserted += 1
        elif state == "updated":
            updated += 1
        else:
            unchanged += 1

    explicit_prefix = f"{repo_full_name.strip()}:" if repo_full_name.strip() else ""
    deleted = _delete_missing_docs(
        conn,
        source_type="github",
        seen_source_pks=seen_source_pks,
        source_pk_prefix=explicit_prefix,
    )
    return {
        "total": len(rows),
        "inserted": inserted,
        "updated": updated,
        "unchanged": unchanged,
        "deleted": deleted,
        "skipped": skipped,
    }


def sync_email_documents(conn: Any) -> dict[str, int]:
    """Backfill semantic documents from ``email_messages``.

    Body is ``subject + "\\n" + snippet`` per the Phase 1 plan — full MIME
    body extraction is deferred to Phase 2. Newest-100 rolling fetches
    don't delete older rows, so we don't reconcile against ``seen``: an
    email row that drops out of the fetch window stays in the index.
    """
    ensure_semantic_schema(conn)
    rows = sem.email_messages_for_semantic(conn)

    inserted = updated = unchanged = 0
    for row in rows:
        subject = row["subject"] or ""
        snippet = row["snippet"] or ""
        body = f"{subject}\n{snippet}".strip()
        if not body:
            continue

        title = subject or (row["from_address"] or "(no subject)")
        received_at = row["received_at"] or row["synced_at"]

        _, state = upsert_document(
            conn,
            source_type="email",
            source_table="email_messages",
            source_pk=row["message_id"],
            doc_kind="message",
            title=title,
            body=body,
            metadata={
                "thread_id": row["thread_id"] or "",
                "from_address": row["from_address"] or "",
                "from_name": row["from_name"] or "",
                "labels": json.loads(row["labels_json"]) if row["labels_json"] else [],
                "received_at": received_at,
            },
            created_at=received_at,
            updated_at=row["synced_at"],
        )
        if state == "inserted":
            inserted += 1
        elif state == "updated":
            updated += 1
        else:
            unchanged += 1

    return {
        "total": len(rows),
        "inserted": inserted,
        "updated": updated,
        "unchanged": unchanged,
        "deleted": 0,
    }


def sync_code_documents(conn: Any, repo_root: Path) -> dict[str, int]:
    """Backfill semantic documents from the local source tree (source_type='code').

    Unlike the other syncs, the source is the *filesystem*, not a DB table — the
    code collector walks ``repo_root`` and AST-chunks Python modules. Change
    detection is by content hash + file mtime, so unchanged files stay
    ``unchanged`` across runs (no needless re-embed).
    """
    ensure_semantic_schema(conn)
    from rebalance.ingest.code_collector import collect_code_chunks

    chunks = collect_code_chunks(Path(repo_root))
    inserted = updated = unchanged = 0
    seen_source_pks: set[str] = set()
    for ch in chunks:
        source_pk = f"{ch.path}::{ch.symbol}"
        seen_source_pks.add(source_pk)
        _, state = upsert_document(
            conn,
            source_type="code",
            source_table="code",
            source_pk=source_pk,
            doc_kind=ch.doc_kind,
            title=f"{ch.path} :: {ch.symbol}",
            body=ch.body,
            metadata={
                "path": ch.path,
                "symbol": ch.symbol,
                "parent_symbol": ch.parent_symbol,
                "language": ch.language,
                "start_line": ch.start_line,
            },
            created_at=ch.mtime_iso,
            updated_at=ch.mtime_iso,
        )
        if state == "inserted":
            inserted += 1
        elif state == "updated":
            updated += 1
        else:
            unchanged += 1

    deleted = _delete_missing_docs(conn, source_type="code", seen_source_pks=seen_source_pks)
    return {
        "total": len(chunks),
        "inserted": inserted,
        "updated": updated,
        "unchanged": unchanged,
        "deleted": deleted,
    }


# Registry sources route through the flag-gated provider path below. Each maps
# to the source table recorded on its ``semantic_documents`` rows. Kept as a
# small explicit map (rather than read off the collector) so the backfill has
# no hard dependency on collector internals — adding a SourceModule means one
# entry here next to its registration.
_REGISTRY_SOURCE_TABLES: dict[str, str] = {"figma": "figma_comments"}

# Sources already handled by the legacy if-ladder; the provider path skips them.
_LADDER_SOURCES: frozenset[str] = frozenset({"vault", "github", "email", "code"})


def project_semantic_documents(
    database_path: Path,
    *,
    source_types: Iterable[str] | None = None,
    repo_full_name: str = "",
) -> SemanticBackfillResult:
    """Source-owned facade over :func:`backfill_semantic_documents` for the
    `semantic-backfill` maintenance command, so the CLI doesn't import the leaf
    directly (COLLECTOR-PATH-AND-PORTABILITY-AUDIT Phase 2)."""
    return backfill_semantic_documents(
        database_path=database_path,
        source_types=source_types,
        repo_full_name=repo_full_name,
    )


def backfill_semantic_documents(
    database_path: Path,
    *,
    source_types: Iterable[str] | None = None,
    repo_full_name: str = "",
    repo_root: Path | None = None,
    use_registry_providers: bool = False,
) -> SemanticBackfillResult:
    """Populate ``semantic_documents`` from existing source tables (+ the source
    tree when ``code`` is requested).

    When ``use_registry_providers`` is True, any selected source NOT handled by
    the legacy if-ladder but registered with a ``semantic_docs`` provider (e.g.
    ``figma``) is backfilled via that provider — the registry-driven strangler
    path. The if-ladder is otherwise untouched.
    """
    start = time.monotonic()
    selected_sources = _normalize_sources(source_types)
    inserted = updated = unchanged = deleted = total = 0

    with db_connection(database_path) as conn:
        ensure_semantic_schema(conn)
        if "vault" in selected_sources:
            ensure_schema(conn)
            result = sync_vault_documents(conn)
            inserted += result["inserted"]
            updated += result["updated"]
            unchanged += result["unchanged"]
            deleted += result["deleted"]
            total += result["total"]
        if "github" in selected_sources:
            ensure_github_schema(conn)
            result = sync_github_documents(conn, repo_full_name=repo_full_name)
            inserted += result["inserted"]
            updated += result["updated"]
            unchanged += result["unchanged"]
            deleted += result["deleted"]
            total += result["total"]
        if "email" in selected_sources:
            from rebalance.ingest.db import ensure_email_schema
            ensure_email_schema(conn)
            result = sync_email_documents(conn)
            inserted += result["inserted"]
            updated += result["updated"]
            unchanged += result["unchanged"]
            deleted += result["deleted"]
            total += result["total"]
        if "code" in selected_sources:
            if repo_root:
                root = repo_root
            else:
                from rebalance.paths import resolve_project_root
                root = resolve_project_root(Path(__file__))
            result = sync_code_documents(conn, root)
            inserted += result["inserted"]
            updated += result["updated"]
            unchanged += result["unchanged"]
            deleted += result["deleted"]
            total += result["total"]
        # Registry-driven provider path (strangler). Runs alongside — never
        # replacing — the if-ladder above. Only sources NOT in the ladder that
        # carry a ``semantic_docs`` provider are iterated here.
        if use_registry_providers:
            from rebalance.ingest.index_ops import COLLECTORS
            for source in selected_sources:
                if source in _LADDER_SOURCES:
                    continue
                collector = COLLECTORS.get(source)
                if collector is None or collector.semantic_docs is None:
                    continue
                run_migrations(conn)
                source_table = _REGISTRY_SOURCE_TABLES.get(source, source)
                for doc in collector.semantic_docs(conn):
                    _, state = upsert_document(
                        conn,
                        source_type=source,
                        source_table=source_table,
                        source_pk=doc.source_pk,
                        doc_kind=doc.doc_kind,
                        title=doc.title,
                        body=doc.body,
                        metadata=doc.metadata,
                        created_at=doc.created_at,
                        updated_at=doc.updated_at,
                    )
                    total += 1
                    if state == "inserted":
                        inserted += 1
                    elif state == "updated":
                        updated += 1
                    else:
                        unchanged += 1
        conn.commit()

    return SemanticBackfillResult(
        source_types=selected_sources,
        total_documents=total,
        inserted_count=inserted,
        updated_count=updated,
        unchanged_count=unchanged,
        deleted_count=deleted,
        elapsed_seconds=round(time.monotonic() - start, 2),
    )


def embed_semantic_pending(
    database_path: Path,
    *,
    source_types: Iterable[str] | None = None,
    model_name: str = DEFAULT_EMBED_MODEL,
    batch_size: int = 32,
    min_chars: int = 1,
    force_reembed: bool = False,
    embed_texts: EmbedTexts | None = None,
) -> SemanticEmbedResult:
    """Source-owned facade over :func:`embed_pending` for the `semantic-embed`
    maintenance command, so the CLI doesn't import the leaf directly
    (COLLECTOR-PATH-AND-PORTABILITY-AUDIT Phase 2)."""
    return embed_pending(
        database_path=database_path,
        source_types=source_types,
        model_name=model_name,
        batch_size=batch_size,
        min_chars=min_chars,
        force_reembed=force_reembed,
        embed_texts=embed_texts,
    )


@guarded_embedding
def embed_pending(
    database_path: Path,
    *,
    model_name: str = DEFAULT_EMBED_MODEL,
    batch_size: int = 32,
    min_chars: int = 1,
    force_reembed: bool = False,
    source_types: Iterable[str] | None = None,
    embed_texts: EmbedTexts | None = None,
) -> SemanticEmbedResult:
    """Embed pending semantic document rows via the shared local embedder.

    Guarded by a single-instance lock and memory ceiling (GH-172), sharing one
    lock with :func:`rebalance.ingest.embedder.embed_chunks` — both load the same
    Qwen model, so their memory cost is cumulative and they must serialise
    against each other, not merely against themselves.
    """
    from rebalance.ingest.embedder import instrument_embedding_pass
    instrument_embedding_pass("embed_pending")
    start = time.monotonic()
    embed_fn = embed_texts or _default_embed_texts
    selected_sources = _normalize_sources(source_types)
    current_model_version = f"{model_name}|{EMBEDDING_DIM}"

    with db_connection(database_path, ensure_semantic_schema) as conn:
        if force_reembed:
            if set(selected_sources) == {"vault", "github", "email"} and len(selected_sources) == 3:
                sem.clear_semantic_embeddings(conn)
                sem.reset_semantic_embedded_state(conn)
            else:
                row_ids = sem.semantic_doc_ids_for_sources(conn, selected_sources)
                sem.delete_semantic_embeddings_for_docs(conn, row_ids)
                sem.reset_semantic_embedded_state(conn, selected_sources)
            conn.commit()

        rows = sem.semantic_documents_pending_embed(
            conn, selected_sources, min_chars, current_model_version
        )
        total_docs = sem.count_embeddable_semantic_documents(
            conn, selected_sources, min_chars
        )

        if not rows:
            return SemanticEmbedResult(
                total_docs=total_docs,
                embedded_docs=0,
                skipped_unchanged=total_docs,
                model_name=model_name,
                embedding_dim=EMBEDDING_DIM,
                elapsed_seconds=round(time.monotonic() - start, 2),
            )

        embedded = 0
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i + batch_size]
            texts = [row["body"][:4000] for row in batch]
            vectors = embed_fn(texts, model_name)
            now_iso = datetime.now(timezone.utc).isoformat()
            for row, vec in zip(batch, vectors):
                sem.delete_semantic_embedding(conn, row["id"])
                sem.insert_semantic_embedding(conn, row["id"], _vec_to_bytes(vec))
                sem.mark_semantic_document_embedded(
                    conn, row["id"], current_model_version, now_iso
                )
                embedded += 1
            conn.commit()

        now_iso = datetime.now(timezone.utc).isoformat()
        for key, value in [
            ("model_name", model_name),
            ("embedding_dim", str(EMBEDDING_DIM)),
            ("embedder_version", current_model_version),
            ("last_embed_at", now_iso),
        ]:
            sem.set_semantic_embedding_meta(conn, key, value)
        conn.commit()

    return SemanticEmbedResult(
        total_docs=total_docs,
        embedded_docs=embedded,
        skipped_unchanged=total_docs - embedded,
        model_name=model_name,
        embedding_dim=EMBEDDING_DIM,
        elapsed_seconds=round(time.monotonic() - start, 2),
    )


def _rrf_fuse(
    result_lists: list[list[Any]], top_k: int, *, k: int = 60
) -> list[Any]:
    """Reciprocal-rank fusion of ranked row lists, keyed on ``doc_id``.

    Rank-based, so the vector (distance) and lexical (bm25) scales never have to
    be compared. Dedupe by doc_id; when a doc is in both lists, keep the row that
    carries a ``distance`` (the vector hit) so a similarity score can be shown.
    """
    scores: dict[Any, float] = {}
    rowmap: dict[Any, Any] = {}
    for rows in result_lists:
        for rank, row in enumerate(rows):
            doc_id = row["doc_id"]
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
            if doc_id not in rowmap or row["distance"] is not None:
                rowmap[doc_id] = row
    ordered = sorted(scores, key=lambda d: -scores[d])
    return [rowmap[d] for d in ordered[:top_k]]


def query(
    database_path: Path,
    query_text: str,
    *,
    top_k: int = 10,
    model_name: str = DEFAULT_EMBED_MODEL,
    source_filter: Iterable[str] | None = None,
    updated_after: str | None = None,
    repo: str | None = None,
    embed_texts: EmbedTexts | None = None,
    hybrid: bool = True,
) -> list[dict[str, Any]]:
    """Semantic search across the unified semantic index.

    Args:
        updated_after: ISO-8601 string (e.g. ``"2026-05-01"``); exclude docs
                       updated before this date/time.
        repo: Restrict github results to one repo (``owner/name``).
        hybrid: Fuse the vector (ANN) ranking with an FTS5 lexical ranking via
                RRF — better recall on exact identifiers/paths/config keys. Set
                False for pure ANN (also the automatic fallback when FTS5 is
                unavailable or the query has no lexical terms).
    """
    selected_sources = normalize_sources(source_filter)
    embed_fn = embed_texts or _default_embed_texts
    query_vec = _vec_to_bytes(embed_fn([query_text], model_name)[0])
    # Fetch a deeper pool per retriever so RRF has material to fuse.
    pool = max(top_k * 4, 24) if hybrid else top_k

    with db_connection(database_path, ensure_semantic_schema) as conn:
        vec_rows = sem.search_semantic_documents(
            conn, query_vec, pool, selected_sources,
            updated_after=updated_after, repo=repo,
        )
        fts_rows = (
            sem.search_semantic_documents_fts(
                conn, query_text, pool, selected_sources,
                updated_after=updated_after, repo=repo,
            )
            if hybrid else []
        )

    rows = _rrf_fuse([vec_rows, fts_rows], top_k) if fts_rows else vec_rows[:top_k]

    results: list[dict[str, Any]] = []
    for row in rows:
        metadata = json.loads(row["metadata_json"]) if row["metadata_json"] else {}
        distance = row["distance"]
        results.append(
            {
                "doc_id": row["doc_id"],
                "source_type": row["source_type"],
                "source_table": row["source_table"],
                "source_pk": row["source_pk"],
                "doc_kind": row["doc_kind"],
                "title": row["title"] or "",
                "body_preview": row["body_preview"],
                "metadata": metadata,
                "updated_at": row["updated_at"],
                "similarity_score": round(1.0 - distance, 4) if distance is not None else None,
            }
        )
    return results
