"""A throwaway out-of-tree source plugin.

Exposes a `module` object via the `rebalance.sources` entry-point group. The
spike's mini-registry discovers and dispatches it WITHOUT rebalance-OS core
importing this package by name — that's the whole point of the test.

`module` mimics the proposed SourceModule descriptor with just the fields the
discovery seam exercises (name + a refresh callable).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class MiniSourceModule:
    name: str
    refresh: Callable[..., dict[str, Any]]


def _refresh(db_path: Any = None, **opts: Any) -> dict[str, Any]:
    return {"scope": "dummy", "discovered": True, "opts_seen": sorted(opts)}


module = MiniSourceModule(name="dummy", refresh=_refresh)
