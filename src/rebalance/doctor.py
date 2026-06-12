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
    """Flag a token that background launchd jobs cannot reach.

    launchd has a stripped environment: gh-cli auth and env vars are unavailable.
    A token in keyring or rbos.config is reachable; gh-cli-only is not.
    set_github_token() now writes to both, so keyring-sourced tokens are fine
    as long as a config copy also exists.
    """
    from rebalance.ingest.config import get_github_token_with_source, _read_config

    token, source = get_github_token_with_source()
    if not token:
        return Check(
            "github token",
            FAIL,
            "no GitHub token configured",
            "run `rebalance config set-github-token`, or `rebalance onboard`",
        )
    if source == "gh-cli":
        return Check(
            "github token",
            WARN,
            "token only reachable via gh-cli — launchd jobs will fail",
            "run `rebalance config set-github-token` to persist it",
        )
    # keyring is preferred for interactive reads; confirm config copy also exists
    # so launchd can fall back if keychain is unavailable in its session
    config_has_token = bool(_read_config().get("github_token"))
    if source == "keyring" and not config_has_token:
        return Check(
            "github token",
            WARN,
            "token in keyring only — launchd session may not reach keychain",
            "run `rebalance config set-github-token` to write the config fallback",
        )
    detail = f"stored in {source} + config (reachable by launchd)"
    # Sidecar lifetime: how long has THIS token value been in use? Surfaces a
    # short-lived PAT (dies every few days) vs a durable one.
    try:
        from rebalance.ingest import token_meta
        meta = token_meta.current_token_meta("github")
        if meta and meta.get("first_added_at"):
            age = token_meta.age_text(meta["first_added_at"])
            kind = meta.get("kind") or "?"
            detail += f" · this token first added {age} ago ({kind})"
    except Exception:  # noqa: BLE001 — doctor must never crash
        pass
    return Check("github token", OK, detail)


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


def _check_unpushed_work() -> Check:
    """Ongoing Phase 6.1 signal: local checkouts with commits that never
    reached the remote (ahead of upstream, or no upstream at all). Off — and
    silent OK — unless local_repo_roots is configured."""
    from rebalance.ingest.config import get_local_repo_roots
    from rebalance.ingest.local_repos import scan_local_repos, unpushed_work

    roots = get_local_repo_roots()
    if not roots:
        return Check(
            "local repos", OK,
            "local scanning off (set local_repo_roots to enable unpushed-work checks)",
        )
    repos = scan_local_repos(roots)
    stale = unpushed_work(repos)
    if not stale:
        return Check("local repos", OK, f"{len(repos)} checkout(s) scanned — all pushed")
    detail = "; ".join(
        f"{r.full_name or r.path.name}: "
        + (f"{r.unpushed_commits} unpushed on {r.branch}" if r.unpushed_commits else f"no upstream for {r.branch}")
        for r in stale[:5]
    )
    if len(stale) > 5:
        detail += f"; +{len(stale) - 5} more"
    return Check(
        "local repos", WARN,
        f"{len(stale)}/{len(repos)} checkout(s) carry unpushed work — {detail}",
        "push the branches (or set their upstreams); discovery offers these repos for promotion",
    )


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



def _check_collector_freshness(
    db_path: Path,
    *,
    name: str,
    table: str,
    ts_col: str,
    warn_days: int,
    empty_hint: str,
    stale_hint: str,
) -> Check:
    """Generic data-freshness check for any collector table.

    Warns when the most recent *ts_col* value is older than *warn_days* days,
    or when the table is empty.  Used for Sleuth, Calendar, and Email — the
    collectors that previously had credential checks but no freshness checks.
    """
    from rebalance.ingest.db import db_connection

    try:
        with db_connection(db_path) as conn:
            has_table = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone()
            if not has_table:
                return Check(name, WARN, f"{table} table not present")
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]  # noqa: S608
            latest = conn.execute(
                f"SELECT MAX({ts_col}) FROM {table}"  # noqa: S608
            ).fetchone()[0]
    except Exception as exc:  # noqa: BLE001
        return Check(name, FAIL, f"could not read {table}: {exc}")

    if count == 0:
        return Check(name, WARN, f"no {name} data ingested", empty_hint)

    if latest:
        try:
            age_days = (
                datetime.now(timezone.utc).date()
                - datetime.fromisoformat(str(latest)).date()
            ).days
            if age_days > warn_days:
                return Check(
                    name, WARN,
                    f"{count} rows, last sync {age_days} days ago (stale > {warn_days}d)",
                    stale_hint,
                )
        except (TypeError, ValueError):
            pass

    return Check(name, OK, f"{count} rows, last sync {latest}")


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


# A file-source export should refresh ~hourly (publisher heartbeat). Allow a few
# missed beats before flagging a likely-dead publisher (or a stalled local sync).
_SLEUTH_HEARTBEAT_STALE_HOURS = 3


def _check_sleuth(db_path: Path | None = None) -> Check:
    """Sleuth/Slack reminders — credentials resolved keyring → config → env file,
    plus a published-file freshness check via the publisher heartbeat."""
    from rebalance.ingest.config import SLEUTH_KEYRING_KEY, _keyring_get, get_sleuth_credentials

    try:
        get_sleuth_credentials()
    except FileNotFoundError:
        return Check(
            "sleuth", WARN,
            "no Sleuth Web API credentials configured",
            "run `rebalance config set-sleuth` (keyring + launchd-reachable config), "
            "or create the sleuth-web-api env file — without it the Slack-reminders "
            "sync fails every run",
        )
    except ValueError as exc:
        return Check(
            "sleuth", WARN, str(exc),
            "set all of SLEUTH_WEB_API_BASE_URL / SLEUTH_WEB_API_TOKEN / SLEUTH_WORKSPACE_NAME",
        )
    except Exception as exc:  # noqa: BLE001 — doctor must never crash
        return Check("sleuth", FAIL, f"could not resolve Sleuth credentials: {exc}")
    where = "keyring" if _keyring_get(SLEUTH_KEYRING_KEY) else "config/env file"

    # Published-file freshness: compare the publisher's own heartbeat
    # (`export_generated_at`) — NOT our local last_synced_at, which we bump on every
    # reread even when the upstream export is dead — against now.
    if db_path is not None:
        try:
            from datetime import datetime, timezone

            from rebalance.ingest.sleuth_reminders import get_export_generated_at

            beat = get_export_generated_at(db_path)
        except Exception:  # noqa: BLE001 — never let the freshness probe crash doctor
            beat = None
        if beat is not None:
            age_h = (datetime.now(timezone.utc) - beat).total_seconds() / 3600
            stamp = beat.isoformat()
            if age_h > _SLEUTH_HEARTBEAT_STALE_HOURS:
                return Check(
                    "sleuth", WARN,
                    f"published export is stale — heartbeat {stamp} ({age_h:.1f}h ago)",
                    "the Sleuth publisher (sleuth-reminders-export.timer on the box) or the "
                    "local export clone may be stuck; check the timer and `git -C ~/git-pulse-sync pull`",
                )
            return Check("sleuth", OK, f"configured (via {where}) · export {age_h:.1f}h old")
    return Check("sleuth", OK, f"configured (via {where})")


def _check_gmail(db_path: Path | None) -> Check:
    """Gmail ingest — desktop OAuth (``oauth`` mode) or the Gmail MCP connector (``mcp`` mode)."""
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

    # oauth mode — desktop OAuth token, resolved keyring → pickle file
    # (mirrors _check_calendar).
    try:
        from rebalance.ingest.gmail import TOKEN_PATH
        from rebalance.ingest.config import get_gmail_oauth_token_json
    except Exception as exc:  # noqa: BLE001 — doctor must never crash
        return Check("gmail", WARN, f"gmail module unavailable: {exc}")

    in_keyring = bool(get_gmail_oauth_token_json())
    if not in_keyring and not TOKEN_PATH.exists():
        return Check(
            "gmail", WARN,
            "no Gmail OAuth credentials (keyring empty, no token file)",
            "🔧 run the Gmail OAuth flow (scripts/setup_gmail_oauth.py), then "
            "`rebalance config migrate-to-keyring` — or switch to MCP mode "
            "(`rebalance config set-gmail-method mcp`)",
        )
    where = "keyring" if in_keyring else "token file"
    return Check("gmail", OK, f"OAuth token present (via {where})")


def _check_calendar() -> Check:
    """Google Calendar OAuth — resolved keyring → pickle file."""
    try:
        from rebalance.ingest.calendar import TOKEN_PATH
        from rebalance.ingest.config import get_calendar_oauth_token_json
    except Exception as exc:  # noqa: BLE001
        return Check("calendar", WARN, f"calendar module unavailable: {exc}")

    in_keyring = bool(get_calendar_oauth_token_json())
    if not in_keyring and not TOKEN_PATH.exists():
        return Check(
            "calendar", WARN,
            "no Calendar OAuth credentials (keyring empty, no token file)",
            "🔧 run the Calendar OAuth flow (scripts/setup_calendar_oauth.py)",
        )
    where = "keyring" if in_keyring else "token file"
    detail = f"OAuth token present (via {where})"
    try:
        from rebalance.ingest import token_meta
        meta = token_meta.current_token_meta("calendar")
        if meta and meta.get("first_added_at"):
            detail += f" · authorized {token_meta.age_text(meta['first_added_at'])} ago"
    except Exception:  # noqa: BLE001
        pass
    return Check("calendar", OK, detail)


_AUTH_FAIL_HINT = {
    "github": "PAT revoked, expired, or lost a scope — run "
              "`rebalance config set-github-token` with a fresh token",
    "calendar": "re-run the Calendar OAuth flow "
                "(scripts/setup_calendar_oauth.py)",
    "gmail": "re-run the Gmail OAuth flow (scripts/setup_gmail_oauth.py) then "
             "`rebalance config migrate-to-keyring`, or switch to MCP mode "
             "(`rebalance config set-gmail-method mcp`)",
}


def _check_auth_failures() -> list[Check]:
    """Surface the last auth failure per integration from the unified auth log.

    Reads ``ingest/auth_log`` (``temp/logs/auth_activity.jsonl``). A source
    whose *most recent* event is a failure is in an active failed-auth state
    and gets a WARN; a later success means it recovered, so it is not flagged.
    When there is auth history and nothing is currently failing, emit a single
    positive check so "no recent deauth" is visible rather than merely absent.
    """
    try:
        from rebalance.ingest import auth_log
    except Exception:  # noqa: BLE001 — doctor must never crash
        return []

    try:
        latest = auth_log.latest_event_by_source()
    except Exception:  # noqa: BLE001
        return []

    if not latest:
        return []  # no auth events recorded yet — nothing to surface

    checks: list[Check] = []
    for source in sorted(latest):
        entry = latest[source]
        if entry.get("event") not in auth_log.FAILURE_EVENTS:
            continue
        event = entry.get("event", "")
        ts = str(entry.get("ts", ""))[:19].replace("T", " ")
        device = entry.get("device", "")
        where = f" on {device}" if device else ""
        checks.append(
            Check(
                f"auth:{source}",
                WARN,
                f"last auth event was a failure — {event} at {ts} UTC{where}",
                _AUTH_FAIL_HINT.get(source, "re-authenticate this integration"),
            )
        )

    if not checks:
        return [Check("auth log", OK, "no active auth failures across collectors")]
    return checks


def _check_pulse_collectors() -> list[Check]:
    """Surface git-pulse per-device collector health (ALIVE/STALE/ALERT/DEGRADED).

    Reads the structured per-device YAML via ``ingest/pulse_health`` so a
    *broken* collector (degraded/stale scan) shows up in ``rebalance doctor``
    next to a *de-authorized* one. Returns ``[]`` when git-pulse is not
    configured — no noise on installs that don't run it.
    """
    try:
        from rebalance.ingest import pulse_health

        devices = pulse_health.read_collector_health()
    except Exception:  # noqa: BLE001 — doctor must never crash
        return []

    checks: list[Check] = []
    for health in devices:
        if health.age_hours is None:
            age = "never pushed"
        elif health.age_hours >= 24:
            age = f"last scan {health.age_hours / 24:.1f}d ago"
        else:
            age = f"last scan {health.age_hours:.1f}h ago"
        detail = f"{health.state} — {age}"
        if health.repo_scan_failures:
            detail += f", {health.repo_scan_failures} repo scan failures"
            if health.scan_failure_examples:
                detail += f" ({health.scan_failure_examples})"
        checks.append(
            Check(
                f"pulse collector:{health.device_name}",
                OK if health.healthy else WARN,
                detail,
                "" if health.healthy else
                "check the collector machine / its launchd git-pulse job; "
                "`python experimental/git-pulse/health-check.py` for the full view",
            )
        )
    return checks


def _diagnostics_index() -> list[Check]:
    """Map every observability surface so ``rebalance doctor`` is the single
    place that points at all of them.

    Diagnostics in this project are deliberately spread across purpose-built
    tools (live auth trail, git-pulse collector health, per-repo probes, the
    issue-filing reporter). Rather than fragilely importing each — git-pulse
    in particular lives behind a not-yet-importable ``experimental/`` path
    until its Phase 9 promotion — doctor enumerates where each one lives and
    how to reach it. All entries are informational (OK); the actionable health
    checks above are what gate exit status.
    """
    checks: list[Check] = []

    # Auth-event trail (this module's sibling) — live count + how to view it.
    try:
        from rebalance.ingest import auth_log

        sources = sorted(auth_log.latest_event_by_source().keys())
        n = len(auth_log.read_log(limit=2000))
        where = f"{n} events across {', '.join(sources)}" if sources else "no events yet"
        checks.append(Check(
            "diagnostics: auth log", OK,
            f"{where} · temp/logs/auth_activity.jsonl · web: `rebalance serve` → /auth-log",
        ))
    except Exception:  # noqa: BLE001 — doctor must never crash
        pass

    checks.append(Check(
        "diagnostics: git-pulse", OK,
        "per-device collector health now shown inline above (`pulse collector:*`); "
        "`python experimental/git-pulse/health-check.py` for the full cross-machine "
        "table. Full module migration tracked in Phase 9.",
    ))
    checks.append(Check(
        "diagnostics: repo probes", OK,
        "live PAT/repo visibility & commit existence: the `diagnose_repo` MCP tool",
    ))
    checks.append(Check(
        "diagnostics: health reporter", OK,
        "launchd issue-filer (runs this doctor + git-pulse, opens GitHub issues): "
        "temp/health-reporter.log.jsonl",
    ))
    return checks


def _check_pulse() -> Check:
    """Pulse publish config — warn when the hourly publisher cannot run."""
    from rebalance.ingest.config import get_pulse_config

    cfg = get_pulse_config()
    required = ("github_login", "pulse_target_path")
    missing = [key for key in required if not str(cfg.get(key) or "").strip()]
    if missing:
        return Check(
            "pulse",
            WARN,
            f"pulse config missing keys: {', '.join(missing)}",
            "set the missing pulse config values in temp/rbos.config so hourly "
            "pulse-sync can render and push",
        )
    target = Path(str(cfg.get("pulse_target_path"))).expanduser()
    if not target.exists():
        return Check(
            "pulse",
            WARN,
            f"pulse_target_path does not exist: {target}",
            "point pulse_target_path at a local clone of the destination git repo",
        )
    if not (target / ".git").exists():
        return Check(
            "pulse",
            WARN,
            f"pulse_target_path is not a git repo: {target}",
            "point pulse_target_path at the root of the destination git repo",
        )
    return Check("pulse", OK, f"configured ({target})")


# ---------------------------------------------------------------------------
# Collector freshness registry
#
# To add a new collector: append one entry.  No other code needs to change.
# Fields: name (Check label), table, ts_col (MAX'd for age), warn_days,
#         empty_hint, stale_hint.
# ---------------------------------------------------------------------------

_COLLECTOR_FRESHNESS: list[dict] = [
    dict(
        name="github data",
        table="github_activity",
        ts_col="scan_date",
        warn_days=2,
        empty_hint=(
            "run `rebalance refresh` (scope github) — check that projects are "
            "registered and the token is in config"
        ),
        stale_hint="run `rebalance refresh` (scope github)",
    ),
    dict(
        name="sleuth data",
        table="sleuth_reminders",
        ts_col="last_synced_at",
        warn_days=2,
        empty_hint="run the Sleuth sync job or check Sleuth credentials",
        stale_hint="run `rebalance refresh` (scope sleuth) — check the launchd sync job",
    ),
    dict(
        name="calendar data",
        table="calendar_events",
        ts_col="fetched_at",
        warn_days=3,
        empty_hint="run the calendar sync or complete the OAuth flow",
        stale_hint="run `rebalance refresh` (scope calendar) — check the launchd sync job",
    ),
    dict(
        name="email data",
        table="email_messages",
        ts_col="received_at",
        warn_days=7,
        empty_hint="ingest email via the Gmail MCP connector or the OAuth sync (scripts/setup_gmail_oauth.py)",
        stale_hint="no new email ingested in 7+ days — ask Claude to call `ingest_gmail_messages` (MCP mode), or check the Gmail OAuth token (`rebalance doctor`)",
    ),
]


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
    report.checks.append(_check_unpushed_work())

    if db_path is not None:
        report.checks.append(_check_schema(db_path))
        report.checks.append(_check_projects(db_path))
        for collector in _COLLECTOR_FRESHNESS:
            report.checks.append(_check_collector_freshness(db_path, **collector))

    # Integration credentials — Sleuth/Slack, Gmail, Google Calendar.
    report.checks.append(_check_sleuth(db_path))
    report.checks.append(_check_gmail(db_path))
    report.checks.append(_check_calendar())
    report.checks.append(_check_pulse())

    # Auth-event log — last deauth/auth failure per integration (calendar,
    # github, gmail), read from the unified temp/logs/auth_activity.jsonl.
    report.checks.extend(_check_auth_failures())

    # git-pulse per-device collector health — a *broken* collector (stale or
    # degraded scan) shown right next to a de-authorized one.
    report.checks.extend(_check_pulse_collectors())

    report.checks.extend(_check_launchd())

    # Final section: a map of every diagnostics surface, so this one command
    # is the single entry point into the project's observability.
    report.checks.extend(_diagnostics_index())
    return report
