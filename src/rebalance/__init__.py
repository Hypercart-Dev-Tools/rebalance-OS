"""rebalance package.

Installs a process-wide logging handler on import so any module that does
``logger = logging.getLogger(__name__)`` gets routed output without each
entry point reconfiguring logging. Verbosity is controlled by the
``REBALANCE_LOG_LEVEL`` environment variable (DEBUG / INFO / WARNING /
ERROR / CRITICAL); default is WARNING so production CLI output stays clean.

Where does output go? — one convention, three destinations
----------------------------------------------------------
1. **Diagnostics / operational messages** → the ``rebalance`` logger
   (``logging.getLogger(__name__)``). Goes to stderr, level-gated by
   ``REBALANCE_LOG_LEVEL``. Use this for "something went wrong / notable
   happened" lines in *library* code (``ingest/``, ``mcp/``). Never use a
   bare ``print()`` for diagnostics — and MCP servers must never print to
   *stdout* at all (it corrupts the stdio JSON-RPC stream); log instead.
2. **Durable structured records** → append-only JSONL under ``temp/logs/``
   (``auth_activity.jsonl`` — auth events; ``health-reporter.log.jsonl`` —
   health runs) or ``temp/`` (per-run summaries). Use this for anything you
   want to query/audit later, not a transient diagnostic.
3. **User-facing CLI output** → ``typer.echo`` / a rich ``Console``. This is
   product output, not logging; it is *not* level-gated and stays as-is.
"""

from __future__ import annotations

import logging
import os

__all__ = ["__version__"]
__version__ = "0.69.2"


def _configure_logging() -> None:
    root = logging.getLogger("rebalance")
    if getattr(root, "_rebalance_configured", False):
        return
    level_name = os.environ.get("REBALANCE_LOG_LEVEL", "WARNING").upper()
    level = getattr(logging, level_name, logging.WARNING)
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        )
    )
    root.addHandler(handler)
    root.setLevel(level)
    root.propagate = False
    root._rebalance_configured = True  # type: ignore[attr-defined]


_configure_logging()
