from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP, database_path: Path) -> None:

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
    def ask(
        query: str,
        since_days: int = 7,
        skip_synthesis: bool = False,
    ) -> dict[str, Any]:
        """
        General-purpose natural language query across all data sources.

        Gathers context from vault embeddings, GitHub activity, project
        registry, and recent vault modifications. Optionally synthesizes
        a first-pass answer via a local Qwen LLM.

        Returns both the synthesis and raw context so the host agent can
        review, adapt, and present a refined answer.

        Set skip_synthesis=True to get raw context only (faster, no model load).
        The HiQS ranked "what should we work on next" verdict is ALWAYS returned
        under the top-level ``hiqs`` key — the same persisted ranking the
        dashboard's /whats-next view reads, so the two surfaces cannot drift.
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
            "hiqs": result.hiqs,
            "model_used": result.model_used,
            "elapsed_seconds": result.elapsed_seconds,
        }
