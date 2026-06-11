"""Path bootstrap for directly-run scripts in this directory.

``import _bootstrap`` makes ``rebalance.*`` (src/) and sibling scripts
importable when a script is run straight from the repo
(``python scripts/foo.py`` puts scripts/ itself on sys.path, so this module
always resolves). The launchd wrappers already export ``PYTHONPATH=src`` via
scripts/lib/scheduler_common.sh — this module is the single remaining place
sys.path is touched for script entry points.
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent

for _path in (str(_ROOT / "src"), str(_ROOT / "scripts")):
    if _path not in sys.path:
        sys.path.insert(0, _path)
