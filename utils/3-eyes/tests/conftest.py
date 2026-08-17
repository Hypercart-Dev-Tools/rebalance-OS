"""Shared fixtures for the 3-Eyes suite (GH-195).

Puts the package dir (utils/3-eyes) on sys.path so ``from three_eyes import ...``
works whether the suite is run standalone (``pytest utils/3-eyes/tests``) or as
part of the repo run (``pytest tests/ utils/3-eyes/tests``). Every test gets an
isolated, tmp state dir and a guaranteed-absent runtime.env so 3-Eyes starts
INERT unless the test opts in.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_PKG_PARENT = Path(__file__).resolve().parent.parent   # utils/3-eyes
if str(_PKG_PARENT) not in sys.path:
    sys.path.insert(0, str(_PKG_PARENT))


@pytest.fixture(autouse=True)
def _isolated_state(tmp_path, monkeypatch):
    """Isolate mutable state + force an inert starting point for every test."""
    monkeypatch.setenv("THREE_EYES_STATE_DIR", str(tmp_path / "state"))
    # Point runtime.env at a path that does not exist -> inert by default.
    monkeypatch.setenv("THREE_EYES_RUNTIME_ENV", str(tmp_path / "no-runtime.env"))
    # Clear any inherited enable flag from the developer's shell.
    monkeypatch.delenv("THREE_EYES_ENABLE", raising=False)
    monkeypatch.delenv("THREE_EYES_CLASSIFY_STUB", raising=False)
    yield


def _activate(monkeypatch, tmp_path):
    """Helper: write a runtime.env and enable 3-Eyes for a test."""
    env = tmp_path / "runtime.env"
    env.write_text("THREE_EYES_ENABLE=1\n")
    monkeypatch.setenv("THREE_EYES_RUNTIME_ENV", str(env))
    return env


@pytest.fixture
def activate(monkeypatch, tmp_path):
    def _do():
        return _activate(monkeypatch, tmp_path)
    return _do
