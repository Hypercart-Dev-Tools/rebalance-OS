"""The TOML registry — the single source of truth for 3-Eyes jobs (GH-195).

Three kinds of file under ``registry/``:

  * ``jobs.d/*.toml``   — one job per file (command, schedule, rules, breakers,
                          routes, relief).
  * ``commands.allow``  — the ONLY commands a job may execute, by name. A job that
                          names a command absent here is a hard validation error;
                          there is no free-form command execution anywhere.
  * ``routes.toml``     — the finding sinks a job may target (pdda-inbox, notify,
                          gh-issue, log-only) and their config.

Parsing is stdlib ``tomllib`` so the launchd run-path needs no install step. The
registry is authored by hand in TOML; ``DASHBOARD.md`` is a *generated projection*
of it (see ``dashboard.py``), never the other way round.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from . import config

#: Every finding sink 3-Eyes knows how to dispatch. A job route must be one of
#: these AND be declared in routes.toml.
KNOWN_ROUTES = ("pdda-inbox", "notify", "gh-issue", "log-only")

#: A job id must be a safe token — it is interpolated into a crontab line and a
#: launchd label, so anything outside this set is a command-injection vector
#: (GH-195 review B2). Lowercase alnum with -/./_ separators, must start alnum.
JOB_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")

#: A single crontab field: digits, *, and the , - / operators only. No spaces,
#: no shell metacharacters, no newlines — so ``expr`` cannot smuggle a command.
_CRON_FIELD_RE = re.compile(r"^[0-9*/,\-]+$")


def cron_expr_problem(expr: str) -> str | None:
    """Return a problem string if ``expr`` is not a safe 5-field cron spec, else None."""
    if not isinstance(expr, str) or "\n" in expr or "\r" in expr:
        return "cron expr must be a single line"
    fields = expr.split()
    if len(fields) != 5:
        return f"cron expr must have exactly 5 fields, got {len(fields)}"
    for f in fields:
        if not _CRON_FIELD_RE.match(f):
            return f"cron field {f!r} has illegal characters (only 0-9 * , - / allowed)"
    return None


class RegistryError(ValueError):
    """A job/command/route definition is invalid. Message names the offender."""


@dataclass(frozen=True)
class Job:
    """One scheduled, safety-bounded local job."""

    id: str
    command: str
    schedule: dict = field(default_factory=dict)
    rules: dict = field(default_factory=dict)
    breakers: dict = field(default_factory=dict)
    routes: tuple[str, ...] = ()
    relief: dict = field(default_factory=dict)
    enabled: bool = True
    description: str = ""
    #: Legacy launchd labels this job REPLACES. Adoption means one emitter, not two:
    #: install refuses while any of these is still loaded, so a managed job can never
    #: silently run alongside the ad-hoc agent it supersedes.
    supersedes: tuple[str, ...] = ()
    source_path: Path | None = None

    # -- convenience accessors -------------------------------------------- #

    @property
    def max_rss_gb(self) -> float | None:
        v = self.breakers.get("max_rss_gb")
        return float(v) if v is not None else None

    @property
    def single_instance(self) -> bool:
        return bool(self.breakers.get("single_instance", True))

    @property
    def trip_after_failures(self) -> int:
        return int(self.breakers.get("trip_after_failures", 0) or 0)

    @property
    def quiet_hours(self) -> str | None:
        return self.rules.get("quiet_hours")

    def launchd_interval(self) -> int | None:
        node = self.schedule.get("launchd") or {}
        v = node.get("StartInterval")
        return int(v) if v is not None else None

    def launchd_calendar(self) -> dict | None:
        node = self.schedule.get("launchd") or {}
        return node.get("StartCalendarInterval")

    def cron_expr(self) -> str | None:
        node = self.schedule.get("cron") or {}
        return node.get("expr")

    def schedule_summary(self) -> str:
        if self.launchd_interval() is not None:
            return f"launchd every {self.launchd_interval()}s"
        cal = self.launchd_calendar()
        if cal:
            return f"launchd calendar {cal}"
        if self.cron_expr():
            return f"cron {self.cron_expr()!r}"
        return "unscheduled"


def _read_toml(path: Path) -> dict:
    try:
        with open(path, "rb") as fh:
            return tomllib.load(fh)
    except FileNotFoundError:
        return {}
    except tomllib.TOMLDecodeError as exc:
        raise RegistryError(f"{path.name}: invalid TOML — {exc}") from exc


def _parse_commands_allow(path: Path, out: dict[str, dict]) -> None:
    """Merge one commands.allow file into ``out`` (later files override by name)."""
    data = _read_toml(path)
    commands = data.get("commands", data)  # allow either [commands] table or top-level
    for name, spec in commands.items():
        if not isinstance(spec, dict) or "exec" not in spec:
            raise RegistryError(
                f"{path.name}: {name!r} must be a table with an 'exec' key"
            )
        out[name] = {
            "exec": str(spec["exec"]),
            "args": list(spec.get("args", [])),
            "description": str(spec.get("description", "")),
        }


def load_commands_allow(
    registry_dir: Path | None = None, include_local: bool = True
) -> dict[str, dict]:
    """The command allowlist: name → {exec, args, description}.

    ``include_local`` also merges the gitignored ``commands.local.allow`` overlay
    (machine-specific absolute-path commands). The committed dashboard renders with
    ``include_local=False`` so it never depends on another machine's local commands.
    """
    reg = registry_dir or config.REGISTRY_DIR
    out: dict[str, dict] = {}
    _parse_commands_allow(reg / "commands.allow", out)
    if include_local:
        local = reg / "commands.local.allow"
        if local.exists():
            _parse_commands_allow(local, out)
    return out


def load_routes(registry_dir: Path | None = None) -> dict[str, dict]:
    """Configured finding sinks: name → config table."""
    path = (registry_dir or config.REGISTRY_DIR) / "routes.toml"
    data = _read_toml(path)
    routes = data.get("routes", data)
    out: dict[str, dict] = {}
    for name, spec in routes.items():
        out[name] = dict(spec) if isinstance(spec, dict) else {}
    return out


def _job_from_toml(data: dict, source: Path) -> Job:
    if "id" not in data:
        raise RegistryError(f"{source.name}: missing required key 'id'")
    if "command" not in data:
        raise RegistryError(f"{source.name}: job {data['id']!r} missing 'command'")
    routes = data.get("routes", [])
    if isinstance(routes, str):
        routes = [routes]
    supersedes = data.get("supersedes", [])
    if isinstance(supersedes, str):
        supersedes = [supersedes]
    return Job(
        id=str(data["id"]),
        command=str(data["command"]),
        schedule=dict(data.get("schedule", {})),
        rules=dict(data.get("rules", {})),
        breakers=dict(data.get("breakers", {})),
        routes=tuple(str(r) for r in routes),
        relief=dict(data.get("relief", {})),
        enabled=bool(data.get("enabled", True)),
        description=str(data.get("description", "")),
        supersedes=tuple(str(s) for s in supersedes),
        source_path=source,
    )


def load_jobs(registry_dir: Path | None = None, include_local: bool = True) -> list[Job]:
    """Load every ``jobs.d/*.toml`` as a :class:`Job`, sorted by id.

    Sorting is what makes the generated dashboard deterministic regardless of
    filesystem ordering — load order must never change the rendered output.

    ``include_local`` also loads the gitignored ``jobs.local.d/*.toml`` overlay
    (machine-specific jobs). Runtime (run/status/health/catalog) loads them;
    ``dashboard.render`` passes ``include_local=False`` so the committed DASHBOARD.md
    stays fleet-portable and never lists another machine's local jobs.
    """
    reg = registry_dir or config.REGISTRY_DIR
    dirs = [reg / "jobs.d"]
    if include_local:
        dirs.append(reg / "jobs.local.d")
    jobs: list[Job] = []
    for jobs_dir in dirs:
        if not jobs_dir.exists():
            continue
        for path in sorted(jobs_dir.glob("*.toml")):
            data = _read_toml(path)
            if not data:
                continue
            jobs.append(_job_from_toml(data, path))
    jobs.sort(key=lambda j: j.id)
    return jobs


def validate(registry_dir: Path | None = None, include_local: bool = True) -> list[str]:
    """Return a list of human-readable problems. Empty list == valid registry.

    Enforced invariants:
      * job ids are unique,
      * every ``job.command`` is declared in ``commands.allow``,
      * every ``job.route`` is a KNOWN_ROUTE and is configured in ``routes.toml``,
      * every job has a schedule (launchd interval/calendar or a cron expr).

    ``include_local`` validates the machine-local overlay too (so a broken local job
    is caught at ``validate``/``install`` time). The committed-registry CI check runs
    with ``include_local=False``.
    """
    registry_dir = registry_dir or config.REGISTRY_DIR
    problems: list[str] = []

    try:
        jobs = load_jobs(registry_dir, include_local=include_local)
    except RegistryError as exc:
        return [str(exc)]
    try:
        allow = load_commands_allow(registry_dir, include_local=include_local)
    except RegistryError as exc:
        return [str(exc)]
    routes_cfg = load_routes(registry_dir)

    seen: set[str] = set()
    for job in jobs:
        where = job.source_path.name if job.source_path else job.id
        if job.id in seen:
            problems.append(f"{where}: duplicate job id {job.id!r}")
        seen.add(job.id)

        if not JOB_ID_RE.match(job.id):
            problems.append(
                f"{where}: unsafe job id {job.id!r} "
                f"(must match {JOB_ID_RE.pattern} — it becomes a crontab/launchd token)"
            )

        cron = job.cron_expr()
        if cron is not None:
            cp = cron_expr_problem(cron)
            if cp:
                problems.append(f"{where}: {cp}")

        if job.command not in allow:
            problems.append(
                f"{where}: command {job.command!r} is not in commands.allow"
            )

        for route in job.routes:
            if route not in KNOWN_ROUTES:
                problems.append(
                    f"{where}: unknown route {route!r} "
                    f"(known: {', '.join(KNOWN_ROUTES)})"
                )
            elif route not in routes_cfg and route != "log-only":
                problems.append(
                    f"{where}: route {route!r} not configured in routes.toml"
                )

        if (
            job.launchd_interval() is None
            and not job.launchd_calendar()
            and not job.cron_expr()
        ):
            problems.append(f"{where}: job {job.id!r} has no schedule")

    return problems


def load_job(job_id: str, registry_dir: Path | None = None) -> Job:
    """Fetch one job by id, or raise :class:`RegistryError`."""
    for job in load_jobs(registry_dir):
        if job.id == job_id:
            return job
    raise RegistryError(f"no job with id {job_id!r} in the registry")
