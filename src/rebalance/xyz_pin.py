"""Read the committed ``.xyz-pin`` — GH-102 seam #2 (harness release channel).

The pin records which ``xyz-3-agents-swarm`` (XYZ) harness commit this Rebalance
install's XYZ integration targets. It is a committed repo-root file so a fresh
clone is reproducible (Guiding Principle 10), distinct from the machine-local,
never-committed ``~/.config/xyz/registry.tsv`` that records the *installed*
commit on a given machine.

This module only *reads* the pin — the recorded-vs-installed drift check itself
is XYZ-side (``xyz-sync check``, GH-102 Phase 1, deferred to the XYZ repo). It is
consumed by ``rebalance doctor`` to surface the pin.

Rebalance never requires XYZ to be present: an absent ``.xyz-pin`` is a normal,
healthy state (GH-102 invariant 1 — mutual independence), so :func:`read_pin`
returns ``None`` rather than raising when the file is missing.
"""

from __future__ import annotations

from pathlib import Path

from rebalance.paths import find_project_root

PIN_FILENAME = ".xyz-pin"


def pin_path(root: Path | None = None) -> Path | None:
    """Resolve the ``.xyz-pin`` path at the repo root, or ``None`` if the repo
    root can't be found (e.g. a non-editable wheel install with no source tree).
    """
    root = root if root is not None else find_project_root(Path(__file__))
    if root is None:
        return None
    return root / PIN_FILENAME


def read_pin(root: Path | None = None) -> dict[str, str] | None:
    """Parse ``.xyz-pin`` into a ``{key: value}`` dict, or ``None`` if absent.

    The format is simple ``key=value`` lines; ``#`` comments and blank lines are
    ignored. Never raises on a malformed line — unparseable lines (no ``=``) are
    skipped, so a partially-corrupt pin still yields whatever valid keys it has.
    The caller decides whether the required ``commit`` key is present.
    """
    path = pin_path(root)
    if path is None or not path.exists():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    data: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key:
            data[key] = value.strip()
    return data
