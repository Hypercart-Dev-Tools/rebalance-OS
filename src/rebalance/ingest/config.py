"""
Configuration loader for rebalance — secrets, API credentials, etc.

Non-secret config:  temp/rbos.config (gitignored, JSON)
Secrets:            OS keyring via the `keyring` library
                    (macOS Keychain, Windows Credential Locker, etc.)
                    Service name: KEYRING_SERVICE = "rebalance-os"

Migration: any secret still in rbos.config is silently moved to keyring
on first read and removed from the file.  The rbos.config legacy path
serves as a fallback when keyring is unavailable (e.g. headless CI).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import threading
from pathlib import Path
from typing import Any

from rebalance.paths import find_project_root


# Override seam for tests. When None, resolve from the active checkout/env.
CONFIG_PATH: Path | None = None
CONFIG_ENV_VAR = "REBALANCE_CONFIG"

# Keyring service name — all secrets stored under this service.
KEYRING_SERVICE = "rebalance-os"


def _keyring_get(key: str) -> str | None:
    """Return a secret from the OS keyring, or None if unavailable/unset."""
    try:
        import keyring  # noqa: PLC0415
        return keyring.get_password(KEYRING_SERVICE, key)
    except Exception:  # noqa: BLE001 — keyring backend missing or locked
        return None


def _keyring_set(key: str, value: str) -> bool:
    """Write a secret to the OS keyring. Returns True on success."""
    try:
        import keyring  # noqa: PLC0415
        keyring.set_password(KEYRING_SERVICE, key, value)
        return True
    except Exception:  # noqa: BLE001
        return False


def _keyring_delete(key: str) -> bool:
    """Delete a secret from the OS keyring. Returns True on success."""
    try:
        import keyring  # noqa: PLC0415
        import keyring.errors  # noqa: PLC0415
        keyring.delete_password(KEYRING_SERVICE, key)
        return True
    except Exception:  # noqa: BLE001
        return False


def _migrate_to_keyring(config_key: str) -> str | None:
    """If *config_key* is in rbos.config but not keyring, move it to keyring silently.

    Returns the migrated value, or None if nothing to migrate.
    """
    config = _read_config()
    value = config.get(config_key)
    if not value:
        return None
    if _keyring_set(config_key, value):
        del config[config_key]
        _write_config(config)
    return value
_GITHUB_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def _resolved_config_path() -> Path:
    if CONFIG_PATH is not None:
        return CONFIG_PATH.expanduser().resolve()

    env_path = os.environ.get(CONFIG_ENV_VAR)
    if env_path:
        return Path(env_path).expanduser().resolve()

    cwd_root = find_project_root(Path.cwd())
    if cwd_root is not None:
        return cwd_root / "temp" / "rbos.config"

    module_root = find_project_root(Path(__file__).resolve())
    if module_root is not None:
        return module_root / "temp" / "rbos.config"

    return Path.cwd() / "temp" / "rbos.config"


def _ensure_config_dir() -> None:
    """Create temp/ dir if missing."""
    _resolved_config_path().parent.mkdir(parents=True, exist_ok=True)


def _read_config() -> dict[str, Any]:
    """Load config from disk; return {} if missing."""
    config_path = _resolved_config_path()
    if not config_path.exists():
        return {}
    try:
        return json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return {}


def _write_config(config: dict[str, Any]) -> None:
    """Write config to disk with .gitignore safety."""
    _ensure_config_dir()
    _resolved_config_path().write_text(json.dumps(config, indent=2), encoding="utf-8")


def normalize_github_repo_name(repo: str) -> str:
    """Normalize one GitHub repo identifier to exact lowercased owner/name form."""
    normalized = repo.strip().strip("/")
    if not normalized or not _GITHUB_REPO_RE.fullmatch(normalized):
        raise ValueError(f"Invalid GitHub repo '{repo}'. Expected owner/name.")
    return normalized.lower()


def _normalize_github_repo_list(repos: list[str] | tuple[str, ...] | set[str]) -> list[str]:
    normalized: list[str] = []
    for repo in repos:
        item = normalize_github_repo_name(repo)
        if item not in normalized:
            normalized.append(item)
    return sorted(normalized)


def _try_gh_cli_token() -> str | None:
    """Return the OAuth token gh CLI is currently using, or None if unavailable."""
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    token = result.stdout.strip()
    return token or None


def get_github_token_via_gh() -> str | None:
    """Return the token the ``gh`` CLI is currently authorized with, or None.

    Public wrapper over the gh-cli probe so other modules (e.g. the scan's
    401-deauth fallback) can use the ambient gh login as a backup credential
    without reaching into a private helper. Only resolvable interactively —
    launchd's stripped environment cannot run ``gh``.
    """
    return _try_gh_cli_token()


def get_github_token_with_source() -> tuple[str | None, str | None]:
    """
    Resolve a GitHub token. Returns (token, source) where source is one of:
      "keyring" — token stored in the OS keyring (preferred)
      "config"  — token still in temp/rbos.config (legacy; auto-migrated on read)
      "gh-cli"  — fell back to `gh auth token`
      None      — not available

    Resolution order: keyring → rbos.config (with auto-migration) → gh-cli.
    Explicit PATs always win over the ambient gh login.
    """
    token = _keyring_get("github_token")
    if token:
        return token, "keyring"
    # Legacy path — auto-migrate to keyring on first read
    token = _migrate_to_keyring("github_token")
    if token:
        return token, "config"
    token = _try_gh_cli_token()
    if token:
        return token, "gh-cli"
    return None, None


def get_github_token() -> str | None:
    """Get GitHub token (keyring → rbos.config → gh-cli)."""
    token, _source = get_github_token_with_source()
    return token


def classify_github_token(token: str) -> str:
    """Human label for a GitHub token by its prefix — for the re-auth log."""
    for prefix, label in (
        ("github_pat_", "fine-grained PAT"),
        ("ghp_", "classic PAT"),
        ("gho_", "gh OAuth (rotates)"),
        ("ghs_", "app installation token"),
        ("ghu_", "user-to-server token"),
    ):
        if token.startswith(prefix):
            return label
    return "unknown"


def set_github_token(token: str, *, source: str = "manual") -> None:
    """Store GitHub PAT in the OS keyring AND rbos.config.

    Both stores are written so launchd jobs (which run with a stripped
    environment and may not reach the user keychain) can always fall back
    to rbos.config. keyring is preferred for interactive reads; config is
    the launchd safety net.

    *source* records how this (re-)authorization happened (``manual`` via the
    CLI, ``gh-fallback`` via the 401 auto-heal); it is logged to the unified
    auth log as a ``token_set`` event so the re-auth cadence — and the gap
    between successive deauths — is visible.
    """
    cleaned = token.strip()
    _keyring_set("github_token", cleaned)  # best-effort; ignored if unavailable
    config = _read_config()
    config["github_token"] = cleaned
    _write_config(config)
    try:  # never let logging break a credential write
        from rebalance.ingest import auth_log, token_meta  # noqa: PLC0415
        kind = classify_github_token(cleaned)
        auth_log.log_github_token_set(kind, source=source)
        # Sidecar: remember when THIS token value was first added (lifetime tracking).
        token_meta.record_token_set("github", cleaned, kind=kind, source=source)
    except Exception:  # noqa: BLE001
        pass


def clear_github_token() -> None:
    """Remove the stored GitHub PAT from both keyring and rbos.config."""
    _keyring_delete("github_token")
    config = _read_config()
    if "github_token" in config:
        del config["github_token"]
        _write_config(config)


def get_vault_path() -> str | None:
    """
    Get Obsidian vault path from config. Returns None if not set.

    Config key: vault_path
    """
    config = _read_config()
    return config.get("vault_path")


def set_vault_path(path: str) -> None:
    """Store Obsidian vault path in config."""
    config = _read_config()
    config["vault_path"] = path.strip()
    _write_config(config)


# ---------------------------------------------------------------------------
# Figma
# ---------------------------------------------------------------------------
#
# The Figma personal access token is a secret, so it follows the same
# keyring-primary / rbos.config-fallback discipline as the GitHub token (see
# get_github_token / set_github_token / clear_github_token). File keys are NOT
# secret — the comments API is file-scoped, so the collector needs an explicit
# allow-list — and live in plain rbos.config.


def get_figma_token() -> str | None:
    """Return the configured Figma personal access token (keyring → rbos.config).

    Mirrors :func:`get_github_token`: keyring is the preferred store, with
    rbos.config as the launchd-safe fallback. Any cleartext token still in
    rbos.config is auto-migrated into keyring on first read.
    """
    token = _keyring_get("figma_token")
    if token:
        return token
    # Legacy / launchd path — auto-migrate to keyring on first read.
    token = _migrate_to_keyring("figma_token")
    if token:
        return token
    config = _read_config()
    value = config.get("figma_token")
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def set_figma_token(token: str) -> None:
    """Store the Figma PAT in the OS keyring AND rbos.config.

    Both stores are written so launchd jobs (stripped environment, no keychain
    access) can fall back to rbos.config. keyring is preferred for interactive
    reads. Mirrors :func:`set_github_token` minus the GitHub-specific auth-log
    and gh-cli machinery.
    """
    cleaned = token.strip()
    _keyring_set("figma_token", cleaned)  # best-effort; ignored if unavailable
    config = _read_config()
    config["figma_token"] = cleaned
    _write_config(config)


def clear_figma_token() -> None:
    """Remove the stored Figma PAT from both keyring and rbos.config."""
    _keyring_delete("figma_token")
    config = _read_config()
    if "figma_token" in config:
        del config["figma_token"]
        _write_config(config)


def get_figma_file_keys() -> list[str]:
    """Return configured Figma file keys to scan for comments.

    Config key: ``figma_file_keys``. The Figma comments API is file-scoped, so
    the collector needs this explicit allow-list. Not secret — plain config.
    """
    config = _read_config()
    value = config.get("figma_file_keys")
    if not isinstance(value, list):
        return []
    keys: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        key = item.strip()
        if key and key not in keys:
            keys.append(key)
    return keys


def set_figma_file_keys(file_keys: list[str]) -> None:
    """Store the Figma file keys scanned by the Figma comments collector."""
    config = _read_config()
    keys: list[str] = []
    for item in file_keys:
        key = str(item or "").strip()
        if key and key not in keys:
            keys.append(key)
    config["figma_file_keys"] = keys
    _write_config(config)


_figma_key_lock = threading.Lock()


def add_figma_file_key(file_key: str) -> bool:
    """Add one Figma file key to the allow-list.

    Returns True when the key was newly added, False when it was already present.
    The stored list remains de-duplicated in insertion order.
    """
    key = str(file_key or "").strip()
    if not key:
        raise ValueError("file_key must be non-empty")
    with _figma_key_lock:
        existing = get_figma_file_keys()
        if key in existing:
            return False
        set_figma_file_keys(existing + [key])
        return True


def get_gmail_query_filter() -> str | None:
    """Return the configured Gmail search query, or None if unset.

    Config key: ``gmail_query_filter``. Default applied by the caller is
    ``in:inbox`` (see ``rebalance.ingest.gmail.DEFAULT_QUERY_FILTER``).
    Power users can scope to e.g. ``in:inbox -category:promotions``.
    """
    config = _read_config()
    value = config.get("gmail_query_filter")
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def set_gmail_query_filter(query: str) -> None:
    """Store the Gmail search query filter in config."""
    config = _read_config()
    config["gmail_query_filter"] = query.strip()
    _write_config(config)


# ---------------------------------------------------------------------------
# Health notices — demote intentional/non-actionable WARNs to a calmer tier
# ---------------------------------------------------------------------------

def get_health_notice_patterns() -> list[str]:
    """Return check-name substrings the user has demoted to "notices".

    A health WARN whose name contains one of these (case-insensitive) is shown
    in a separate, low-key Notices section instead of counting toward the
    "collector attention needed" verdict. Intended for *intentional* states
    (e.g. a deliberately narrow Gmail filter that reads "stale") or
    *non-actionable-from-here* ones (another machine's pulse collector). FAIL
    checks are never demoted. Config key: ``health_notices`` (list of strings).
    """
    config = _read_config()
    raw = config.get("health_notices")
    if isinstance(raw, list):
        return [str(p).strip() for p in raw if str(p).strip()]
    return []


def add_health_notice_pattern(pattern: str) -> bool:
    """Add a notice pattern. Returns True if added, False if blank/duplicate."""
    pattern = pattern.strip()
    if not pattern:
        return False
    config = _read_config()
    patterns = config.get("health_notices")
    if not isinstance(patterns, list):
        patterns = []
    if pattern in patterns:
        return False
    patterns.append(pattern)
    config["health_notices"] = patterns
    _write_config(config)
    return True


def remove_health_notice_pattern(pattern: str) -> bool:
    """Remove a notice pattern. Returns True if it was present and removed."""
    pattern = pattern.strip()
    config = _read_config()
    patterns = config.get("health_notices")
    if not isinstance(patterns, list) or pattern not in patterns:
        return False
    patterns.remove(pattern)
    config["health_notices"] = patterns
    _write_config(config)
    return True


# ---------------------------------------------------------------------------
# ask_self federation (chat_with_data code/doc retrieval)
# ---------------------------------------------------------------------------

def get_ask_self_path() -> str | None:
    """Return the ask-self install path for chat federation, or None.

    Resolution: ``ASK_SELF_PATH`` env first (per-shell override), then the
    ``ask_self_path`` config key (persisted, so the dashboard server can
    federate too). See PROJECT/2-WORKING/CHAT-WITH-DATA.md.
    """
    env = os.environ.get("ASK_SELF_PATH")
    if env and env.strip():
        return env.strip()
    value = _read_config().get("ask_self_path")
    return value.strip() if isinstance(value, str) and value.strip() else None


def set_ask_self_path(path: str) -> None:
    """Persist the ask-self install path used for chat federation."""
    config = _read_config()
    config["ask_self_path"] = path.strip()
    _write_config(config)


def get_repo_scan_roots() -> list[str]:
    """Return the directories repo-discovery collectors walk on this device.

    Shared by the Focus 5 repo collector and the ask_self index inventory —
    a generic "where do this machine's repos live" setting, not specific to
    ask_self (hence the neutral name; see COLLECTOR-PATH-AND-PORTABILITY-AUDIT).

    Config key: ``repo_scan_roots`` (list of absolute dirs). The legacy
    ``ask_self_scan_roots`` key is still honored as a fallback. When unset,
    defaults to the common dev-checkout parents that actually exist on this
    machine, falling back to the home directory. Keeping this configurable
    means a full-tree walk of ``$HOME`` is opt-in rather than the default.
    """
    config = _read_config()
    raw = config.get("repo_scan_roots")
    if not isinstance(raw, list):
        raw = config.get("ask_self_scan_roots")  # back-compat: pre-decouple key
    if isinstance(raw, list):
        roots = [str(p).strip() for p in raw if str(p).strip()]
        if roots:
            return roots
    home = Path.home()
    candidates = [
        home / "Documents" / "GitHub-Repos",
        home / "Documents" / "GitHub",
        home / "GitHub",
        home / "code",
        home / "src",
        home / "dev",
        home / "repos",
        home / "Projects",
    ]
    existing = [str(c) for c in candidates if c.is_dir()]
    return existing or [str(home)]


def set_repo_scan_roots(roots: list[str]) -> None:
    """Store the directories repo-discovery collectors walk. Config key: ``repo_scan_roots``."""
    cleaned = [str(Path(p).expanduser()) for p in roots if str(p).strip()]
    config = _read_config()
    config["repo_scan_roots"] = cleaned
    _write_config(config)


# Deprecated pre-decouple aliases — kept so existing imports keep working while
# the COLLECTOR-PATH-AND-PORTABILITY-AUDIT rename settles. Prefer the repo_* names.
get_ask_self_scan_roots = get_repo_scan_roots
set_ask_self_scan_roots = set_repo_scan_roots


def get_focus5_scan_roots() -> list[str]:
    """Return the directories the Focus 5 collector walks for git repos.

    Config key: ``focus5_scan_roots``. When unset, reuses the shared
    zero-config discovery defaults (:func:`get_repo_scan_roots`) so the
    operator never has to configure repo locations — Focus 5 just keeps its own
    overridable key for the day the two surfaces want different scopes.
    """
    config = _read_config()
    raw = config.get("focus5_scan_roots")
    if isinstance(raw, list):
        roots = [str(p).strip() for p in raw if str(p).strip()]
        if roots:
            return roots
    return get_repo_scan_roots()


def get_focus5_ranking_mode() -> str:
    """Return the active Focus 5 ranking mode. Config key: ``focus5_ranking_mode``.

    Defaults to ``dirty_first`` (surface uncommitted/unpushed work first). The
    value is validated by the collector against the registered strategies; an
    unknown mode is surfaced as a collector error rather than silently ignored.
    """
    config = _read_config()
    mode = config.get("focus5_ranking_mode")
    if isinstance(mode, str) and mode.strip():
        return mode.strip()
    return "dirty_first"


def set_focus5_ranking_mode(mode: str) -> None:
    """Store the Focus 5 ranking mode. Config key: ``focus5_ranking_mode``."""
    config = _read_config()
    config["focus5_ranking_mode"] = mode.strip()
    _write_config(config)


def get_focus5_hidden_repos() -> list[str]:
    """Return repo identities the operator has hidden from the Focus 5 roster.

    Config key: ``focus5_hidden_repos`` (a list of identity strings). Each entry
    is a repo's ``repo_full_name`` (``owner/repo``) when it has a remote, else its
    device-local path — the same identity :func:`focus5_repo_identity` derives.
    This is a *display* filter (hide from the board); it is independent of
    ``github_ignored_repos``, which suppresses GitHub *ingest*.
    """
    value = _read_config().get("focus5_hidden_repos")
    if not isinstance(value, list):
        return []
    seen: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip() and item.strip() not in seen:
            seen.append(item.strip())
    return seen


def set_focus5_hidden_repos(repos: list[str]) -> None:
    """Store the canonical Focus 5 hidden-repo list. Config key: ``focus5_hidden_repos``."""
    cleaned: list[str] = []
    for r in repos:
        s = str(r).strip()
        if s and s not in cleaned:
            cleaned.append(s)
    config = _read_config()
    config["focus5_hidden_repos"] = cleaned
    _write_config(config)


def add_focus5_hidden_repo(repo: str) -> bool:
    """Hide one repo from the Focus 5 roster. Returns False if already hidden."""
    identity = repo.strip()
    if not identity:
        return False
    existing = get_focus5_hidden_repos()
    if identity in existing:
        return False
    existing.append(identity)
    set_focus5_hidden_repos(existing)
    return True


def remove_focus5_hidden_repo(repo: str) -> bool:
    """Un-hide one repo. Returns False if it was not hidden."""
    identity = repo.strip()
    existing = get_focus5_hidden_repos()
    if identity not in existing:
        return False
    set_focus5_hidden_repos([item for item in existing if item != identity])
    return True


def is_focus5_repo_hidden(repo: str) -> bool:
    """Return True when *repo*'s identity is in the Focus 5 hidden list."""
    return repo.strip() in set(get_focus5_hidden_repos())


GMAIL_INGEST_METHODS = ("oauth", "mcp")


def get_gmail_ingest_method() -> str:
    """Return how Gmail is ingested: ``oauth`` (default) or ``mcp``.

    Config key: ``gmail_ingest_method``.

    - ``oauth`` — the autonomous path: ``sync_gmail`` fetches via a desktop
      OAuth token (browser consent once via ``scripts/setup_gmail_oauth.py``,
      stored in keyring with a pickle-file fallback for launchd). Mirrors the
      Calendar credential model.
    - ``mcp``   — email_messages is populated externally by an agent using the
      Gmail MCP connector (see ``ingest_email_messages``). The launchd email
      job does not fetch in this mode — it cannot reach an MCP connector.
    """
    config = _read_config()
    value = config.get("gmail_ingest_method")
    if isinstance(value, str) and value.strip().lower() in GMAIL_INGEST_METHODS:
        return value.strip().lower()
    return "oauth"


def set_gmail_ingest_method(method: str) -> None:
    """Store the Gmail ingest method (``oauth`` or ``mcp``)."""
    normalized = method.strip().lower()
    if normalized not in GMAIL_INGEST_METHODS:
        raise ValueError(
            f"gmail_ingest_method must be one of {GMAIL_INGEST_METHODS}, got {method!r}"
        )
    config = _read_config()
    config["gmail_ingest_method"] = normalized
    _write_config(config)


def get_github_ignored_repos() -> list[str]:
    """Return the locally configured GitHub repos to skip across ingest."""
    config = _read_config()
    value = config.get("github_ignored_repos")
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        try:
            repo = normalize_github_repo_name(item)
        except ValueError:
            continue
        if repo not in normalized:
            normalized.append(repo)
    return sorted(normalized)


def set_github_ignored_repos(repos: list[str]) -> None:
    """Store the canonical operator-local GitHub ignore list."""
    config = _read_config()
    config["github_ignored_repos"] = _normalize_github_repo_list(repos)
    _write_config(config)


def add_github_ignored_repo(repo: str) -> bool:
    """Add one repo to the operator-local GitHub ignore list."""
    normalized = normalize_github_repo_name(repo)
    existing = get_github_ignored_repos()
    if normalized in existing:
        return False
    existing.append(normalized)
    set_github_ignored_repos(existing)
    return True


def remove_github_ignored_repo(repo: str) -> bool:
    """Remove one repo from the operator-local GitHub ignore list."""
    normalized = normalize_github_repo_name(repo)
    existing = get_github_ignored_repos()
    if normalized not in existing:
        return False
    set_github_ignored_repos([item for item in existing if item != normalized])
    return True


def is_github_repo_ignored(repo: str) -> bool:
    """Return True when the exact repo is in the operator-local ignore list."""
    normalized = normalize_github_repo_name(repo)
    return normalized in set(get_github_ignored_repos())


def get_calendar_ignored_summaries() -> list[str]:
    """Return operator-local calendar event summaries to suppress.

    Patterns are matched case-insensitively as substrings against
    ``calendar_events.summary``. Stored in ``temp/rbos.config`` under
    ``calendar_ignored_summaries`` (list of strings, edited manually).
    """
    config = _read_config()
    value = config.get("calendar_ignored_summaries")
    if not isinstance(value, list):
        return []
    return [s.strip() for s in value if isinstance(s, str) and s.strip()]


def get_github_related_repos(repo: str) -> list[str]:
    """Return repos treated as affiliate implementation repos for a central tracker."""
    normalized_repo = normalize_github_repo_name(repo)
    config = _read_config()
    value = config.get("github_related_repos")
    if not isinstance(value, dict):
        return []
    repos = value.get(normalized_repo) or value.get(repo.strip())
    if repos is None:
        for key, candidate in value.items():
            if isinstance(key, str) and key.lower() == normalized_repo:
                repos = candidate
                break
    if not isinstance(repos, list):
        return []
    normalized: list[str] = []
    for item in repos:
        if not isinstance(item, str):
            continue
        try:
            related_repo = normalize_github_repo_name(item)
        except ValueError:
            continue
        if related_repo != normalized_repo and related_repo not in normalized:
            normalized.append(related_repo)
    return sorted(normalized)


def set_github_related_repos(repo: str, related_repos: list[str]) -> None:
    """Store affiliate implementation repos for one central GitHub tracker repo."""
    normalized_repo = normalize_github_repo_name(repo)
    normalized_related = [
        item
        for item in _normalize_github_repo_list(related_repos)
        if item != normalized_repo
    ]
    config = _read_config()
    value = config.get("github_related_repos")
    mapping = value if isinstance(value, dict) else {}
    mapping[normalized_repo] = normalized_related
    config["github_related_repos"] = mapping
    _write_config(config)


def add_github_related_repo(repo: str, related_repo: str) -> bool:
    """Add one affiliate implementation repo for a central GitHub tracker repo."""
    normalized_related = normalize_github_repo_name(related_repo)
    existing = get_github_related_repos(repo)
    if normalized_related in existing:
        return False
    existing.append(normalized_related)
    set_github_related_repos(repo, existing)
    return True


def remove_github_related_repo(repo: str, related_repo: str) -> bool:
    """Remove one affiliate implementation repo from a central tracker repo."""
    normalized_related = normalize_github_repo_name(related_repo)
    existing = get_github_related_repos(repo)
    if normalized_related not in existing:
        return False
    set_github_related_repos(
        repo,
        [item for item in existing if item != normalized_related],
    )
    return True


def _normalize_priority_tier(value: Any) -> int | None:
    if value in ("", None):
        return None
    try:
        tier = int(value)
    except (TypeError, ValueError):
        return None
    if tier < 1 or tier > 5:
        return None
    return tier


def _normalize_value_score(value: Any) -> int | None:
    if value in ("", None):
        return None
    try:
        score = int(value)
    except (TypeError, ValueError):
        return None
    if score < 1 or score > 10:
        return None
    return score


def _normalize_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    for item in value:
        text = str(item).strip()
        if text and text not in normalized:
            normalized.append(text)
    return normalized


def _normalize_project_priority_rule(rule: dict[str, Any]) -> dict[str, Any] | None:
    name = str(rule.get("name") or "").strip()
    if not name:
        return None
    normalized: dict[str, Any] = {
        "name": name,
        "aliases": _normalize_string_list(rule.get("aliases")),
    }
    client = str(rule.get("client") or "").strip()
    if client:
        normalized["client"] = client
    priority_tier = _normalize_priority_tier(rule.get("priority_tier"))
    if priority_tier is not None:
        normalized["priority_tier"] = priority_tier
    value_score = _normalize_value_score(rule.get("value_score"))
    if value_score is not None:
        normalized["value_score"] = value_score
    value_level = str(rule.get("value_level") or "").strip()
    if value_level:
        normalized["value_level"] = value_level
    risk_level = str(rule.get("risk_level") or "").strip()
    if risk_level:
        normalized["risk_level"] = risk_level
    return normalized


def get_project_priority_rules() -> list[dict[str, Any]]:
    """Return local project/client priority rules from gitignored config."""
    config = _read_config()
    value = config.get("project_priority_rules")
    if not isinstance(value, list):
        return []
    rules: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, dict):
            continue
        normalized = _normalize_project_priority_rule(item)
        if not normalized:
            continue
        key = normalized["name"].casefold()
        if key in seen:
            continue
        seen.add(key)
        rules.append(normalized)
    return rules


def set_project_priority_rule(
    *,
    name: str,
    aliases: list[str] | None = None,
    client: str = "",
    priority_tier: int | None = None,
    value_score: int | None = None,
    value_level: str = "",
    risk_level: str = "",
) -> dict[str, Any]:
    """Upsert one local project/client priority rule."""
    candidate = {
        "name": name,
        "aliases": list(aliases or []),
        "client": client,
        "priority_tier": priority_tier,
        "value_score": value_score,
        "value_level": value_level,
        "risk_level": risk_level,
    }
    normalized = _normalize_project_priority_rule(candidate)
    if normalized is None:
        raise ValueError("Project priority rule requires a non-empty name.")
    if priority_tier is not None and "priority_tier" not in normalized:
        raise ValueError("priority_tier must be between 1 and 5.")
    if value_score is not None and "value_score" not in normalized:
        raise ValueError("value_score must be between 1 and 10.")

    config = _read_config()
    existing = get_project_priority_rules()
    replaced = False
    out: list[dict[str, Any]] = []
    key = normalized["name"].casefold()
    for rule in existing:
        if rule["name"].casefold() == key:
            out.append(normalized)
            replaced = True
        else:
            out.append(rule)
    if not replaced:
        out.append(normalized)
    config["project_priority_rules"] = out
    _write_config(config)
    return normalized


def remove_project_priority_rule(name: str) -> bool:
    """Remove one local project/client priority rule by project name."""
    key = str(name or "").strip().casefold()
    if not key:
        return False
    existing = get_project_priority_rules()
    remaining = [rule for rule in existing if rule["name"].casefold() != key]
    if len(remaining) == len(existing):
        return False
    config = _read_config()
    config["project_priority_rules"] = remaining
    _write_config(config)
    return True


def get_config_path() -> Path:
    """Return the config file path (for user reference)."""
    return _resolved_config_path()


# ---------------------------------------------------------------------------
# Pulse (hourly status report) config
# ---------------------------------------------------------------------------


def get_pulse_config() -> dict[str, Any]:
    """Return the pulse-related config block.

    Keys (all optional; pulse rendering will fail loudly if a required one is
    missing at run time):
      - github_login: GitHub username to attribute work to
      - slack_user_id: Slack user_id for Sleuth reminders assigned to/by you
      - pulse_target_path: absolute path to the local clone of the destination
        git repo (e.g. a private "git-pulse-sync" working tree)
      - pulse_filename: relative path of the markdown file inside the target
        repo (default: "live-pulse.md")
      - pulse_timezone: IANA timezone name for "today" / "yesterday" boundaries
        (default: read from CalendarConfig if available)
      - sleuth_ignored_workspaces: list of Slack workspace_name values to
        suppress from pulse Sleuth surfacing (e.g. ["neochrome-dev"] hides
        test-bot reminders so only Sleuth AI v2 in `neochrome` appears).
    """
    config = _read_config()
    return {
        "github_login": config.get("github_login"),
        "slack_user_id": config.get("slack_user_id"),
        "pulse_target_path": config.get("pulse_target_path"),
        "pulse_filename": config.get("pulse_filename", "live-pulse.md"),
        "pulse_timezone": config.get("pulse_timezone"),
        "sleuth_ignored_workspaces": config.get("sleuth_ignored_workspaces") or [],
    }


def set_pulse_config(**values: Any) -> None:
    """Update one or more pulse config keys. Pass None to leave a key unchanged."""
    allowed = {"github_login", "slack_user_id", "pulse_target_path", "pulse_filename", "pulse_timezone"}
    config = _read_config()
    for key, value in values.items():
        if key not in allowed:
            raise ValueError(f"Unknown pulse config key: {key}")
        if value is None:
            continue
        config[key] = str(value).strip() if isinstance(value, str) else value
    _write_config(config)


# ---------------------------------------------------------------------------
# Calendar OAuth token (keyring-backed)
# ---------------------------------------------------------------------------

def get_calendar_oauth_token_json() -> str | None:
    """Return the serialized Google OAuth2 token JSON from keyring, or None if absent."""
    return _keyring_get("calendar_oauth_token")


def set_calendar_oauth_token_json(token_json: str, *, source: str = "manual", record: bool = True) -> bool:
    """Store the serialized Google OAuth2 token JSON in keyring.

    Returns True on success. If keyring is unavailable, returns False and the
    caller should fall back to the existing pickle-file storage path.

    When *record* is True (an explicit (re)authorization — migration or OAuth
    flow — not an automatic access-token refresh), logs a `token_set` auth-log
    event + sidecar metadata keyed on the stable ``refresh_token`` so the
    authorization's age is tracked (and not reset on every access-token refresh).
    """
    ok = _keyring_set("calendar_oauth_token", token_json)
    if ok and record:
        try:  # never let logging break a credential write
            import json as _json
            from rebalance.ingest import auth_log, token_meta  # noqa: PLC0415
            refresh = str((_json.loads(token_json) or {}).get("refresh_token") or "")
            auth_log.log_calendar_token_set(source=source)
            if refresh:
                token_meta.record_token_set("calendar", refresh, kind="google oauth", source=source)
        except Exception:  # noqa: BLE001
            pass
    return ok


def clear_calendar_oauth_token() -> None:
    """Remove the Calendar OAuth token from keyring."""
    _keyring_delete("calendar_oauth_token")


# ---------------------------------------------------------------------------
# Gmail OAuth token (keyring-backed) — mirrors the Calendar helpers above
# ---------------------------------------------------------------------------

def get_gmail_oauth_token_json() -> str | None:
    """Return the serialized Gmail OAuth2 token JSON from keyring, or None if absent."""
    return _keyring_get("gmail_oauth_token")


def set_gmail_oauth_token_json(token_json: str, *, source: str = "manual", record: bool = True) -> bool:
    """Store the serialized Gmail OAuth2 token JSON in keyring.

    Returns True on success. If keyring is unavailable, returns False and the
    caller should fall back to the pickle-file storage path (launchd-reachable).

    When *record* is True (an explicit (re)authorization — migration or OAuth
    flow — not an automatic access-token refresh), logs a `token_set` auth-log
    event + sidecar metadata keyed on the stable ``refresh_token`` so the
    authorization's age is tracked (and not reset on every access-token refresh).
    """
    ok = _keyring_set("gmail_oauth_token", token_json)
    if ok and record:
        try:  # never let logging break a credential write
            import json as _json
            from rebalance.ingest import auth_log, token_meta  # noqa: PLC0415
            refresh = str((_json.loads(token_json) or {}).get("refresh_token") or "")
            auth_log.log_gmail_token_set(source=source)
            if refresh:
                token_meta.record_token_set("gmail", refresh, kind="google oauth", source=source)
        except Exception:  # noqa: BLE001
            pass
    return ok


def clear_gmail_oauth_token() -> None:
    """Remove the Gmail OAuth token from keyring."""
    _keyring_delete("gmail_oauth_token")


# ---------------------------------------------------------------------------
# Sync repo config (Issue #39 — multi-device snapshot sharing)
# ---------------------------------------------------------------------------

def get_sync_subdir() -> str:
    """Return the subfolder within pulse_target_path used for device snapshots.

    Defaults to 'sync'. Snapshots are written as:
      {pulse_target_path}/{sync_subdir}/calendar/{device_id}.json
      {pulse_target_path}/{sync_subdir}/email/{device_id}.json
    """
    config = _read_config()
    return str(config.get("sync_subdir") or "sync")


def set_sync_subdir(subdir: str) -> None:
    """Override the sync subfolder name (default: 'sync')."""
    config = _read_config()
    config["sync_subdir"] = subdir.strip()
    _write_config(config)


# ---------------------------------------------------------------------------
# LLM API keys
# ---------------------------------------------------------------------------

def get_anthropic_api_key() -> str | None:
    """Return the Anthropic API key from the environment, or None if absent."""
    return os.environ.get("ANTHROPIC_API_KEY")


def get_gemini_api_key() -> str | None:
    """Return the Gemini API key.

    Resolution order:
      1. Google Secret Manager (requires google-cloud-secret-manager and
         GOOGLE_CLOUD_PROJECT env var; secret name from GEMINI_SECRET_NAME,
         default "gemini-api-key")
      2. GEMINI_API_KEY environment variable
      3. GOOGLE_API_KEY environment variable
    """
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if project:
        secret_name = os.environ.get("GEMINI_SECRET_NAME", "gemini-api-key")
        try:
            from google.cloud import secretmanager  # noqa: PLC0415
            client = secretmanager.SecretManagerServiceClient()
            resource = f"projects/{project}/secrets/{secret_name}/versions/latest"
            response = client.access_secret_version(request={"name": resource})
            value = response.payload.data.decode("utf-8").strip()
            if value:
                return value
        except Exception:  # noqa: BLE001 — library absent or secret missing
            pass
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")


# ---------------------------------------------------------------------------
# Sleuth credentials
# ---------------------------------------------------------------------------

_SLEUTH_REQUIRED = ("SLEUTH_WEB_API_BASE_URL", "SLEUTH_WEB_API_TOKEN", "SLEUTH_WORKSPACE_NAME")


SLEUTH_KEYRING_KEY = "sleuth_web_api"  # JSON blob in keyring + rbos.config


def _sleuth_creds_complete(values: object) -> dict[str, str] | None:
    """Return normalized creds if every required key is present and non-empty."""
    if not isinstance(values, dict):
        return None
    out = {k: str(values.get(k) or "").strip() for k in _SLEUTH_REQUIRED}
    return out if all(out.values()) else None


def set_sleuth_credentials(
    base_url: str, token: str, workspace: str, *, source: str = "manual"
) -> None:
    """Store Sleuth Web API creds in the OS keyring AND rbos.config.

    Mirrors set_github_token: keyring is the interactive primary; rbos.config is
    the launchd safety net (the Sleuth daily-sync runs unattended and cannot reach
    the keychain). Logs a `token_set` auth-log event + sidecar first-added metadata.
    """
    import json as _json

    creds = {
        "SLEUTH_WEB_API_BASE_URL": base_url.strip(),
        "SLEUTH_WEB_API_TOKEN": token.strip(),
        "SLEUTH_WORKSPACE_NAME": workspace.strip(),
    }
    _keyring_set(SLEUTH_KEYRING_KEY, _json.dumps(creds))
    config = _read_config()
    config[SLEUTH_KEYRING_KEY] = creds
    _write_config(config)
    try:  # never let logging break a credential write
        from rebalance.ingest import auth_log, token_meta  # noqa: PLC0415
        auth_log.log_sleuth_credentials_set(source=source, workspace=creds["SLEUTH_WORKSPACE_NAME"])
        token_meta.record_token_set(
            "sleuth", creds["SLEUTH_WEB_API_TOKEN"], kind="sleuth web api", source=source
        )
    except Exception:  # noqa: BLE001
        pass


def clear_sleuth_credentials() -> None:
    """Remove Sleuth creds from keyring + rbos.config (the env file is left alone)."""
    _keyring_delete(SLEUTH_KEYRING_KEY)
    config = _read_config()
    if SLEUTH_KEYRING_KEY in config:
        del config[SLEUTH_KEYRING_KEY]
        _write_config(config)


def get_sleuth_credentials(which: str = "production") -> dict[str, str]:
    """Resolve Sleuth Web API creds: keyring → rbos.config → legacy env file.

    Mirrors the github token resolution (keyring-primary + config fallback for
    launchd) so secrets are stored consistently. The operator-owned
    ``sleuth-web-api-{which}.env`` remains a backward-compatible fallback.

    Raises FileNotFoundError if nothing resolves; ValueError if a resolved source
    is missing required keys.
    """
    import json as _json

    blob = _keyring_get(SLEUTH_KEYRING_KEY)
    if blob:
        try:
            creds = _sleuth_creds_complete(_json.loads(blob))
        except (ValueError, TypeError):
            creds = None
        if creds:
            return creds
    creds = _sleuth_creds_complete(_read_config().get(SLEUTH_KEYRING_KEY))
    if creds:
        return creds
    return _read_sleuth_env_file(which)


def _read_sleuth_env_file(which: str = "production") -> dict[str, str]:
    """Legacy fallback — load Sleuth creds from the operator-owned env file.

    Looks up ``sleuth-web-api-{which}.env`` (default: production), falling back to
    the development env file. Raises FileNotFoundError if neither exists, or
    ValueError if required keys are missing.
    """
    from rebalance.paths import resolve_secret_path

    primary = resolve_secret_path(f"sleuth-web-api-{which}.env")
    fallback = resolve_secret_path("sleuth-web-api-development.env")
    if primary.exists():
        path = primary
    elif fallback.exists():
        path = fallback
    else:
        raise FileNotFoundError(
            f"Sleuth env file not found: tried {primary} then {fallback}"
        )

    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()

    missing = [k for k in _SLEUTH_REQUIRED if not values.get(k)]
    if missing:
        raise ValueError(
            f"Sleuth env file missing required keys: {', '.join(missing)} (in {path})"
        )
    return values


def get_sleuth_client_mapping_path() -> str:
    """Return the configured path to client-channel-mapping.json, or '' if unset.

    When set, sleuth_grouping.py uses this path instead of the sibling-checkout
    heuristic. Set with ``rebalance config set-sleuth-mapping-path <path>`` or
    directly in temp/rbos.config under ``sleuth_client_mapping_path``.
    """
    return str(_read_config().get("sleuth_client_mapping_path", ""))


def set_sleuth_client_mapping_path(path: str) -> None:
    """Store the path to client-channel-mapping.json in rbos.config."""
    config = _read_config()
    config["sleuth_client_mapping_path"] = path
    _write_config(config)
