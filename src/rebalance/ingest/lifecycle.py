"""Onboarding and project lifecycle contract (Phase 5).

Two machine-readable maps, both queryable without an LLM. They are the
single source of truth the Phase 6 welcome agent — and any other client
(CLI, doctor, tests) — renders. Clients never re-declare stages.

1. PROJECT_LIFECYCLE — what happens to a *project* as it moves through the
   system: which function owns each stage and whether that stage may write
   durable registry state. The write-semantics vocabulary is the contract:

   - ``read_only``            never writes; safe to re-run any number of times
   - ``confirmation_gated``   the ONLY path that writes curated registry state,
                              and only with an explicitly confirmed payload
   - ``machine_owned``        maintains rows it created (marked by provenance);
                              must never create, update, or delete curated rows
   - ``read_time_overlay``    transforms query results in memory; never persists

2. SETUP_STAGES — the ordered setup journey a new operator walks (config,
   vault, auth, discovery, persistence), each with a cheap local check and a
   remediation hint. :func:`evaluate_setup` assigns each stage one status:

   - ``done``     the stage's exit condition is verified right now
   - ``now``      the first incomplete required stage whose prerequisites are
                  all done (at most one stage is ``now``)
   - ``next``     incomplete, prerequisites met, but not the current focus —
                  includes reachable optional stages, so agents offer rather
                  than silently skip them
   - ``blocked``  incomplete and at least one prerequisite is not done
   - ``skipped``  optional stage the operator deliberately skipped (persisted
                  in rbos.config via ``set_onboarding_stage_skipped``); still
                  re-enterable — completing it flips it to ``done``, and
                  un-skipping returns it to ``next`` (contract v2).
                  Precedence: ``done`` > ``blocked`` > ``skipped`` — a skip
                  marker never masks unmet prerequisites, so clients may
                  execute any ``skipped`` stage without re-checking deps

Each stage also carries an ``executor`` hint — the machine-actionable way to
complete it, in a small vocabulary the welcome agent can dispatch on:
``mcp:<tool>`` (call an MCP tool), ``cli:<command>`` (run a CLI command),
``script:<path>`` (run a repo script; OAuth consent flows). Remediation prose
stays human-facing; the executor is for agents (contract v2, spike finding).

Adding a stage = adding one entry to the relevant tuple (plus, for setup
stages, a check function). Clients pick it up without edits.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

CONTRACT_VERSION = 2

STATUS_DONE = "done"
STATUS_NOW = "now"
STATUS_NEXT = "next"
STATUS_BLOCKED = "blocked"
STATUS_SKIPPED = "skipped"
SETUP_STATUS_VALUES = (STATUS_DONE, STATUS_NOW, STATUS_NEXT, STATUS_BLOCKED, STATUS_SKIPPED)

EXECUTOR_KINDS = ("mcp", "cli", "script")

WRITE_SEMANTICS_VALUES = (
    "read_only",
    "confirmation_gated",
    "machine_owned",
    "read_time_overlay",
)


# ---------------------------------------------------------------------------
# Map 1: project lifecycle — ownership and write semantics
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProjectStage:
    """One stage of a project's journey through the system."""

    id: str
    title: str
    owner: str  # "module:function" — the single function that owns this stage
    write_semantics: str  # one of WRITE_SEMANTICS_VALUES
    description: str


PROJECT_LIFECYCLE: tuple[ProjectStage, ...] = (
    ProjectStage(
        id="discovery",
        title="Discovery",
        owner="rebalance.ingest.preflight:discover_candidates",
        write_semantics="read_only",
        description=(
            "Candidates assembled from remote GitHub activity and vault note "
            "titles. Each candidate carries a `provenance` field "
            "(remote-activity | vault-note; local-scan reserved for Phase 6)."
        ),
    ),
    ProjectStage(
        id="review",
        title="Review",
        owner="(host agent / CLI prompt)",
        write_semantics="read_only",
        description=(
            "The operator curates the candidate list — edits summaries, "
            "priorities, tags. Purely in-memory; nothing persists yet."
        ),
    ),
    ProjectStage(
        id="confirmation",
        title="Confirmation (promote)",
        owner="rebalance.ingest.preflight:confirm_and_write",
        write_semantics="confirmation_gated",
        description=(
            "The ONLY write path for curated registry state. Writes the "
            "registry markdown, then pull-syncs projects.yaml and the "
            "project_registry table."
        ),
    ),
    ProjectStage(
        id="persistence",
        title="Persistence",
        owner="rebalance.ingest.registry:sync_registry",
        write_semantics="confirmation_gated",
        description=(
            "Materializes the confirmed registry into projects.yaml and "
            "SQLite. Deterministic projection of confirmed state — runs only "
            "downstream of confirmation or an explicit operator sync command."
        ),
    ),
    ProjectStage(
        id="inference",
        title="Inference",
        owner="rebalance.ingest.project_inference:sync_inferred_project_registry",
        write_semantics="machine_owned",
        description=(
            "Activity-derived project rows, marked by "
            "custom_fields.inference.generated_by. Maintains only rows it "
            "created: curated rows are never created, updated, or deleted by "
            "inference — operator state always wins."
        ),
    ),
    ProjectStage(
        id="prioritization",
        title="Prioritization",
        owner="rebalance.ingest.project_priority:apply_project_priorities",
        write_semantics="read_time_overlay",
        description=(
            "Operator priority rules from temp/rbos.config overlay scores at "
            "read time. Never persisted back to the registry."
        ),
    ),
)


# ---------------------------------------------------------------------------
# Map 2: setup stages — the onboarding journey
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SetupStage:
    """One stage of the operator setup journey.

    ``check`` returns ``(complete, detail)``; it must be cheap, local, and
    side-effect free. ``requires`` lists prerequisite stage ids — an
    incomplete prerequisite makes this stage ``blocked``.
    """

    id: str
    title: str
    check: Callable[["SetupContext"], tuple[bool, str]]
    remediation: str
    executor: str = ""  # "<kind>:<target>", kind in EXECUTOR_KINDS
    optional: bool = False
    requires: tuple[str, ...] = ()


@dataclass(frozen=True)
class SetupContext:
    vault_path: Path | None
    database_path: Path | None


def _check_config_exists(ctx: SetupContext) -> tuple[bool, str]:
    from rebalance.ingest.config import get_config_path

    path = get_config_path()
    return path.exists(), str(path)


def _check_vault_path_set(ctx: SetupContext) -> tuple[bool, str]:
    from rebalance.ingest.config import get_vault_path

    configured = (get_vault_path() or "").strip()
    if configured and Path(configured).expanduser().exists():
        return True, configured
    if configured:
        return False, f"configured but missing on disk: {configured}"
    return False, "vault path not configured"


def _check_github_token(ctx: SetupContext) -> tuple[bool, str]:
    from rebalance.ingest.config import get_github_token

    token = get_github_token()
    return token is not None, "token configured" if token else "no token found"


def _oauth_token_file_exists(service: str) -> bool:
    """File-fallback probe (review finding): the runtime collectors read a
    token FILE via resolve_oauth_token_path, not just the keyring — a
    file-only machine has working auth and must not show the stage
    incomplete. Machine-global path, so hermetic mode skips it."""
    from rebalance.ingest.config import _hermetic

    if _hermetic():
        return False
    from rebalance.paths import resolve_oauth_token_path

    try:
        return resolve_oauth_token_path(service).exists()
    except Exception:  # noqa: BLE001 — unresolvable path = no file token
        return False


def _check_calendar_auth(ctx: SetupContext) -> tuple[bool, str]:
    from rebalance.ingest.config import get_calendar_oauth_token_json

    if get_calendar_oauth_token_json():
        return True, "OAuth token present (keyring)"
    if _oauth_token_file_exists("calendar"):
        return True, "OAuth token present (file)"
    return False, "no Calendar OAuth token"


def _check_gmail_auth(ctx: SetupContext) -> tuple[bool, str]:
    from rebalance.ingest.config import get_gmail_oauth_token_json

    if get_gmail_oauth_token_json():
        return True, "OAuth token present (keyring)"
    if _oauth_token_file_exists("gmail"):
        return True, "OAuth token present (file)"
    return False, "no Gmail OAuth token"


def _registry_path(ctx: SetupContext) -> Path | None:
    if ctx.vault_path is None:
        return None
    return ctx.vault_path / "Projects" / "00-project-registry.md"


def _check_registry_exists(ctx: SetupContext) -> tuple[bool, str]:
    path = _registry_path(ctx)
    if path is None:
        return False, "vault path unknown"
    return path.exists(), str(path)


def _check_projection_exists(ctx: SetupContext) -> tuple[bool, str]:
    if ctx.vault_path is None:
        return False, "vault path unknown"
    path = ctx.vault_path / "projects.yaml"
    return path.exists(), str(path)


# Patchable seams for the graduation checks — both read machine-global
# locations (LaunchAgents, the repo's web/ dir), so hermetic sandboxes
# override these the same way REBALANCE_NO_KEYRING covers the keyring.
def _launch_agents_dir() -> Path:
    return Path.home() / "Library" / "LaunchAgents"


def _pulse_html_path() -> Path | None:
    from rebalance.paths import find_project_root

    root = find_project_root(Path(__file__).resolve())
    return (root / "web" / "pulse.html") if root else None


def _check_schedulers_installed(ctx: SetupContext) -> tuple[bool, str]:
    plist = _launch_agents_dir() / "com.rebalance-os.daily-sync.plist"
    if plist.exists():
        return True, f"daily-sync installed ({plist})"
    return False, "daily-sync launchd job not installed"


def _check_first_pulse(ctx: SetupContext) -> tuple[bool, str]:
    path = _pulse_html_path()
    if path is None:
        return False, "repo root not found"
    return path.exists(), str(path)


def _check_db_synced(ctx: SetupContext) -> tuple[bool, str]:
    if ctx.database_path is None or not ctx.database_path.exists():
        return False, str(ctx.database_path or "database path unknown")
    try:
        from rebalance.ingest.registry import get_projects

        count = len(get_projects(ctx.database_path))
    except Exception as exc:  # pragma: no cover - defensive: unreadable DB
        return False, f"could not read project_registry: {exc}"
    return count > 0, f"{count} project(s) in {ctx.database_path}"


SETUP_STAGES: tuple[SetupStage, ...] = (
    SetupStage(
        id="config_exists",
        title="Operator config",
        check=_check_config_exists,
        remediation="Any config write creates it — e.g. `rebalance config set-vault-path <path>`.",
        executor="cli:rebalance config set-vault-path <path>",
    ),
    SetupStage(
        id="vault_path_set",
        title="Obsidian vault path",
        check=_check_vault_path_set,
        remediation="Run `rebalance config set-vault-path <path>` with an existing folder.",
        executor="cli:rebalance config set-vault-path <path>",
        requires=("config_exists",),
    ),
    SetupStage(
        id="github_token_set",
        title="GitHub PAT",
        check=_check_github_token,
        remediation="Use the setup_github_token MCP tool or `rebalance config set-github-token`.",
        executor="mcp:setup_github_token",
    ),
    SetupStage(
        id="calendar_auth",
        # Titles never encode optionality — the `optional` flag is the
        # machine-readable source; renderers decorate (spike finding).
        title="Google Calendar",
        check=_check_calendar_auth,
        remediation="Run `python scripts/setup_calendar_oauth.py` and complete the browser consent.",
        executor="script:scripts/setup_calendar_oauth.py",
        optional=True,
        requires=("config_exists",),
    ),
    SetupStage(
        id="gmail_auth",
        title="Gmail",
        check=_check_gmail_auth,
        remediation="Run `python scripts/setup_gmail_oauth.py` and complete the browser consent.",
        executor="script:scripts/setup_gmail_oauth.py",
        optional=True,
        requires=("config_exists",),
    ),
    SetupStage(
        id="registry_exists",
        title="Project registry confirmed",
        check=_check_registry_exists,
        remediation="Run run_preflight, review candidates, then confirm_projects (or `rebalance onboard`).",
        executor="mcp:run_preflight",
        requires=("vault_path_set", "github_token_set"),
    ),
    SetupStage(
        id="projection_exists",
        title="projects.yaml projection",
        check=_check_projection_exists,
        remediation="confirm_projects pull-syncs it; or run `rebalance ingest sync --mode pull`.",
        executor="mcp:confirm_projects",
        requires=("registry_exists",),
    ),
    SetupStage(
        id="db_synced",
        title="SQLite registry synced",
        check=_check_db_synced,
        remediation="confirm_projects pull-syncs it; or run `rebalance ingest sync --mode pull`.",
        executor="mcp:confirm_projects",
        requires=("registry_exists",),
    ),
    # Graduation (Phase 6): optional so portable/Linux installs without
    # launchd can still reach setup_complete — but the welcome agent always
    # offers them; first pulse is the journey's intended endpoint.
    SetupStage(
        id="schedulers_installed",
        title="Scheduled sync fleet",
        check=_check_schedulers_installed,
        remediation="Install the daily job, then the hourly jobs per SCHEDULER.md: `bash scripts/install_scheduler.sh`.",
        executor="cli:bash scripts/install_scheduler.sh",
        optional=True,
        requires=("db_synced",),
    ),
    SetupStage(
        id="first_pulse",
        title="First pulse rendered",
        check=_check_first_pulse,
        remediation="Render web/pulse.html: `bash scripts/pulse_web_sync.sh`, then open it.",
        executor="cli:bash scripts/pulse_web_sync.sh",
        optional=True,
        requires=("db_synced",),
    ),
)


def project_lifecycle_map() -> list[dict[str, Any]]:
    """The project-lifecycle ownership table as plain dicts.

    Runtime consumers (onboarding_status, the Phase 6 welcome agent) use this
    to explain the write discipline — e.g. "confirmation is the only curated
    write path" — without re-declaring it.
    """
    return [
        {
            "id": stage.id,
            "title": stage.title,
            "owner": stage.owner,
            "write_semantics": stage.write_semantics,
            "description": stage.description,
        }
        for stage in PROJECT_LIFECYCLE
    ]


def evaluate_setup(
    *,
    vault_path: Path | None,
    database_path: Path | None,
) -> dict[str, Any]:
    """Evaluate every setup stage and assign the status vocabulary.

    Pure read: every check is local and side-effect free, so calling this
    repeatedly (an agent re-polling "where am I") is always safe.
    """
    from rebalance.ingest.config import get_onboarding_skipped_stages

    ctx = SetupContext(vault_path=vault_path, database_path=database_path)
    skipped_ids = set(get_onboarding_skipped_stages())

    results: dict[str, dict[str, Any]] = {}
    for stage in SETUP_STAGES:
        complete, detail = stage.check(ctx)
        results[stage.id] = {
            "id": stage.id,
            "title": stage.title,
            "optional": stage.optional,
            "requires": list(stage.requires),
            "complete": complete,
            "detail": detail,
            "executor": stage.executor,
        }

    now_assigned = False
    for stage in SETUP_STAGES:
        entry = results[stage.id]
        if entry["complete"]:
            # Completing a stage always wins over a stale skip marker.
            entry["status"] = STATUS_DONE
            continue
        deps_done = all(results[dep]["complete"] for dep in stage.requires)
        # Precedence: blocked beats skipped (review finding). A skip marker
        # is an operator preference; unmet prerequisites are a structural
        # fact — clients may safely execute any `skipped` stage on request
        # without re-verifying dependencies themselves.
        if not deps_done:
            entry["status"] = STATUS_BLOCKED
        elif stage.optional and stage.id in skipped_ids:
            entry["status"] = STATUS_SKIPPED
        elif not now_assigned and not stage.optional:
            entry["status"] = STATUS_NOW
            now_assigned = True
        else:
            entry["status"] = STATUS_NEXT
        entry["remediation"] = stage.remediation

    stages = [results[stage.id] for stage in SETUP_STAGES]
    now_ids = [s["id"] for s in stages if s["status"] == STATUS_NOW]
    required_remaining = [
        s["id"] for s in stages if not s["optional"] and not s["complete"]
    ]
    return {
        "contract_version": CONTRACT_VERSION,
        "stages": stages,
        "now": now_ids[0] if now_ids else None,
        "required_remaining": required_remaining,
        "setup_complete": not required_remaining,
    }
