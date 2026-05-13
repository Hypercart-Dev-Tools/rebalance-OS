"""
Configuration loader for rebalance — secrets, API credentials, etc.

Storage path: temp/rbos.config (gitignored, at workspace root)
Format: JSON

Future: Migrate sensitive fields to keyring library when multi-user or compliance required.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any


# Resolve to repo root: __file__ is src/rebalance/ingest/config.py
# Parent chain: config.py -> ingest -> rebalance -> src -> rebalance-OS (root)
CONFIG_PATH = Path(__file__).parent.parent.parent.parent / "temp" / "rbos.config"
_GITHUB_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def _ensure_config_dir() -> None:
    """Create temp/ dir if missing."""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)


def _read_config() -> dict[str, Any]:
    """Load config from disk; return {} if missing."""
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return {}


def _write_config(config: dict[str, Any]) -> None:
    """Write config to disk with .gitignore safety."""
    _ensure_config_dir()
    CONFIG_PATH.write_text(json.dumps(config, indent=2), encoding="utf-8")


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


def get_github_token_with_source() -> tuple[str | None, str | None]:
    """
    Resolve a GitHub token. Returns (token, source) where source is one of:
      "config"  — token came from temp/rbos.config
      "gh-cli"  — fell back to `gh auth token`
      None      — neither available

    Resolution order is config first, then gh CLI. This keeps explicit
    PATs authoritative when both are present, so a user who set a token
    deliberately won't be silently overridden by an ambient gh login.
    """
    config = _read_config()
    token = config.get("github_token")
    if token:
        return token, "config"
    token = _try_gh_cli_token()
    if token:
        return token, "gh-cli"
    return None, None


def get_github_token() -> str | None:
    """
    Get GitHub token. Falls back to `gh auth token` if no PAT is in config.

    Config key: github_token
    """
    token, _source = get_github_token_with_source()
    return token


def set_github_token(token: str) -> None:
    """Store GitHub PAT in config."""
    config = _read_config()
    config["github_token"] = token.strip()
    _write_config(config)


def clear_github_token() -> None:
    """Remove the stored GitHub PAT from config (e.g. to switch to `gh auth token`)."""
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
    return CONFIG_PATH


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
