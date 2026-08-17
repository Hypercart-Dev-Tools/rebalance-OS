"""Command-line entry point for the HiQS skeleton."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from typing import Any

from .config import load_config
from .db import db_connection
from .docs_index import project_docs
from .events import log_event, status
from .plugins import discover_sources


def _positive_integer(value: str) -> int:
    """Parse a strictly positive integer for bounded CLI options."""
    integer = int(value)
    if integer < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return integer


def build_parser() -> argparse.ArgumentParser:
    """Build the stable six-command HiQS command-line interface."""
    parser = argparse.ArgumentParser(prog="hiqs", description="High-integrity query system")
    subcommands = parser.add_subparsers(dest="command", required=True)

    refresh_parser = subcommands.add_parser("refresh", help="refresh configured sources")
    refresh_parser.add_argument(
        "--source",
        action="append",
        default=[],
        metavar="SOURCE",
        help="refresh only this source (may be repeated)",
    )

    status_parser = subcommands.add_parser("status", help="show indexed-source health")
    status_parser.add_argument("--json", action="store_true", help="emit compact JSON")

    search_parser = subcommands.add_parser("search", help="search indexed documents")
    search_parser.add_argument("query", help="search query")
    search_parser.add_argument("--limit", type=_positive_integer, default=10, help="maximum results")

    ask_parser = subcommands.add_parser("ask", help="return attested context for a question")
    ask_parser.add_argument("query", help="question to answer")

    serve_parser = subcommands.add_parser("serve", help="serve the local health page")
    serve_parser.add_argument("--host", default="127.0.0.1", help="bind address")
    serve_parser.add_argument("--port", type=_positive_integer, default=8790, help="bind port")

    auth_parser = subcommands.add_parser("auth", help="authenticate an interactive source")
    auth_parser.add_argument("source", choices=("calendar",), help="source to authenticate")

    return parser


_IMPLEMENTATION_PHASE = {
    "ask": "Phase 3",
    "serve": "Phase 4",
    "auth": "Phase 4",
}


def refresh(
    only: Sequence[str] = (),
    *,
    connection=None,
    config=None,
    embedder=None,
) -> dict[str, Any]:
    """Run every configured source once, then project what they fetched into the index.

    This is §5's "one refresh walk" — the only thing that turns configuration into a
    searchable corpus. Every part of it existed before this function did; nothing
    connected them, so the system passed 133 tests without ever having ingested a file.

    Plugin rule 5 governs the loop: a source that raises does NOT abort the walk. Its
    error lands in `events` and in the returned summary, and the remaining sources still
    run. A failing source must not be able to take the others down with it.
    """
    config = load_config() if config is None else config
    owns_connection = connection is None
    connection = db_connection() if owns_connection else connection

    try:
        sources = [s for s in discover_sources() if not only or s.name in only]
        missing = sorted(set(only) - {s.name for s in sources})

        reports: dict[str, Any] = {}
        errors: dict[str, str] = {}
        for source in sources:
            try:
                reports[source.name] = source.fetch(connection, config)
            except Exception as error:  # plugin rule 5 — isolate, record, continue
                errors[source.name] = f"{type(error).__name__}: {error}"
                log_event("sync.failed", source.name, "error", {"error": errors[source.name]})
            else:
                log_event(
                    "sync.completed",
                    source.name,
                    "warn" if reports[source.name].errors else "ok",
                    {"counts": reports[source.name].counts},
                )

        # Only sources that actually returned a report may reach the projection: a source
        # that raised has no units_ok, and absent attestation must never authorise pruning
        # (§5 rule 2). Passing it through would be the GH-169 RC5 scar re-armed.
        fetched = [s for s in sources if s.name in reports]
        projection = project_docs(
            connection, sources=fetched, reports=reports, embedder=embedder
        )
        log_event(
            "projection.completed",
            "core",
            "warn" if projection.errors else "ok",
            {"counts": projection.counts},
        )

        # A source can fail without raising: github's fetch collects per-repo errors and
        # returns them in the report. That happened on a real run where all seven repos
        # failed and `refresh` still printed errors:{} and exited 0 — indistinguishable
        # from success to a scheduled job, which is the failure mode this project exists to
        # kill. Report-level errors are surfaced and counted the same as an exception.
        source_errors = {
            name: list(report.errors) for name, report in reports.items() if report.errors
        }

        summary = {
            "sources": {name: report.counts for name, report in reports.items()},
            "projection": projection.counts,
            "errors": errors,
            "source_errors": source_errors,
            "unknown_sources": missing,
        }
        if missing:
            # Asking for a source that does not exist is a typo, not a no-op. Silently
            # refreshing nothing and reporting success is the failure mode this project exists
            # to kill, so it is named in the summary and reflected in the exit code.
            log_event("refresh.unknown_source", "core", "warn", {"requested": missing})
        return summary
    finally:
        if owns_connection:
            connection.close()


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI, returning a conventional process exit code."""
    parser = build_parser()
    arguments = parser.parse_args(argv)

    if arguments.command == "status":
        indent = None if arguments.json else 2
        print(json.dumps(status(), indent=indent, sort_keys=True))
        return 0

    if arguments.command == "refresh":
        summary = refresh(arguments.source)
        print(json.dumps(summary, indent=2, sort_keys=True))
        # Non-zero when any source failed or was misnamed. A walk that silently half-ran
        # and exited 0 is indistinguishable from success to a scheduled job (L6, L19).
        # source_errors counts here too: a source that reported failures without raising
        # is still a failed walk.
        failed = (
            summary["errors"] or summary["source_errors"] or summary["unknown_sources"]
        )
        return 1 if failed else 0

    if arguments.command == "search":
        from .search import search as run_search

        for rank, doc in enumerate(run_search(arguments.query, limit=arguments.limit), 1):
            print(f"{rank:2}. [{doc.source}] {doc.title}  {doc.url}".rstrip())
        return 0

    phase = _IMPLEMENTATION_PHASE[arguments.command]
    try:
        raise NotImplementedError(f"hiqs {arguments.command} is implemented in {phase}")
    except NotImplementedError as error:
        parser.error(str(error))
    return 2  # pragma: no cover - parser.error always exits


if __name__ == "__main__":  # pragma: no cover - exercised by Python's module runner
    raise SystemExit(main())
