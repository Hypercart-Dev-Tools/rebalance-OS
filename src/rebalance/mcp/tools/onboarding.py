from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from rebalance.ingest.config import get_github_token, set_github_token, set_vault_path
from rebalance.ingest.github_scan import validate_github_token
from rebalance.ingest.preflight import confirm_and_write, discover_candidates


def register(mcp: FastMCP, database_path: Path) -> None:
    @mcp.tool()
    def onboarding_status(vault_path: str) -> dict[str, Any]:
        """
        Report the full setup lifecycle: every stage (config, vault, GitHub
        PAT, optional Calendar/Gmail auth, registry, projections) with a
        ``done`` / ``now`` / ``next`` / ``blocked`` status and a remediation
        hint, so the host agent always knows where the operator is and what
        comes next. Pure read — safe to call repeatedly.

        The stage map is owned by ``rebalance.ingest.lifecycle`` (the Phase 5
        contract); this tool is a thin view over it. The legacy ``steps``
        list is preserved for existing clients. DB path is resolved from
        REBALANCE_DB (same as all server tools).
        """
        from rebalance.ingest.lifecycle import evaluate_setup

        vp = Path(vault_path).expanduser().resolve()
        report = evaluate_setup(vault_path=vp, database_path=database_path)

        # Legacy shape: flat steps with name/complete/detail.
        report["steps"] = [
            {"name": s["id"], "complete": s["complete"], "detail": s["detail"]}
            for s in report["stages"]
        ]
        return report

    @mcp.tool()
    def setup_github_token(token: str) -> dict[str, Any]:
        """
        Validate a GitHub PAT against the /user endpoint and store it.

        Returns validation result with login and scopes.  If invalid,
        the token is not stored.
        """
        result = validate_github_token(token)
        if result["valid"]:
            set_github_token(token)
        return result

    @mcp.tool()
    def run_preflight(vault_path: str) -> dict[str, Any]:
        """
        Discover project candidates from vault note titles and GitHub
        activity.  Read-only — does not write to the registry.

        Returns candidates segmented by activity recency.  The host agent
        presents these to the user, then sends the curated list to
        confirm_projects.
        """
        vp = Path(vault_path).expanduser().resolve()
        registry_path = vp / "Projects" / "00-project-registry.md"
        token = get_github_token()

        discovery = discover_candidates(
            vault_path=vp,
            registry_path=registry_path,
            github_token=token,
        )
        return discovery

    @mcp.tool()
    def confirm_projects(projects: list[dict[str, Any]], vault_path: str) -> dict[str, Any]:
        """
        Write confirmed projects to the canonical registry and run pull
        sync to materialize projects.yaml and the SQLite project_registry
        table.  Creates standard vault directories if missing.

        Pass the curated project list from run_preflight (with any
        user-edited fields like summary, priority_tier, tags).
        """
        vp = Path(vault_path).expanduser().resolve()
        registry_path = vp / "Projects" / "00-project-registry.md"
        projects_yaml_path = vp / "projects.yaml"

        result = confirm_and_write(
            projects=projects,
            vault_path=vp,
            registry_path=registry_path,
            projects_yaml_path=projects_yaml_path,
            database_path=database_path,
        )

        set_vault_path(str(vp))

        return {
            "registry_path": result.registry_path,
            "project_count": result.project_count,
            "sync_ok": result.sync_ok,
        }

    @mcp.tool()
    def ingest_gmail_messages(messages: list[dict[str, Any]]) -> dict[str, Any]:
        """Ingest pre-fetched Gmail messages into the local ``email_messages`` table.

        The MCP-path Gmail ingest, for installs configured with
        ``gmail_ingest_method=mcp``. An agent fetches messages via the Gmail
        MCP connector and pushes them here — a launchd job cannot reach an MCP
        connector, so this is the supported way to keep email fresh in MCP mode.

        Each *messages* dict accepts: ``message_id`` (required), ``thread_id``,
        ``from_address``, ``from_name``, ``subject``, ``snippet``,
        ``received_at``, and ``labels`` (list of label strings). Rows are stored
        immediately; semantic projection runs in the next ``semantic`` stage
        (``semantic_pending: true`` in this result signals that). To make new
        messages searchable right away, follow up with
        ``refresh_index(scope=["semantic"])``.
        """
        from rebalance.ingest.gmail import push_email_messages

        result = push_email_messages(database_path, messages)
        return {
            "messages_listed": result.messages_listed,
            "messages_stored": result.messages_stored,
            "messages_inserted": result.messages_inserted,
            "messages_updated": result.messages_updated,
            "semantic_pending": True,
        }
