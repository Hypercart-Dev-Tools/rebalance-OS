"""Command-line entry point for the HiQS skeleton."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from .events import status


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
    "refresh": "Phase 1",
    "search": "Phase 1",
    "ask": "Phase 3",
    "serve": "Phase 4",
    "auth": "Phase 4",
}


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI, returning a conventional process exit code."""
    parser = build_parser()
    arguments = parser.parse_args(argv)

    if arguments.command == "status":
        indent = None if arguments.json else 2
        print(json.dumps(status(), indent=indent, sort_keys=True))
        return 0

    phase = _IMPLEMENTATION_PHASE[arguments.command]
    try:
        raise NotImplementedError(f"hiqs {arguments.command} is implemented in {phase}")
    except NotImplementedError as error:
        parser.error(str(error))
    return 2  # pragma: no cover - parser.error always exits


if __name__ == "__main__":  # pragma: no cover - exercised by Python's module runner
    raise SystemExit(main())
