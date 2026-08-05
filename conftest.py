"""Root conftest.py — make pytest import THIS checkout's own ``src/`` tree.

GH-170: the package is installed editable from wherever it was last
``pip install -e``'d (see ``pyproject.toml``'s ``package-dir = {"" = "src"}``).
Editable installs resolve via an absolute path baked into a ``.pth`` file in
site-packages at install time. That means running ``pytest`` inside a linked
git worktree would otherwise still import the ORIGINAL checkout's copy of
``rebalance`` (whatever path was active when ``pip install -e .`` ran),
even though a fully independent copy of ``rebalance`` sits right next to
this very file. A green suite in a worktree would then prove nothing about
that worktree's own changes.

Fix: prepend this repo's own ``src/`` directory to ``sys.path`` before any
test module gets a chance to ``import rebalance``. Python resolves imports by
walking ``sys.path`` in order and using the first match, so this local
``src/`` always wins over whatever is installed editable in site-packages —
regardless of which checkout that editable install happens to point at.

This is a path-resolution shim only. It does not change ``pyproject.toml``'s
package layout and has no effect outside of test collection.
"""

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent / "src"

if _SRC.is_dir():
    _src_str = str(_SRC)
    # De-dupe first so this ends up at index 0 even if something upstream
    # (e.g. an editable install of THIS SAME checkout) already added it.
    if _src_str in sys.path:
        sys.path.remove(_src_str)
    sys.path.insert(0, _src_str)
