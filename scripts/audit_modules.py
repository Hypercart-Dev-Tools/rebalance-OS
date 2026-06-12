#!/usr/bin/env python3
"""
audit_modules.py

Post-hoc audit script (Approach A) that verifies ingest collectors, render
modules, and supporting infrastructure are documented in ARCHITECTURE.md and
CHANGELOG.md.

Three checks:

  1. ARCHITECTURE.md mention check
       For every Python module in src/rebalance/, src/rebalance/ingest/, and
       scripts/ (minus IGNORED_FILES), confirm the filename or stem appears
       somewhere in ARCHITECTURE.md.

  2. CHANGELOG.md historical-mention check
       Same idea against CHANGELOG.md — confirms the module name has appeared
       in *any* version's section at least once in history.

  3. CHANGELOG.md recent-commit coverage check
       Walks the last N git commits (default 20, --no-merges) and confirms that
       any audit-worthy file (.py / .sh / .plist under ingest/ or scripts/) the
       commit touched is mentioned in the most-recent version section of
       CHANGELOG.md.

       This is the live-coverage check. There is no "Unreleased" section — the
       most-recent version's section is treated as the live area that grows
       until a new version tag is cut.

Baseline lockfile:
    Pre-existing doc gaps from checks #1 and #2 can be snapshotted to
    scripts/audit_modules.lock so the audit fails only on NEW drift relative
    to that baseline. Re-generate with --init after a deliberate doc backfill.

Output modes:
    Default is human-readable text. Pass --json for a stable, machine-parseable
    schema suitable for orchestrating agents. The schema carries an
    `audit_version` field so consumers can detect breaking changes.

Usage:
    python scripts/audit_modules.py                          # text output, all checks
    python scripts/audit_modules.py --json                   # JSON output for agents
    python scripts/audit_modules.py --init                   # snapshot baseline lockfile
    python scripts/audit_modules.py --commits 50             # widen the recent-commits window
    python scripts/audit_modules.py --include-uncommitted    # pre-commit preview: also check
                                                             # working-tree changes (modified/untracked
                                                             # audit-worthy files) against the live
                                                             # CHANGELOG section

Exit codes:
    0  audit passed
    1  new drift detected
    2  audit could not run (stale ignore-list, missing target, invalid lockfile)
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Schema version for machine consumers. Bump when the JSON shape changes
# in a non-additive way.
AUDIT_VERSION = 1

# Paths relative to project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_PACKAGE_DIR = PROJECT_ROOT / "src" / "rebalance"
INGEST_DIR = SRC_PACKAGE_DIR / "ingest"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
ARCHITECTURE_FILE = PROJECT_ROOT / "ARCHITECTURE.md"
CHANGELOG_FILE = PROJECT_ROOT / "CHANGELOG.md"
LOCK_FILE = SCRIPTS_DIR / "audit_modules.lock"

# Top-level package files (src/rebalance/*.py) that aren't real "modules" in
# the documentation sense — listed alongside the ingest/ helpers in
# IGNORED_FILES below.

# File extensions the recent-commits check considers "audit-worthy."
# .py covers collectors and render modules; .sh / .plist cover scheduled-job
# infrastructure (wrappers + launchd entries).
AUDIT_WORTHY_EXTS = {".py", ".sh", ".plist"}

# Files that are NOT considered standalone modules (helpers, configs, etc.)
IGNORED_FILES = {
    "__init__.py",
    "__main__.py",                   # CLI entry point shim, not a module
    "config.py",
    "calendar_config.py",
    "calendar_helpers.py",
    "agent_tags.py",
    "index_ops.py",
    "md_parser.py",
    "setup_calendar_oauth.py",
    "build_extension.py",
    "dashboard.py",                  # Poller, doesn't need same fan-out
    "audit_modules.py",              # This script
    "audit.py",                      # Internal helper for destructive-op logging
    "_bootstrap.py",                 # sys.path shim, not a module
}


# ---------------------------------------------------------------------------
# Setup / discovery
# ---------------------------------------------------------------------------

def validate_ignored_files():
    """Return list of stale IGNORED_FILES entries, or empty list."""
    search_dirs = [SRC_PACKAGE_DIR, INGEST_DIR, SCRIPTS_DIR]
    return sorted(
        name for name in IGNORED_FILES
        if not any((d / name).exists() for d in search_dirs)
    )


def get_candidate_modules():
    """Find all .py files in src/rebalance/, ingest/, and scripts/ that aren't ignored.

    Top-level src/rebalance/*.py covers cli.py, mcp_server.py, paths.py — which
    are first-class modules that need ARCHITECTURE.md / CHANGELOG.md fan-out
    just like the ingest collectors and scripts.
    """
    candidates = []
    for d in (SRC_PACKAGE_DIR, INGEST_DIR, SCRIPTS_DIR):
        if d.exists():
            for p in d.glob("*.py"):  # non-recursive — INGEST_DIR is handled separately
                if p.name not in IGNORED_FILES:
                    candidates.append(p)
    return candidates


# ---------------------------------------------------------------------------
# File-level mention checks (checks #1 and #2)
# ---------------------------------------------------------------------------

def check_file_mentions(modules, target_file):
    """Return sorted list of module names not mentioned in target_file.

    Raises FileNotFoundError if the target itself is missing — caller decides
    whether that is a hard error.
    """
    if not target_file.exists():
        raise FileNotFoundError(target_file)
    # Case-insensitive match: 'cli.py' / 'cli' should match prose like "the CLI"
    # so the audit doesn't false-negative when docs talk about a module using
    # capitalized words but never write its lowercased filename. Trades a small
    # false-positive risk (English word matching a module stem) for catching the
    # genuinely-undocumented case.
    content = target_file.read_text(encoding="utf-8").lower()
    missing = [
        mod.name for mod in modules
        if mod.name.lower() not in content and mod.stem.lower() not in content
    ]
    return sorted(missing)


# ---------------------------------------------------------------------------
# Lockfile (baseline of pre-existing gaps)
# ---------------------------------------------------------------------------

def load_lockfile():
    """Return parsed lockfile dict, or None if absent. Exits on invalid JSON."""
    if not LOCK_FILE.exists():
        return None
    try:
        return json.loads(LOCK_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"[!] {LOCK_FILE.name} is not valid JSON: {exc}", file=sys.stderr)
        sys.exit(2)


def write_lockfile(arch_missing, changelog_missing):
    payload = {
        "_note": (
            "Baseline of pre-existing documentation gaps. Modules listed here "
            "are silenced from the audit until removed. Re-generate after a "
            "deliberate doc backfill via: python scripts/audit_modules.py --init"
        ),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "missing_from_architecture": sorted(arch_missing),
        "missing_from_changelog": sorted(changelog_missing),
    }
    LOCK_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


# ---------------------------------------------------------------------------
# CHANGELOG version parsing + recent-commits check (check #3)
# ---------------------------------------------------------------------------

VERSION_HEADER_RE = re.compile(r"^## \[([^\]]+)\]", re.MULTILINE)
VERSION_DATE_RE = re.compile(r"\[([^\]]+)\]\s*-\s*(\d{4}-\d{2}-\d{2})")


def parse_most_recent_changelog_version():
    """Return (version, date_str_or_None, section_text) for the most-recent block.

    Returns (None, None, None) if CHANGELOG.md is missing or has no version
    headers. ``date_str`` is the ``YYYY-MM-DD`` from the header line (if present),
    used to bound the recent-commits check so commits older than the live
    version aren't falsely flagged.
    """
    if not CHANGELOG_FILE.exists():
        return None, None, None
    content = CHANGELOG_FILE.read_text(encoding="utf-8")
    matches = list(VERSION_HEADER_RE.finditer(content))
    if not matches:
        return None, None, None
    first = matches[0]
    end = matches[1].start() if len(matches) > 1 else len(content)
    section_text = content[first.start():end]
    header_line = content[first.start():content.find("\n", first.start())]
    date_match = VERSION_DATE_RE.search(header_line)
    date_str = date_match.group(2) if date_match else None
    return first.group(1), date_str, section_text


def _git(*args):
    """Run a git command from PROJECT_ROOT; return stdout string or None on error."""
    try:
        out = subprocess.check_output(
            ["git", *args],
            cwd=PROJECT_ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        )
        return out
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def check_recent_commits(n=20):
    """Verify last N commits' touched audit-worthy files appear in latest CHANGELOG section.

    Returns a result dict matching the JSON schema shape.
    """
    result = {
        "status": "skipped",
        "commits_examined": 0,
        "version_section_checked": None,
        "version_date": None,
        "missing_from_changelog": [],
    }

    version, version_date, section_text = parse_most_recent_changelog_version()
    if version is None:
        result["reason"] = "No version section found in CHANGELOG.md"
        return result
    result["version_section_checked"] = version
    result["version_date"] = version_date
    section_text_lower = section_text.lower()  # case-insensitive substring match

    log_args = ["log", f"-n{n}", "--no-merges", "--pretty=format:%H|%s"]
    if version_date:
        # Only consider commits at or after the latest version's date — earlier
        # commits were documented under a prior version and shouldn't be
        # flagged as missing from the live section.
        log_args.append(f"--since={version_date}")
    log_out = _git(*log_args)
    if log_out is None:
        result["reason"] = "git log failed (not a git repo, or git not available)"
        return result

    commits = []
    for line in log_out.splitlines():
        sha, _, subject = line.partition("|")
        if sha:
            commits.append({"sha": sha, "subject": subject})
    result["commits_examined"] = len(commits)

    missing = []
    for commit in commits:
        files_out = _git("show", "--name-only", "--pretty=format:", commit["sha"])
        if files_out is None:
            continue

        relevant = []
        for f in files_out.splitlines():
            f = f.strip()
            if not f:
                continue
            p = Path(f)
            if p.suffix not in AUDIT_WORTHY_EXTS:
                continue
            if not (f.startswith("src/rebalance/") or f.startswith("scripts/")):
                continue
            if p.name in IGNORED_FILES:
                continue
            if p.name.lower() not in section_text_lower and p.stem.lower() not in section_text_lower:
                relevant.append(f)

        if relevant:
            missing.append({
                "sha": commit["sha"][:7],
                "subject": commit["subject"],
                "files": sorted(relevant),
            })

    result["missing_from_changelog"] = missing
    result["status"] = "fail" if missing else "pass"
    return result


def check_working_tree():
    """Pre-commit preview: flag uncommitted audit-worthy files not in latest CHANGELOG section.

    Same shape as check_recent_commits but sourced from `git status --porcelain`.
    Default is skipped; the audit runs this check only when --include-uncommitted
    is passed.
    """
    result = {
        "status": "skipped",
        "version_section_checked": None,
        "version_date": None,
        "uncommitted_files": [],
        "missing_from_changelog": [],
    }

    version, version_date, section_text = parse_most_recent_changelog_version()
    if version is None:
        result["reason"] = "No version section found in CHANGELOG.md"
        return result
    result["version_section_checked"] = version
    result["version_date"] = version_date
    section_text_lower = section_text.lower()  # case-insensitive substring match

    status_out = _git("status", "--porcelain")
    if status_out is None:
        result["reason"] = "git status failed (not a git repo, or git not available)"
        return result

    uncommitted_relevant = []
    missing = []
    for raw_line in status_out.splitlines():
        # Format: "XY path" where X is index status, Y is worktree status. Untracked is "??".
        # Renames are "R  old -> new"; we only care about the new path.
        if len(raw_line) < 4:
            continue
        code = raw_line[:2]
        path_part = raw_line[3:].strip()
        # Skip clean entries (shouldn't appear, but defensive)
        if code == "  ":
            continue
        # Handle renames: "old -> new"
        if " -> " in path_part:
            path_part = path_part.split(" -> ", 1)[1]
        # Strip surrounding quotes that git adds for paths with special chars
        if path_part.startswith('"') and path_part.endswith('"'):
            path_part = path_part[1:-1]

        p = Path(path_part)
        if p.suffix not in AUDIT_WORTHY_EXTS:
            continue
        if not (path_part.startswith("src/rebalance/") or path_part.startswith("scripts/")):
            continue
        if p.name in IGNORED_FILES:
            continue

        uncommitted_relevant.append({"path": path_part, "git_code": code.strip() or "M"})
        if p.name.lower() not in section_text_lower and p.stem.lower() not in section_text_lower:
            missing.append(path_part)

    result["uncommitted_files"] = sorted(uncommitted_relevant, key=lambda x: x["path"])
    result["missing_from_changelog"] = sorted(missing)
    result["status"] = "fail" if missing else "pass"
    return result


# ---------------------------------------------------------------------------
# Audit assembly
# ---------------------------------------------------------------------------

def run_audit(commits_window, include_uncommitted=False):
    """Run all checks and return the structured result dict."""
    result = {
        "audit_version": AUDIT_VERSION,
        "ran_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "candidate_modules_count": 0,
        "checks": {},
        "passed": True,
        "exit_code": 0,
        "summary": "",
        "next_steps": [],
    }

    # ---- IGNORED_FILES validation (hard-exits if stale) ------------------
    stale = validate_ignored_files()
    result["checks"]["ignored_files_valid"] = {
        "status": "fail" if stale else "pass",
        "stale_entries": stale,
    }
    if stale:
        result["passed"] = False
        result["exit_code"] = 2
        result["summary"] = (
            f"IGNORED_FILES has {len(stale)} stale entry/entries. "
            "Audit cannot proceed."
        )
        result["next_steps"].append(
            f"Remove stale IGNORED_FILES entries from scripts/audit_modules.py: "
            f"{', '.join(stale)}"
        )
        return result

    modules = get_candidate_modules()
    result["candidate_modules_count"] = len(modules)

    # ---- ARCHITECTURE.md and CHANGELOG.md presence checks ----------------
    try:
        arch_missing = set(check_file_mentions(modules, ARCHITECTURE_FILE))
    except FileNotFoundError as exc:
        result["passed"] = False
        result["exit_code"] = 2
        result["summary"] = f"ARCHITECTURE.md not found at {exc}"
        result["next_steps"].append(f"Restore or recreate {exc}")
        result["checks"]["architecture_md"] = {"status": "error", "reason": "missing"}
        return result

    try:
        changelog_missing = set(check_file_mentions(modules, CHANGELOG_FILE))
    except FileNotFoundError as exc:
        result["passed"] = False
        result["exit_code"] = 2
        result["summary"] = f"CHANGELOG.md not found at {exc}"
        result["next_steps"].append(f"Restore or recreate {exc}")
        result["checks"]["changelog_md"] = {"status": "error", "reason": "missing"}
        return result

    # ---- Apply baseline lockfile -----------------------------------------
    lockfile = load_lockfile()
    arch_baseline = set(lockfile.get("missing_from_architecture", [])) if lockfile else set()
    changelog_baseline = set(lockfile.get("missing_from_changelog", [])) if lockfile else set()

    arch_new = sorted(arch_missing - arch_baseline)
    arch_silenced = sorted(arch_missing & arch_baseline)
    arch_resolved = sorted(arch_baseline - arch_missing)

    changelog_new = sorted(changelog_missing - changelog_baseline)
    changelog_silenced = sorted(changelog_missing & changelog_baseline)
    changelog_resolved = sorted(changelog_baseline - changelog_missing)

    result["checks"]["architecture_md"] = {
        "status": "fail" if arch_new else "pass",
        "new_misses": arch_new,
        "silenced_by_baseline": arch_silenced,
        "resolved_in_lockfile": arch_resolved,
    }
    result["checks"]["changelog_md"] = {
        "status": "fail" if changelog_new else "pass",
        "new_misses": changelog_new,
        "silenced_by_baseline": changelog_silenced,
        "resolved_in_lockfile": changelog_resolved,
    }

    # ---- Recent-commit coverage check ------------------------------------
    recent = check_recent_commits(n=commits_window)
    result["checks"]["recent_commits"] = recent

    # ---- Working-tree (uncommitted) preview ------------------------------
    if include_uncommitted:
        wt = check_working_tree()
    else:
        wt = {"status": "skipped", "reason": "--include-uncommitted not set"}
    result["checks"]["working_tree"] = wt

    # ---- Aggregate pass/fail --------------------------------------------
    failed = (
        bool(arch_new)
        or bool(changelog_new)
        or recent["status"] == "fail"
        or wt.get("status") == "fail"
    )
    result["passed"] = not failed
    result["exit_code"] = 1 if failed else 0

    # ---- Build next_steps -----------------------------------------------
    if arch_new:
        result["next_steps"].append(
            "Add to ARCHITECTURE.md (module map and/or Signal Sources table): "
            + ", ".join(arch_new)
        )
    if changelog_new:
        result["next_steps"].append(
            "Add a historical mention of these modules in CHANGELOG.md "
            f"(any past version section): {', '.join(changelog_new)}"
        )
    if recent["status"] == "fail":
        all_files = sorted({
            f for entry in recent["missing_from_changelog"] for f in entry["files"]
        })
        version_label = recent.get("version_section_checked", "<latest>")
        result["next_steps"].append(
            f"Append the following file changes to CHANGELOG.md version [{version_label}]: "
            f"{', '.join(all_files)}. The most-recent version section is the live area; "
            "either grow it or cut a new version tag if these constitute a release."
        )
    if wt.get("status") == "fail":
        version_label = wt.get("version_section_checked", "<latest>")
        result["next_steps"].append(
            f"Working-tree preview: the following uncommitted files would fail the audit on commit. "
            f"Add them to CHANGELOG.md version [{version_label}] before committing: "
            f"{', '.join(wt['missing_from_changelog'])}"
        )
    if arch_resolved or changelog_resolved:
        result["next_steps"].append(
            "Run `python scripts/audit_modules.py --init` to refresh the baseline "
            "lockfile — the following entries are now documented and can be pruned: "
            + ", ".join(sorted(set(arch_resolved + changelog_resolved)))
        )

    # ---- Summary --------------------------------------------------------
    if result["passed"]:
        result["summary"] = "Audit passed. No new drift."
    else:
        bits = []
        if arch_new:
            bits.append(f"{len(arch_new)} new ARCHITECTURE.md miss(es)")
        if changelog_new:
            bits.append(f"{len(changelog_new)} new CHANGELOG.md miss(es)")
        if recent["status"] == "fail":
            bits.append(
                f"{len(recent['missing_from_changelog'])} commit(s) with "
                "undocumented changes"
            )
        if wt.get("status") == "fail":
            bits.append(
                f"{len(wt['missing_from_changelog'])} uncommitted file(s) "
                "missing from latest CHANGELOG section"
            )
        result["summary"] = "Audit failed: " + "; ".join(bits) + "."

    return result


# ---------------------------------------------------------------------------
# Output renderers
# ---------------------------------------------------------------------------

def render_text(result):
    """Human-readable rendering of the audit result."""
    print("Starting module audit...")

    ifv = result["checks"].get("ignored_files_valid", {})
    if ifv.get("status") == "fail":
        print("[!] IGNORED_FILES contains entries that don't exist on disk:")
        for name in ifv.get("stale_entries", []):
            print(f"  - {name}")
        print("\nRemove the stale entries (or add the missing files) before re-running.")
        return

    print(f"Found {result['candidate_modules_count']} candidate modules to audit.")

    arch = result["checks"].get("architecture_md", {})
    if arch.get("status") == "error":
        print(f"\n[!] ARCHITECTURE.md error: {arch.get('reason')}")
    elif arch.get("new_misses"):
        print("\n[!] NEW drift — modules missing from ARCHITECTURE.md:")
        for m in arch["new_misses"]:
            print(f"  - {m}")
    elif arch.get("silenced_by_baseline"):
        print(f"\n[~] ARCHITECTURE.md: {len(arch['silenced_by_baseline'])} pre-existing miss(es) silenced by baseline lockfile.")
    else:
        print("\n[+] ARCHITECTURE.md audit passed.")

    cl = result["checks"].get("changelog_md", {})
    if cl.get("status") == "error":
        print(f"\n[!] CHANGELOG.md error: {cl.get('reason')}")
    elif cl.get("new_misses"):
        print("\n[!] NEW drift — modules missing from CHANGELOG.md:")
        for m in cl["new_misses"]:
            print(f"  - {m}")
    elif cl.get("silenced_by_baseline"):
        print(f"\n[~] CHANGELOG.md: {len(cl['silenced_by_baseline'])} pre-existing miss(es) silenced by baseline lockfile.")
    else:
        print("\n[+] CHANGELOG.md audit passed.")

    arch_resolved = arch.get("resolved_in_lockfile") or []
    cl_resolved = cl.get("resolved_in_lockfile") or []
    if arch_resolved or cl_resolved:
        print("\n[*] Lockfile entries that are now documented (safe to prune via --init):")
        for m in arch_resolved:
            print(f"  - {m} (was: missing_from_architecture)")
        for m in cl_resolved:
            print(f"  - {m} (was: missing_from_changelog)")

    rc = result["checks"].get("recent_commits", {})
    if rc.get("status") == "skipped":
        print(f"\n[*] Recent-commits check skipped: {rc.get('reason', 'unknown reason')}")
    elif rc.get("status") == "fail":
        version = rc.get("version_section_checked", "<latest>")
        print(
            f"\n[!] CHANGELOG version [{version}] does not cover changes in the "
            f"last {rc['commits_examined']} commits:"
        )
        for entry in rc["missing_from_changelog"]:
            print(f"  - {entry['sha']}  {entry['subject']}")
            for f in entry["files"]:
                print(f"      {f}")
    else:
        version = rc.get("version_section_checked", "<latest>")
        print(
            f"\n[+] Recent-commits check passed "
            f"({rc['commits_examined']} commits checked against version [{version}])."
        )

    wt = result["checks"].get("working_tree", {})
    if wt.get("status") == "skipped":
        # Quiet skip — not running this check by default.
        pass
    elif wt.get("status") == "fail":
        version = wt.get("version_section_checked", "<latest>")
        print(
            f"\n[!] Working-tree preview: {len(wt['missing_from_changelog'])} uncommitted "
            f"file(s) NOT yet in CHANGELOG version [{version}]:"
        )
        for f in wt["missing_from_changelog"]:
            print(f"  - {f}")
    elif wt.get("status") == "pass":
        n = len(wt.get("uncommitted_files") or [])
        if n:
            print(f"\n[+] Working-tree preview: {n} uncommitted audit-worthy file(s), all in latest CHANGELOG section.")
        else:
            print("\n[+] Working-tree preview: no uncommitted audit-worthy changes.")

    if result["next_steps"]:
        print("\nNext steps:")
        for step in result["next_steps"]:
            print(f"  - {step}")

    print()
    print(result["summary"])


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Audit ingest collectors, render modules, and scheduled-job "
            "infrastructure against ARCHITECTURE.md and CHANGELOG.md."
        )
    )
    parser.add_argument(
        "--init",
        action="store_true",
        help="Snapshot current ARCHITECTURE.md and CHANGELOG.md misses as the baseline lockfile and exit.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit a stable JSON schema for orchestrating agents instead of human text.",
    )
    parser.add_argument(
        "--commits",
        type=int,
        default=20,
        help="How many recent commits to check against the latest CHANGELOG version (default: 20).",
    )
    parser.add_argument(
        "--include-uncommitted",
        action="store_true",
        help="Pre-commit preview: also flag working-tree changes (modified/untracked audit-worthy files) not in the latest CHANGELOG section.",
    )
    args = parser.parse_args()

    if args.init:
        # Validate IGNORED_FILES first; refuse to snapshot a stale state.
        stale = validate_ignored_files()
        if stale:
            msg = f"IGNORED_FILES is stale; refusing to write lockfile: {', '.join(stale)}"
            if args.json:
                print(json.dumps({"audit_version": AUDIT_VERSION, "init": False, "error": msg}, indent=2))
            else:
                print(f"[!] {msg}", file=sys.stderr)
            sys.exit(2)

        modules = get_candidate_modules()
        try:
            arch_missing = set(check_file_mentions(modules, ARCHITECTURE_FILE))
            changelog_missing = set(check_file_mentions(modules, CHANGELOG_FILE))
        except FileNotFoundError as exc:
            msg = f"{exc} not found; cannot snapshot baseline"
            if args.json:
                print(json.dumps({"audit_version": AUDIT_VERSION, "init": False, "error": msg}, indent=2))
            else:
                print(f"[!] {msg}", file=sys.stderr)
            sys.exit(2)

        payload = write_lockfile(arch_missing, changelog_missing)
        if args.json:
            print(json.dumps({
                "audit_version": AUDIT_VERSION,
                "init": True,
                "lockfile_path": str(LOCK_FILE.relative_to(PROJECT_ROOT)),
                "missing_from_architecture": payload["missing_from_architecture"],
                "missing_from_changelog": payload["missing_from_changelog"],
            }, indent=2))
        else:
            print(f"[+] Wrote baseline lockfile to {LOCK_FILE.relative_to(PROJECT_ROOT)}")
            print(f"    {len(arch_missing)} silenced from ARCHITECTURE.md")
            print(f"    {len(changelog_missing)} silenced from CHANGELOG.md")
        sys.exit(0)

    result = run_audit(commits_window=args.commits, include_uncommitted=args.include_uncommitted)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        render_text(result)

    sys.exit(result["exit_code"])


if __name__ == "__main__":
    main()
