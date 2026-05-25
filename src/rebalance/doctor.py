"""Health check for a rebalance install — backs ``rebalance doctor``.

Inspects the live configuration and environment for the class of problem a
unit test cannot catch: which database is actually in use, whether the GitHub
token is reachable by background (launchd) jobs, schema version, registered
projects, GitHub data freshness, the credentials for each external integration
(Sleuth/Slack, Gmail, Google Calendar), and scheduled-job exit status.

``run_doctor()`` returns a structured :class:`DoctorReport`; the CLI renders it.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

OK = "ok"
WARN = "warn"
FAIL = "fail"


@dataclass
class Check:
    """One health check result."""

    name: str
    status: str  # OK | WARN | FAIL
    detail: str
    hint: str = ""


@dataclass
class DoctorReport:
    checks: list[Check] = field(default_factory=list)

    @property
    def failed(self) -> bool:
        return any(c.status == FAIL for c in self.checks)

    @property
    def warned(self) -> bool:
        return any(c.status == WARN for c in self.checks)


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


def _check_database(explicit: Path | None) -> tuple[list[Check], Path | None]:
    """Resolve the active DB and flag any path split (the resolved DB not at
    the canonical location, or REBALANCE_DB pointing somewhere else)."""
    from rebalance.paths import (
        DatabaseNotFoundError,
        canonical_database_path,
        resolve_database_path,
    )

    checks: list[Check] = []
    canonical = canonical_database_path().resolve()
    try:
        resolved = resolve_database_path(explicit).resolve()
    except DatabaseNotFoundError:
        checks.append(
            Check(
                "database",
                FAIL,
                "no rebalance.db could be resolved",
                "run `rebalance onboard`, or `rebalance refresh`, to create one",
            )
        )
        return checks, None

    exists = resolved.exists()
    size = resolved.stat().st_size if exists else 0
    checks.append(
        Check(
            "database",
            OK if exists else FAIL,
            f"{resolved}" + (f" ({size // 1024} KB)" if exists else " — MISSING"),
        )
    )

    if resolved != canonical:
        checks.append(
            Check(
                "database location",
                WARN,
                f"active DB is not the canonical path\n  canonical: {canonical}",
                "run `python -m rebalance.paths --migrate` to consolidate",
            )
        )

    env_db = os.environ.get("REBALANCE_DB")
    if env_db:
        env_resolved = Path(env_db).expanduser().resolve()
        if env_resolved != resolved:
            checks.append(
                Check(
                    "database split",
                    WARN,
                    f"REBALANCE_DB env points elsewhere than the resolved DB\n"
                    f"  REBALANCE_DB: {env_resolved}\n  resolved:     {resolved}",
                    "background jobs and the shell will read different databases — "
                    "align REBALANCE_DB with the canonical path",
                )
            )
    return checks, (resolved if exists else None)


def _check_token() -> Check:
    """Flag a token that background launchd jobs cannot reach."""
    from rebalance.ingest.config import get_github_token_with_source

    token, source = get_github_token_with_source()
    if not token:
        return Check(
            "github token",
            FAIL,
            "no GitHub token configured",
            "run `rebalance config set-github-token`, or `rebalance onboard`",
        )
    if source != "config":
        return Check(
            "github token",
            WARN,
            f"token resolves via '{source}', not the rebalance config",
            "launchd jobs run with a minimal environment and cannot reach "
            "`gh`/env vars — run `rebalance config set-github-token` to persist it",
        )
    return Check("github token", OK, "stored in config (reachable by launchd jobs)")


def _check_vault() -> Check:
    from rebalance.ingest.config import get_vault_path

    vault = get_vault_path()
    if not vault:
        return Check(
            "vault", WARN, "no vault path configured",
            "run `rebalance config set-vault-path`",
        )
    if not Path(vault).expanduser().exists():
        return Check(
            "vault", FAIL, f"configured vault path does not exist: {vault}",
            "fix the path with `rebalance config set-vault-path`",
        )
    return Check("vault", OK, str(vault))


def _check_schema(db_path: Path) -> Check:
    from rebalance.ingest.db import current_schema_version, db_connection

    try:
        with db_connection(db_path) as conn:
            has_table = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_version'"
            ).fetchone()
            if not has_table:
                return Check(
                    "schema", WARN, "schema_version table not present",
                    "run `rebalance refresh` once — migrations stamp the version",
                )
            return Check("schema", OK, f"version {current_schema_version(conn)}")
    except Exception as exc:  # noqa: BLE001 — doctor must never crash
        return Check("schema", FAIL, f"could not read schema: {exc}")


def _check_projects(db_path: Path) -> Check:
    from rebalance.ingest.db import db_connection

    try:
        with db_connection(db_path) as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table' "
                "AND name='project_registry'"
            ).fetchone()
            if not row or not row[0]:
                return Check("projects", WARN, "project_registry table not present")
            count = conn.execute("SELECT COUNT(*) FROM project_registry").fetchone()[0]
    except Exception as exc:  # noqa: BLE001
        return Check("projects", FAIL, f"could not read project_registry: {exc}")

    if count == 0:
        return Check(
            "projects", WARN, "no projects registered",
            "run `rebalance onboard` to discover and register projects",
        )
    return Check("projects", OK, f"{count} registered")


def _check_github_data(db_path: Path) -> Check:
    from rebalance.ingest.db import db_connection

    try:
        with db_connection(db_path) as conn:
            has_table = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='github_activity'"
            ).fetchone()
            if not has_table:
                return Check("github data", WARN, "github_activity table not present")
            count = conn.execute("SELECT COUNT(*) FROM github_activity").fetchone()[0]
            latest = conn.execute("SELECT MAX(scan_date) FROM github_activity").fetchone()[0]
    except Exception as exc:  # noqa: BLE001
        return Check("github data", FAIL, f"could not read github_activity: {exc}")

    if count == 0:
        return Check(
            "github data", WARN, "no GitHub activity ingested",
            "run `rebalance refresh` (scope github) — check that projects are "
            "registered and the token is in config",
        )
    stale = ""
    if latest:
        try:
            age_days = (datetime.now(timezone.utc).date()
                        - datetime.fromisoformat(latest).date()).days
            if age_days > 2:
                stale = f" — last scan {age_days} days ago (stale)"
        except (TypeError, ValueError):
            pass
    status = WARN if stale else OK
    return Check("github data", status, f"{count} activity rows, latest {latest}{stale}")


def _check_launchd() -> list[Check]:
    """Report rebalance launchd jobs and their last exit status (macOS only)."""
    try:
        out = subprocess.run(
            ["launchctl", "list"], capture_output=True, text=True, timeout=10
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return []  # not macOS / launchctl unavailable — silently skip

    checks: list[Check] = []
    for line in out.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) != 3 or "rebalance" not in parts[2]:
            continue
        pid, status, label = parts
        short = label.replace("com.rebalance-os.", "").replace("com.user.", "")
        if status.strip() not in ("0", "-"):
            checks.append(
                Check(
                    f"launchd:{short}", WARN,
                    f"last run exited with status {status.strip()}",
                    "inspect temp/logs/ for this job's error output",
                )
            )
        else:
            running = "running" if pid.strip() != "-" else "idle, last run ok"
            checks.append(Check(f"launchd:{short}", OK, running))
    return checks


# ---------------------------------------------------------------------------
# Integration credential checks
#
# These verify that each external integration's credentials are *present and
# well-formed* — the class of "improper config" that otherwise fails silently
# inside a launchd sync. They are deliberately offline: presence, not liveness.
# ---------------------------------------------------------------------------


def _check_sleuth() -> Check:
    """Sleuth/Slack reminders — the operator-owned Sleuth Web API env file."""
    from rebalance.paths import resolve_secret_path

    primary = resolve_secret_path("sleuth-web-api-production.env")
    fallback = resolve_secret_path("sleuth-web-api-development.env")
    path = primary if primary.exists() else (fallback if fallback.exists() else None)
    if path is None:
        return Check(
            "sleuth", WARN,
            f"no Sleuth Web API env file ({primary})",
            "create it with SLEUTH_WEB_API_BASE_URL / SLEUTH_WEB_API_TOKEN / "
            "SLEUTH_WORKSPACE_NAME — without it the Slack-reminders sync fails every run",
        )
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return Check("sleuth", FAIL, f"cannot read {path}: {exc}")
    present = {
        line.split("=", 1)[0].strip()
        for line in text.splitlines()
        if "=" in line and not line.strip().startswith("#")
    }
    required = {"SLEUTH_WEB_API_BASE_URL", "SLEUTH_WEB_API_TOKEN", "SLEUTH_WORKSPACE_NAME"}
    missing = required - present
    if missing:
        return Check(
            "sleuth", WARN,
            f"{path.name} is missing keys: {', '.join(sorted(missing))}",
            "add the missing keys to the Sleuth env file",
        )
    return Check("sleuth", OK, f"configured ({path.name})")


def _check_gmail(db_path: Path | None) -> Check:
    """Gmail ingest — ADC (``oauth`` mode) or the Gmail MCP connector (``mcp`` mode)."""
    from rebalance.ingest.config import get_gmail_ingest_method

    if get_gmail_ingest_method() == "mcp":
        # MCP mode — credentials live in the agent's Gmail connector, not here.
        # Report how much email has actually been ingested instead.
        if db_path is not None:
            try:
                from rebalance.ingest.db import db_connection

                with db_connection(db_path) as conn:
                    has_table = conn.execute(
                        "SELECT 1 FROM sqlite_master WHERE type='table' "
                        "AND name='email_messages'"
                    ).fetchone()
                    count = (
                        conn.execute("SELECT COUNT(*) FROM email_messages").fetchone()[0]
                        if has_table
                        else 0
                    )
            except Exception as exc:  # noqa: BLE001
                return Check("gmail", WARN, f"MCP mode — could not read email_messages: {exc}")
            if count == 0:
                return Check(
                    "gmail", WARN, "MCP mode — no email ingested yet",
                    "have an agent fetch via the Gmail MCP connector and call "
                    "`ingest_gmail_messages`",
                )
            return Check("gmail", OK, f"MCP mode — {count} messages ingested")
        return Check("gmail", OK, "MCP mode — email ingested via the Gmail MCP connector")

    # oauth mode — Google Application Default Credentials.
    try:
        from rebalance.ingest.gmail import GmailAuthError, _load_adc_credentials
    except Exception as exc:  # noqa: BLE001 — doctor must never crash
        return Check("gmail", WARN, f"gmail module unavailable: {exc}")
    try:
        _load_adc_credentials()
    except GmailAuthError as exc:
        return Check(
            "gmail", WARN, str(exc).splitlines()[0],
            "run `gcloud auth application-default login` with the Gmail readonly "
            "scope, or switch to MCP mode (`gmail_ingest_method=mcp`)",
        )
    except Exception as exc:  # noqa: BLE001
        return Check("gmail", WARN, f"could not load ADC: {exc}")
    return Check("gmail", OK, "Application Default Credentials present")


def _check_calendar() -> Check:
    """Google Calendar — the OAuth token file."""
    try:
        from rebalance.ingest.calendar import TOKEN_PATH
    except Exception as exc:  # noqa: BLE001
        return Check("calendar", WARN, f"calendar module unavailable: {exc}")
    if not TOKEN_PATH.exists():
        return Check(
            "calendar", WARN,
            f"OAuth token not found at {TOKEN_PATH}",
            "run the Calendar OAuth flow (scripts/setup_calendar_oauth.py)",
        )
    return Check("calendar", OK, f"OAuth token present ({TOKEN_PATH})")


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def run_doctor(database_path: Path | None = None) -> DoctorReport:
    """Run every health check and return a structured report.

    *database_path* overrides DB resolution (useful for tests); omit it to use
    the normal resolver chain.
    """
    report = DoctorReport()

    db_checks, db_path = _check_database(database_path)
    report.checks.extend(db_checks)
    report.checks.append(_check_token())
    report.checks.append(_check_vault())

    if db_path is not None:
        report.checks.append(_check_schema(db_path))
        report.checks.append(_check_projects(db_path))
        report.checks.append(_check_github_data(db_path))

    # Integration credentials — Sleuth/Slack, Gmail, Google Calendar.
    report.checks.append(_check_sleuth())
    report.checks.append(_check_gmail(db_path))
    report.checks.append(_check_calendar())

    report.checks.extend(_check_launchd())
    return report
