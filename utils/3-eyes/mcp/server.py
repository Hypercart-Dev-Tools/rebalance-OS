#!/usr/bin/env python3
"""3-Eyes MCP server (GH-195) — talk to your jobs from Claude.

Exposes the read + control surface of 3-Eyes as MCP tools: list jobs, get status,
explain why a job fires, dry-run a job (no egress), pause/resume, inventory
LaunchAgents, and regenerate the dashboard. The mutating tools (pause/resume/
sync-dashboard) are the same operator-safe actions the CLI offers; nothing here
can activate 3-Eyes or fire egress — those stay gated behind runtime.env.

Design: the tool *functions* are plain and dependency-free (return JSON-able
dicts), so they are unit-testable without the MCP SDK installed. The MCP transport
is a thin wrapper built only when the server actually runs.
"""

from __future__ import annotations

import sys
from pathlib import Path

# The package lives one level up (utils/3-eyes); put it on the path so this
# standalone script can import it whether launched by MCP or by a test.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from three_eyes import breakers, config, dashboard, launchd, registry, relief, routes  # noqa: E402


# --------------------------------------------------------------------------- #
# Plain, testable tool functions
# --------------------------------------------------------------------------- #

def list_jobs() -> dict:
    """List every job in the registry with its schedule, command, and routes."""
    return {
        "active": config.three_eyes_active(),
        "jobs": [
            {
                "id": j.id,
                "enabled": j.enabled,
                "schedule": j.schedule_summary(),
                "command": j.command,
                "routes": list(j.routes),
                "description": j.description,
            }
            for j in registry.load_jobs()
        ],
    }


def job_status(job_id: str) -> dict:
    """Live status for one job: config, breaker state, live launchctl state."""
    try:
        job = registry.load_job(job_id)
    except registry.RegistryError as exc:
        return {"error": str(exc)}
    st = breakers.FailureBreaker().status(job_id)
    return {
        "id": job.id,
        "schedule": job.schedule_summary(),
        "quiet_hours": job.quiet_hours,
        "in_quiet_now": relief.in_quiet_hours(job.quiet_hours),
        "breaker_open": bool(st.get("quarantined")),
        "consecutive_failures": st.get("consecutive_failures", 0),
        "live": launchd.launchctl_state(launchd.plist_label(job_id)),
    }


def why(job_id: str) -> dict:
    """Explain when and why a job fires, and its current breaker state."""
    try:
        job = registry.load_job(job_id)
    except registry.RegistryError as exc:
        return {"error": str(exc)}
    st = breakers.FailureBreaker().status(job_id)
    return {
        "id": job.id,
        "description": job.description,
        "fires": job.schedule_summary(),
        "fire_when": job.rules.get("fire_when"),
        "quiet_hours": job.quiet_hours,
        "breaker": "open" if st.get("quarantined") else "closed",
        "reason": st.get("reason"),
    }


def dry_run(job_id: str) -> dict:
    """Show what a job would do, including route previews. No egress."""
    try:
        job = registry.load_job(job_id)
    except registry.RegistryError as exc:
        return {"error": str(exc)}
    sample = {"source": job.id, "title": f"sample from {job.id}", "severity": "warn",
              "summary": "dry-run sample", "text": "sample"}
    return {
        "id": job.id,
        "command": job.command,
        "routes": [r for r in routes.route(sample, job.routes, dry_run=True)],
    }


def pause(job_id: str) -> dict:
    breakers.FailureBreaker().quarantine(job_id, reason="paused via MCP")
    return {"id": job_id, "paused": True}


def resume(job_id: str) -> dict:
    breakers.FailureBreaker().reset(job_id)
    return {"id": job_id, "paused": False}


def observe_agents() -> dict:
    """Read-only inventory of every user LaunchAgent."""
    return {"agents": launchd.observe_existing()}


def sync_dashboard() -> dict:
    path = dashboard.write()
    return {"regenerated": str(path)}


TOOLS = [list_jobs, job_status, why, dry_run, pause, resume, observe_agents, sync_dashboard]


# --------------------------------------------------------------------------- #
# MCP transport (built only when actually serving)
# --------------------------------------------------------------------------- #

def build_server():  # pragma: no cover - exercised only under a live MCP host
    from mcp.server.fastmcp import FastMCP

    server = FastMCP("3-eyes")
    server.add_tool(list_jobs, description="List 3-Eyes jobs in the registry.")
    server.add_tool(job_status, description="Live status for one job.")
    server.add_tool(why, description="Explain when/why a job fires.")
    server.add_tool(dry_run, description="Dry-run a job (route previews, no egress).")
    server.add_tool(pause, description="Pause (quarantine) a job.")
    server.add_tool(resume, description="Resume (un-quarantine) a job.")
    server.add_tool(observe_agents, description="Read-only LaunchAgent inventory.")
    server.add_tool(sync_dashboard, description="Regenerate DASHBOARD.md from the registry.")
    return server


if __name__ == "__main__":  # pragma: no cover
    build_server().run()
