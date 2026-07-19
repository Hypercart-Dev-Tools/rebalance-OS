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
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Literal

OK = "ok"
WARN = "warn"
FAIL = "fail"

NOTICE = "notice"
WARNING = "warning"
ERROR = "error"
Severity = Literal["notice", "warning", "error"]


@dataclass
class Check:
    """One health check result."""

    name: str
    status: str  # OK | WARN | FAIL
    detail: str
    hint: str = ""
    severity: Severity = WARNING

    def __post_init__(self) -> None:
        """Keep legacy FAIL emitters in the error bucket and reject typos."""
        if self.severity not in {NOTICE, WARNING, ERROR}:
            raise ValueError(f"invalid check severity: {self.severity}")
        if self.status == FAIL and self.severity == WARNING:
            self.severity = ERROR


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
    A token in keyring or a file fallback (the out-of-repo secret store, or
    legacy rbos.config) is reachable; gh-cli-only is not. Phase 2 made the secret
    store the durable launchd fallback (rbos.config is no longer written).
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
    # keyring is the interactive primary; launchd (stripped env, maybe no
    # keychain) needs a file fallback. Phase 2: the out-of-repo secret store is
    # that fallback (rbos.config is legacy and no longer written).
    from rebalance.ingest import secret_store
    in_secret_store = secret_store.read_secret_file("github_token") is not None
    in_config = bool(_read_config().get("github_token"))
    if source == "keyring" and not (in_secret_store or in_config):
        return Check(
            "github token",
            WARN,
            "token in keyring only — launchd session may not reach keychain",
            "run `rebalance config set-github-token` to write the secret-store fallback",
        )
    locations = []
    if source == "keyring":
        locations.append("keyring")
    if in_secret_store:
        locations.append("secret store")
    if in_config:
        locations.append("config (legacy)")
    detail = f"stored in {' + '.join(locations) or source} (reachable by launchd)"
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


def _secret_permission_check(paths_to_check: list[Path]) -> Check:
    """Verdict for a set of secret paths: WARN if any is broader than 0600/0700.

    Pure over its input so it is hermetically testable. Posture only — a broad
    mode is an exposure, not a broken credential, so this WARNs (it does not FAIL
    and break unattended doctor gating).
    """
    import stat as _stat

    from rebalance.ingest import secret_store

    checked = [p for p in paths_to_check if p.exists()]
    insecure = [p for p in checked if not secret_store.permission_ok(p)]
    if insecure:
        labels = ", ".join(
            f"{p.name}={_stat.S_IMODE(p.stat().st_mode):04o}" for p in insecure
        )
        return Check(
            "secret permissions",
            WARN,
            f"{len(insecure)} of {len(checked)} secret path(s) broader than 0600/0700: {labels}",
            "chmod 600 files / 700 dirs; rebalance writers self-correct on the next write",
        )
    return Check(
        "secret permissions", OK, f"{len(checked)} secret file(s)/dir(s) at 0600/0700"
    )


def _check_secret_permissions() -> Check:
    """Posture check over every known secret file/dir (Phase 1 hardening)."""
    from rebalance import paths
    from rebalance.ingest import config as _config
    from rebalance.ingest import secret_store

    candidates: list[Path] = [
        _config._resolved_config_path(),
        paths.USER_CONFIG_DIR,
        paths.USER_CONFIG_FILE,
        paths.resolve_oauth_token_path("calendar"),
        paths.resolve_oauth_token_path("gmail"),
        secret_store.secret_store_root(),
    ]
    root = secret_store.secret_store_root()
    if root.is_dir():
        candidates.extend(p for p in root.iterdir() if p.is_file())
    return _secret_permission_check(candidates)


def _check_repo_local_secrets() -> Check:
    """Flag any live secret still persisted in repo-local rbos.config (Phase 2)."""
    from rebalance.ingest import config as _config

    try:
        present = _config.repo_local_secret_keys_present()
    except Exception:  # noqa: BLE001 — doctor must never crash
        return Check("repo-local secrets", OK, "could not read rbos.config")
    if present:
        return Check(
            "repo-local secrets",
            WARN,
            f"{len(present)} secret key(s) still in temp/rbos.config: {', '.join(present)}",
            "run `rebalance config migrate-secrets` to lift them into the secret store",
        )
    return Check("repo-local secrets", OK, "temp/rbos.config holds no live secrets")


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
    quality_predicate: str | None = None,
    quality_label: str = "meaningful content",
    quality_table: str | None = None,
    max_invalid_fraction: float = 0.5,
    volume_ts_col: str | None = None,
    quiet_filter: Callable[[], str] | None = None,
) -> Check:
    """Generic data-freshness check for any collector table.

    Warns when the most recent *ts_col* value is older than *warn_days* days,
    or when the table is empty. A declared ``quality_predicate`` is a local,
    declarative SQL assertion about a meaningful row; a majority of failures
    degrades the check even when rows are fresh. ``volume_ts_col`` lets a
    successful filtered collector name an intentionally quiet window.
    """
    from rebalance.ingest.db import db_connection

    try:
        with db_connection(db_path) as conn:
            has_table = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone()
            if not has_table:
                return Check(
                    name, WARN, f"{table} table not present", severity=ERROR
                )
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]  # noqa: S608
            latest = conn.execute(
                f"SELECT MAX({ts_col}) FROM {table}"  # noqa: S608
            ).fetchone()[0]
            invalid_count = 0
            quality_count = 0
            if quality_predicate:
                predicate_table = quality_table or table
                quality_count = conn.execute(
                    f"SELECT COUNT(*) FROM {predicate_table}"  # noqa: S608
                ).fetchone()[0]
                invalid_count = conn.execute(
                    f"SELECT COUNT(*) FROM {predicate_table} "  # noqa: S608
                    f"WHERE NOT ({quality_predicate})"  # noqa: S608
                ).fetchone()[0]
            recent_count = None
            if volume_ts_col:
                recent_count = conn.execute(
                    f"SELECT COUNT(*) FROM {table} "  # noqa: S608
                    f"WHERE julianday({volume_ts_col}) >= julianday('now', ?)",  # noqa: S608
                    (f"-{warn_days} days",),
                ).fetchone()[0]
    except Exception as exc:  # noqa: BLE001
        return Check(name, FAIL, f"could not read {table}: {exc}")

    if count == 0:
        return Check(
            name, WARN, f"no {name} ingested", empty_hint, severity=ERROR
        )

    if quality_count and invalid_count / quality_count > max_invalid_fraction:
        invalid_percent = round(invalid_count / quality_count * 100)
        return Check(
            name,
            WARN,
            f"degraded: {invalid_count}/{quality_count} rows ({invalid_percent}%) lack {quality_label}",
            "check the collector payload before refreshing the semantic index",
        )

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

    detail = f"{count} rows, last sync {latest}"
    if recent_count == 0 and quiet_filter is not None:
        detail += f"; no rows matched in the last {warn_days}d ({quiet_filter()})"
    return Check(name, OK, detail, severity=NOTICE)


def _launchctl_list() -> str | None:
    """Return the live launchd listing, or ``None`` when unavailable."""
    try:
        out = subprocess.run(
            ["launchctl", "list"], capture_output=True, text=True, timeout=10
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return None
    return out.stdout


def _scheduler_policy_jobs(policy_path: Path | None = None) -> list[str]:
    """Read launchd job suffixes from SCHEDULER.md's job policy table.

    The policy document intentionally remains the source of truth.  This is a
    deliberately narrow Markdown parser: it recognizes only the first-column
    backticked job name under the ``Job (label suffix)`` table header.
    """
    if policy_path is None:
        from rebalance.paths import resolve_project_root

        policy_path = resolve_project_root(Path(__file__)) / "SCHEDULER.md"

    lines = policy_path.read_text(encoding="utf-8").splitlines()
    header = "| Job (label suffix) |"
    try:
        start = next(i for i, line in enumerate(lines) if line.startswith(header))
    except StopIteration:
        return []

    jobs: list[str] = []
    for line in lines[start + 2 :]:  # skip the Markdown separator row
        if not line.startswith("|"):
            break
        first_cell = line.split("|", 2)[1].strip()
        match = re.fullmatch(r"`([a-z0-9-]+)`", first_cell)
        if match:
            jobs.append(match.group(1))
    return jobs


def _loaded_rebalance_labels(launchctl_output: str) -> set[str]:
    """Extract ``com.rebalance-os.*`` labels from ``launchctl list`` output."""
    labels: set[str] = set()
    for line in launchctl_output.splitlines():
        fields = line.split()
        if fields and fields[-1].startswith("com.rebalance-os."):
            labels.add(fields[-1])
    return labels


def _scheduler_installer(job: str, repo_root: Path) -> str:
    """Find the installer that declares *job*, with a conventional fallback.

    Installers predate the policy table and some omit ``-sync`` from their
    filename.  Reading their declared label keeps the liveness check
    table-driven while still giving the operator the real installer command.
    """
    label = f"com.rebalance-os.{job}"
    scripts_dir = repo_root / "scripts"
    installers = [
        *scripts_dir.glob("install*_scheduler.sh"),
        scripts_dir / "install_scheduler.sh",  # legacy daily-sync installer
    ]
    for installer in sorted(set(installers)):
        try:
            if label in installer.read_text(encoding="utf-8"):
                return installer.relative_to(repo_root).as_posix()
        except OSError:
            continue
    return f"scripts/install_{job.replace('-', '_')}_scheduler.sh"


def _check_scheduler_liveness(
    policy_path: Path | None = None, launchctl_output: str | None = None
) -> list[Check]:
    """Warn for policy jobs absent from this device's live launchd registry."""
    try:
        if policy_path is None:
            from rebalance.paths import resolve_project_root

            repo_root = resolve_project_root(Path(__file__))
            policy_path = repo_root / "SCHEDULER.md"
        else:
            repo_root = policy_path.parent
        jobs = _scheduler_policy_jobs(policy_path)
    except (OSError, RuntimeError) as exc:
        return [Check("scheduler policy", WARN, f"could not read SCHEDULER.md: {exc}")]

    if not jobs:
        return [
            Check(
                "scheduler policy",
                WARN,
                "SCHEDULER.md contains no readable launchd job policy rows",
            )
        ]

    if launchctl_output is None:
        launchctl_output = _launchctl_list()
    if launchctl_output is None:
        return []  # not macOS / launchctl unavailable — silently skip

    loaded = _loaded_rebalance_labels(launchctl_output)
    checks: list[Check] = []
    for job in jobs:
        if f"com.rebalance-os.{job}" not in loaded:
            installer = _scheduler_installer(job, repo_root)
            checks.append(
                Check(
                    f"scheduler:{job}",
                    WARN,
                    "scheduled job is not loaded on this device",
                    f"install it with `bash {installer}`",
                    severity=NOTICE,
                )
            )
    return checks


def _check_launchd(launchctl_output: str | None = None) -> list[Check]:
    """Report rebalance launchd jobs and their last exit status (macOS only)."""
    if launchctl_output is None:
        launchctl_output = _launchctl_list()
    if launchctl_output is None:
        return []  # not macOS / launchctl unavailable — silently skip

    checks: list[Check] = []
    for line in launchctl_output.splitlines():
        parts = line.split("\t")
        if len(parts) != 3 or "rebalance" not in parts[2]:
            continue
        pid, status, label = parts
        short = label.replace("com.rebalance-os.", "").replace("com.user.", "")

        pid_val = pid.strip()
        status_val = status.strip()
        has_live_pid = pid_val != "-"

        is_negative_signal = False
        try:
            val = int(status_val)
            if val < 0:
                is_negative_signal = True
        except ValueError:
            pass

        is_ok_status = status_val in ("0", "-") or is_negative_signal

        if has_live_pid or is_ok_status:
            running = "running" if has_live_pid else "idle, last run ok"
            checks.append(
                Check(f"launchd:{short}", OK, running, severity=NOTICE)
            )
        else:
            checks.append(
                Check(
                    f"launchd:{short}", WARN,
                    f"last run exited with status {status_val}",
                    "inspect temp/logs/ for this job's error output",
                )
            )
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
    from rebalance.ingest.config import (
        SLEUTH_KEYRING_KEY,
        _keyring_get,
        get_sleuth_credentials,
        get_sleuth_sync_repo_path,
    )

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
                sync_repo = get_sleuth_sync_repo_path() or "~/git-pulse-sync"
                return Check(
                    "sleuth", WARN,
                    f"published export is stale — heartbeat {stamp} ({age_h:.1f}h ago)",
                    "the Sleuth publisher (sleuth-reminders-export.timer on the box) or the "
                    f"local export clone may be stuck; check the timer and `git -C {sync_repo} pull`",
                    severity=ERROR,
                )
            return Check("sleuth", OK, f"configured (via {where}) · export {age_h:.1f}h old")
    return Check("sleuth", OK, f"configured (via {where})")


def _check_apple_reminders(db_path: Path | None = None) -> Check:
    """Apple Reminders — opt-in local macOS source. Surfaces schema drift from the
    last sync (cheap, DB-only; no live-store read, so it's safe on any host)."""
    name = "apple reminders"
    if db_path is None:
        return Check(name, OK, "no database")
    try:
        from rebalance.ingest.apple_reminders import apple_reminders_health

        health = apple_reminders_health(db_path)
    except Exception as exc:  # noqa: BLE001 — doctor must never crash
        return Check(name, WARN, f"health probe failed: {exc}")

    status = health.get("status")
    if status == "never_synced":
        # Opt-in source — a machine that never enabled it is fine, not a warning.
        return Check(name, OK, "not enabled (opt-in; never synced)")
    if status == "drift":
        return Check(
            name, WARN,
            health.get("message", "schema drift"),
            health.get("remediation"),
        )
    fp = health.get("schema_fingerprint") or {}
    macos = fp.get("macos") or "?"
    return Check(name, OK, f"synced · macOS {macos} · {health.get('last_sync_at', '')}")


def _google_oauth_source(service: str, in_keyring: bool) -> str | None:
    """Where a Google OAuth token resolves from: keyring → secret-store JSON →
    legacy pickle. Returns None when nothing is present (unconfigured)."""
    if in_keyring:
        return "keyring"
    from rebalance.ingest import secret_store
    from rebalance.paths import resolve_oauth_token_path
    if secret_store.read_secret_file(f"google-{service}-oauth"):
        return "secret-store JSON"
    if resolve_oauth_token_path(service).exists():
        return "legacy pickle (migrates to JSON on next sync)"
    return None


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
        from rebalance.ingest.config import get_gmail_oauth_token_json
    except Exception as exc:  # noqa: BLE001 — doctor must never crash
        return Check("gmail", WARN, f"gmail module unavailable: {exc}")

    source = _google_oauth_source("gmail", bool(get_gmail_oauth_token_json()))
    if source is None:
        return Check(
            "gmail", WARN,
            "no Gmail OAuth credentials (keyring + secret store empty, no token file)",
            "🔧 run the Gmail OAuth flow (scripts/setup_gmail_oauth.py) — or switch "
            "to MCP mode (`rebalance config set-gmail-method mcp`)",
        )
    return Check("gmail", OK, f"OAuth token present (via {source})")


def _check_calendar() -> Check:
    """Google Calendar OAuth — resolved keyring → secret-store JSON → legacy pickle."""
    try:
        from rebalance.ingest.config import get_calendar_oauth_token_json
    except Exception as exc:  # noqa: BLE001
        return Check("calendar", WARN, f"calendar module unavailable: {exc}")

    source = _google_oauth_source("calendar", bool(get_calendar_oauth_token_json()))
    if source is None:
        return Check(
            "calendar", WARN,
            "no Calendar OAuth credentials (keyring + secret store empty, no token file)",
            "🔧 run the Calendar OAuth flow (scripts/setup_calendar_oauth.py)",
        )
    detail = f"OAuth token present (via {source})"
    try:
        from rebalance.ingest import token_meta
        meta = token_meta.current_token_meta("calendar")
        if meta and meta.get("first_added_at"):
            detail += f" · authorized {token_meta.age_text(meta['first_added_at'])} ago"
    except Exception:  # noqa: BLE001
        pass
    return Check("calendar", OK, detail)


def _check_figma() -> Check:
    """Figma personal access token — an opt-in source. Resolves keyring →
    secret-store → rbos.config (launchd-safe fallback), same dual store as the
    GitHub PAT. Posture, not nagging: optional+unconfigured is a clean skip
    (OK), while a half-configured state (token without file keys, or file keys
    without a token) is a real misconfiguration and warns. Insecure repo-local
    storage of ``figma_token`` is already covered by ``_check_repo_local_secrets``.
    """
    try:
        from rebalance.ingest.config import _get_secret_dual_store, get_figma_file_keys
    except Exception as exc:  # noqa: BLE001 — doctor must never crash
        return Check("figma", WARN, f"figma module unavailable: {exc}")

    token, source = _get_secret_dual_store("figma_token")
    has_token = bool(token.strip()) if isinstance(token, str) else False
    try:
        file_keys = get_figma_file_keys()
    except Exception:  # noqa: BLE001 — never let config reads crash doctor
        file_keys = []

    if not has_token and not file_keys:
        return Check("figma", OK, "not configured (optional integration)")
    if not has_token:
        return Check(
            "figma", WARN,
            f"{len(file_keys)} Figma file key(s) configured but no token",
            "store a Figma personal access token in the `figma_token` secret "
            "(keyring) — the figma sync fails every run without it",
        )
    where = source or "config"
    if not file_keys:
        return Check(
            "figma", WARN,
            f"token present (via {where}) but no file keys to sync",
            "add a Figma file via the pulse dashboard so the figma source has "
            "something to ingest",
        )
    return Check("figma", OK, f"token present (via {where}) · {len(file_keys)} file(s)")


def _check_xyz_pin() -> Check:
    """XYZ harness pin — GH-102 seam #2 (optional cross-repo integration).

    Posture, not nagging (mirrors :func:`_check_figma`): no ``.xyz-pin`` is a
    clean OK skip — Rebalance runs fully standalone without XYZ (GH-102 invariant
    1, mutual independence). A pin that is present but missing its ``commit`` key
    is a real misconfiguration and warns. The recorded-vs-installed drift check
    itself is XYZ-side (``xyz-sync check``, GH-102 Phase 1, deferred); doctor only
    surfaces the pin so the operator can see what the integration targets.
    """
    try:
        from rebalance.xyz_pin import read_pin
    except Exception as exc:  # noqa: BLE001 — doctor must never crash
        return Check("xyz pin", WARN, f"xyz_pin module unavailable: {exc}")

    try:
        pin = read_pin()
    except Exception as exc:  # noqa: BLE001 — never let a file read crash doctor
        return Check("xyz pin", WARN, f"could not read .xyz-pin: {exc}")

    if pin is None:
        return Check("xyz pin", OK, "no XYZ harness pinned (optional integration)")

    commit = pin.get("commit", "").strip()
    if not commit:
        return Check(
            "xyz pin", WARN,
            ".xyz-pin present but has no `commit=` — pin is unusable",
            "record the pinned xyz-3-agents-swarm commit in .xyz-pin (via PR)",
        )
    pinned_at = pin.get("pinned_at", "").strip()
    suffix = f" · pinned {pinned_at}" if pinned_at else ""
    return Check("xyz pin", OK, f"xyz harness pinned @ {commit[:12]}{suffix}")


_AUTH_FAIL_HINT = {
    "github": "PAT revoked, expired, or lost a scope — run "
              "`rebalance config set-github-token` with a fresh token",
    "calendar": "re-run the Calendar OAuth flow "
                "(scripts/setup_calendar_oauth.py)",
    "gmail": "re-run the Gmail OAuth flow (scripts/setup_gmail_oauth.py) — it "
             "writes keyring + JSON in one pass — or switch to MCP mode "
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
                severity=ERROR,
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
                severity=WARNING if health.healthy else ERROR,
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


def _check_deep_work_stalls(db_path: Path) -> Check:
    """Observe-only Phase 1 signal: projects that went quiet with open work."""
    try:
        from rebalance.ingest.next_actions import compute_deep_work_signals

        signals = compute_deep_work_signals(
            db_path,
            datetime.now(timezone.utc).date(),
            lookback_days=7,
        )
    except Exception as exc:  # noqa: BLE001 — doctor must never crash
        return Check("deep work", WARN, f"stall signal unavailable: {exc}")

    flagged = [
        signal for signal in signals.values()
        if signal.get("possible_stall")
    ]
    if not flagged:
        return Check("deep work", OK, "no possible-stall projects in the last 7 days")

    parts: list[str] = []
    for signal in flagged:
        evidence = signal.get("evidence") or {}
        yesterday = evidence.get("yesterday_date") or "yesterday"
        yesterday_rows = ", ".join((evidence.get("yesterday_rows") or [])[:2]) or "activity recorded"
        open_items = evidence.get("open_items") or []
        open_summary = ", ".join(
            f"{'pr' if item.get('item_type') == 'pull_request' else item.get('item_type') or 'item'} "
            f"#{item.get('number')} {item.get('title') or ''}".strip()
            for item in open_items[:2]
        ) or "open work item"
        parts.append(
            f"{signal.get('project')}: quiet {evidence.get('today_date')} after {yesterday} "
            f"({yesterday_rows}); still open: {open_summary}"
        )
    return Check("deep work", WARN, "; ".join(parts))


# ---------------------------------------------------------------------------
# Collector freshness registry
#
# To add a new collector: append one entry.  No other code needs to change.
# Fields: name (Check label), table, ts_col (MAX'd for age), warn_days,
#         empty_hint, stale_hint, plus optional quality/volume declarations.
# ---------------------------------------------------------------------------


def _active_gmail_filter() -> str:
    """Name the active Gmail query when a successful sync is intentionally quiet.

    GH-145: delegates to the shared formatter so this check and the CLI's
    ``signal health`` line cannot describe the same filter differently.
    """
    from rebalance.ingest.config import describe_gmail_query_filter  # noqa: PLC0415

    return describe_gmail_query_filter()


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
        quality_table="github_items",
        quality_predicate="title IS NOT NULL AND TRIM(title) != ''",
        quality_label="a title",
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
        ts_col="synced_at",
        warn_days=7,
        empty_hint="ingest email via the Gmail MCP connector or the OAuth sync (scripts/setup_gmail_oauth.py)",
        stale_hint="no new email ingested in 7+ days — ask Claude to call `ingest_gmail_messages` (MCP mode), or check the Gmail OAuth token (`rebalance doctor`)",
        quality_predicate=(
            "(from_address IS NOT NULL AND TRIM(from_address) != '') "
            "OR (subject IS NOT NULL AND TRIM(subject) != '')"
        ),
        quality_label="a sender or subject",
        volume_ts_col="received_at",
        quiet_filter=_active_gmail_filter,
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
    report.checks.append(_check_secret_permissions())
    report.checks.append(_check_repo_local_secrets())
    report.checks.append(_check_vault())
    report.checks.append(_check_unpushed_work())

    if db_path is not None:
        report.checks.append(_check_schema(db_path))
        report.checks.append(_check_projects(db_path))
        for collector in _COLLECTOR_FRESHNESS:
            report.checks.append(_check_collector_freshness(db_path, **collector))
        report.checks.append(_check_deep_work_stalls(db_path))

    # Integration credentials — Sleuth/Slack, Gmail, Google Calendar, Figma.
    report.checks.append(_check_sleuth(db_path))
    report.checks.append(_check_apple_reminders(db_path))
    report.checks.append(_check_gmail(db_path))
    report.checks.append(_check_calendar())
    report.checks.append(_check_figma())
    report.checks.append(_check_xyz_pin())
    report.checks.append(_check_pulse())

    # Auth-event log — last deauth/auth failure per integration (calendar,
    # github, gmail), read from the unified temp/logs/auth_activity.jsonl.
    report.checks.extend(_check_auth_failures())

    # git-pulse per-device collector health — a *broken* collector (stale or
    # degraded scan) shown right next to a de-authorized one.
    report.checks.extend(_check_pulse_collectors())

    # One live snapshot serves both checks: policy absence is different from a
    # loaded job whose most recent run exited non-zero.
    launchctl_output = _launchctl_list()
    report.checks.extend(_check_scheduler_liveness(launchctl_output=launchctl_output))
    report.checks.extend(_check_launchd(launchctl_output))

    # Final section: a map of every diagnostics surface, so this one command
    # is the single entry point into the project's observability.
    report.checks.extend(_diagnostics_index())
    return report
