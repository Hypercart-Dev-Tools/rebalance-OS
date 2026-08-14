"""`rebalance query` / `search` / `ask` — retrieval over the local knowledge store.

Extracted from the cli monolith (Phase 5). Registers on the shared Typer `app`.
"""

from __future__ import annotations

from pathlib import Path

import typer

from rebalance.cli._core import app
from rebalance.paths import DatabaseNotFoundError, DBOption, resolve_database_path


@app.command("query")
def query_cmd(
    text: str = typer.Argument(..., help="Natural language query"),
    database: Path | None = DBOption(),
    top_k: int = typer.Option(10, help="Number of results to return"),
    model: str = typer.Option("Qwen/Qwen3-Embedding-0.6B", help="Embedding model for query"),
) -> None:
    """Semantic search over vault notes."""
    from rebalance.ingest.semantic_index import query as semantic_query

    try:
        db_path = resolve_database_path(database)
    except DatabaseNotFoundError as exc:
        typer.echo(str(exc))
        raise typer.Exit(2) from exc
    results = semantic_query(
        database_path=db_path, query_text=text, model_name=model, top_k=top_k, source_filter=["vault"]
    )
    if not results:
        typer.echo("No results found. Run `rebalance ingest notes` and `rebalance refresh` first.")
        return
    for i, r in enumerate(results, 1):
        metadata = r["metadata"]
        heading = f" > {metadata['heading']}" if metadata.get("heading") else ""
        typer.echo(f"{i}. [{r['similarity_score']:.3f}] {r['title']}{heading}")
        typer.echo(f"   {metadata.get('file_path', '')}")
        typer.echo(f"   {r['body_preview'][:120]}...")
        typer.echo()


@app.command("search")
def search_cmd(
    keyword: str = typer.Argument(..., help="Keyword to search"),
    database: Path | None = DBOption(),
    limit: int = typer.Option(20, help="Max results"),
) -> None:
    """Full-text keyword search over vault files and chunks."""
    from rebalance.ingest.note_ingester import search_by_keyword

    try:
        db_path = resolve_database_path(database)
    except DatabaseNotFoundError as exc:
        typer.echo(str(exc))
        raise typer.Exit(2) from exc
    results = search_by_keyword(database_path=db_path, keyword=keyword, limit=limit)
    if not results:
        typer.echo(f"No results for '{keyword}'. Run `rebalance ingest notes` first.")
        return
    for i, r in enumerate(results, 1):
        heading = f" > {r['heading']}" if r["heading"] else ""
        typer.echo(f"{i}. [{r['keyword_score']:.3f}] {r['title']}{heading}")
        typer.echo(f"   {r['file_path']}")
        typer.echo()


@app.command("ask")
def ask_cmd(
    text: str = typer.Argument(..., help="Natural language question"),
    database: Path | None = DBOption(),
    days: int = typer.Option(7, help="Activity window in days"),
    no_llm: bool = typer.Option(False, help="Skip local LLM synthesis, return raw context only"),
    chat_model: str = typer.Option("Qwen/Qwen3-0.6B", help="Chat model for synthesis"),
) -> None:
    """Ask a natural language question across all data sources."""
    from rebalance.ingest.querier import ask as querier_ask

    try:
        db_path = resolve_database_path(database)
    except DatabaseNotFoundError as exc:
        typer.echo(str(exc))
        raise typer.Exit(2) from exc
    typer.echo(f"Gathering context...")
    result = querier_ask(
        query=text,
        database_path=db_path,
        chat_model=chat_model,
        since_days=days,
        skip_synthesis=no_llm,
    )

    if result.temporal_context:
        today = result.temporal_context.get("today", {})
        tomorrow = result.temporal_context.get("tomorrow", {})
        typer.echo(f"\n--- Schedule ---")
        typer.echo(f"  Today:    {today.get('day_name', '')} — {today.get('day_type', '')}")
        typer.echo(f"  Tomorrow: {tomorrow.get('day_name', '')} — {tomorrow.get('day_type', '')}")

    if result.synthesis:
        typer.echo(f"\n--- Synthesis ({result.model_used}, {result.elapsed_seconds}s) ---\n")
        typer.echo(result.synthesis)
    else:
        typer.echo(f"\n--- Raw context ({result.elapsed_seconds}s) ---\n")

    if result.github_context:
        typer.echo("\n--- GitHub Activity ---")
        for g in result.github_context:
            if g.get("is_idle"):
                typer.echo(f"  {g['project_name']:25s}  IDLE")
            else:
                typer.echo(f"  {g['project_name']:25s}  {g['total_commits']:3d} commits  {g['prs_opened']} PRs  {g['issues_opened']} issues")

    if result.github_semantic_context:
        typer.echo("\n--- Relevant GitHub Artifacts ---")
        for item in result.github_semantic_context[:8]:
            typer.echo(
                f"  {item['repo_full_name']} {item['source_type']} #{item['source_number']} "
                f"[{item['similarity_score']:.3f}] {item['title']}"
            )

    if result.calendar_context:
        upcoming = result.calendar_context.get("upcoming", [])
        if upcoming:
            typer.echo("\n--- Upcoming Calendar ---")
            for e in upcoming[:10]:
                t = e["start_time"][:16].replace("T", " ")
                loc = f"  @ {e['location']}" if e.get("location") else ""
                typer.echo(f"  {t}  {e['summary']}{loc}")

    if result.vault_activity:
        typer.echo("\n--- Recent Vault Notes ---")
        for v in result.vault_activity[:10]:
            typer.echo(f"  {v['last_modified'][:10]}  {v['title']}")
