from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP, database_path: Path) -> None:
    @mcp.tool()
    def query_notes(query: str, top_k: int = 10) -> list[dict[str, Any]]:
        """
        Semantic search over chunked vault notes via sqlite-vec.

        Embeds the query using the same model used for indexing, then
        runs ANN search to find the most similar chunks.
        Requires: `rebalance ingest notes` + `rebalance ingest embed`.

        FACADE: delegates to the legacy vault-only embeddings index
        (embedder.query_similar / embeddings table). Preserved for backward
        compatibility. For cross-source ranked retrieval, prefer semantic_query()
        with sources=["vault"] instead.
        """
        # FACADE: delegates to embedder.query_similar (legacy vault-only index)
        from rebalance.ingest.embedder import query_similar
        return query_similar(database_path=database_path, query_text=query, top_k=top_k)

    @mcp.tool()
    def search_vault(keyword: str, limit: int = 20) -> list[dict[str, Any]]:
        """
        Full-text keyword search over vault files via TF-IDF index.

        Searches the keywords table and returns ranked results.
        Requires: `rebalance ingest notes`.
        """
        from rebalance.ingest.note_ingester import search_by_keyword
        return search_by_keyword(database_path=database_path, keyword=keyword, limit=limit)

    @mcp.tool()
    def query_github_context(query: str, repo_full_name: str = "", top_k: int = 8) -> list[dict[str, Any]]:
        """
        Semantic search over the local GitHub artifact corpus.

        Searches synced issues, pull requests, comments, reviews, and commit
        messages that have already been ingested into SQLite and embedded with
        the local model.

        FACADE: delegates to the legacy GitHub-only embeddings index
        (github_knowledge.query_github_documents / github_embeddings table).
        Preserved for backward compatibility. For cross-source ranked retrieval,
        prefer semantic_query() with sources=["github"] instead.
        """
        # FACADE: delegates to github_knowledge.query_github_documents (legacy github-only index)
        from rebalance.ingest.github_knowledge import query_github_documents

        return query_github_documents(
            database_path=database_path,
            query_text=query,
            repo_full_name=repo_full_name,
            top_k=top_k,
        )

    @mcp.tool()
    def github_release_readiness(repo_full_name: str, milestone_title: str = "") -> dict[str, Any]:
        """
        Infer current milestone/release readiness from the local GitHub corpus.

        Returns explicit status, confidence, blockers, evidence, and per-issue
        classifications using only locally synced GitHub signals.
        """
        from rebalance.ingest.github_readiness import infer_github_release_readiness

        result = infer_github_release_readiness(
            database_path=database_path,
            repo_full_name=repo_full_name,
            milestone_title=milestone_title,
        )
        return result.as_dict()

    @mcp.tool()
    def github_close_candidates(repo_full_name: str) -> dict[str, Any]:
        """
        Suggest open issues that likely map to merged PRs and may be ready to close.

        Returns explicit and inferred issue <-> PR matches grouped into
        high-confidence and medium-confidence recommendations.
        """
        from rebalance.ingest.github_reconciliation import infer_issue_pr_close_candidates

        report = infer_issue_pr_close_candidates(
            database_path=database_path,
            repo_full_name=repo_full_name,
        )
        return report.as_dict()

    @mcp.tool()
    def ask(query: str, since_days: int = 7, skip_synthesis: bool = False) -> dict[str, Any]:
        """
        General-purpose natural language query across all data sources.

        Gathers context from vault embeddings, GitHub activity, project
        registry, and recent vault modifications. Optionally synthesizes
        a first-pass answer via a local Qwen LLM.

        Returns both the synthesis and raw context so the host agent can
        review, adapt, and present a refined answer.

        Set skip_synthesis=True to get raw context only (faster, no model load).
        """
        from rebalance.ingest.querier import ask as querier_ask
        result = querier_ask(
            query=query,
            database_path=database_path,
            since_days=since_days,
            skip_synthesis=skip_synthesis,
        )
        return {
            "query": result.query,
            "synthesis": result.synthesis,
            "vault_context": result.vault_context,
            "github_context": result.github_context,
            "github_semantic_context": result.github_semantic_context,
            "project_context": result.project_context,
            "vault_activity": result.vault_activity,
            "calendar_context": result.calendar_context,
            "temporal_context": result.temporal_context,
            "model_used": result.model_used,
            "elapsed_seconds": result.elapsed_seconds,
        }
