"""Centralized secret-file storage with enforced permissions and atomic writes.

Phase 1 of the auth / API-key storage hardening plan
(``PROJECT/2-WORKING/AUTH-AND-API-KEY-STORAGE-HARDENING.md``).

This module owns the *durable local fallback* secret store: the on-disk files
used when the OS keyring is unavailable (e.g. launchd's stripped environment).
Keyring stays the interactive primary store; this module is the single,
permission-enforced root that replaces the repo-local plaintext
(``temp/rbos.config``) and pickle fallbacks.

It is deliberately a thin *file primitive*: it does not reach into keyring,
``config.py``, or any integration. The per-integration loaders
(GitHub / Figma / Sleuth / OAuth) call these helpers in later Phase-1/Phase-2
steps so that every secret file is written atomically at ``0600`` under a
``0700`` directory, with one structured status contract for diagnostics.

Canonical secret root (Phase 0 decision): ``<USER_CONFIG_DIR>/secrets``
(default ``~/.config/rebalance-os/secrets``). Chosen over ``~/secrets`` because
``USER_CONFIG_DIR`` is already the app-owned, launchd-resolvable root that
``paths.resolve_oauth_token_path`` uses; keeping one root avoids a second
permission surface. The legacy ``~/secrets`` env-file path stays readable for
migration via ``paths.resolve_secrets_dir`` until Phase 5 decommissions it.
"""

from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path

from rebalance import paths

# --- seams ------------------------------------------------------------------
# Env override for the secret-store root, so unattended jobs and tests can
# redirect it without touching the operator's real ~/.config tree. Mirrors the
# REBALANCE_* seam convention used by config.py.
SECRET_STORE_DIR_ENV_VAR = "REBALANCE_SECRET_STORE_DIR"

# In-process module override (mirrors config.CONFIG_PATH) for test seams.
SECRET_STORE_DIR: Path | None = None

# Enforced modes — the whole point of the module.
FILE_MODE = 0o600
DIR_MODE = 0o700


def secret_store_root() -> Path:
    """Return the canonical secret-store root directory.

    Resolution order:
      1. ``SECRET_STORE_DIR`` module override (in-process test seam)
      2. ``REBALANCE_SECRET_STORE_DIR`` env var (unattended / test redirect)
      3. ``<USER_CONFIG_DIR>/secrets`` (default ``~/.config/rebalance-os/secrets``)
    """
    if SECRET_STORE_DIR is not None:
        return SECRET_STORE_DIR
    env = os.environ.get(SECRET_STORE_DIR_ENV_VAR)
    if env:
        return Path(env).expanduser()
    return paths.USER_CONFIG_DIR / "secrets"


# --- permission enforcement -------------------------------------------------

def _mode_of(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def harden_mode(path: Path, mode: int) -> bool:
    """``chmod`` *path* to *mode* if it isn't already. Returns True if changed.

    Best-effort: a chmod failure (e.g. an FS that ignores modes) is swallowed.
    Callers that must *assert* posture read :func:`permission_ok` instead.
    """
    try:
        if _mode_of(path) != mode:
            path.chmod(mode)
            return True
    except OSError:
        pass
    return False


def ensure_dir(path: Path) -> Path:
    """Create *path* (and parents) if missing and force it to ``0700``."""
    path.mkdir(parents=True, exist_ok=True)
    harden_mode(path, DIR_MODE)
    return path


def permission_ok(path: Path) -> bool:
    """True if *path* exists and grants no access beyond the enforced mode.

    A directory is checked against ``0700`` and a file against ``0600``: any
    group/other bit (or stray owner-execute on a file) makes it not-ok.
    """
    try:
        mode = _mode_of(path)
    except OSError:
        return False
    enforced = DIR_MODE if path.is_dir() else FILE_MODE
    return (mode & ~enforced) == 0


# --- atomic, permission-enforced writes/reads -------------------------------

def write_secret_file(name: str, data: str) -> Path:
    """Atomically write *data* to ``<root>/<name>`` at ``0600`` under a ``0700`` root.

    The payload is written to a sibling ``.tmp`` that is *created* with ``0600``
    (no world-readable window), fsync'd, then ``os.replace``'d into place — so a
    crash never leaves a half-written or wrongly-moded secret. The destination
    mode is re-hardened after the replace as belt-and-suspenders.
    """
    root = ensure_dir(secret_store_root())
    dest = root / name
    tmp = dest.with_name(dest.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, FILE_MODE)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    os.replace(tmp, dest)
    harden_mode(dest, FILE_MODE)
    return dest


def write_secret_json(name: str, obj) -> Path:
    """Atomically write *obj* as pretty JSON to ``<root>/<name>``."""
    return write_secret_file(name, json.dumps(obj, indent=2))


def read_secret_file(name: str) -> str | None:
    """Read ``<root>/<name>``; return its text, or None if absent/unreadable.

    Never raises — a missing or corrupt fallback is a normal, recoverable state
    (keyring is the primary), and callers branch on None.
    """
    try:
        return (secret_store_root() / name).read_text(encoding="utf-8")
    except OSError:
        return None


def read_secret_json(name: str):
    """Read and JSON-decode ``<root>/<name>``; return the object or None."""
    raw = read_secret_file(name)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return None


def delete_secret_file(name: str) -> bool:
    """Delete ``<root>/<name>`` if present. Returns True if a file was removed."""
    try:
        (secret_store_root() / name).unlink()
        return True
    except OSError:
        return False


def secret_path(name: str) -> Path:
    """Return the resolved path for *name* without touching the filesystem."""
    return secret_store_root() / name


# --- source labeling / resolver status --------------------------------------

@dataclass(frozen=True)
class ResolverStatus:
    """The structured per-integration resolver contract from the plan's Target State.

    Every auth/API-key resolver reports these six fields so doctor can show
    *posture*, not just presence. Phase 1 wires the auth integrations to emit
    this; Phase 4 extends the same shape to API keys.
    """

    source: str | None             # live value origin: "keyring" | "secret-store" | "config" | "env" | "gh-cli" | None
    primary_store: str             # intended primary store, e.g. "keyring"
    fallback_store: str            # durable fallback store, e.g. "secret-store"
    launchd_safe: bool             # can an unattended (no-shell) job read it?
    last_validated_at: str | None  # ISO-8601 of last successful validation, or None
    permission_ok: bool            # fallback file/dir modes are 0600/0700 (True when N/A)

    def as_dict(self) -> dict:
        """Flat dict for doctor / JSON diagnostics output."""
        return {
            "source": self.source,
            "primary_store": self.primary_store,
            "fallback_store": self.fallback_store,
            "launchd_safe": self.launchd_safe,
            "last_validated_at": self.last_validated_at,
            "permission_ok": self.permission_ok,
        }
