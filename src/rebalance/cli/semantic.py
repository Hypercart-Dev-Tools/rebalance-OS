"""`rebalance semantic-*` commands — unified semantic index backfill/embed/query.

Extracted from the cli monolith (Phase 5). Registers on the shared Typer `app`.
"""

from __future__ import annotations

from pathlib import Path

import typer

from rebalance.cli._core import app
from rebalance.paths import DatabaseNotFoundError, DBOption, resolve_database_path
from rebalance.tz_utils import format_local, local_tz


def _normalize_semantic_sources_option(values: list[str]) -> list[str]:
    """Normalize repeatable --source flags for unified semantic commands.

    Delegates membership validation to ``semantic_index.normalize_sources``
    (the canonical source-vocabulary owner) and wraps any ``ValueError`` into
    a ``typer.BadParameter`` for CLI-appropriate error display.

    "all" expansion uses ``_all_semantic_sources()`` (dynamic registry-aware)
    rather than the core's legacy triad — that difference is intentional and
    documented in semantic_index._normalize_sources.
    """
    normalized = [value.strip().lower() for value in values if value.strip()]
    if not normalized or "all" in normalized:
        from rebalance.ingest.index_ops import _all_semantic_sources
        return _all_semantic_sources()
    try:
        from rebalance.ingest.semantic_index import normalize_sources
        return list(normalize_sources(normalized))
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


@app.command("semantic-backfill")
def semantic_backfill_cmd(
    source: list[str] = typer.Option(
        ["all"],
        "--source",
        help="Source family to backfill. Repeat for multiple values.",
    ),
    repo: str = typer.Option(
        "",
        "--repo",
        help="Optional owner/name filter when backfilling GitHub semantic documents.",
    ),
    database: Path | None = DBOption(),
) -> None:
    """Populate the unified semantic document layer from existing source tables."""
    from rebalance.ingest.semantic_index import project_semantic_documents

    try:
        db_path = resolve_database_path(database)
    except DatabaseNotFoundError as exc:
        typer.echo(str(exc))
        raise typer.Exit(2) from exc
    sources = _normalize_semantic_sources_option(source)
    typer.echo(f"Backfilling semantic documents for {', '.join(sources)}...")
    result = project_semantic_documents(
        database_path=db_path,
        source_types=sources,
        repo_full_name=repo,
    )
    typer.echo(
        f"Semantic backfill complete: inserted={result.inserted_count}, "
        f"updated={result.updated_count}, unchanged={result.unchanged_count}, "
        f"deleted={result.deleted_count}, total_scanned={result.total_documents} "
        f"({result.elapsed_seconds}s)"
    )


@app.command("semantic-embed")
def semantic_embed_cmd(
    source: list[str] = typer.Option(
        ["all"],
        "--source",
        help="Source family to embed. Repeat for multiple values.",
    ),
    database: Path | None = DBOption(),
    model: str = typer.Option("Qwen/Qwen3-Embedding-0.6B", help="HuggingFace model name"),
    batch_size: int = typer.Option(32, help="Batch size for embedding"),
    min_chars: int = typer.Option(1, help="Minimum document length to embed"),
    force: bool = typer.Option(False, help="Force re-embed matching semantic documents"),
) -> None:
    """Generate embeddings for the unified semantic document layer."""
    from rebalance.ingest.semantic_index import embed_semantic_pending

    try:
        db_path = resolve_database_path(database)
    except DatabaseNotFoundError as exc:
        typer.echo(str(exc))
        raise typer.Exit(2) from exc
    sources = _normalize_semantic_sources_option(source)
    typer.echo(
        f"Embedding semantic documents for {', '.join(sources)} with {model} "
        f"(batch_size={batch_size})..."
    )
    result = embed_semantic_pending(
        database_path=db_path,
        source_types=sources,
        model_name=model,
        batch_size=batch_size,
        min_chars=min_chars,
        force_reembed=force,
    )
    typer.echo(
        f"Semantic embed complete: embedded={result.embedded_docs}, "
        f"skipped={result.skipped_unchanged}, total_docs={result.total_docs}, "
        f"model={result.model_name}, dim={result.embedding_dim} "
        f"({result.elapsed_seconds}s)"
    )


@app.command("semantic-query")
def semantic_query_cmd(
    text: str = typer.Argument(..., help="Natural language query"),
    source: list[str] = typer.Option(
        ["all"],
        "--source",
        help="Source family to search. Repeat for multiple values.",
    ),
    database: Path | None = DBOption(),
    top_k: int = typer.Option(10, help="Number of results to return"),
    model: str = typer.Option("Qwen/Qwen3-Embedding-0.6B", help="Embedding model for query"),
    updated_after: str = typer.Option(
        None, "--updated-after",
        help="ISO-8601 date/datetime — exclude docs updated before this (e.g. 2026-05-01).",
    ),
    repo: str = typer.Option(
        None, "--repo",
        help="Restrict GitHub results to one repo in owner/name form.",
    ),
) -> None:
    """Semantic search over the unified semantic index."""
    from rebalance.ingest.semantic_index import query

    try:
        db_path = resolve_database_path(database)
    except DatabaseNotFoundError as exc:
        typer.echo(str(exc))
        raise typer.Exit(2) from exc
    sources = _normalize_semantic_sources_option(source)
    results = query(
        database_path=db_path,
        query_text=text,
        top_k=top_k,
        model_name=model,
        source_filter=sources,
        updated_after=updated_after or None,
        repo=repo or None,
    )
    if not results:
        typer.echo(
            "No semantic results found. Run `rebalance semantic-backfill` and "
            "`rebalance semantic-embed` first."
        )
        return
    for i, result in enumerate(results, 1):
        metadata = result["metadata"]
        heading = f" > {metadata.get('heading')}" if metadata.get("heading") else ""
        repo_label = f" {metadata.get('repo_full_name')}" if metadata.get("repo_full_name") else ""
        html_url = metadata.get("html_url") or ""
        updated_local = format_local(result.get("updated_at"), "%Y-%m-%d %H:%M %Z", tz=local_tz())
        typer.echo(
            f"{i}. [{result['similarity_score']:.3f}] {result['source_type']}:{result['doc_kind']}{repo_label}"
        )
        typer.echo(f"   {result['title']}{heading}")
        if updated_local:
            typer.echo(f"   Local Time: {updated_local}")
        if metadata.get("file_path"):
            typer.echo(f"   {metadata['file_path']}")
        if html_url:
            typer.echo(f"   {html_url}")
        typer.echo(f"   {result['body_preview'][:180]}...")
        typer.echo()
