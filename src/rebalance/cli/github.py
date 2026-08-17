"""`rebalance github-*` commands — scan, artifact sync, embed, query, readiness.

Extracted from the cli monolith (Phase 5). Registers on the shared Typer `app`
and owns the `_resolve_github_repos` helper.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

from rebalance.cli._core import app
from rebalance.ingest.config import (
    get_github_ignored_repos,
    get_github_token,
    normalize_github_repo_name,
)
from rebalance.paths import DatabaseNotFoundError, DBOption, resolve_database_path


def _resolve_github_repos(database_path: Path, repos: list[str]) -> list[str]:
    """Use explicit --repo values or fall back to active project registry repos."""
    ignored = set(get_github_ignored_repos())
    normalized = [repo.strip() for repo in repos if repo.strip()]
    if normalized:
        explicit = [normalize_github_repo_name(repo) for repo in normalized]
        ignored_explicit = [repo for repo in explicit if repo in ignored]
        if ignored_explicit:
            typer.echo(f"GitHub repo is ignored: {', '.join(ignored_explicit)}")
            raise typer.Exit(code=2)
        return sorted(set(normalized))

    from rebalance.ingest.registry import get_projects

    discovered: list[str] = []
    if database_path.exists():
        for project in get_projects(database_path, status="active"):
            discovered.extend(project.get("repos") or [])

    unique = sorted(
        {
            repo.strip()
            for repo in discovered
            if repo and repo.strip() and normalize_github_repo_name(repo) not in ignored
        }
    )
    if unique:
        return unique

    raise typer.BadParameter(
        "No eligible GitHub repos provided. Pass --repo owner/name or sync the project registry first."
    )


@app.command("github-scan")
def github_scan(
    token: str = typer.Option(..., envvar="GITHUB_TOKEN", help="GitHub Personal Access Token"),
    days: int = typer.Option(30, help="Number of days to look back (supports 30-day A/B/C band classification)"),
    database: Path | None = DBOption(),
) -> None:
    """Fetch GitHub activity and persist to database for use by github_balance MCP tool."""
    from rebalance.ingest.github_scan import scan_and_store_github_activity

    try:
        db_path = resolve_database_path(database)
    except DatabaseNotFoundError as exc:
        typer.echo(str(exc))
        raise typer.Exit(2) from exc
    typer.echo(f"Scanning GitHub activity for last {days} days...")
    result, skipped_repos = scan_and_store_github_activity(db_path, token=token, since_days=days)
    typer.echo(
        f"Done: login={result.login}, events={result.total_events}, "
        f"repos={len(result.repo_activity)}, skipped={len(skipped_repos)}, stored to {db_path}"
    )


@app.command("github-sync-artifacts")
def github_sync_artifacts(
    repos: list[str] = typer.Option(
        [],
        "--repo",
        help="GitHub repo in owner/name form. Repeat the flag to sync multiple repos.",
    ),
    token: str = typer.Option("", envvar="GITHUB_TOKEN", help="GitHub Personal Access Token"),
    days: int = typer.Option(90, help="Lookback window for changed issues and PRs"),
    database: Path | None = DBOption(),
) -> None:
    """Sync detailed GitHub issues, PRs, comments, reviews, checks, and releases."""
    from rebalance.ingest.github_knowledge import sync_github_artifacts

    # When the caller pins explicit --repo values, validate them against the
    # ignored list BEFORE resolving the DB. Catches "you told me to sync an
    # ignored repo" with the right error, instead of letting a missing DB
    # mask the misuse.
    normalized_explicit = [r.strip() for r in (repos or []) if r.strip()]
    if normalized_explicit:
        explicit_normalized = [normalize_github_repo_name(r) for r in normalized_explicit]
        ignored = set(get_github_ignored_repos())
        ignored_explicit = [r for r in explicit_normalized if r in ignored]
        if ignored_explicit:
            typer.echo(f"GitHub repo is ignored: {', '.join(ignored_explicit)}")
            raise typer.Exit(code=2)

    try:
        db_path = resolve_database_path(database)
    except DatabaseNotFoundError as exc:
        typer.echo(str(exc))
        raise typer.Exit(2) from exc
    target_repos = _resolve_github_repos(db_path, repos or [])
    resolved_token = token.strip() or (get_github_token() or "")
    if not resolved_token:
        if not normalized_explicit:
            raise typer.BadParameter(
                "GitHub token not configured. Use --token, GITHUB_TOKEN, or `rebalance config set-github-token`."
            )
        typer.echo(
            "GitHub token not configured; attempting unauthenticated sync for explicit public repo targets."
        )

    sync_github_artifacts(
        db_path,
        target_repos,
        token=resolved_token,
        since_days=days,
        on_repo_start=lambda repo: typer.echo(
            f"Syncing GitHub artifacts for {repo} ({days} days)..."
        ),
        on_repo_result=lambda repo, result: typer.echo(
            f"  synced branches={result.branches_synced}, issues={result.issues_synced}, prs={result.prs_synced}, "
            f"comments={result.comments_synced}, commits={result.commits_synced}, "
            f"checks={result.checks_synced}, docs={result.docs_built} "
            f"({result.elapsed_seconds}s)"
        ),
    )


@app.command("github-embed")
def github_embed(
    database: Path | None = DBOption(),
    model: str = typer.Option("Qwen/Qwen3-Embedding-0.6B", help="HuggingFace model name"),
    batch_size: int = typer.Option(32, help="Batch size for embedding"),
    min_chars: int = typer.Option(40, help="Minimum document length to embed"),
    force: bool = typer.Option(False, help="Force re-embed all GitHub documents"),
) -> None:
    """Generate embeddings for the local GitHub artifact corpus."""
    from rebalance.ingest.github_knowledge import refresh_github_embeddings

    try:
        db_path = resolve_database_path(database)
    except DatabaseNotFoundError as exc:
        typer.echo(str(exc))
        raise typer.Exit(2) from exc
    typer.echo(f"Embedding GitHub documents with {model} (batch_size={batch_size})...")
    result = refresh_github_embeddings(
        database_path=db_path,
        model_name=model,
        batch_size=batch_size,
        min_chars=min_chars,
        force_reembed=force,
    )
    typer.echo(
        f"GitHub embed complete: embedded={result.embedded_docs}, "
        f"skipped={result.skipped_unchanged}, total_docs={result.total_docs}, "
        f"model={result.model_name}, dim={result.embedding_dim} "
        f"({result.elapsed_seconds}s)"
    )


@app.command("github-query")
def github_query_cmd(
    text: str = typer.Argument(..., help="Natural language query"),
    database: Path | None = DBOption(),
    repo: str = typer.Option("", help="Optional owner/name repo filter"),
    top_k: int = typer.Option(8, help="Number of results to return"),
    model: str = typer.Option("Qwen/Qwen3-Embedding-0.6B", help="Embedding model for query"),
) -> None:
    """Semantic search over the local GitHub issue/PR/comment corpus."""
    from rebalance.ingest.semantic_index import query as semantic_query

    try:
        db_path = resolve_database_path(database)
    except DatabaseNotFoundError as exc:
        typer.echo(str(exc))
        raise typer.Exit(2) from exc
    results = semantic_query(
        database_path=db_path,
        query_text=text,
        repo=repo if repo else None,
        top_k=top_k,
        model_name=model,
        source_filter=["github"],
    )
    if not results:
        typer.echo(
            "No GitHub results found. Run `rebalance refresh` first."
        )
        return
    for i, result in enumerate(results, 1):
        metadata = result["metadata"]
        labels = f" [{', '.join(metadata['labels'])}]" if metadata.get("labels") else ""
        milestone = (
            f" milestone={metadata['milestone_title']}" if metadata.get("milestone_title") else ""
        )
        state = f" state={metadata['state']}" if metadata.get("state") else ""
        # source_type is "github" for every row here; the issue/pr/commit
        # distinction lives in metadata.item_type, and doc_type is now doc_kind.
        item_type = metadata.get("item_type", "")
        typer.echo(
            f"{i}. [{result['similarity_score']:.3f}] {metadata.get('repo_full_name', '')} "
            f"{item_type} #{metadata.get('source_number', '')} {result['doc_kind']}{labels}{state}{milestone}"
        )
        typer.echo(f"   {result['title']}")
        if metadata.get("html_url"):
            typer.echo(f"   {metadata['html_url']}")
        typer.echo(f"   {result['body_preview'][:180]}...")
        typer.echo()


@app.command("github-release-readiness")
def github_release_readiness_cmd(
    repo: str = typer.Option(..., "--repo", help="Repo in owner/name form"),
    milestone: str = typer.Option("", "--milestone", help="Optional milestone title"),
    database: Path | None = DBOption(),
    output_format: str = typer.Option("text", "--output", help="Output format: text or json"),
) -> None:
    """Infer current release/readiness state from the local GitHub corpus."""
    from rebalance.ingest.github_readiness import infer_github_release_readiness

    normalized_output = output_format.strip().lower()
    if normalized_output not in {"text", "json"}:
        raise typer.BadParameter("--output must be 'text' or 'json'.")

    try:
        db_path = resolve_database_path(database)
    except DatabaseNotFoundError as exc:
        typer.echo(str(exc))
        raise typer.Exit(2) from exc
    result = infer_github_release_readiness(
        database_path=db_path,
        repo_full_name=repo.strip(),
        milestone_title=milestone.strip(),
    )
    data = result.as_dict()
    if normalized_output == "json":
        typer.echo(json.dumps(data, ensure_ascii=False))
        return

    typer.echo(f"Repo:       {result.repo_full_name}")
    typer.echo(f"Milestone:  {result.milestone_title or '(none)'}")
    if result.milestone_due_on:
        typer.echo(f"Due:        {result.milestone_due_on[:10]}")
    typer.echo(f"Status:     {result.status}")
    typer.echo(f"Confidence: {result.confidence:.2f}")
    typer.echo(f"\n{result.summary}")

    if result.blockers:
        typer.echo("\nBlockers:")
        for blocker in result.blockers:
            typer.echo(f"  - {blocker}")

    if result.evidence:
        typer.echo("\nEvidence:")
        for line in result.evidence[:12]:
            typer.echo(f"  - {line}")

    if result.issue_states:
        typer.echo("\nIssue States:")
        for item in result.issue_states[:12]:
            prs = f" prs={','.join(str(n) for n in item.linked_pr_numbers)}" if item.linked_pr_numbers else ""
            typer.echo(f"  - #{item.issue_number} {item.classification}{prs} — {item.title}")


@app.command("github-close-candidates")
def github_close_candidates_cmd(
    repo: str = typer.Option(..., "--repo", help="Repo in owner/name form"),
    database: Path | None = DBOption(),
    output_format: str = typer.Option("text", "--output", help="Output format: text or json"),
) -> None:
    """Suggest open issues that likely map to merged PRs and may be ready to close."""
    from rebalance.ingest.github_reconciliation import infer_issue_pr_close_candidates

    normalized_output = output_format.strip().lower()
    if normalized_output not in {"text", "json"}:
        raise typer.BadParameter("--output must be 'text' or 'json'.")

    try:
        db_path = resolve_database_path(database)
    except DatabaseNotFoundError as exc:
        typer.echo(str(exc))
        raise typer.Exit(2) from exc
    report = infer_issue_pr_close_candidates(
        database_path=db_path,
        repo_full_name=repo.strip(),
    )
    data = report.as_dict()
    if normalized_output == "json":
        typer.echo(json.dumps(data, ensure_ascii=False))
        return

    typer.echo(f"Repo: {report.repo_full_name}")
    typer.echo(report.summary)
    typer.echo(
        "Counts: "
        f"open_issues={report.counts.get('open_issues_considered', 0)}, "
        f"merged_prs={report.counts.get('merged_prs_considered', 0)}, "
        f"high={report.counts.get('high_confidence', 0)}, "
        f"medium={report.counts.get('medium_confidence', 0)}, "
        f"explicit_auto_close={report.counts.get('explicit_auto_close', 0)}"
    )

    if report.high_confidence:
        typer.echo("\nHigh Confidence")
        for item in report.high_confidence[:15]:
            typer.echo(
                f"  - Issue #{item.issue_number} -> PR #{item.pr_number} "
                f"[{item.recommendation}, {item.confidence:.2f}] {item.issue_title}"
            )
            for line in item.evidence[:3]:
                typer.echo(f"      {line}")

    if report.medium_confidence:
        typer.echo("\nMedium Confidence")
        for item in report.medium_confidence[:15]:
            typer.echo(
                f"  - Issue #{item.issue_number} -> PR #{item.pr_number} "
                f"[{item.recommendation}, {item.confidence:.2f}] {item.issue_title}"
            )
            for line in item.evidence[:3]:
                typer.echo(f"      {line}")
