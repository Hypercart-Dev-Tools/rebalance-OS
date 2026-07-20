"""Bridge from the ``rebalance`` package to ``utils/job_guard.py`` (GH-172).

Why this file exists
--------------------
``utils/job_guard.py`` deliberately lives OUTSIDE the package: it must run under
the system ``python3`` inside launchd wrappers, with no install step and no
third-party imports. That makes it unimportable by normal means from
``rebalance.ingest``, so this module loads it by path and exposes one helper.

What it guards
--------------
GH-172: on 2026-07-19 three unbounded Python embedding runs stacked to ~90 GB
resident on a 68.7 GB machine, saturated the VM compressor, starved ``watchdogd``
for 90s and hard-panicked the kernel. The runs were **agent-spawned, not
launchd-spawned**, which is why guarding the launchd wrappers alone would not
have prevented it. The guard therefore sits at the *library* leaves — every
caller (launchd, CLI, MCP tool, agent, interactive shell) funnels through them.

Lock scoping
------------
Both embedding leaves share ONE lock name. They load the same Qwen model and
their memory cost is cumulative, so they must serialise against each other, not
just against themselves. They are only ever called sequentially within a process
(``index_ops`` invokes them from different scopes), never nested — nesting would
self-deadlock, since ``flock`` is keyed on the open file description and a second
``open()`` in the same process takes a different one.

Failure posture
---------------
If the guard module cannot be loaded, this **fails open with a loud warning**
rather than blocking ingest. Refusing to embed would break daily-sync on every
machine that installed the package without ``utils/``; a warning keeps the job
running while making the gap visible. ``rebalance doctor`` surfaces the same
condition so it does not stay invisible.

Disable with ``REBALANCE_JOB_GUARD=0`` (the test suite does this — see
``tests/conftest.py`` — because ``MemoryCeiling.preflight()`` refuses to start on
a memory-starved machine, which would make tests fail spuriously on a busy box).
"""

from __future__ import annotations

import functools
import importlib.util
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any

#: One lock for every embedding path. See "Lock scoping" above.
EMBEDDING_LOCK = "rebalance-embed"

_ENV_ENABLED = "REBALANCE_JOB_GUARD"
_ENV_ON_CONFLICT = "REBALANCE_JOB_GUARD_ON_CONFLICT"
_ENV_MAX_RSS_GB = "REBALANCE_JOB_GUARD_MAX_RSS_GB"
_ENV_MODULE = "JOB_GUARD_MODULE"

_FALSEY = {"0", "false", "no", "off", ""}

_module: Any | None = None
_load_attempted = False
_warned = False


def module_path() -> Path:
    """Filesystem location of ``utils/job_guard.py``.

    ``JOB_GUARD_MODULE`` overrides it, which is what lets a non-editable install
    point at a vendored copy.
    """
    override = os.environ.get(_ENV_MODULE, "").strip()
    if override:
        return Path(override).expanduser()
    # src/rebalance/ingest/_job_guard.py -> repo root
    return Path(__file__).resolve().parents[3] / "utils" / "job_guard.py"


def load_job_guard() -> Any | None:
    """Import ``utils/job_guard.py`` by path. Returns None if unavailable.

    Cached, including the failure case: a missing guard must not cost a filesystem
    probe on every batch.
    """
    global _module, _load_attempted
    if _load_attempted:
        return _module
    _load_attempted = True

    path = module_path()
    if not path.is_file():
        return None
    try:
        spec = importlib.util.spec_from_file_location("rebalance_job_guard", path)
        if spec is None or spec.loader is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    except Exception:  # pragma: no cover - defensive; a broken guard must not break ingest
        return None
    _module = mod
    return _module


def enabled() -> bool:
    """False when ``REBALANCE_JOB_GUARD`` is set to a falsey value."""
    return os.environ.get(_ENV_ENABLED, "1").strip().lower() not in _FALSEY


def available() -> bool:
    """True when the guard module can actually be loaded. Used by ``doctor``."""
    return load_job_guard() is not None


def _warn_once(message: str) -> None:
    global _warned
    if _warned:
        return
    _warned = True
    print(f"[job-guard] WARNING: {message}", file=sys.stderr)


@contextmanager
def embedding_guard(
    name: str = EMBEDDING_LOCK,
    *,
    max_rss_gb: float | None = None,
    on_conflict: str | None = None,
):
    """Single-instance lock + memory ceiling around an embedding pass.

    Raises ``InstanceConflict`` when another embedding run holds the lock, and
    ``MemoryCeilingExceeded`` when the job trips the RSS ceiling or the machine's
    available-memory floor. Both are strictly better outcomes than #172.

    ``max_rss_gb`` defaults to ``job_guard.DEFAULT_MAX_RSS_FRACTION`` (35% of
    physical RAM) when unset — the ceiling is applied by ``MemoryCeiling``, not
    hardcoded here.
    """
    if not enabled():
        yield
        return

    mod = load_job_guard()
    if mod is None:
        _warn_once(
            f"job guard unavailable at {module_path()}; embedding is running "
            "UNGUARDED (see GH-172). Set JOB_GUARD_MODULE to a vendored copy."
        )
        yield
        return

    if max_rss_gb is None:
        raw = os.environ.get(_ENV_MAX_RSS_GB, "").strip()
        if raw:
            try:
                max_rss_gb = float(raw)
            except ValueError:
                _warn_once(f"ignoring non-numeric {_ENV_MAX_RSS_GB}={raw!r}")

    resolved_conflict = on_conflict or os.environ.get(_ENV_ON_CONFLICT, "refuse").strip()

    with mod.guard(name, max_rss_gb=max_rss_gb, on_conflict=resolved_conflict):
        yield


def guarded_embedding(fn):
    """Apply :func:`embedding_guard` to an embedding leaf function.

    Used as a decorator so the guard is a two-line change at each leaf rather
    than a re-indent of the whole body — and so it cannot be accidentally
    bypassed by an early ``return`` inside the function.
    """

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        with embedding_guard():
            return fn(*args, **kwargs)

    return wrapper
