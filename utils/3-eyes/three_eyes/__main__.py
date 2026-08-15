"""3-Eyes CLI — talk to your jobs from the shell (GH-195).

    python -m three_eyes list                # jobs in the registry
    python -m three_eyes status              # active/inert + registry ⋈ live launchctl + breakers
    python -m three_eyes validate            # registry integrity (exit 1 on problems)
    python -m three_eyes dry-run <job>       # what would run + a preview of each route (no egress)
    python -m three_eyes why <job>           # explain a job's config + breaker state
    python -m three_eyes pause <job>         # quarantine a job (operator pause)
    python -m three_eyes resume <job>        # clear the breaker / un-pause
    python -m three_eyes run <job>           # trigger a run now (still gated: inert clones no-op)
    python -m three_eyes observe             # read-only inventory of ALL user LaunchAgents
    python -m three_eyes sync-dashboard      # regenerate DASHBOARD.md from the registry
    python -m three_eyes install <job>       # write+load the job's launchd agent (GATED)
    python -m three_eyes uninstall <job>     # unload+remove it (GATED)
"""

from __future__ import annotations

import argparse
import sys
import time

from . import breakers, catalog, config, dashboard, health, launchd, registry, relief, routes, run


def _cmd_list(_args) -> int:
    for job in registry.load_jobs():
        flag = "" if job.enabled else " (disabled)"
        print(f"{job.id:<28} {job.schedule_summary():<24} -> {job.command}{flag}")
    return 0


def _cmd_status(_args) -> int:
    active = config.three_eyes_active()
    print(f"3-Eyes: {'ACTIVE' if active else 'INERT (no runtime.env / disabled)'}")
    if breakers.global_halt():
        print("  ⚠️  GLOBAL HALT engaged (PANIC file or THREE_EYES_ENABLE=0)")
    breaker = breakers.FailureBreaker()
    print()
    print(dashboard.render_live())
    print()
    print("Breakers:")
    now = time.time()
    for job in registry.load_jobs():
        st = breaker.status(job.id)
        state = "OPEN" if st.get("quarantined") else "closed"
        line = f"  {job.id:<28} {state:<7} fails={st.get('consecutive_failures', 0)}"
        # P6: an OPEN breaker now says WHEN it retries itself, so "quarantined"
        # is never mistaken for "dead forever" the way skill-sync's was.
        if st.get("quarantined"):
            if st.get("paused"):
                line += "  paused by operator (no auto-retry; use `resume`)"
            else:
                cooldown = int(st.get("cooldown_seconds") or breakers.DEFAULT_COOLDOWN_SECONDS)
                since = max(
                    float(st.get("quarantined_at") or 0.0),
                    float(st.get("probe_at") or 0.0),
                )
                if since <= 0.0:
                    line += "  (pre-P6 state: no retry clock; use `resume`)"
                else:
                    remaining = int(since + cooldown - now)
                    line += (
                        "  probe due now"
                        if remaining <= 0
                        else f"  probe in {remaining // 60}m (cooldown {cooldown // 60}m)"
                    )
        if st.get("last") == "deferred":
            line += f"  last=deferred(exit {st.get('last_deferred_code')})"
        print(line)
    return 0


def _cmd_validate(_args) -> int:
    problems = registry.validate()
    if not problems:
        print("registry OK")
        return 0
    print("registry has problems:", file=sys.stderr)
    for p in problems:
        print(f"  - {p}", file=sys.stderr)
    return 1


def _cmd_dry_run(args) -> int:
    try:
        job = registry.load_job(args.job)
    except registry.RegistryError as exc:
        print(exc, file=sys.stderr)
        return 2
    allow = registry.load_commands_allow()
    spec = allow.get(job.command)
    print(f"job:      {job.id}")
    print(f"schedule: {job.schedule_summary()}")
    print(f"command:  {job.command} -> {spec['exec'] if spec else '??? NOT IN ALLOWLIST'}"
          + (f" {' '.join(spec['args'])}" if spec else ""))
    print(f"quiet:    {job.quiet_hours or '—'}  (now in quiet? {relief.in_quiet_hours(job.quiet_hours)})")
    print(f"breakers: single_instance={job.single_instance} max_rss_gb={job.max_rss_gb} "
          f"trip_after={job.trip_after_failures}")
    print(f"routes:   {', '.join(job.routes) or '—'}")
    sample = {"source": job.id, "title": f"sample finding from {job.id}",
              "severity": "warn", "summary": "dry-run sample", "text": "sample text"}
    print("\nroute preview (dry-run, no egress):")
    for res in routes.route(sample, job.routes, dry_run=True):
        line = f"  - {res['route']}: {res['status']}"
        if res.get("filename"):
            line += f" -> {res['filename']}"
        print(line)
    return 0


def _cmd_why(args) -> int:
    try:
        job = registry.load_job(args.job)
    except registry.RegistryError as exc:
        print(exc, file=sys.stderr)
        return 2
    st = breakers.FailureBreaker().status(job.id)
    print(f"{job.id}: {job.description or '(no description)'}")
    print(f"  fires:    {job.schedule_summary()}")
    print(f"  when:     {job.rules.get('fire_when', '—')}")
    print(f"  quiet:    {job.quiet_hours or '—'}")
    print(f"  breaker:  {'OPEN/quarantined' if st.get('quarantined') else 'closed'} "
          f"(consecutive failures: {st.get('consecutive_failures', 0)}, last: {st.get('last')})")
    if st.get("reason"):
        print(f"  reason:   {st['reason']}")
    return 0


def _cmd_pause(args) -> int:
    breakers.FailureBreaker().quarantine(args.job, reason="paused via CLI")
    print(f"{args.job} paused (breaker forced open). Resume with: python -m three_eyes resume {args.job}")
    return 0


def _cmd_resume(args) -> int:
    breakers.FailureBreaker().reset(args.job)
    print(f"{args.job} resumed (breaker cleared).")
    return 0


def _cmd_run(args) -> int:
    return run.run_job(args.job)


def _cmd_observe(_args) -> int:
    agents = launchd.observe_existing()
    if not agents:
        print("no user LaunchAgents found (or ~/Library/LaunchAgents absent)")
        return 0
    print(f"{len(agents)} user LaunchAgent(s) — read-only inventory:\n")
    for a in agents:
        tag = "3eyes" if a.get("managed_by_3eyes") else "     "
        if a.get("unreadable"):
            print(f"  [{tag}] {a['label']:<45} (unreadable)")
            continue
        print(f"  [{tag}] {a['label']:<45} {a.get('schedule', '?')}")
    return 0


def _cmd_sync_dashboard(_args) -> int:
    path = dashboard.write()
    print(f"regenerated {path}")
    return 0


def _cmd_catalog(args) -> int:
    if args.check:
        d = catalog.drift()
        if catalog.check() and not d["new"] and not d["removed"]:
            print("CATALOG.md is current.")
            return 0
        print("CATALOG.md is STALE — run `python -m three_eyes catalog --write`.", file=sys.stderr)
        for lbl in d["new"]:
            print(f"  + new (unclassified): {lbl}", file=sys.stderr)
        for lbl in d["removed"]:
            print(f"  - gone: {lbl}", file=sys.stderr)
        return 1
    if args.write:
        print(f"regenerated {catalog.write()}")
        return 0
    print(catalog.render())
    return 0


def _cmd_health(_args) -> int:
    print(health.format_report())
    return 0


def _cmd_install(args) -> int:
    try:
        job = registry.load_job(args.job)
        path = launchd.install(job)
    except registry.RegistryError as exc:
        print(exc, file=sys.stderr)
        return 2
    except PermissionError as exc:
        print(exc, file=sys.stderr)
        return 3
    print(f"installed {path}")
    return 0


def _cmd_uninstall(args) -> int:
    try:
        launchd.uninstall(args.job)
    except PermissionError as exc:
        print(exc, file=sys.stderr)
        return 3
    print(f"uninstalled {args.job}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="three_eyes",
        description=(
            "3-Eyes job supervisor (GH-195) — ALPHA, not fully working. "
            "Diagnostic tool, not part of the supported core. Known defect: `pause` does "
            "not stop a launchd-managed job, so a paused writer may still be running — use "
            "`launchctl bootout` and verify. Treat its output as a hint, never as proof."
        ),
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    def _job_cmd(name, func, help_):
        p = sub.add_parser(name, help=help_)
        p.add_argument("job")
        p.set_defaults(func=func)

    sub.add_parser("list", help="list registry jobs").set_defaults(func=_cmd_list)
    sub.add_parser("status", help="active/inert + live state + breakers").set_defaults(func=_cmd_status)
    sub.add_parser("validate", help="registry integrity").set_defaults(func=_cmd_validate)
    sub.add_parser("observe", help="read-only LaunchAgent inventory").set_defaults(func=_cmd_observe)
    sub.add_parser("sync-dashboard", help="regenerate DASHBOARD.md").set_defaults(func=_cmd_sync_dashboard)
    sub.add_parser("health", help="fleet health of all catalogued jobs").set_defaults(func=_cmd_health)
    cat = sub.add_parser("catalog", help="render/check/refresh CATALOG.md")
    cat.add_argument("--check", action="store_true", help="exit 1 if CATALOG.md is stale")
    cat.add_argument("--write", action="store_true", help="regenerate CATALOG.md")
    cat.set_defaults(func=_cmd_catalog)
    _job_cmd("dry-run", _cmd_dry_run, "what would run (no egress)")
    _job_cmd("why", _cmd_why, "explain a job")
    _job_cmd("pause", _cmd_pause, "quarantine a job")
    _job_cmd("resume", _cmd_resume, "un-quarantine a job")
    _job_cmd("run", _cmd_run, "trigger a run now (gated)")
    _job_cmd("install", _cmd_install, "install launchd agent (gated)")
    _job_cmd("uninstall", _cmd_uninstall, "remove launchd agent (gated)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
