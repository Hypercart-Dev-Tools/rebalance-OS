"""rebalance package.

Installs a process-wide logging handler on import so any module that does
``logger = logging.getLogger(__name__)`` gets routed output without each
entry point reconfiguring logging. Verbosity is controlled by the
``REBALANCE_LOG_LEVEL`` environment variable (DEBUG / INFO / WARNING /
ERROR / CRITICAL); default is WARNING so production CLI output stays
clean. User-facing CLI output continues to go through ``typer.echo``;
``logging`` is for diagnostics only.
"""

from __future__ import annotations

import logging
import os

__all__ = ["__version__"]
__version__ = "0.30.0"


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
