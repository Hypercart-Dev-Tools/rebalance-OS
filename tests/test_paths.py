"""Tests for resolve_database_path() — GH-201 explicit-path-must-exist contract."""

import pytest

from rebalance import paths
from rebalance.paths import DatabaseNotFoundError, resolve_database_path


class TestExplicitPath:
    """GH-201: explicit --database path is never silently bypassed."""

    def test_explicit_existing_returned(self, tmp_path):
        db = tmp_path / "rebalance.db"
        db.touch()
        assert resolve_database_path(explicit=db) == db.resolve()

    def test_explicit_missing_raises(self, tmp_path):
        with pytest.raises(DatabaseNotFoundError):
            resolve_database_path(explicit=tmp_path / "nope.db")

    def test_explicit_missing_error_names_flag(self, tmp_path):
        with pytest.raises(DatabaseNotFoundError) as exc_info:
            resolve_database_path(explicit=tmp_path / "nope.db")
        assert "--database flag" in str(exc_info.value)

    def test_explicit_missing_does_not_fall_back_to_canonical(self, tmp_path, monkeypatch):
        """Canonical DB present but explicit missing → must raise, not silently resolve canonical."""
        canonical = tmp_path / "canonical.db"
        canonical.touch()
        monkeypatch.setattr(paths, "canonical_database_path", lambda: canonical)
        with pytest.raises(DatabaseNotFoundError):
            resolve_database_path(explicit=tmp_path / "nope.db")

    def test_explicit_missing_candidates_list_is_explicit_only(self, tmp_path):
        missing = tmp_path / "nope.db"
        with pytest.raises(DatabaseNotFoundError) as exc_info:
            resolve_database_path(explicit=missing)
        cands = exc_info.value.candidates
        assert len(cands) == 1
        assert cands[0][1] == "--database flag"
        assert cands[0][0] == missing.resolve()


class TestFallbackChain:
    """Without explicit arg, the layered fallback chain still works."""

    def test_env_var_wins(self, tmp_path, monkeypatch):
        db = tmp_path / "rebalance.db"
        db.touch()
        monkeypatch.setenv("REBALANCE_DB", str(db))
        assert resolve_database_path() == db.resolve()

    def test_canonical_wins_when_env_absent(self, tmp_path, monkeypatch):
        canonical = tmp_path / "rebalance.db"
        canonical.touch()
        monkeypatch.delenv("REBALANCE_DB", raising=False)
        monkeypatch.setattr(paths, "canonical_database_path", lambda: canonical)
        monkeypatch.setattr(paths, "USER_CONFIG_FILE", tmp_path / "config.json")
        monkeypatch.setattr(paths, "USER_CONFIG_DIR", tmp_path)
        monkeypatch.setattr(paths, "_walk_up_for_project_root", lambda start=None: None)
        assert resolve_database_path() == canonical.resolve()

    def test_no_db_anywhere_raises(self, tmp_path, monkeypatch):
        monkeypatch.delenv("REBALANCE_DB", raising=False)
        monkeypatch.setattr(paths, "canonical_database_path", lambda: tmp_path / "nonexistent.db")
        monkeypatch.setattr(paths, "USER_CONFIG_FILE", tmp_path / "config.json")
        monkeypatch.setattr(paths, "USER_CONFIG_DIR", tmp_path)
        monkeypatch.setattr(paths, "_walk_up_for_project_root", lambda start=None: None)
        with pytest.raises(DatabaseNotFoundError):
            resolve_database_path()
