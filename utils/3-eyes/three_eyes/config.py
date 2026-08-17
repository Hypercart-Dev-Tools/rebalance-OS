"""The single activation gate for 3-Eyes (GH-195).

Everything egress-capable in 3-Eyes asks exactly one question before it acts:
``three_eyes_active()``. This module is the *only* place that answer is computed,
so "is 3-Eyes allowed to touch the outside world?" has one definition, not one per
caller.

Inert by default. The gate is TRUE only when BOTH hold:

  1. ``config/runtime.env`` exists (a gitignored, operator-authored file), and
  2. ``THREE_EYES_ENABLE`` resolves to ``1`` (process env wins over the file).

A downstream clone has neither, so it is inert: no network, no ``ollama``, no
``gh``, no launchd/cron mutation, no marathon fire. There is nothing to turn off
because nothing is on. (Precisely: the gate keys off the *effective* runtime.env —
``config/runtime.env`` by default, or the path in ``THREE_EYES_RUNTIME_ENV``, an
override that exists only so tests can point at an isolated tmp file. A default
deployment has neither an enabled file nor that override, so it is inert.)

Two hard overrides force the gate CLOSED regardless of the above — the global
kill-switch:

  * ``THREE_EYES_ENABLE=0`` in the process env (explicit off beats the file), and
  * a ``PANIC`` file in the state dir (drop the file, everything halts).
"""

from __future__ import annotations

import os
from pathlib import Path

# --------------------------------------------------------------------------- #
# Canonical paths (all relative to the package, never hardcoded to a machine)
# --------------------------------------------------------------------------- #

PKG_DIR = Path(__file__).resolve().parent          # .../utils/3-eyes/three_eyes
ROOT = PKG_DIR.parent                               # .../utils/3-eyes
REGISTRY_DIR = ROOT / "registry"
JOBS_DIR = REGISTRY_DIR / "jobs.d"
COMMANDS_ALLOW = REGISTRY_DIR / "commands.allow"
ROUTES_TOML = REGISTRY_DIR / "routes.toml"

#: Machine-local registry overlay (GH-195). Jobs/commands that point at absolute,
#: machine-specific paths (e.g. an automation syncing two of THIS Mac's repos) live
#: here and are GITIGNORED — runtime (run/status/health/catalog) reads them, but the
#: committed, fleet-portable DASHBOARD.md deliberately excludes them so a downstream
#: clone never inherits another machine's paths. This is where an adopted cross-repo
#: job lands when its command isn't repo-relative.
JOBS_LOCAL_DIR = REGISTRY_DIR / "jobs.local.d"
COMMANDS_LOCAL_ALLOW = REGISTRY_DIR / "commands.local.allow"
CONFIG_DIR = ROOT / "config"
RUNTIME_ENV = CONFIG_DIR / "runtime.env"
DASHBOARD = ROOT / "DASHBOARD.md"

#: The rebalance-OS repo root (utils/3-eyes/../..). Used to resolve allowlisted
#: command paths and PDDA inbox drafts against the host repo.
REPO_ROOT = ROOT.parent.parent

ENABLE_VAR = "THREE_EYES_ENABLE"
STATE_DIR_VAR = "THREE_EYES_STATE_DIR"
RUNTIME_ENV_VAR = "THREE_EYES_RUNTIME_ENV"
CLASSIFY_STUB_VAR = "THREE_EYES_CLASSIFY_STUB"


def state_dir() -> Path:
    """Where mutable run-state lives (locks, breaker counters, budgets, PANIC).

    Kept out of the repo by default so worktrees share one namespace and nothing
    mutable is ever committed. Overridable via ``THREE_EYES_STATE_DIR`` (tests set
    this to a tmp dir).
    """
    override = os.environ.get(STATE_DIR_VAR)
    if override:
        return Path(override)
    return Path.home() / ".cache" / "rebalance-os" / "3-eyes"


def panic_file() -> Path:
    return state_dir() / "PANIC"


def _runtime_env_path() -> Path:
    override = os.environ.get(RUNTIME_ENV_VAR)
    return Path(override) if override else RUNTIME_ENV


def load_runtime_env() -> dict[str, str]:
    """Parse ``config/runtime.env`` into a dict. Missing file → ``{}``.

    Deliberately a tiny ``KEY=VALUE`` reader (no shell, no exec): the file is
    operator-authored config, and 3-Eyes must never *run* it. Blank lines and
    ``#`` comments are ignored; surrounding quotes on the value are stripped.
    """
    path = _runtime_env_path()
    out: dict[str, str] = {}
    try:
        raw = path.read_text()
    except OSError:
        return out
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            out[key] = value
    return out


def _enable_value() -> str | None:
    """Resolve the enable flag: process env wins, else the runtime.env file."""
    if ENABLE_VAR in os.environ:
        return os.environ[ENABLE_VAR].strip()
    return load_runtime_env().get(ENABLE_VAR)


def kill_switch_engaged() -> bool:
    """True when a hard override forces the gate closed (global halt)."""
    if os.environ.get(ENABLE_VAR, "").strip() == "0":
        return True
    return panic_file().exists()


def three_eyes_active() -> bool:
    """The one gate. True only when 3-Eyes is genuinely opted-in and not halted.

    Requires a runtime.env file to exist AND the enable flag to be ``1``. Any hard
    override (``THREE_EYES_ENABLE=0`` or a PANIC file) forces False.
    """
    if kill_switch_engaged():
        return False
    if not _runtime_env_path().exists():
        return False
    return _enable_value() == "1"


def classify_stubbed() -> bool:
    """True when the classifier is stubbed for tests/dry-runs (no real ollama)."""
    return os.environ.get(CLASSIFY_STUB_VAR, "").strip() not in ("", "0")


def require_active(action: str) -> bool:
    """Guard helper for egress paths. Returns True iff the action may proceed.

    A stubbed classify counts as "may proceed" only for the classifier itself;
    every other egress path (gh, git push, launchd mutation) requires the real
    gate. Callers pass a human-readable ``action`` for logging.
    """
    return three_eyes_active()


def config_value(key: str, default: str | None = None) -> str | None:
    """Read a config value: process env first, then runtime.env, then default."""
    if key in os.environ:
        return os.environ[key]
    return load_runtime_env().get(key, default)
