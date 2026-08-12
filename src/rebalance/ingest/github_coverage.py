"""Commit-corpus completeness, measured against the remote (GH-169 Phase 3).

This is the phase that exists to end the #155 -> #157 -> #169 chain. Each of
those fixed something real and left a gap that surfaced only when an operator
asked a question and got a bad answer. Completeness has to be continuously
derivable instead.

Three design rules, each earned from a specific failure:

**Anchor on the remote, not the local clone.** Comparing local ``git log`` to
the local DB proves only that the backfill ran. If the clone is stale both
sides are equally behind and the check reports a confident ``0`` -- it would
have passed green through the entire #155 -> #157 sequence while the gap was
live. A check that can silently agree with itself is worse than no check.

**Never net the gaps together.** A force-push leaves a phantom row (a captured
SHA no longer on the remote) *and* a real gap (the rewritten SHA, uncollected).
A single count subtracts one from the other and reports zero. They are tracked
as separate quantities.

**Presence of a row is not coverage.** A row with ``path_coverage =
'unavailable'`` is a captured commit with no file data at all. Counting it as
covered is the last way all three numbers could read zero while data is
missing, so the gap is computed against ``complete`` rows only, with
``incomplete`` reported alongside.
"""

from __future__ import annotations

import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from rebalance.ingest.db import db_connection, ensure_github_schema
from rebalance.ingest.github_commit_backfill import _git, resolve_clone
from rebalance.lib.time_ops import _now

_LS_REMOTE_TIMEOUT_S = 30

# Health thresholds. A non-zero gap is a real finding, but one or two commits
# in flight during a refresh is normal, so the WARN floor is above zero.
GAP_WARN_THRESHOLD = 5
STALE_FETCH_WARN_HOURS = 48


@dataclass
class RepoCoverage:
    repo: str = ""
    state: str = "ok"  # ok | stale | uncoverable
    reason: str = ""
    local_tip: str = ""
    remote_tip: str = ""
    # The three quantities, deliberately never combined into one number.
    collection_gap: int = 0
    projection_gap: int = 0
    orphan_count: int = 0
    incomplete: int = 0
    remote_commits: int = 0
    captured_complete: int = 0
    fetch_age_hours: float | None = None

    def as_dict(self) -> dict:
        return asdict(self)

    @property
    def is_clean(self) -> bool:
        return (
            self.state == "ok"
            and self.collection_gap == 0
            and self.projection_gap == 0
            and self.orphan_count == 0
            and self.incomplete == 0
        )


@dataclass
class CoverageReport:
    repos: list[RepoCoverage] = field(default_factory=list)
    checked_at: str = ""

    def as_dict(self) -> dict:
        return {"checked_at": self.checked_at, "repos": [r.as_dict() for r in self.repos]}

    @property
    def worst_state(self) -> str:
        for state in ("uncoverable", "stale"):
            if any(r.state == state for r in self.repos):
                return state
        return "ok"

    def problems(self) -> list[RepoCoverage]:
        return [r for r in self.repos if not r.is_clean]


def _fetch_age_hours(repo_path: Path) -> float | None:
    """Hours since this clone last fetched, from FETCH_HEAD's mtime.

    A network-free staleness proxy: it answers "could this clone be behind?"
    without a round-trip, which is what makes the doctor check affordable.
    """
    fetch_head = repo_path / ".git" / "FETCH_HEAD"
    if not fetch_head.exists():
        # A worktree keeps .git as a file; resolve the real git dir.
        code, out, _ = _git(repo_path, "rev-parse", "--path-format=absolute", "--git-common-dir")
        if code != 0 or not out:
            return None
        fetch_head = Path(out) / "FETCH_HEAD"
    try:
        mtime = fetch_head.stat().st_mtime
    except OSError:
        return None
    return (datetime.now(timezone.utc).timestamp() - mtime) / 3600.0


def remote_tip(repo_full_name: str, branch: str = "HEAD") -> str:
    """Remote tip SHA via ``git ls-remote`` — one cheap call, no clone needed.

    This is the anchor that makes the check honest: without it, a stale clone
    and a stale DB agree with each other and report perfect coverage.
    """
    url = f"https://github.com/{repo_full_name}.git"
    try:
        result = subprocess.run(
            ["git", "ls-remote", url, branch],
            capture_output=True, text=True, timeout=_LS_REMOTE_TIMEOUT_S,
        )
    except (subprocess.TimeoutExpired, OSError):
        return ""
    if result.returncode != 0 or not result.stdout.strip():
        return ""
    return result.stdout.split()[0].strip()


def check_repo_coverage(
    database_path: Path,
    repo_full_name: str,
    *,
    clone_path: Path | None = None,
    roots: list[str] | None = None,
    check_remote: bool = True,
) -> RepoCoverage:
    """Measure the three gaps for one repo."""
    coverage = RepoCoverage(repo=repo_full_name)

    path = clone_path or resolve_clone(repo_full_name, roots=roots)
    if path is None:
        coverage.state = "uncoverable"
        coverage.reason = "no local clone on this machine"
        return coverage

    code, local_tip, _ = _git(path, "rev-parse", "HEAD")
    coverage.local_tip = local_tip if code == 0 else ""

    # Clone freshness without touching the network. `git ls-remote` per repo is
    # ~1 network round-trip each, which is fine for a refresh but NOT for a
    # doctor run over 60 watched repos (measured: doctor exceeded 2 minutes).
    # Fetch AGE still enforces the anti-self-agreement invariant -- a clone that
    # has not been fetched in days can never report a confident 0 -- so the
    # local-only path degrades honestly instead of going quiet.
    fetch_age_hours = _fetch_age_hours(path)
    coverage.fetch_age_hours = fetch_age_hours
    if not check_remote:
        if fetch_age_hours is None or fetch_age_hours > STALE_FETCH_WARN_HOURS:
            coverage.state = "stale"
            coverage.reason = (
                "clone not fetched recently"
                if fetch_age_hours is None
                else f"clone last fetched {fetch_age_hours:.0f}h ago"
            )
            return coverage

    if check_remote:
        coverage.remote_tip = remote_tip(repo_full_name)
        if not coverage.remote_tip:
            coverage.state = "uncoverable"
            coverage.reason = "could not reach remote to anchor the check"
            return coverage
        # The clone must actually CONTAIN the remote tip. Comparing to local
        # HEAD would pass on any checked-out branch; containment is the real
        # question ("do we have everything the remote has?").
        code, _, _ = _git(path, "cat-file", "-e", f"{coverage.remote_tip}^{{commit}}")
        if code != 0:
            coverage.state = "stale"
            coverage.reason = (
                f"clone does not contain remote tip {coverage.remote_tip[:8]}; "
                "fetch before trusting any gap number"
            )
            return coverage

    code, raw, _ = _git(path, "log", "--remotes=origin", "--format=%H")
    if code != 0:
        coverage.state = "uncoverable"
        coverage.reason = "git log failed on the local clone"
        return coverage
    remote_shas = {line.strip() for line in raw.splitlines() if line.strip()}
    coverage.remote_commits = len(remote_shas)

    with db_connection(database_path, ensure_github_schema) as conn:
        complete = {
            r[0] for r in conn.execute(
                "SELECT sha FROM github_direct_commits "
                "WHERE repo_full_name = ? AND path_coverage = 'complete'",
                (repo_full_name,),
            )
        }
        any_direct = {
            r[0] for r in conn.execute(
                "SELECT sha FROM github_direct_commits WHERE repo_full_name = ?",
                (repo_full_name,),
            )
        }
        pr_shas = {
            r[0] for r in conn.execute(
                "SELECT sha FROM github_commits WHERE repo_full_name = ?",
                (repo_full_name,),
            )
        }
        projected = {
            r[0] for r in conn.execute(
                "SELECT source_key FROM github_documents "
                "WHERE repo_full_name = ? AND doc_type = 'direct_commit'",
                (repo_full_name,),
            )
        }

    covered = complete | pr_shas
    coverage.captured_complete = len(covered)

    # 1. On the remote, not covered by a complete row or a PR commit.
    coverage.collection_gap = len(remote_shas - covered)

    # 2. Captured but never projected into the searchable corpus. Measured
    #    independently because sync_direct_commit_documents() DELETEs the whole
    #    doc_type then rebuilds -- a partial failure shortens the corpus while
    #    the collector's own tables still look complete (RC5).
    expected_docs = {sha for sha in any_direct if sha not in pr_shas}
    projected_shas = {key.rsplit(":", 1)[-1] for key in projected}
    coverage.projection_gap = len(expected_docs - projected_shas)

    # 3. Captured but no longer reachable on the remote (force-push / squash).
    #    Reported on its own so it cannot cancel out a real collection gap.
    coverage.orphan_count = len(any_direct - remote_shas)

    # 4. Rows that exist but carry no file data -- present, yet not covered.
    coverage.incomplete = len(any_direct - complete)

    return coverage


def check_coverage(
    database_path: Path,
    repos: list[str],
    *,
    roots: list[str] | None = None,
    check_remote: bool = False,
) -> CoverageReport:
    """Measure coverage across *repos*; one repo's failure never hides another."""
    return CoverageReport(
        repos=[
            check_repo_coverage(
                database_path, repo, roots=roots, check_remote=check_remote
            )
            for repo in repos
        ],
        checked_at=_now(),
    )


def coverage_health(report: CoverageReport) -> dict:
    """Collapse a report into a doctor/index_status health verdict.

    Degrades on any of: a non-zero gap past threshold, a stale clone, or an
    uncoverable repo. An uncoverable repo is a WARN rather than silence — that
    silence is the failure shape this whole issue is about.
    """
    problems = report.problems()
    if not problems:
        return {"status": "ok", "reason": "commit corpus matches every watched remote"}

    reasons: list[str] = []
    status = "ok"
    for repo in problems:
        if repo.state == "uncoverable":
            status = "warn" if status == "ok" else status
            reasons.append(f"{repo.repo}: uncoverable ({repo.reason})")
        elif repo.state == "stale":
            status = "degraded"
            reasons.append(f"{repo.repo}: stale clone ({repo.reason})")
        else:
            total = repo.collection_gap + repo.projection_gap + repo.orphan_count
            if total >= GAP_WARN_THRESHOLD or repo.incomplete >= GAP_WARN_THRESHOLD:
                status = "degraded"
            elif status == "ok":
                status = "warn"
            reasons.append(
                f"{repo.repo}: collection {repo.collection_gap}, "
                f"projection {repo.projection_gap}, orphans {repo.orphan_count}, "
                f"incomplete {repo.incomplete}"
            )
    return {"status": status, "reason": "; ".join(reasons)}
