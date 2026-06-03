"""Tests for the reconciled health verdict (src/rebalance/health.py).

Focus: the single-verdict computation and the suppression layer — especially
that a stale auth:* WARN self-clears when the underlying collector synced
recently (the deauth-recovery mitigation), so dashboards stop contradicting.
"""

import unittest
from datetime import datetime, timedelta, timezone

from rebalance.doctor import FAIL, OK, WARN, Check
from rebalance.health import compute_health_status, ordered_problem_checks

NOW = datetime(2026, 6, 3, 12, 0, 0, tzinfo=timezone.utc)


def _github_status(scanned_ago_hours: float | None):
    """Index-status snapshot with a github activity timestamp N hours ago."""
    if scanned_ago_hours is None:
        return {"sources": {}}
    ts = (NOW - timedelta(hours=scanned_ago_hours)).isoformat()
    return {"sources": {"github": {"activity_last_scanned_at": ts}}}


class VerdictTests(unittest.TestCase):
    def test_ok_when_no_problems(self) -> None:
        checks = [Check("github token", OK, "fine")]
        self.assertEqual(compute_health_status(checks, {"sources": {}}, NOW).verdict, OK)

    def test_warn_when_only_warnings(self) -> None:
        checks = [Check("sleuth", WARN, "no env file")]
        h = compute_health_status(checks, {"sources": {}}, NOW)
        self.assertEqual(h.verdict, WARN)
        self.assertEqual(h.status_text, "1 warning")

    def test_fail_dominates(self) -> None:
        checks = [Check("sleuth", WARN, "x"), Check("database", FAIL, "missing")]
        h = compute_health_status(checks, {"sources": {}}, NOW)
        self.assertEqual(h.verdict, FAIL)
        self.assertEqual(h.status_text, "1 error")

    def test_ordering_fail_first_launchd_last(self) -> None:
        checks = [
            Check("launchd:github-sync", WARN, "exited 1"),
            Check("sleuth", WARN, "x"),
            Check("database", FAIL, "missing"),
        ]
        ordered = ordered_problem_checks(checks, {"sources": {}}, NOW)
        self.assertEqual(ordered[0].name, "database")        # FAIL first
        self.assertEqual(ordered[-1].name, "launchd:github-sync")  # launchd last


class AuthRecoverySuppressionTests(unittest.TestCase):
    """auth:github WARN clears when github data synced recently (mitigation)."""

    def test_auth_github_suppressed_when_github_fresh(self) -> None:
        checks = [Check("auth:github", WARN, "last auth event was a failure — auth_failed")]
        # github scanned 1h ago → independent evidence auth works now → suppress.
        h = compute_health_status(checks, _github_status(1), NOW)
        self.assertEqual(h.verdict, OK)
        self.assertEqual(h.count, 0)

    def test_auth_github_kept_when_github_stale(self) -> None:
        checks = [Check("auth:github", WARN, "auth_failed")]
        # github last scanned 72h ago (> 48h window) → not recovered → keep WARN.
        h = compute_health_status(checks, _github_status(72), NOW)
        self.assertEqual(h.verdict, WARN)
        self.assertEqual(h.count, 1)

    def test_auth_github_kept_when_no_github_activity(self) -> None:
        checks = [Check("auth:github", WARN, "auth_failed")]
        h = compute_health_status(checks, _github_status(None), NOW)
        self.assertEqual(h.verdict, WARN)

    def test_fail_auth_never_suppressed(self) -> None:
        # Suppression only applies to WARN; a FAIL always shows.
        checks = [Check("auth:github", FAIL, "auth_failed")]
        h = compute_health_status(checks, _github_status(1), NOW)
        self.assertEqual(h.verdict, FAIL)


class CredentialSuppressionTests(unittest.TestCase):
    def test_gmail_credential_warn_suppressed_when_email_fresh(self) -> None:
        checks = [Check("gmail", WARN, "ADC missing")]
        ts = (NOW - timedelta(hours=10)).isoformat()
        status = {"sources": {"email": {"last_synced_at": ts}}}
        self.assertEqual(compute_health_status(checks, status, NOW).verdict, OK)

    def test_gmail_credential_warn_kept_when_email_stale(self) -> None:
        checks = [Check("gmail", WARN, "ADC missing")]
        ts = (NOW - timedelta(hours=200)).isoformat()  # > 168h
        status = {"sources": {"email": {"last_synced_at": ts}}}
        self.assertEqual(compute_health_status(checks, status, NOW).verdict, WARN)


if __name__ == "__main__":
    unittest.main()
