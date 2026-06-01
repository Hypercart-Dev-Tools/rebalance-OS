"""Unit tests for RepairFSM — no git, no network."""

import pytest

from rebalance.repair import RepairFSM, RepairResult, RepairState, RepairStatus, is_unrecoverable


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ok() -> RepairResult:
    return RepairResult(ok=True)

def _fail(error: str = "transient failure") -> RepairResult:
    return RepairResult(ok=False, error=error)

def _make_fsm(actions: dict, *, preferred: str | None = None, api_key: str | None = None, max_det: int = 2, max_haiku: int = 1) -> RepairFSM:
    return RepairFSM(
        actions=actions,
        action_descriptions={k: k for k in actions},
        preferred_action=preferred,
        error_context="test context",
        max_deterministic_attempts=max_det,
        max_haiku_attempts=max_haiku,
        haiku_api_key=api_key,
    )


# ---------------------------------------------------------------------------
# is_unrecoverable
# ---------------------------------------------------------------------------

class TestIsUnrecoverable:
    def test_auth_failure(self) -> None:
        assert is_unrecoverable("fatal: Authentication failed for 'https://...'")

    def test_permission_denied(self) -> None:
        assert is_unrecoverable("Permission denied (publickey)")

    def test_transient_rejection_is_recoverable(self) -> None:
        assert not is_unrecoverable("! [rejected] main -> main (fetch first)")

    def test_empty_string(self) -> None:
        assert not is_unrecoverable("")


# ---------------------------------------------------------------------------
# Deterministic repair
# ---------------------------------------------------------------------------

class TestDeterministicRepair:
    def test_succeeds_first_attempt(self) -> None:
        fsm = _make_fsm({"fix": _ok})
        state = fsm.run("some push error")
        assert state.status == RepairStatus.REPAIRED
        assert state.attempts == 1
        assert state.haiku_attempts == 0

    def test_succeeds_second_attempt(self) -> None:
        calls = [0]
        def flaky() -> RepairResult:
            calls[0] += 1
            return _ok() if calls[0] >= 2 else _fail()

        fsm = _make_fsm({"flaky": flaky}, max_det=2)
        state = fsm.run("initial error")
        assert state.status == RepairStatus.REPAIRED
        assert state.attempts == 2

    def test_dead_after_max_attempts_no_haiku(self) -> None:
        fsm = _make_fsm({"fix": lambda: _fail("still broken")}, max_det=2, api_key=None)
        state = fsm.run("push rejected")
        assert state.status == RepairStatus.DEAD
        assert state.attempts == 2
        assert "no ANTHROPIC_API_KEY" in " ".join(state.log)

    def test_unrecoverable_initial_error_skips_immediately(self) -> None:
        called = [False]
        def should_not_be_called() -> RepairResult:
            called[0] = True
            return _ok()

        fsm = _make_fsm({"fix": should_not_be_called})
        state = fsm.run("Authentication failed for https://github.com/")
        assert state.status == RepairStatus.DEAD
        assert state.attempts == 0
        assert not called[0]
        assert "circuit-breaker" in " ".join(state.log)

    def test_unrecoverable_mid_repair_stops(self) -> None:
        fsm = _make_fsm({"fix": lambda: _fail("Permission denied (publickey)")}, max_det=2)
        state = fsm.run("push rejected")
        assert state.status == RepairStatus.DEAD
        assert state.attempts == 1  # stopped after first attempt hit unrecoverable

    def test_unknown_preferred_action_goes_dead(self) -> None:
        fsm = _make_fsm({"fix": _ok}, preferred="nonexistent")
        state = fsm.run("push rejected")
        assert state.status == RepairStatus.DEAD
        assert state.attempts == 0


# ---------------------------------------------------------------------------
# Haiku escalation
# ---------------------------------------------------------------------------

class TestHaikuEscalation:
    def test_haiku_called_after_deterministic_exhaustion(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "rebalance.repair.RepairFSM._haiku_triage",
            lambda self, state: "secondary",
        )
        fsm = _make_fsm(
            {"primary": lambda: _fail("failed"), "secondary": _ok},
            preferred="primary",
            api_key="test-key",
        )
        state = fsm.run("push rejected")
        assert state.status == RepairStatus.REPAIRED
        assert state.haiku_attempts == 1
        assert RepairStatus.ESCALATED.value in " ".join(state.log) or \
               any("escalating" in line for line in state.log)

    def test_haiku_invalid_action_goes_dead(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "rebalance.repair.RepairFSM._haiku_triage",
            lambda self, state: "completely_unknown_action",
        )
        fsm = _make_fsm({"fix": lambda: _fail()}, api_key="test-key")
        state = fsm.run("push rejected")
        assert state.status == RepairStatus.DEAD
        assert any("invalid" in line or "unknown" in line for line in state.log)

    def test_haiku_none_response_goes_dead(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "rebalance.repair.RepairFSM._haiku_triage",
            lambda self, state: None,
        )
        fsm = _make_fsm({"fix": lambda: _fail()}, api_key="test-key")
        state = fsm.run("push rejected")
        assert state.status == RepairStatus.DEAD

    def test_haiku_action_also_fails_goes_dead(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "rebalance.repair.RepairFSM._haiku_triage",
            lambda self, state: "fix",
        )
        fsm = _make_fsm({"fix": lambda: _fail("still broken after haiku")}, api_key="test-key")
        state = fsm.run("push rejected")
        assert state.status == RepairStatus.DEAD
        assert state.haiku_attempts == 1

    def test_skipped_when_no_api_key(self) -> None:
        fsm = _make_fsm({"fix": lambda: _fail()}, api_key=None)
        state = fsm.run("push rejected")
        assert state.status == RepairStatus.DEAD
        assert state.haiku_attempts == 0
        assert any("ANTHROPIC_API_KEY" in line for line in state.log)

    def test_haiku_capped_at_max_attempts(self, monkeypatch) -> None:
        calls = [0]
        def triage(self, state):  # noqa: ARG001
            calls[0] += 1
            return "fix"

        monkeypatch.setattr("rebalance.repair.RepairFSM._haiku_triage", triage)
        fsm = _make_fsm({"fix": lambda: _fail()}, api_key="test-key", max_haiku=1)
        state = fsm.run("push rejected")
        assert calls[0] == 1  # called exactly once regardless of outcome


# ---------------------------------------------------------------------------
# RepairState
# ---------------------------------------------------------------------------

class TestRepairState:
    def test_as_dict_shape(self) -> None:
        state = RepairState(
            status=RepairStatus.DEAD,
            attempts=2,
            haiku_attempts=1,
            log=["a", "b"],
            final_error="boom",
        )
        d = state.as_dict()
        assert d["status"] == "dead"
        assert d["attempts"] == 2
        assert d["haiku_attempts"] == 1
        assert d["log"] == ["a", "b"]
        assert d["final_error"] == "boom"
