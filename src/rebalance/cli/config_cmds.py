"""`rebalance config *` commands — credentials, ignore/related repos, priorities.

Extracted from the cli monolith (Phase 5). Registers on the shared `config_app`
sub-Typer from `_core`.
"""

from __future__ import annotations

from pathlib import Path

import typer

from rebalance.cli._core import config_app
from rebalance.ingest.audit import append_audit_entry
from rebalance.ingest.config import (
    add_focus5_hidden_repo,
    add_focus5_scan_root,
    add_github_ignored_repo,
    add_github_related_repo,
    add_health_notice_pattern,
    clear_github_token,
    get_config_path,
    get_focus5_hidden_repos,
    get_focus5_scan_roots,
    get_gemini_api_key,
    get_github_ignored_repos,
    get_github_related_repos,
    get_github_token_with_source,
    get_gmail_ingest_method,
    get_health_notice_patterns,
    get_project_priority_rules,
    get_sleuth_credentials,
    get_vault_path,
    normalize_github_repo_name,
    remove_focus5_hidden_repo,
    remove_focus5_scan_root,
    remove_github_ignored_repo,
    remove_github_related_repo,
    remove_health_notice_pattern,
    remove_project_priority_rule,
    set_github_token,
    set_gmail_ingest_method,
    set_project_priority_rule,
    set_vault_path,
)
from rebalance.paths import DatabaseNotFoundError, DBOption, resolve_database_path


def _format_purge_counts(row_counts: dict[str, int]) -> str:
    parts = [f"{name}={count}" for name, count in row_counts.items() if count]
    return ", ".join(parts) if parts else "no matching rows"


@config_app.command("add-github-ignored-repo")
def config_add_github_ignored_repo(
    repo: str = typer.Argument(..., help="GitHub repo in owner/name form"),
    purge: bool = typer.Option(False, help="Purge existing local GitHub rows for this repo"),
    dry_run: bool = typer.Option(False, help="Preview purge counts without deleting"),
    confirm: bool = typer.Option(False, help="Confirm destructive purge execution"),
    database: Path | None = DBOption(help="SQLite database path for purge operations (resolves via layered chain)"),
) -> None:
    """Add one repo to the local GitHub ingest ignore list, with optional purge."""
    from rebalance.ingest.github_knowledge import purge_github_repo_data

    normalized_repo = normalize_github_repo_name(repo)
    added = add_github_ignored_repo(normalized_repo)
    if added:
        typer.echo(f"✓ Added ignored GitHub repo: {normalized_repo}")
    else:
        typer.echo(f"✓ GitHub repo already ignored: {normalized_repo}")

    if not purge and not dry_run:
        return

    # Validate destructive-flag combination before touching the DB so missing
    # databases don't mask user-facing argument errors.
    if purge and not dry_run and not confirm:
        typer.echo("Use --confirm with --purge to execute the destructive delete.")
        raise typer.Exit(code=2)

    try:
        db_path = resolve_database_path(database)
    except DatabaseNotFoundError as exc:
        typer.echo(str(exc))
        raise typer.Exit(2) from exc
    if dry_run:
        purge_result = purge_github_repo_data(db_path, normalized_repo, dry_run=True)
        append_audit_entry(
            "github_repo_purge",
            normalized_repo,
            dry_run=True,
            confirmed=False,
            database_path=str(db_path),
            row_counts=purge_result.row_counts,
            total_rows=purge_result.total_rows,
            deleted_rows=purge_result.deleted_rows,
        )
        typer.echo(
            f"Dry run: {normalized_repo} would purge {purge_result.total_rows} rows "
            f"({_format_purge_counts(purge_result.row_counts)})"
        )
        return

    purge_result = purge_github_repo_data(db_path, normalized_repo, dry_run=False)
    append_audit_entry(
        "github_repo_purge",
        normalized_repo,
        dry_run=False,
        confirmed=True,
        database_path=str(db_path),
        row_counts=purge_result.row_counts,
        total_rows=purge_result.total_rows,
        deleted_rows=purge_result.deleted_rows,
    )
    typer.echo(
        f"Purged {purge_result.deleted_rows} rows for {normalized_repo} "
        f"({_format_purge_counts(purge_result.row_counts)})"
    )


@config_app.command("remove-github-ignored-repo")
def config_remove_github_ignored_repo(
    repo: str = typer.Argument(..., help="GitHub repo in owner/name form"),
) -> None:
    """Remove one repo from the local GitHub ingest ignore list."""
    normalized_repo = normalize_github_repo_name(repo)
    removed = remove_github_ignored_repo(normalized_repo)
    if removed:
        typer.echo(f"✓ Removed ignored GitHub repo: {normalized_repo}")
    else:
        typer.echo(f"✓ GitHub repo was not ignored: {normalized_repo}")


@config_app.command("list-github-ignored-repos")
def config_list_github_ignored_repos() -> None:
    """List the operator-local GitHub repos excluded from ingest."""
    repos = get_github_ignored_repos()
    if not repos:
        typer.echo("No ignored GitHub repos configured.")
        return
    for repo in repos:
        typer.echo(repo)


def _focus5_rerank_after_change() -> None:
    """Best-effort re-rank from cache so a Focus 5 hide/un-hide takes effect on the
    next page load without a manual refresh. Silent when no database exists yet."""
    try:
        from rebalance.ingest.focus5_scan import rerank_focus5_from_cache
        from rebalance.paths import DatabaseNotFoundError, resolve_database_path

        try:
            db = resolve_database_path()
        except DatabaseNotFoundError:
            return
        rerank_focus5_from_cache(db)
    except Exception:  # noqa: BLE001 — the config change stuck; re-rank is a nicety
        pass


@config_app.command("add-focus5-hidden-repo")
def config_add_focus5_hidden_repo(
    repo: str = typer.Argument(..., help="Repo identity: owner/name (remote) or device-local path"),
) -> None:
    """Hide one repo from the Focus 5 roster (display-only; does not affect ingest)."""
    added = add_focus5_hidden_repo(repo)
    _focus5_rerank_after_change()
    if added:
        typer.echo(f"✓ Hidden from Focus 5: {repo.strip()}")
    else:
        typer.echo(f"✓ Already hidden from Focus 5: {repo.strip()}")


@config_app.command("remove-focus5-hidden-repo")
def config_remove_focus5_hidden_repo(
    repo: str = typer.Argument(..., help="Repo identity to un-hide"),
) -> None:
    """Un-hide one repo so it can re-enter the Focus 5 roster."""
    removed = remove_focus5_hidden_repo(repo)
    _focus5_rerank_after_change()
    if removed:
        typer.echo(f"✓ Un-hidden from Focus 5: {repo.strip()}")
    else:
        typer.echo(f"✓ Repo was not hidden from Focus 5: {repo.strip()}")


@config_app.command("list-focus5-hidden-repos")
def config_list_focus5_hidden_repos() -> None:
    """List the repos hidden from the Focus 5 roster."""
    repos = get_focus5_hidden_repos()
    if not repos:
        typer.echo("No repos hidden from Focus 5.")
        return
    for repo in repos:
        typer.echo(repo)


@config_app.command("add-focus5-scan-root")
def config_add_focus5_scan_root(
    path: str = typer.Argument(..., help="Directory the Focus 5 collector should walk for git repos"),
) -> None:
    """Add one directory to the Focus 5 scan roots (a root may itself be a repo)."""
    expanded = str(Path(path.strip()).expanduser())
    added = add_focus5_scan_root(path)
    _focus5_rerank_after_change()
    if added:
        typer.echo(f"✓ Added Focus 5 scan root: {expanded}")
        typer.echo("  Run `rebalance refresh-index --scope focus5` to discover repos under it.")
    else:
        typer.echo(f"✓ Already a Focus 5 scan root: {expanded}")


@config_app.command("remove-focus5-scan-root")
def config_remove_focus5_scan_root(
    path: str = typer.Argument(..., help="Scan-root directory to stop walking"),
) -> None:
    """Remove one directory from the Focus 5 scan roots."""
    expanded = str(Path(path.strip()).expanduser())
    removed = remove_focus5_scan_root(path)
    _focus5_rerank_after_change()
    if removed:
        typer.echo(f"✓ Removed Focus 5 scan root: {expanded}")
    else:
        typer.echo(f"✓ Not a Focus 5 scan root: {expanded}")


@config_app.command("list-focus5-scan-roots")
def config_list_focus5_scan_roots() -> None:
    """List the directories the Focus 5 collector walks (effective, incl. defaults)."""
    for root in get_focus5_scan_roots():
        typer.echo(root)


@config_app.command("add-github-related-repo")
def config_add_github_related_repo(
    repo: str = typer.Argument(..., help="Central tracker repo in owner/name form"),
    related_repo: str = typer.Argument(..., help="Related implementation repo in owner/name form"),
) -> None:
    """Add an affiliate implementation repo for a central GitHub tracker repo."""
    normalized_repo = normalize_github_repo_name(repo)
    normalized_related = normalize_github_repo_name(related_repo)
    added = add_github_related_repo(normalized_repo, normalized_related)
    if added:
        typer.echo(f"✓ Added related GitHub repo for {normalized_repo}: {normalized_related}")
    else:
        typer.echo(f"✓ Related GitHub repo already configured for {normalized_repo}: {normalized_related}")


@config_app.command("remove-github-related-repo")
def config_remove_github_related_repo(
    repo: str = typer.Argument(..., help="Central tracker repo in owner/name form"),
    related_repo: str = typer.Argument(..., help="Related implementation repo in owner/name form"),
) -> None:
    """Remove an affiliate implementation repo from a central tracker repo."""
    normalized_repo = normalize_github_repo_name(repo)
    normalized_related = normalize_github_repo_name(related_repo)
    removed = remove_github_related_repo(normalized_repo, normalized_related)
    if removed:
        typer.echo(f"✓ Removed related GitHub repo for {normalized_repo}: {normalized_related}")
    else:
        typer.echo(f"✓ Related GitHub repo was not configured for {normalized_repo}: {normalized_related}")


@config_app.command("list-github-related-repos")
def config_list_github_related_repos(
    repo: str = typer.Argument(..., help="Central tracker repo in owner/name form"),
) -> None:
    """List affiliate implementation repos for a central GitHub tracker repo."""
    normalized_repo = normalize_github_repo_name(repo)
    repos = get_github_related_repos(normalized_repo)
    if not repos:
        typer.echo(f"No related GitHub repos configured for {normalized_repo}.")
        return
    for related_repo in repos:
        typer.echo(related_repo)


@config_app.command("set-project-priority")
def config_set_project_priority(
    name: str = typer.Argument(..., help="Canonical project name"),
    alias: list[str] = typer.Option([], "--alias", help="Project/client alias. Repeat for multiple aliases."),
    client: str = typer.Option("", "--client", help="Client or account label"),
    priority_tier: int | None = typer.Option(None, "--priority-tier", min=1, max=5, help="Priority tier: 1 is highest, 5 is lowest"),
    value_score: int | None = typer.Option(None, "--value-score", min=1, max=10, help="Value score: 10 is highest"),
    value_level: str = typer.Option("", "--value-level", help="Value level, e.g. strategic or revenue-generating"),
    risk_level: str = typer.Option("", "--risk-level", help="Risk level, e.g. high, medium, low"),
) -> None:
    """Set local project/client priority metadata used by dashboards."""
    try:
        rule = set_project_priority_rule(
            name=name,
            aliases=alias,
            client=client,
            priority_tier=priority_tier,
            value_score=value_score,
            value_level=value_level,
            risk_level=risk_level,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"✓ Set project priority: {rule['name']}")


@config_app.command("remove-project-priority")
def config_remove_project_priority(
    name: str = typer.Argument(..., help="Canonical project name"),
) -> None:
    """Remove local project/client priority metadata by project name."""
    removed = remove_project_priority_rule(name)
    if removed:
        typer.echo(f"✓ Removed project priority: {name}")
    else:
        typer.echo(f"✓ Project priority was not configured: {name}")


@config_app.command("list-project-priorities")
def config_list_project_priorities() -> None:
    """List local project/client priority metadata."""
    rules = get_project_priority_rules()
    if not rules:
        typer.echo("No project priorities configured.")
        return
    for rule in rules:
        pieces = [
            rule["name"],
            f"tier={rule.get('priority_tier', 'n/a')}",
            f"value={rule.get('value_score', 'n/a')}",
        ]
        if rule.get("client"):
            pieces.append(f"client={rule['client']}")
        if rule.get("aliases"):
            pieces.append(f"aliases={', '.join(rule['aliases'])}")
        typer.echo(" | ".join(pieces))


@config_app.command("doctor")
def config_doctor() -> None:
    """Show the status of every credential and config source — with live GitHub validation."""
    from rebalance.ingest.github_scan import validate_github_token
    from rebalance.paths import resolve_database_path, DatabaseNotFoundError, resolve_secret_path

    ok = "✓"
    missing = "✗"

    def row(label: str, status: bool, detail: str = "") -> None:
        sym = ok if status else missing
        line = f"  {sym}  {label}"
        if detail:
            line += f"  ({detail})"
        typer.echo(line)

    from rebalance.ingest.config import KEYRING_SERVICE, _keyring_get

    typer.echo("\n── Config file ─────────────────────────────")
    cfg_path = get_config_path()
    row("temp/rbos.config", cfg_path.exists(), str(cfg_path))

    typer.echo("\n── Keyring ──────────────────────────────────")
    try:
        import keyring as _kr
        _kr.get_password(KEYRING_SERVICE, "__probe__")
        row("OS keyring", True, f"service={KEYRING_SERVICE}  backend={type(_kr.get_keyring()).__name__}")
    except Exception as exc:
        row("OS keyring", False, f"unavailable — secrets fall back to rbos.config ({exc})")

    typer.echo("\n── GitHub ───────────────────────────────────")
    token, source = get_github_token_with_source()
    if token:
        result = validate_github_token(token)
        if result["valid"]:
            row("GitHub token", True, f"source={source}  login={result.get('login')}  scopes={result.get('scopes')}")
        else:
            row("GitHub token", False, f"source={source}  invalid — {result.get('error', 'unknown error')}")
    else:
        row("GitHub token", False, "not configured — run: rebalance config set-github-token <PAT>")

    typer.echo("\n── Calendar OAuth ───────────────────────────")
    from rebalance.ingest.config import get_calendar_oauth_token_json
    cal_token_json = get_calendar_oauth_token_json()
    row("Calendar OAuth (keyring)", bool(cal_token_json), "token stored in keyring" if cal_token_json else "not in keyring — using pickle fallback")

    typer.echo("\n── Vault & database ─────────────────────────")
    vault = get_vault_path()
    row("Vault path", bool(vault), vault or "not set — run: rebalance config set-vault-path <path>")
    try:
        db = resolve_database_path()
        row("Database", True, str(db))
    except DatabaseNotFoundError:
        row("Database", False, "not found — run: rebalance refresh-index")

    typer.echo("\n── LLM API keys (env vars) ──────────────────")
    row("GEMINI_API_KEY / GOOGLE_API_KEY", bool(get_gemini_api_key()), "used by RepairFSM and dashboard synthesis")

    typer.echo("\n── Sleuth credentials ───────────────────────")
    try:
        get_sleuth_credentials()
        sleuth_path = resolve_secret_path("sleuth-web-api-production.env")
        if not sleuth_path.exists():
            sleuth_path = resolve_secret_path("sleuth-web-api-development.env")
        row("Sleuth env file", True, str(sleuth_path))
    except FileNotFoundError as exc:
        row("Sleuth env file", False, str(exc))
    except ValueError as exc:
        row("Sleuth env file (found but invalid)", False, str(exc))

    typer.echo("\n── Google Calendar OAuth ────────────────────")
    cal_path = resolve_secret_path("google-calendar.env")
    row("google-calendar.env", cal_path.exists(), str(cal_path))

    typer.echo("\n── Auth activity (last event per collector) ─")
    from rebalance.ingest import auth_log
    latest = auth_log.latest_event_by_source()
    if not latest:
        typer.echo("  ·  no auth events logged yet (temp/logs/auth_activity.jsonl)")
    else:
        for src in sorted(latest):
            entry = latest[src]
            event = entry.get("event", "")
            ts = str(entry.get("ts", ""))[:19].replace("T", " ")
            failed = event in auth_log.FAILURE_EVENTS
            row(f"{src}", not failed, f"last: {event} at {ts} UTC")

    typer.echo("")


@config_app.command("set-github-token")
def config_set_github_token(
    token: str = typer.Argument(..., help="GitHub Personal Access Token (ghp_...)"),
) -> None:
    """Store GitHub PAT in local config (temp/rbos.config, gitignored)."""
    set_github_token(token)
    typer.echo(f"✓ GitHub token stored in {get_config_path()}")
    typer.echo("  Keep this file secret and never commit it.")


@config_app.command("get-github-token")
def config_get_github_token() -> None:
    """Check if GitHub token is available (config first, gh CLI fallback)."""
    token, source = get_github_token_with_source()
    if token:
        masked = token[:10] + "..." + token[-4:] if len(token) > 14 else "***"
        label = {"config": "stored PAT", "gh-cli": "via `gh auth token`"}.get(source, source or "unknown")
        typer.echo(f"✓ GitHub token available: {masked}  (source: {label})")
    else:
        typer.echo("✗ No GitHub token available. Either:")
        typer.echo("  rebalance config set-github-token <PAT>")
        typer.echo("  — or —")
        typer.echo("  gh auth login   (then it'll be picked up automatically)")


@config_app.command("clear-github-token")
def config_clear_github_token() -> None:
    """Remove stored PAT so the gh CLI fallback takes over (`gh auth token`)."""
    clear_github_token()
    typer.echo("✓ Stored PAT cleared. `get-github-token` will now fall back to gh CLI.")


@config_app.command("set-sleuth")
def config_set_sleuth(
    base_url: str = typer.Option("", "--base-url", help="Sleuth Web API base URL"),
    token: str = typer.Option("", "--token", help="Sleuth Web API token"),
    workspace: str = typer.Option("", "--workspace", help="Sleuth workspace name"),
    from_env: Path = typer.Option(
        None, "--from-env",
        help="Import all three values from an existing sleuth-web-api env file.",
    ),
) -> None:
    """Store Sleuth Web API credentials in the OS keyring + rbos.config (launchd-reachable).

    Consistent with the GitHub token: keyring is the interactive primary, the
    config copy is the launchd fallback. Run this once per machine. Logs a
    `token_set` auth-log event + sidecar first-added metadata.
    """
    from rebalance.ingest.config import set_sleuth_credentials

    if from_env:
        p = from_env.expanduser()
        if not p.exists():
            raise typer.BadParameter(f"env file not found: {p}")
        vals: dict[str, str] = {}
        for raw in p.read_text(encoding="utf-8").splitlines():
            raw = raw.strip()
            if not raw or raw.startswith("#") or "=" not in raw:
                continue
            k, v = raw.split("=", 1)
            vals[k.strip()] = v.strip()
        base_url = base_url or vals.get("SLEUTH_WEB_API_BASE_URL", "")
        token = token or vals.get("SLEUTH_WEB_API_TOKEN", "")
        workspace = workspace or vals.get("SLEUTH_WORKSPACE_NAME", "")

    missing = [
        name for name, value in (
            ("--base-url", base_url), ("--token", token), ("--workspace", workspace),
        ) if not value.strip()
    ]
    if missing:
        raise typer.BadParameter(
            f"missing required value(s): {', '.join(missing)} (pass them or use --from-env)"
        )

    set_sleuth_credentials(base_url, token, workspace, source="manual")
    typer.echo(f"✓ Sleuth credentials stored in keyring + config (workspace: {workspace.strip()})")
    typer.echo("  Token kept secret. Run the same command on your other machines to replicate.")


@config_app.command("clear-sleuth")
def config_clear_sleuth() -> None:
    """Remove Sleuth credentials from keyring + rbos.config (env file untouched)."""
    from rebalance.ingest.config import clear_sleuth_credentials
    clear_sleuth_credentials()
    typer.echo("✓ Sleuth credentials cleared from keyring + config.")


@config_app.command("add-health-notice")
def config_add_health_notice(
    pattern: str = typer.Argument(..., help="Check-name substring to demote, e.g. 'email data' or 'pulse collector:noel’s MacBook'"),
) -> None:
    """Demote a health WARN to a 'notice' (shown on the dashboard, but not
    counted as 'collector attention needed'). Matches the check name as a
    case-insensitive substring. FAIL checks are never demoted."""
    if add_health_notice_pattern(pattern):
        typer.echo(f"health notice added: {pattern!r} ✓")
    else:
        typer.echo(f"health notice unchanged (blank or already present): {pattern!r}")


@config_app.command("remove-health-notice")
def config_remove_health_notice(
    pattern: str = typer.Argument(..., help="Exact notice pattern to remove"),
) -> None:
    """Remove a health-notice pattern (re-promotes matching WARNs to problems)."""
    if remove_health_notice_pattern(pattern):
        typer.echo(f"health notice removed: {pattern!r} ✓")
    else:
        typer.echo(f"no such health notice: {pattern!r}")


@config_app.command("list-health-notices")
def config_list_health_notices() -> None:
    """List the configured health-notice patterns."""
    patterns = get_health_notice_patterns()
    if not patterns:
        typer.echo("no health-notice patterns configured")
        return
    for p in patterns:
        typer.echo(f"  • {p}")


@config_app.command("set-gmail-method")
def config_set_gmail_method(
    method: str = typer.Argument(..., help="'oauth' (desktop OAuth token) or 'mcp' (Gmail MCP connector)"),
) -> None:
    """Choose how Gmail is ingested.

    - oauth: autonomous — `sync_gmail` fetches via the desktop OAuth token
      (set up with scripts/setup_gmail_oauth.py, stored in keyring). Works under
      launchd.
    - mcp: email_messages is populated by an agent using the Gmail MCP connector.
      No local credential needed, but requires an agent to trigger ingest.
    """
    try:
        set_gmail_ingest_method(method)
    except ValueError as exc:
        typer.echo(f"❌ {exc}")
        raise typer.Exit(1)
    typer.echo(f"gmail ingest method → {method.strip().lower()} ✓")
    if method.strip().lower() == "oauth":
        typer.echo("  Ensure a token exists: scripts/setup_gmail_oauth.py → migrate-to-keyring")


def _refresh_token_of(token_json: str | None) -> str:
    """Pull the stable refresh_token out of a serialized Google OAuth blob."""
    if not token_json:
        return ""
    import json as _json
    try:
        return str((_json.loads(token_json) or {}).get("refresh_token") or "")
    except (ValueError, TypeError):
        return ""


def _migrate_google_pickle_to_keyring(
    *,
    label: str,
    token_path: Path,
    get_keyring,
    set_keyring,
    missing_hint: str,
) -> None:
    """Sync a Google OAuth pickle file into keyring.

    Unlike a naive "skip if keyring already set", this detects a *freshly
    re-authed* pickle (different refresh_token than the keyring copy) and updates
    keyring from it — so the documented `setup_*_oauth.py → migrate-to-keyring`
    re-auth flow actually takes effect on a device that already had a keyring
    entry, instead of silently keeping the stale token.
    """
    import pickle
    try:
        keyring_blob = get_keyring()
        if not token_path.exists():
            if keyring_blob:
                typer.echo(f"{label}: already in keyring ✓")
            else:
                typer.echo(f"{label}: no token found — {missing_hint}")
            return

        with open(token_path, "rb") as f:
            creds = pickle.load(f)
        pickle_json = creds.to_json()

        if not keyring_blob:
            set_keyring(pickle_json, source="migrate", record=True)
            typer.echo(f"{label}: migrated pickle file → keyring ✓")
        elif _refresh_token_of(pickle_json) != _refresh_token_of(keyring_blob):
            set_keyring(pickle_json, source="reauth", record=True)
            typer.echo(f"{label}: refreshed keyring from newer pickle (re-auth) ✓")
        else:
            typer.echo(f"{label}: already in keyring ✓")
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"{label}: skipped ({type(exc).__name__}: {exc})")


@config_app.command("migrate-to-keyring")
def config_migrate_to_keyring() -> None:
    """One-shot: move local credentials (calendar pickle, sleuth env file) into keyring.

    Run on each device after `git pull` to adopt the keyring credential model.
    Idempotent. The GitHub PAT can't be auto-migrated (it's a value only you have)
    — set it with `rebalance config set-github-token <PAT>`.
    """
    from rebalance.ingest import config as cfg

    # calendar: pickle → keyring
    from rebalance.ingest.calendar import TOKEN_PATH as CALENDAR_TOKEN_PATH
    _migrate_google_pickle_to_keyring(
        label="calendar",
        token_path=CALENDAR_TOKEN_PATH,
        get_keyring=cfg.get_calendar_oauth_token_json,
        set_keyring=cfg.set_calendar_oauth_token_json,
        missing_hint="run scripts/setup_calendar_oauth.py",
    )

    # gmail: pickle → keyring (mirrors calendar)
    from rebalance.ingest.gmail import TOKEN_PATH as GMAIL_TOKEN_PATH
    _migrate_google_pickle_to_keyring(
        label="gmail",
        token_path=GMAIL_TOKEN_PATH,
        get_keyring=cfg.get_gmail_oauth_token_json,
        set_keyring=cfg.set_gmail_oauth_token_json,
        missing_hint="run scripts/setup_gmail_oauth.py "
                     "(or stay on the Gmail MCP connector: gmail_ingest_method=mcp)",
    )

    # sleuth: env file → keyring
    try:
        if cfg._keyring_get(cfg.SLEUTH_KEYRING_KEY):
            typer.echo("sleuth: already in keyring ✓")
        else:
            try:
                creds = cfg.get_sleuth_credentials()  # falls back to the env file
                cfg.set_sleuth_credentials(
                    creds["SLEUTH_WEB_API_BASE_URL"], creds["SLEUTH_WEB_API_TOKEN"],
                    creds["SLEUTH_WORKSPACE_NAME"], source="migrate",
                )
                typer.echo("sleuth: migrated env file → keyring ✓")
            except FileNotFoundError:
                typer.echo("sleuth: no source found — run `rebalance config set-sleuth ...`")
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"sleuth: skipped ({type(exc).__name__}: {exc})")

    # github: report only (can't auto-migrate a token value)
    token, source = cfg.get_github_token_with_source()
    if source == "keyring":
        typer.echo("github: in keyring ✓")
    elif token:
        typer.echo(f"github: resolves via '{source}' — run `rebalance config set-github-token <PAT>` to keyring it")
    else:
        typer.echo("github: not configured — run `rebalance config set-github-token <PAT>`")

    typer.echo("\nDone. Verify with `rebalance doctor`. (Keyring is per-machine — run this on each device.)")


@config_app.command("migrate-secrets")
def config_migrate_secrets() -> None:
    """Phase 2: lift secret keys (github/figma/sleuth) out of repo-local rbos.config
    into the out-of-repo secret store.

    Per-machine and idempotent — for each key still in rbos.config it writes the
    keyring + secret store, verifies, then deletes the repo-local copy. Run on
    each device after `git pull`, then verify with `rebalance doctor`.
    """
    from rebalance.ingest import config as cfg

    results = cfg.migrate_repo_local_secrets()
    for key, status in results.items():
        typer.echo(f"{key}: {status}")
    # Phase 3: also retire legacy Google OAuth pickle files (JSON fallback only).
    for service, status in cfg.migrate_oauth_pickles().items():
        typer.echo(f"google-{service}-oauth: {status}")
    leftover = cfg.repo_local_secret_keys_present()
    if leftover:
        typer.echo(f"\n⚠ still in temp/rbos.config: {', '.join(leftover)} — see FAILED lines above")
    else:
        typer.echo("\n✓ temp/rbos.config holds no live secrets. Verify with `rebalance doctor`.")


@config_app.command("set-vault")
def config_set_vault(
    path: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True, help="Absolute path to the Obsidian vault root"),
) -> None:
    """Store Obsidian vault path in local config (temp/rbos.config). Canonical source for all ingest/sync workflows."""
    resolved = str(path.expanduser().resolve())
    set_vault_path(resolved)
    typer.echo(f"✓ Vault path stored in {get_config_path()}")
    typer.echo(f"  vault_path = {resolved}")


@config_app.command("get-vault")
def config_get_vault() -> None:
    """Show the configured Obsidian vault path."""
    path = get_vault_path()
    if path:
        typer.echo(f"✓ Vault path: {path}")
    else:
        typer.echo("✗ Vault path not configured. Set it with:")
        typer.echo("  rebalance config set-vault <absolute-path>")


@config_app.command("show-config-path")
def config_show_config_path() -> None:
    """Show where configuration is stored."""
    path = get_config_path()
    typer.echo(f"Config file: {path}")
    typer.echo(f"Gitignored:  {path.parent.name}/ is in .gitignore")


@config_app.command("set-default-database")
def config_set_default_database(
    path: Path = typer.Argument(..., help="Absolute path to rebalance.db"),
) -> None:
    """Set the user-level default database path.

    Writes ``database_path`` to ~/.config/rebalance-os/config.json so any
    `rebalance` command run from any directory on this machine resolves to
    the right database without needing REBALANCE_DB in the shell rc.

    Resolution order (highest priority first):
      1. --database flag
      2. REBALANCE_DB env var
      3. Walk-up from cwd for a project marker (.git / pyproject.toml)
      4. This user-level default
    """
    from rebalance.paths import set_user_config_value

    abs_path = path.expanduser().resolve()
    if not abs_path.exists():
        typer.echo(f"[error] {abs_path} does not exist; refusing to write default")
        raise typer.Exit(2)
    config_file = set_user_config_value("database_path", str(abs_path))
    typer.echo(f"[+] wrote database_path={abs_path}")
    typer.echo(f"    to {config_file}")


@config_app.command("set-secrets-dir")
def config_set_secrets_dir(
    path: Path = typer.Argument(..., help="Absolute path to secrets directory"),
) -> None:
    """Set the user-level secrets directory.

    Writes ``secrets_dir`` to ~/.config/rebalance-os/config.json. Used when
    resolving env files like google-calendar.env, sleuth-web-api-development.env,
    etc.

    Resolution order:
      1. REBALANCE_SECRETS_DIR env var
      2. This user-level default
      3. ~/secrets (legacy fallback)
    """
    from rebalance.paths import set_user_config_value

    abs_path = path.expanduser().resolve()
    if not abs_path.exists():
        typer.echo(f"[error] {abs_path} does not exist; refusing to write default")
        raise typer.Exit(2)
    if not abs_path.is_dir():
        typer.echo(f"[error] {abs_path} is not a directory")
        raise typer.Exit(2)
    config_file = set_user_config_value("secrets_dir", str(abs_path))
    typer.echo(f"[+] wrote secrets_dir={abs_path}")
    typer.echo(f"    to {config_file}")


@config_app.command("show-defaults")
def config_show_defaults() -> None:
    """Show the layered path-resolution state (debug helper).

    Prints what every layer of the resolver currently sees, so you can tell
    *why* a particular DB or secret path is being used.
    """
    from rebalance.paths import get_user_config_summary

    summary = get_user_config_summary()
    for k, v in summary.items():
        typer.echo(f"  {k}: {v}")
