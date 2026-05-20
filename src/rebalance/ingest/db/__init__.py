"""Shared database layer for rebalance.

Connection factory, schema creation, and typed query helpers. The
implementation is split into submodules:

- ``connection`` — connection factory + ``db_connection`` context manager
- ``schema``     — every ``CREATE TABLE`` statement, grouped by source
- ``github``     — typed query helpers for the ``github_*`` tables

Everything is re-exported here, so ``from rebalance.ingest.db import ...``
keeps working unchanged regardless of which submodule a symbol lives in.
"""

from __future__ import annotations

from rebalance.ingest.db.connection import db_connection, get_connection
from rebalance.ingest.db.github import (
    repo_last_active,
    repo_meta_names,
    top_active_repos,
)
from rebalance.ingest.db.schema import (
    ensure_calendar_schema,
    ensure_email_schema,
    ensure_github_schema,
    ensure_project_schema,
    ensure_schema,
    ensure_semantic_schema,
)

__all__ = [
    "get_connection",
    "db_connection",
    "ensure_schema",
    "ensure_semantic_schema",
    "ensure_calendar_schema",
    "ensure_email_schema",
    "ensure_github_schema",
    "ensure_project_schema",
    "top_active_repos",
    "repo_last_active",
    "repo_meta_names",
]
