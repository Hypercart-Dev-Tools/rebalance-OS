"""Reconciled collector-health verdict — one source of truth for the dashboards.

`doctor.run_doctor()` produces raw per-check results. This module reconciles
them against recent collector activity and collapses them into a single
`HealthStatus`, so every surface (web pulse, TUI, …) renders a *consistent*
verdict instead of three independently-computed pills that can contradict each
other.

Two reconciliations, both "a recent success is evidence the problem cleared":

* **Credential checks** (`vault` / `calendar` / `gmail` / `sleuth`): a WARN is
  suppressed when that source synced within its stale window.
* **Auth checks** (`auth:github` / `auth:gmail` / `auth:calendar`, emitted by
  ``doctor._check_auth_failures`` from the unified auth log): a WARN is
  suppressed when the *underlying collector* synced recently — independent
  evidence the credential works now, even if no success event was logged after
  the failure. This is what lets a deauth warning self-clear on recovery for
  every install, not just one machine.

Suppression windows MUST track ``doctor.py`` ``warn_days * 24`` for each source;
update both together.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from rebalance.doctor import FAIL, OK, WARN, Check

# Credential-check name → suppression window (hours). Mirrors doctor warn_days*24.
CREDENTIAL_SUPPRESSION_HOURS: dict[str, int] = {
    "vault":    48,   # no freshness check; 2d safe default
    "calendar": 72,   # calendar data warn_days=3
    "gmail":   168,   # email data warn_days=7
    "sleuth":   48,   # sleuth data warn_days=2
}

# auth:* check name → (freshness status key, window hours). A recent successful
# sync of the underlying collector clears a stale auth WARN.
AUTH_RECOVERY: dict[str, tuple[str, int]] = {
    "auth:github":   ("github data", 48),
    "auth:gmail":    ("gmail", 168),
    "auth:calendar": ("calendar", 72),
}


def _parse_iso(raw: Any) -> datetime | None:
    if not raw or not isinstance(raw, str):
        return None
    s = raw.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def status_timestamp(status: dict[str, Any], key: str) -> str | None:
    """Most-recent successful-activity timestamp for a check/source *key*.

    Reads the index-status snapshot's ``sources`` block. Keys match the doctor
    check names that participate in suppression.
    """
    sources = status.get("sources") or {}
    semantic = status.get("semantic_index") or {}
    mapping = {
        "vault": (sources.get("vault") or {}).get("last_ingested_at"),
        "github data": (sources.get("github") or {}).get("activity_last_scanned_at")
        or (sources.get("github") or {}).get("documents_last_fetched_at"),
        "calendar": (sources.get("calendar") or {}).get("last_fetched_at"),
        "sleuth": (sources.get("sleuth") or {}).get("last_synced_at"),
        "gmail": (sources.get("email") or {}).get("last_synced_at"),
        "semantic": semantic.get("last_embedded_at"),
    }
    return mapping.get(key)


def source_recently_succeeded(
    status: dict[str, Any], key: str, now: datetime, *, within_hours: int = 48
) -> bool:
    dt = _parse_iso(status_timestamp(status, key))
    if dt is None:
        return False
    return (now - dt).total_seconds() <= within_hours * 3600


def _is_suppressed(name: str, status: dict[str, Any], now: datetime) -> bool:
    if name in CREDENTIAL_SUPPRESSION_HOURS:
        return source_recently_succeeded(
            status, name, now, within_hours=CREDENTIAL_SUPPRESSION_HOURS[name]
        )
    if name in AUTH_RECOVERY:
        fresh_key, hours = AUTH_RECOVERY[name]
        return source_recently_succeeded(status, fresh_key, now, within_hours=hours)
    return False


def visible_problem_checks(
    checks: list[Check], status: dict[str, Any], now: datetime
) -> list[Check]:
    """WARN/FAIL checks minus those a recent success has cleared."""
    visible: list[Check] = []
    for check in checks:
        if check.status not in {FAIL, WARN}:
            continue
        if check.status == WARN and _is_suppressed(check.name, status, now):
            continue
        visible.append(check)
    return visible


def ordered_problem_checks(
    checks: list[Check], status: dict[str, Any], now: datetime
) -> list[Check]:
    """Visible problems, worst-first (FAIL before WARN; launchd noise last)."""
    def priority(check: Check) -> tuple[int, int, str]:
        severity = 0 if check.status == FAIL else 1
        launchd = 1 if check.name.startswith("launchd:") else 0
        return (severity, launchd, check.name)

    return sorted(visible_problem_checks(checks, status, now), key=priority)


@dataclass
class HealthStatus:
    """The one verdict every dashboard surface renders from."""

    verdict: str  # OK | WARN | FAIL
    problems: list[Check]

    @property
    def failures(self) -> list[Check]:
        return [c for c in self.problems if c.status == FAIL]

    @property
    def warnings(self) -> list[Check]:
        return [c for c in self.problems if c.status == WARN]

    @property
    def count(self) -> int:
        return len(self.problems)

    @property
    def status_text(self) -> str:
        failures = self.failures
        if failures:
            return f"{len(failures)} error{'s' if len(failures) != 1 else ''}"
        warnings = self.warnings
        if warnings:
            return f"{len(warnings)} warning{'s' if len(warnings) != 1 else ''}"
        return "healthy"


def compute_health_status(
    checks: list[Check], status: dict[str, Any], now: datetime
) -> HealthStatus:
    """Reconcile *checks* against recent activity into a single verdict."""
    problems = ordered_problem_checks(checks, status, now)
    if any(c.status == FAIL for c in problems):
        verdict = FAIL
    elif problems:
        verdict = WARN
    else:
        verdict = OK
    return HealthStatus(verdict=verdict, problems=problems)
