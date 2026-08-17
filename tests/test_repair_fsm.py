"""Unit tests for RepairFSM — no git, no network."""

import unittest
from unittest.mock import patch

from rebalance.repair import RepairFSM, RepairResult, RepairState, RepairStatus, is_unrecoverable


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ok() -> RepairResult:
    return RepairResult(ok=True)

def _fail(error: str = "transient failure") -> RepairResult:
    return RepairResult(ok=False, error=error)

def _make_fsm(actions: dict, *, preferred: str | None = None, api_key: str | None = None, max_det: int = 2, max_llm: int = 1) -> RepairFSM:
    # Hermetic: RepairFSM.__init__ does `llm_api_key or get_gemini_api_key()`, so
    # a bare api_key=None would otherwise resolve an AMBIENT machine key (env /
    # key file / gcloud). These are "no network" unit tests — pin the resolver to
    # None during construction so api_key=None genuinely means "no key".
    with patch("rebalance.repair.get_gemini_api_key", return_value=None):
        return RepairFSM(
            actions=actions,
            action_descriptions={k: k for k in actions},
            preferred_action=preferred,
            error_context="test context",
            max_deterministic_attempts=max_det,
            max_llm_attempts=max_llm,
            llm_api_key=api_key,
        )


# ---------------------------------------------------------------------------
# is_unrecoverable
# ---------------------------------------------------------------------------

class TestIsUnrecoverable(unittest.TestCase):
    def test_auth_failure(self) -> None:
        self.assertTrue(is_unrecoverable("fatal: Authentication failed for 'https://...'"))

    def test_permission_denied(self) -> None:
        self.assertTrue(is_unrecoverable("Permission denied (publickey)"))

    def test_transient_rejection_is_recoverable(self) -> None:
        self.assertFalse(is_unrecoverable("! [rejected] main -> main (fetch first)"))

    def test_empty_string(self) -> None:
        self.assertFalse(is_unrecoverable(""))


# ---------------------------------------------------------------------------
# Deterministic repair
# ---------------------------------------------------------------------------

class TestDeterministicRepair(unittest.TestCase):
    def test_succeeds_first_attempt(self) -> None:
        fsm = _make_fsm({"fix": _ok})
        state = fsm.run("some push error")
        self.assertEqual(state.status, RepairStatus.REPAIRED)
        self.assertEqual(state.attempts, 1)
        self.assertEqual(state.llm_attempts, 0)

    def test_succeeds_second_attempt(self) -> None:
        calls = [0]
        def flaky() -> RepairResult:
            calls[0] += 1
            return _ok() if calls[0] >= 2 else _fail()

        fsm = _make_fsm({"flaky": flaky}, max_det=2)
        state = fsm.run("initial error")
        self.assertEqual(state.status, RepairStatus.REPAIRED)
        self.assertEqual(state.attempts, 2)

    def test_dead_after_max_attempts_no_llm(self) -> None:
        fsm = _make_fsm({"fix": lambda: _fail("still broken")}, max_det=2, api_key=None)
        state = fsm.run("push rejected")
        self.assertEqual(state.status, RepairStatus.DEAD)
        self.assertEqual(state.attempts, 2)
        self.assertIn("GEMINI_API_KEY", " ".join(state.log))

    def test_unrecoverable_initial_error_skips_immediately(self) -> None:
        called = [False]
        def should_not_be_called() -> RepairResult:
            called[0] = True
            return _ok()

        fsm = _make_fsm({"fix": should_not_be_called})
        state = fsm.run("Authentication failed for https://github.com/")
        self.assertEqual(state.status, RepairStatus.DEAD)
        self.assertEqual(state.attempts, 0)
        self.assertFalse(called[0])
        self.assertIn("circuit-breaker", " ".join(state.log))

    def test_unrecoverable_mid_repair_stops(self) -> None:
        fsm = _make_fsm({"fix": lambda: _fail("Permission denied (publickey)")}, max_det=2)
        state = fsm.run("push rejected")
        self.assertEqual(state.status, RepairStatus.DEAD)
        self.assertEqual(state.attempts, 1)

    def test_unknown_preferred_action_goes_dead(self) -> None:
        fsm = _make_fsm({"fix": _ok}, preferred="nonexistent")
        state = fsm.run("push rejected")
        self.assertEqual(state.status, RepairStatus.DEAD)
        self.assertEqual(state.attempts, 0)


# ---------------------------------------------------------------------------
# Haiku escalation
# ---------------------------------------------------------------------------

class TestLLMEscalation(unittest.TestCase):
    def test_llm_called_after_deterministic_exhaustion(self) -> None:
        with patch.object(RepairFSM, "_llm_triage", return_value="secondary"):
            fsm = _make_fsm(
                {"primary": lambda: _fail("failed"), "secondary": _ok},
                preferred="primary",
                api_key="test-key",
            )
            state = fsm.run("push rejected")
        self.assertEqual(state.status, RepairStatus.REPAIRED)
        self.assertEqual(state.llm_attempts, 1)
        self.assertTrue(any("escalating" in line for line in state.log))

    def test_llm_invalid_action_goes_dead(self) -> None:
        with patch.object(RepairFSM, "_llm_triage", return_value="completely_unknown_action"):
            fsm = _make_fsm({"fix": lambda: _fail()}, api_key="test-key")
            state = fsm.run("push rejected")
        self.assertEqual(state.status, RepairStatus.DEAD)
        self.assertTrue(any("invalid" in line or "unknown" in line for line in state.log))

    def test_llm_none_response_goes_dead(self) -> None:
        with patch.object(RepairFSM, "_llm_triage", return_value=None):
            fsm = _make_fsm({"fix": lambda: _fail()}, api_key="test-key")
            state = fsm.run("push rejected")
        self.assertEqual(state.status, RepairStatus.DEAD)

    def test_llm_action_also_fails_goes_dead(self) -> None:
        with patch.object(RepairFSM, "_llm_triage", return_value="fix"):
            fsm = _make_fsm({"fix": lambda: _fail("still broken after llm")}, api_key="test-key")
            state = fsm.run("push rejected")
        self.assertEqual(state.status, RepairStatus.DEAD)
        self.assertEqual(state.llm_attempts, 1)

    def test_skipped_when_no_api_key(self) -> None:
        fsm = _make_fsm({"fix": lambda: _fail()}, api_key=None)
        state = fsm.run("push rejected")
        self.assertEqual(state.status, RepairStatus.DEAD)
        self.assertEqual(state.llm_attempts, 0)
        self.assertTrue(any("GEMINI_API_KEY" in line for line in state.log))

    def test_llm_capped_at_max_attempts(self) -> None:
        calls = [0]
        def triage(self_inner, state):  # noqa: ARG001
            calls[0] += 1
            return "fix"

        with patch.object(RepairFSM, "_llm_triage", triage):
            fsm = _make_fsm({"fix": lambda: _fail()}, api_key="test-key", max_llm=1)
            fsm.run("push rejected")
        self.assertEqual(calls[0], 1)


# ---------------------------------------------------------------------------
# RepairState
# ---------------------------------------------------------------------------

class TestRepairState(unittest.TestCase):
    def test_as_dict_shape(self) -> None:
        state = RepairState(
            status=RepairStatus.DEAD,
            attempts=2,
            llm_attempts=1,
            log=["a", "b"],
            final_error="boom",
        )
        d = state.as_dict()
        self.assertEqual(d["status"], "dead")
        self.assertEqual(d["attempts"], 2)
        self.assertEqual(d["llm_attempts"], 1)
        self.assertEqual(d["log"], ["a", "b"])
        self.assertEqual(d["final_error"], "boom")


if __name__ == "__main__":
    unittest.main()
