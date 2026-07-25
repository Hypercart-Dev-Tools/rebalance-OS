"""Regression coverage for GH-201: `resolve_database_path()` must not silently
fall back to the canonical DB when an explicit `--database` path is given and
doesn't exist.

Before this fix, an explicit path was just candidate #1 in an ordered list
with the canonical DB appended unconditionally as a later candidate; the
resolution loop returned the first candidate that *existed*, regardless of
source. So `--database /nonexistent/path.db` silently fell through to the
canonical DB instead of raising — masking typos.
"""

from __future__ import annotations

import pytest

from rebalance import paths as paths_module
from rebalance.paths import (
    DatabaseNotFoundError,
    ExplicitDatabasePathNotFoundError,
    resolve_database_path,
)


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch):
    """Keep every test's resolution chain independent of the real machine.

    - Clears REBALANCE_DB so a developer's/CI's real env var can't leak in.
    - Points the user-level config file at a nonexistent tmp path so
      `_load_user_config()` returns `{}` (no `database_path` candidate).
    """
    monkeypatch.delenv("REBALANCE_DB", raising=False)
    monkeypatch.setattr(paths_module, "USER_CONFIG_FILE", paths_module.USER_CONFIG_FILE.with_name("does-not-exist.json"))


def test_explicit_valid_database_path_is_honored(tmp_path):
    """(a) An explicit --database path that exists is returned as-is."""
    db_file = tmp_path / "mydb.db"
    db_file.write_bytes(b"")

    resolved = resolve_database_path(db_file)

    assert resolved == db_file.resolve()


def test_explicit_nonexistent_database_path_raises(tmp_path, monkeypatch):
    """(b) An explicit --database path that does NOT exist raises instead of
    silently falling back to the canonical DB (the GH-201 bug)."""
    missing = tmp_path / "typo-path" / "rebalance.db"

    # Make the canonical DB resolvable too, so a passing test here proves the
    # resolver deliberately refused the fallback — not that it merely had
    # nothing else to fall back to.
    canonical_dir = tmp_path / "canonical"
    canonical_dir.mkdir()
    canonical_db = canonical_dir / "rebalance.db"
    canonical_db.write_bytes(b"")
    monkeypatch.setattr(paths_module, "canonical_database_path", lambda: canonical_db)

    with pytest.raises(ExplicitDatabasePathNotFoundError) as exc_info:
        resolve_database_path(missing)

    # It's a DatabaseNotFoundError subclass, so existing `except
    # DatabaseNotFoundError` call sites across the CLI still catch it.
    assert isinstance(exc_info.value, DatabaseNotFoundError)
    assert str(missing.resolve()) in str(exc_info.value)


def test_no_database_given_falls_back_to_canonical(tmp_path, monkeypatch):
    """(c) With no explicit path (and no env var), resolution still falls
    back to the canonical DB when it exists."""
    canonical_dir = tmp_path / "canonical"
    canonical_dir.mkdir()
    canonical_db = canonical_dir / "rebalance.db"
    canonical_db.write_bytes(b"")
    monkeypatch.setattr(paths_module, "canonical_database_path", lambda: canonical_db)

    resolved = resolve_database_path(None)

    assert resolved == canonical_db.resolve()


def test_no_database_given_and_nothing_resolvable_raises_generic_error(tmp_path, monkeypatch):
    """No explicit path, and no layer resolves anything: the generic
    DatabaseNotFoundError (not the explicit-path variant) is raised."""
    canonical_dir = tmp_path / "canonical-missing"
    canonical_db = canonical_dir / "rebalance.db"  # never created
    monkeypatch.setattr(paths_module, "canonical_database_path", lambda: canonical_db)
    # Force the project-root walk-up to find nothing either, so this test
    # doesn't depend on whether a rebalance.db happens to sit next to the
    # repo's own .git / pyproject.toml.
    monkeypatch.setattr(paths_module, "_walk_up_for_project_root", lambda *a, **k: None)

    with pytest.raises(DatabaseNotFoundError) as exc_info:
        resolve_database_path(None)

    assert not isinstance(exc_info.value, ExplicitDatabasePathNotFoundError)
