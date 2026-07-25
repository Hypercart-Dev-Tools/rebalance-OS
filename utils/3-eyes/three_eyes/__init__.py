"""3-Eyes — one optional, always-safe local job supervisor (GH-195).

Unifies the three sentinels we run today (XYZ debug flywheel, Cactus Needle PDDA
sentinel, Rebalance collector-health) under one TOML registry, one set of circuit
breakers + pressure-relief valves, one generated dashboard, and one way to talk to
jobs (MCP + Claude skill).

The load-bearing property is **inert by default**: with no ``config/runtime.env``
(or ``THREE_EYES_ENABLE != 1``) the whole system is a clean no-op — zero network,
zero ``ollama``, zero ``gh``, zero launchd/cron mutation. Activation is a local,
gitignored opt-in. See ``config.py`` for the single gate that decides it.
"""

from __future__ import annotations

__version__ = "0.1.1"

__all__ = ["__version__"]
