"""Tests for src/rebalance/paths.py — resolve_database_path and helpers.

GH-201: explicit --database pointing at a nonexistent path must raise
DatabaseNotFoundError immediately rather than silently falling back to
the canonical DB or any other layer.
"""

import os

import pytest

from rebalance import paths
from rebalance.paths import DatabaseNotFoundError, resolve_database_path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _no_walk_up(start=None):
    """Patch target: always reports no project root, so tests never accidentally
    find a real rebalance.db by walking up to the repo root."""
    return None


# ---------------------------------------------------------------------------
# GH-201: explicit path behaviour
# ---------------------------------------------------------------------------

class TestExplicitPath:
    def test_explicit_nonexistent_raises_immediately(self, tmp_path, monkeypatch):
        """An explicit --database path that doesn't exist must raise, not fall back."""
        monkeypatch.delenv("REBALANCE_DB", raising=False)
        monkeypatch.setattr(paths, "_walk_up_for_project_root", _no_walk_up)
        nonexistent = tmp_path / "does_not_exist.db"

        with pytest.raises(DatabaseNotFoundError) as exc_info:
            resolve_database_path(nonexistent)

        err = exc_info.value
        # Only the explicit candidate should appear — no canonical fallback.
        assert len(err.candidates) == 1
        label = err.candidates[0][1]
        assert "--database flag" in label

    def test_explicit_nonexistent_does_not_fall_through_to_canonical(self, tmp_path, monkeypatch):
        """Regression for GH-201: canonical DB must NOT be returned when explicit is wrong."""
        canonical_dir = tmp_path / "canonical"
        canonical_dir.mkdir()
        fake_canonical = canonical_dir / "rebalance.db"
        fake_canonical.write_bytes(b"")  # canonical exists

        monkeypatch.delenv("REBALANCE_DB", raising=False)
        monkeypatch.setattr(paths, "canonical_database_path", lambda: fake_canonical)
        monkeypatch.setattr(paths, "_walk_up_for_project_root", _no_walk_up)

        bad_explicit = tmp_path / "wrong.db"  # does not exist

        with pytest.raises(DatabaseNotFoundError):
            resolve_database_path(bad_explicit)

    def test_explicit_existing_returns_it(self, tmp_path, monkeypatch):
        """An explicit path that exists must be returned without consulting other layers."""
        monkeypatch.delenv("REBALANCE_DB", raising=False)
        monkeypatch.setattr(paths, "_walk_up_for_project_root", _no_walk_up)

        db = tmp_path / "my.db"
        db.write_bytes(b"")

        result = resolve_database_path(db)

        assert result == db.resolve()

    def test_explicit_existing_ignores_env_var(self, tmp_path, monkeypatch):
        """When explicit is provided and exists, REBALANCE_DB must not override it."""
        other_db = tmp_path / "env.db"
        other_db.write_bytes(b"")
        monkeypatch.setenv("REBALANCE_DB", str(other_db))
        monkeypatch.setattr(paths, "_walk_up_for_project_root", _no_walk_up)

        target_db = tmp_path / "explicit.db"
        target_db.write_bytes(b"")

        result = resolve_database_path(target_db)

        assert result == target_db.resolve()


# ---------------------------------------------------------------------------
# Fallback chain (no explicit)
# ---------------------------------------------------------------------------

class TestFallbackChain:
    def test_env_var_wins_over_canonical(self, tmp_path, monkeypatch):
        env_db = tmp_path / "env.db"
        env_db.write_bytes(b"")
        monkeypatch.setenv("REBALANCE_DB", str(env_db))
        monkeypatch.setattr(paths, "_walk_up_for_project_root", _no_walk_up)
        monkeypatch.setattr(paths, "USER_CONFIG_FILE", tmp_path / "no-config.json")
        monkeypatch.setattr(paths, "USER_CONFIG_DIR", tmp_path / "no-config-dir")

        # canonical does NOT exist
        monkeypatch.setattr(paths, "canonical_database_path", lambda: tmp_path / "canonical.db")

        result = resolve_database_path()

        assert result == env_db.resolve()

    def test_canonical_returned_when_it_exists(self, tmp_path, monkeypatch):
        monkeypatch.delenv("REBALANCE_DB", raising=False)
        monkeypatch.setattr(paths, "_walk_up_for_project_root", _no_walk_up)
        monkeypatch.setattr(paths, "USER_CONFIG_FILE", tmp_path / "no-config.json")
        monkeypatch.setattr(paths, "USER_CONFIG_DIR", tmp_path / "no-config-dir")

        canonical = tmp_path / "canonical.db"
        canonical.write_bytes(b"")
        monkeypatch.setattr(paths, "canonical_database_path", lambda: canonical)

        result = resolve_database_path()

        assert result == canonical.resolve()

    def test_user_config_db_used_when_canonical_absent(self, tmp_path, monkeypatch):
        monkeypatch.delenv("REBALANCE_DB", raising=False)
        monkeypatch.setattr(paths, "_walk_up_for_project_root", _no_walk_up)

        cfg_dir = tmp_path / "config"
        cfg_dir.mkdir()
        cfg_file = cfg_dir / "config.json"
        user_db = tmp_path / "user.db"
        user_db.write_bytes(b"")
        cfg_file.write_text(f'{{"database_path": "{user_db}"}}')

        monkeypatch.setattr(paths, "USER_CONFIG_DIR", cfg_dir)
        monkeypatch.setattr(paths, "USER_CONFIG_FILE", cfg_file)
        monkeypatch.setattr(paths, "canonical_database_path", lambda: tmp_path / "canonical.db")

        result = resolve_database_path()

        assert result == user_db.resolve()

    def test_walk_up_db_used_as_last_resort(self, tmp_path, monkeypatch):
        monkeypatch.delenv("REBALANCE_DB", raising=False)
        monkeypatch.setattr(paths, "USER_CONFIG_FILE", tmp_path / "no-config.json")
        monkeypatch.setattr(paths, "USER_CONFIG_DIR", tmp_path / "no-config-dir")
        monkeypatch.setattr(paths, "canonical_database_path", lambda: tmp_path / "canonical.db")

        project_root = tmp_path / "project"
        project_root.mkdir()
        project_db = project_root / "rebalance.db"
        project_db.write_bytes(b"")
        monkeypatch.setattr(paths, "_walk_up_for_project_root", lambda start=None: project_root)

        result = resolve_database_path()

        assert result == project_db.resolve()

    def test_no_db_anywhere_raises(self, tmp_path, monkeypatch):
        monkeypatch.delenv("REBALANCE_DB", raising=False)
        monkeypatch.setattr(paths, "_walk_up_for_project_root", _no_walk_up)
        monkeypatch.setattr(paths, "USER_CONFIG_FILE", tmp_path / "no-config.json")
        monkeypatch.setattr(paths, "USER_CONFIG_DIR", tmp_path / "no-config-dir")
        monkeypatch.setattr(paths, "canonical_database_path", lambda: tmp_path / "canonical.db")

        with pytest.raises(DatabaseNotFoundError) as exc_info:
            resolve_database_path()

        # Should list at least the canonical candidate in the error
        msg = str(exc_info.value)
        assert "Could not resolve rebalance.db" in msg
        assert "canonical" in msg


# ---------------------------------------------------------------------------
# DatabaseNotFoundError structure
# ---------------------------------------------------------------------------

class TestDatabaseNotFoundError:
    def test_candidates_stored(self, tmp_path):
        candidates = [(tmp_path / "a.db", "source A"), (tmp_path / "b.db", "source B")]
        err = DatabaseNotFoundError(candidates)
        assert err.candidates is candidates

    def test_message_lists_paths(self, tmp_path):
        db = tmp_path / "missing.db"
        err = DatabaseNotFoundError([(db, "test source")])
        assert str(db) in str(err)
        assert "test source" in str(err)

    def test_is_file_not_found_error(self, tmp_path):
        err = DatabaseNotFoundError([(tmp_path / "x.db", "s")])
        assert isinstance(err, FileNotFoundError)
