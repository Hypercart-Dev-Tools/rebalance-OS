"""Device-local activity scan + ranking for the Focus 5 dashboard.

Focus 5 answers "which 5 repos am I actually working on right now, and did I
forget to commit or push?". It is device-local: discovery and ranking lean on
local git, and the GitHub corpus is enrichment only (newest PR), never a
ranking input.

Pipeline (mirrors the established collect → store pattern):

    discover .git repos under the bounded scan roots
        → probe per-repo SIGNALS (branch, ahead/behind, dirty, commit times)
        → persist ALL signals (focus5_repo_signals — also the off-roster cache)
        → rank via the selected strategy → persist top-N (focus5_roster)

Why the spike forced this shape (see PROJECT/2-WORKING/FOCUS-5.md):

- **Raw signals are persisted, never a baked score.** The ranking "mode" is a
  pure function ``RepoSignals -> RankVerdict``. Switching modes is a config
  flip, and because the raw signals are stored, an existing roster can be
  re-ranked under a different mode *without re-probing git*. This is the seam
  that keeps mode changes from becoming a refactor.
- **`.git/index` mtime is NOT a ranking input.** The spike proved it is bumped
  by clone/fetch/checkout and surfaced dormant third-party clones over the
  operator's own dirty WIP. The honest signals are operator-authored commits
  (matched against each repo's own ``user.email`` — the operator commits under a
  GitHub noreply address, so a hardcoded email would silently miss them) and a
  dirty/unpushed working tree.

Everything here is read-only with respect to the scanned repos: we only run
read-only git plumbing and ``stat`` files; we never write to a foreign repo.
"""
from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, Iterable, Iterator

from rebalance.ingest.db import db_connection, run_migrations
from rebalance.ingest.sync_snapshot import get_device_id
# Reuse the prune discipline and the (already tested) remote-URL → owner/repo
# parser rather than duplicating them; both are low-churn and shared by intent.
from rebalance.ingest.ask_self_scan import _PRUNE_DIRS, derive_repo_full_name
from rebalance.lib.git_ops import _git

logger = logging.getLogger(__name__)

DEFAULT_MAX_DEPTH = 6
DEFAULT_ROSTER_SIZE = 5
GIT_TIMEOUT = 5
# A single repo probe over this many seconds is worth flagging — a slow disk, a
# huge working tree, or a hung git is the usual cause.
SLOW_REPO_SECONDS = 1.5


# ---------------------------------------------------------------------------
# Signal model — the mode-agnostic facts a repo exposes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RepoSignals:
    """Raw, ranking-mode-agnostic signals for one discovered repo.

    Persisted verbatim so the roster can be re-ranked under any mode without
    re-probing git. No field here is a score or a rank.
    """

    device_id: str
    local_path: str
    repo_name: str
    repo_full_name: str | None
    branch: str | None
    upstream: str | None
    has_upstream: bool
    ahead: int
    behind: int
    modified_count: int
    untracked_count: int
    is_dirty: bool
    last_commit_at: str | None
    last_commit_ts: int | None
    my_last_commit_ts: int | None
    # GH-81 identity-agnostic ranking vector: "did MY local checkout commit
    # recently?" resolved from the HEAD reflog with a recorded fallback basis.
    my_local_commit_ts: int | None
    recency_basis: str  # local_reflog | author_email | any_commit | none
    head_reflog_ts: int | None
    index_mtime_ts: int | None  # diagnostics only — never ranked on
    remote_url: str | None
    probed_at: str

    @property
    def is_unpushed(self) -> bool:
        """Local commits not on the upstream (a 'did I forget to push?' signal)."""
        return self.ahead > 0


def focus5_repo_identity(s: RepoSignals) -> str:
    """Stable hide/ignore key for a repo.

    Its ``owner/repo`` (``repo_full_name``) when it has a remote, else its
    device-local path. This is exactly what the ``focus5_hidden_repos`` config
    list stores, so a repo with a remote is hidden across devices while a
    local-only clone is hidden per-path.
    """
    return s.repo_full_name or s.local_path


# ---------------------------------------------------------------------------
# GH-81: the identity-agnostic recency vector (local-commit reflog + fallback)
# ---------------------------------------------------------------------------
#
# Email is a fragile proxy for "did I work here?" (author vs committer, web-merge
# noreply, squash author-rewrite, co-authors). The durable signal is "did MY
# local checkout CREATE or REWRITE a commit reachable at HEAD?" — the HEAD
# reflog, filtered to local-commit operations. It is identity-agnostic (no email
# list to maintain) and foreign-push-resistant (a pull-only repo has no local
# `commit:` reflog entry). Author email is retained only as a fallback + display.

# Op families for a HEAD-reflog subject (git ``%gs``). Classification keys on the
# LEADING operation keyword so message-tail variance across git versions doesn't
# matter. Accept = the op creates/rewrites a locally-authored commit reachable at
# HEAD; reject = it moves HEAD to a commit produced elsewhere (foreign push,
# navigation). Enumerated in ONE place; an unrecognized op is treated
# conservatively as reject and logged so a new git phrasing is diagnosable.
_REFLOG_ACCEPT_OPS = frozenset({"commit", "cherry-pick", "revert", "rebase"})
_REFLOG_REJECT_OPS = frozenset({"pull", "fetch", "clone", "checkout", "reset", "branch"})


def _classify_reflog_op(subject: str) -> bool | None:
    """Classify a HEAD-reflog subject as a local-commit op.

    Returns ``True`` (accept — creates/rewrites a local commit reachable at HEAD),
    ``False`` (reject — a foreign/navigation move), or ``None`` (unrecognized →
    caller treats conservatively as reject and logs). Examples: ``commit: x`` /
    ``commit (amend): x`` / ``cherry-pick: x`` / ``rebase (pick): x`` → accept;
    ``pull: Fast-forward`` / ``checkout: moving …`` / ``reset: …`` → reject; a
    non-fast-forward ``merge feature: Merge made …`` → accept (a real local merge
    commit), a ``merge …: Fast-forward`` → reject (foreign).
    """
    op = subject.split(":", 1)[0].strip()
    head = op.split(" ", 1)[0].split("(", 1)[0]  # "merge feat"→"merge", "commit (amend)"→"commit"
    if head == "merge":
        detail = subject.split(":", 1)[1].strip().lower() if ":" in subject else ""
        return not detail.startswith("fast-forward")
    if head in _REFLOG_ACCEPT_OPS:
        return True
    if head in _REFLOG_REJECT_OPS:
        return False
    return None


def resolve_recency(
    *, reflog_commit_ts: int | None, reflog_available: bool,
    author_email_ts: int | None, any_commit_ts: int | None,
) -> tuple[int | None, str]:
    """Resolve the headline ranking recency + its (recorded, never silent) basis.

    Fallback ladder: ``local_reflog`` (a local-commit op in HEAD's reflog) →
    ``author_email`` (the old ``user.email`` match, so we never regress below
    today) → ``any_commit`` (**only** when the reflog is genuinely unavailable, so
    a foreign-only clone whose reflog IS readable can never masquerade as my work)
    → ``none`` (ineligible). The ``reflog_available`` gate on the ``any_commit``
    rung is the GH-81 refinement that keeps the core fix intact: an available
    reflog with no local-commit op is a *definitive* "I have not committed here",
    not a reason to fall through to a foreign author's commit time.
    """
    if reflog_commit_ts is not None:
        return reflog_commit_ts, "local_reflog"
    if author_email_ts is not None:
        return author_email_ts, "author_email"
    if not reflog_available and any_commit_ts is not None:
        return any_commit_ts, "any_commit"
    return None, "none"


# Human "why" for each fallback basis (GH-81 Phase 2). Only the degraded rungs get
# a note — a fallback must be SHOWN, never silent; `local_reflog` needs none (it's
# the expected basis). `none` is handled separately (ineligibility, not a fallback).
_BASIS_NOTE = {
    "author_email": "ranked by author email — this clone's HEAD reflog is disabled",
    "any_commit": "ranked by latest commit — reflog disabled, no commit under your email",
}

# Short form of the same vocabulary for a compact on-card badge.
_BASIS_BADGE = {
    "author_email": "via author email",
    "any_commit": "via latest commit",
}


def basis_badge(recency_basis: str | None) -> str:
    """Short fallback-basis label for a rostered card (GH-81 Phase 2).

    Returns ``""`` for the expected ``local_reflog`` basis (and ``none``); a
    non-empty badge means "this repo ranked by a FALLBACK" — surfaced so a
    degraded basis is visible on the board, never silent.
    """
    return _BASIS_BADGE.get(recency_basis or "", "")


def explain_recency(
    recency_basis: str | None, my_local_commit_ts: int | None,
    rank_cutoff_ts: int | None, now_ts: int,
) -> str:
    """One-line operator-facing "why does this repo rank where it does?" string.

    A pure render over the Phase-1 explain payload (basis + resolved recency + the
    #5 cutoff) — no git, no recompute — so the question that needed ``git log``
    forensics in GH-81 has a one-line answer, including when a fallback basis was
    used. Eligible: "your local commit 3d ago · below the #5 cutoff (16h ago) ·
    <fallback note>"; ineligible: the no-local-commit reason.
    """
    if recency_basis in (None, "none") or my_local_commit_ts is None:
        return "no local commit here — not eligible for Focus 5"
    parts = [f"your local commit {_humanize_ago(my_local_commit_ts, now_ts)}"]
    if rank_cutoff_ts is not None and my_local_commit_ts < rank_cutoff_ts:
        parts.append(f"below the #5 cutoff ({_humanize_ago(rank_cutoff_ts, now_ts)})")
    note = _BASIS_NOTE.get(recency_basis)
    if note:
        parts.append(note)
    return " · ".join(parts)


def pick_newest_dirty_off_roster(off_roster_warnings: list[dict]) -> dict | None:
    """The single most-recently-touched dirty repo outside the top 5 (GH-105).

    A slim "BTW, recent work made this dirty" banner needs exactly one repo,
    not the full off-roster list ``_f5_warning_strip`` already renders. Ranks
    by ``my_local_commit_ts`` (last authored commit before it went dirty) —
    never ``index_mtime_ts`` (clone/fetch pollution; see module docstring) —
    so a repo the operator hasn't touched in months but merely re-cloned can't
    win. Ties broken by ``repo_name`` for determinism. Returns ``None`` when no
    off-roster repo is dirty (unpushed-only entries don't count — this banner
    is specifically "you left uncommitted work", not "you forgot to push").
    """
    candidates = [
        w for w in off_roster_warnings
        if w.get("is_dirty") and w.get("my_local_commit_ts") is not None
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda w: (w["my_local_commit_ts"], w["repo_name"]))


def off_roster_reason(w: dict | RepoSignals) -> str:
    """The short, specific reason why a repo is in off-roster warnings (GH-104)."""
    if isinstance(w, dict):
        is_dirty = w.get("is_dirty")
        ahead = w.get("ahead") or 0
    else:
        is_dirty = w.is_dirty
        ahead = w.ahead or 0

    if is_dirty:
        return "uncommitted changes"
    if ahead > 0:
        return f"{ahead} ahead of origin"
    return "needs attention"


# ---------------------------------------------------------------------------
# Ranking strategies — a pure function per mode, selected by config
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RankVerdict:
    """A strategy's verdict for one repo.

    ``sort_key`` is compared descending (bigger = higher in the roster). Within
    a single ranking run every repo is scored by the same strategy, so all
    ``sort_key`` tuples share a shape and sort cleanly.
    """

    eligible: bool
    sort_key: tuple
    reason: str


# A ranking strategy maps (signals, now_epoch) -> verdict. Pure: no I/O, no clock.
RankingStrategy = Callable[[RepoSignals, int], RankVerdict]

# The headline Focus 5 view: "what am I working on right now?" Kept in lockstep
# with config.get_focus5_ranking_mode()'s unset default — change both together.
DEFAULT_RANKING_MODE = "recent_activity"


def _humanize_ago(ts: int | None, now_ts: int) -> str:
    if not ts:
        return "no local commits"
    secs = max(0, now_ts - ts)
    for label, unit in (("d", 86400), ("h", 3600), ("m", 60)):
        if secs >= unit:
            return f"{secs // unit}{label} ago"
    return "just now"


def _recency(s: RepoSignals) -> int:
    """Best 'when did I last touch this' estimate from operator-authored signals.

    Deliberately excludes index_mtime_ts (clone/fetch pollution); falls back to
    head-reflog (local HEAD moves) and finally any-author commit time so a repo
    is never ranked purely on a foreign push.
    """
    return s.my_last_commit_ts or s.head_reflog_ts or s.last_commit_ts or 0


def _eligible_as_my_work(s: RepoSignals) -> bool:
    """Operator has work here: authored a commit, or the tree is dirty."""
    return s.is_dirty or s.my_last_commit_ts is not None


def rank_my_work(s: RepoSignals, now_ts: int) -> RankVerdict:
    """My work only — exclude repos I've never committed to unless dirty now."""
    eligible = _eligible_as_my_work(s)
    recency = max(s.my_last_commit_ts or 0, now_ts if s.is_dirty else 0)
    reason = "uncommitted changes" if s.is_dirty else f"your commit {_humanize_ago(s.my_last_commit_ts, now_ts)}"
    return RankVerdict(eligible, (recency,), reason)


def rank_dirty_first(s: RepoSignals, now_ts: int) -> RankVerdict:
    """Dirty-first safety view (DEFAULT).

    Same eligibility as my_work, but anything with uncommitted or unpushed work
    is forced above clean repos, then ordered by operator-authored recency. This
    optimizes for "don't lose track of WIP".
    """
    eligible = _eligible_as_my_work(s)
    at_risk = s.is_dirty or s.is_unpushed
    if s.is_dirty and s.is_unpushed:
        reason = f"{s.modified_count + s.untracked_count} uncommitted, {s.ahead} unpushed"
    elif s.is_dirty:
        reason = f"{s.modified_count} modified, {s.untracked_count} untracked"
    elif s.is_unpushed:
        reason = f"{s.ahead} unpushed commit(s)"
    else:
        reason = f"your commit {_humanize_ago(s.my_last_commit_ts, now_ts)}"
    return RankVerdict(eligible, (1 if at_risk else 0, _recency(s)), reason)


def rank_recent_activity(s: RepoSignals, now_ts: int) -> RankVerdict:
    """My most recently *locally-committed* active repos (DEFAULT — the headline).

    Answers "what am I working on right now?" GH-81: ranks on the
    identity-agnostic **local-commit recency** (``my_local_commit_ts``, resolved
    from the HEAD reflog with a recorded fallback ``recency_basis``) — NOT on a
    single ``user.email`` match. The operator commits under multiple author emails
    (CLI vs web-merge noreply), so an email-only gate silently drops recent local
    work authored under a non-matching identity; the reflog vector does not.

    Eligibility requires a resolved local-commit recency (``my_local_commit_ts is
    not None`` ⇔ ``recency_basis != "none"``). A dirty-only / never-committed repo
    is therefore **excluded** from Focus 5 — it is carried by ``dirty_first`` (the
    Dirty Five safety view) and the off-roster strip instead. Because the basis
    prefers the reflog and only falls to a foreign author's commit time when the
    reflog is *unavailable*, a foreign push or clone/checkout cannot masquerade as
    my activity.
    """
    eligible = s.my_local_commit_ts is not None
    reason = f"your commit {_humanize_ago(s.my_local_commit_ts, now_ts)}"
    return RankVerdict(eligible, (s.my_local_commit_ts or 0,), reason)


def rank_any_touch(s: RepoSignals, now_ts: int) -> RankVerdict:
    """Anything I've touched — broadest, includes clone/fetch/checkout activity.

    Provided for completeness/comparison; noisier (the Phase 0 default that
    surfaced dormant clones). Eligible for every discovered repo.
    """
    recency = max(
        s.index_mtime_ts or 0, s.head_reflog_ts or 0,
        s.last_commit_ts or 0, s.my_last_commit_ts or 0,
    )
    return RankVerdict(True, (recency,), f"local activity {_humanize_ago(recency, now_ts)}")


RANKING_STRATEGIES: dict[str, RankingStrategy] = {
    "recent_activity": rank_recent_activity,
    "my_work": rank_my_work,
    "dirty_first": rank_dirty_first,
    "any_touch": rank_any_touch,
}


def resolve_ranking_strategy(mode: str) -> RankingStrategy:
    """Return the strategy for *mode*, or raise with the valid set listed.

    Raising (rather than silently defaulting) keeps a misconfigured mode honest
    — the collector surfaces it in its error envelope instead of quietly serving
    a different ranking than configured.
    """
    try:
        return RANKING_STRATEGIES[mode]
    except KeyError:
        valid = ", ".join(sorted(RANKING_STRATEGIES))
        raise ValueError(f"unknown focus5 ranking mode {mode!r}; valid modes: {valid}") from None


@dataclass(frozen=True)
class RankedRepo:
    signals: RepoSignals
    position: int
    reason: str


def rank_repos(
    signals: list[RepoSignals], *, mode: str, now_ts: int, limit: int = DEFAULT_ROSTER_SIZE,
    hidden: Iterable[str] = (),
) -> list[RankedRepo]:
    """Apply *mode* to *signals* and return the top *limit* eligible repos.

    Repos whose identity (:func:`focus5_repo_identity`) is in *hidden* are dropped
    before ranking — so a hidden repo never claims a roster slot and the next
    eligible candidate is promoted into its place.
    """
    strategy = resolve_ranking_strategy(mode)
    hidden_set = set(hidden)
    scored: list[tuple[tuple, RepoSignals, RankVerdict]] = []
    for s in signals:
        if focus5_repo_identity(s) in hidden_set:
            continue
        v = strategy(s, now_ts)
        if v.eligible:
            scored.append((v.sort_key, s, v))
    # Sort by score desc, then local_path for a stable tiebreak across runs.
    scored.sort(key=lambda t: (t[0], t[1].local_path), reverse=True)
    return [RankedRepo(s, i, v.reason) for i, (_k, s, v) in enumerate(scored[:limit], 1)]


# ---------------------------------------------------------------------------
# Discovery — bounded, zero-config .git walk (reuses the ask_self prune list)
# ---------------------------------------------------------------------------

def _should_descend(name: str) -> bool:
    if name in _PRUNE_DIRS:
        return False
    return not name.startswith(".")  # ".git" is matched by marker, never descended


def iter_git_repos(
    roots: list[str] | list[Path], *, max_depth: int = DEFAULT_MAX_DEPTH,
) -> Iterator[Path]:
    """Yield each git repo root under *roots*, bounded by depth + the prune list.

    Stops descending at a repo boundary so nested submodules don't multiply the
    candidate set. De-duplicates by resolved path so overlapping roots are safe.
    """
    seen: set[Path] = set()
    for raw_root in roots:
        root = Path(raw_root).expanduser()
        if not root.is_dir():
            continue
        base_depth = len(root.resolve().parts)
        for dirpath, dirnames, _files in os.walk(root, followlinks=False):
            cur = Path(dirpath)
            # `.git` may be a dir (normal checkout) or a file (worktree/submodule).
            if (cur / ".git").exists():
                rp = cur.resolve()
                if rp not in seen:
                    seen.add(rp)
                    yield rp
                dirnames[:] = []  # repo boundary — do not descend further
                continue
            if len(cur.resolve().parts) - base_depth >= max_depth:
                dirnames[:] = []
            else:
                dirnames[:] = [d for d in dirnames if _should_descend(d)]


# ---------------------------------------------------------------------------
# Signal probing — read-only git plumbing per repo
# ---------------------------------------------------------------------------

def _parse_status(out: str) -> dict[str, Any]:
    """Parse ``git status --porcelain=v2 --branch`` into health fields."""
    branch = upstream = None
    ahead = behind = modified = untracked = 0
    has_upstream = False
    for line in out.splitlines():
        if line.startswith("# branch.head"):
            branch = line.split(" ", 2)[2]
            if branch == "(detached)":
                branch = None
        elif line.startswith("# branch.upstream"):
            upstream = line.split(" ", 2)[2]
            has_upstream = True
        elif line.startswith("# branch.ab"):
            parts = line.split()
            ahead = int(parts[2].lstrip("+"))
            behind = int(parts[3].lstrip("-"))
        elif line[:1] in ("1", "2", "u"):  # changed/renamed/unmerged tracked entry
            modified += 1
        elif line.startswith("?"):
            untracked += 1
    return {
        "branch": branch, "upstream": upstream, "has_upstream": has_upstream,
        "ahead": ahead, "behind": behind,
        "modified_count": modified, "untracked_count": untracked,
        "is_dirty": modified > 0 or untracked > 0,
    }


def _mtime(path: Path) -> int | None:
    try:
        return int(path.stat().st_mtime)
    except OSError:
        return None


def _probe_head_reflog_commit(
    repo: Path, stats: dict[str, Any] | None = None,
) -> tuple[int | None, bool]:
    """GH-81: ``(newest local-commit-op epoch | None, reflog_available)``.

    Reads HEAD's reflog newest-first and returns the committer timestamp of the
    first entry whose op CREATES/REWRITES a local commit reachable at HEAD (see
    :func:`_classify_reflog_op`). The second value distinguishes "reflog is
    unavailable" (disabled via ``core.logAllRefUpdates=false``, GC-expired, or an
    atypical clone — caller may fall back to author-email/any-commit) from "reflog
    is readable but shows no local-commit op" (a definitive negative). Never
    raises; unrecognized ops are skipped (treated as reject) and logged so a new
    git phrasing surfaces instead of being silently counted.
    """
    out = _git(repo, "reflog", "show", "--format=%ct%x1f%gs")
    if not out or not out.strip():
        return None, False  # unreadable / disabled / empty → unavailable
    for line in out.splitlines():
        ts_str, _sep, subject = line.partition("\x1f")
        verdict = _classify_reflog_op(subject)
        if verdict is True:
            return (int(ts_str) if ts_str.strip().isdigit() else None), True
        if verdict is None:
            logger.info(
                "focus5: unrecognized HEAD-reflog op %r in %s (treated as reject)",
                subject.split(":", 1)[0][:40], repo,
            )
            if stats is not None:
                stats.setdefault("unknown_reflog_ops", []).append(subject.split(":", 1)[0][:40])
    return None, True  # readable, but no local-commit op among the entries


def probe_repo_signals(
    repo: Path, *, device_id: str, probed_at: str, stats: dict[str, Any] | None = None,
) -> RepoSignals:
    """Read one repo's signals with read-only git plumbing + file stats.

    Pass a ``stats`` dict to accumulate diagnostics across a scan: per-repo probe
    duration is timed, slow probes (> ``SLOW_REPO_SECONDS``) and repos whose
    ``git status`` fails are logged and counted so a degraded scan is diagnosable
    from the logs rather than silently slow or partial.
    """
    started = perf_counter()
    status_out = _git(repo, "status", "--porcelain=v2", "--branch")
    if status_out is None:
        logger.warning("focus5: git status failed for %s (skipping its health)", repo)
        if stats is not None:
            stats["failed"] = stats.get("failed", 0) + 1
    status = _parse_status(status_out or "")

    # Newest commit (any author): epoch | ISO. Empty repos return None.
    last_commit_ts = last_commit_at = None
    head = _git(repo, "log", "-1", "--format=%ct|%cI")
    if head and "|" in head:
        epoch, iso = head.strip().split("|", 1)
        if epoch.isdigit():
            last_commit_ts, last_commit_at = int(epoch), iso

    # Operator-authored newest commit: match THIS repo's configured identity,
    # not a hardcoded address (the operator commits under a noreply email).
    my_last_commit_ts = None
    email = _git(repo, "config", "user.email")
    if email and email.strip():
        mine = _git(repo, "log", "-1", f"--author={email.strip()}", "--format=%ct")
        if mine and mine.strip().isdigit():
            my_last_commit_ts = int(mine.strip())

    # GH-81: identity-agnostic local-commit recency from the HEAD reflog, with a
    # recorded fallback basis (never raises — degrades to author_email/any_commit).
    reflog_commit_ts, reflog_available = _probe_head_reflog_commit(repo, stats)
    my_local_commit_ts, recency_basis = resolve_recency(
        reflog_commit_ts=reflog_commit_ts, reflog_available=reflog_available,
        author_email_ts=my_last_commit_ts, any_commit_ts=last_commit_ts,
    )

    remote_url = (_git(repo, "remote", "get-url", "origin") or "").strip() or None

    git_dir = repo / ".git"
    head_reflog_ts = _mtime(git_dir / "logs" / "HEAD") if git_dir.is_dir() else None
    index_mtime_ts = _mtime(git_dir / "index") if git_dir.is_dir() else None

    elapsed = perf_counter() - started
    if elapsed > SLOW_REPO_SECONDS:
        logger.warning("focus5: slow repo probe %.2fs for %s", elapsed, repo)
        if stats is not None:
            stats.setdefault("slow", []).append((str(repo), round(elapsed, 2)))

    return RepoSignals(
        device_id=device_id,
        local_path=str(repo),
        repo_name=repo.name,
        repo_full_name=derive_repo_full_name(remote_url),
        last_commit_at=last_commit_at,
        last_commit_ts=last_commit_ts,
        my_last_commit_ts=my_last_commit_ts,
        my_local_commit_ts=my_local_commit_ts,
        recency_basis=recency_basis,
        head_reflog_ts=head_reflog_ts,
        index_mtime_ts=index_mtime_ts,
        remote_url=remote_url,
        probed_at=probed_at,
        **status,
    )


def scan_focus5_repos(
    roots: list[str] | list[Path], *, device_id: str, probed_at: str,
    max_depth: int = DEFAULT_MAX_DEPTH, stats: dict[str, Any] | None = None,
) -> list[RepoSignals]:
    """Discover repos under *roots* and probe each one's signals.

    ``stats`` (optional) accumulates slow-probe and git-failure diagnostics
    across the scan; see :func:`probe_repo_signals`.
    """
    return [
        probe_repo_signals(repo, device_id=device_id, probed_at=probed_at, stats=stats)
        for repo in iter_git_repos(roots, max_depth=max_depth)
    ]


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

_SIGNAL_COLUMNS = (
    "device_id", "local_path", "repo_name", "repo_full_name", "branch",
    "upstream", "has_upstream", "ahead", "behind", "modified_count",
    "untracked_count", "is_dirty", "last_commit_at", "last_commit_ts",
    "my_last_commit_ts", "my_local_commit_ts", "recency_basis",
    "head_reflog_ts", "index_mtime_ts", "remote_url",
    "probed_at",
)


@dataclass(frozen=True)
class Focus5SyncResult:
    device_id: str
    discovered: int
    roster_size: int
    ranking_mode: str
    scan_roots: list[str]
    computed_at: str
    elapsed_seconds: float = 0.0
    slow_repos: int = 0
    failed_repos: int = 0

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _signal_row(s: RepoSignals) -> tuple:
    d = asdict(s)
    d["has_upstream"] = 1 if s.has_upstream else 0
    d["is_dirty"] = 1 if s.is_dirty else 0
    return tuple(d[c] for c in _SIGNAL_COLUMNS)


def _row_to_signals(row: Any) -> RepoSignals:
    """Reconstruct a RepoSignals from a focus5_repo_signals row (inverse of _signal_row).

    Lets the roster be re-ranked from the cached signals without re-probing git.
    """
    d = {k: row[k] for k in row.keys()}
    d["has_upstream"] = bool(d["has_upstream"])
    d["is_dirty"] = bool(d["is_dirty"])
    return RepoSignals(**{f: d[f] for f in RepoSignals.__dataclass_fields__})


def sync_focus5(
    database_path: Path, *,
    roots: list[str] | list[Path] | None = None,
    device_id: str | None = None,
    mode: str | None = None,
    limit: int = DEFAULT_ROSTER_SIZE,
    max_depth: int = DEFAULT_MAX_DEPTH,
) -> Focus5SyncResult:
    """Scan the device, persist all signals, and rewrite this device's roster.

    Signals and roster are each replaced wholesale for this device inside one
    transaction, so a removed repo never lingers in the cache and a re-rank is
    atomic.
    """
    dev = device_id or get_device_id()
    if roots is None:
        from rebalance.ingest.config import get_focus5_scan_roots
        roots = get_focus5_scan_roots()
    if mode is None:
        from rebalance.ingest.config import get_focus5_ranking_mode
        mode = get_focus5_ranking_mode()
    from rebalance.ingest.config import get_focus5_hidden_repos
    hidden = get_focus5_hidden_repos()

    now = datetime.now(timezone.utc)
    now_ts = int(now.timestamp())
    computed_at = now.isoformat()

    started = perf_counter()
    stats: dict[str, Any] = {}
    signals = scan_focus5_repos(
        roots, device_id=dev, probed_at=computed_at, max_depth=max_depth, stats=stats
    )
    t_scan = perf_counter() - started
    # resolve_ranking_strategy raises on a bad mode BEFORE we touch the DB.
    # Hidden repos still get their signals cached (so an un-hide can re-rank them
    # back in) but are filtered out of the ranked roster.
    t0 = perf_counter()
    ranked = rank_repos(signals, mode=mode, now_ts=now_ts, limit=limit, hidden=hidden)
    t_rank = perf_counter() - t0

    t0 = perf_counter()
    placeholders = ", ".join("?" for _ in _SIGNAL_COLUMNS)
    with db_connection(database_path) as conn:
        run_migrations(conn)  # ensure tables exist even on a direct call
        conn.execute("DELETE FROM focus5_repo_signals WHERE device_id=?", (dev,))
        conn.executemany(
            f"INSERT INTO focus5_repo_signals ({', '.join(_SIGNAL_COLUMNS)}) "
            f"VALUES ({placeholders})",
            [_signal_row(s) for s in signals],
        )
        conn.execute("DELETE FROM focus5_roster WHERE device_id=?", (dev,))
        conn.executemany(
            "INSERT INTO focus5_roster "
            "(device_id, local_path, position, rank_reason, ranking_mode, computed_at) "
            "VALUES (?,?,?,?,?,?)",
            [
                (dev, r.signals.local_path, r.position, r.reason, mode, computed_at)
                for r in ranked
            ],
        )
        conn.commit()
    t_persist = perf_counter() - t0

    elapsed = perf_counter() - started
    slow_repos, failed_repos = len(stats.get("slow", [])), stats.get("failed", 0)
    logger.info(
        "focus5 sync: %d repos in %.2fs (scan %.2fs, rank %.3fs, persist %.3fs); "
        "roster=%d mode=%s slow=%d failed=%d",
        len(signals), elapsed, t_scan, t_rank, t_persist,
        len(ranked), mode, slow_repos, failed_repos,
    )
    if failed_repos:
        logger.warning(
            "focus5 sync: %d/%d repo(s) failed their git probe — health for those is "
            "stale/blank (see per-repo warnings above)", failed_repos, len(signals),
        )

    return Focus5SyncResult(
        device_id=dev,
        discovered=len(signals),
        roster_size=len(ranked),
        ranking_mode=mode,
        scan_roots=[str(r) for r in roots],
        computed_at=computed_at,
        elapsed_seconds=round(elapsed, 3),
        slow_repos=slow_repos,
        failed_repos=failed_repos,
    )


def rerank_focus5_from_cache(
    database_path: Path, *,
    device_id: str | None = None,
    mode: str | None = None,
    limit: int = DEFAULT_ROSTER_SIZE,
) -> int:
    """Re-rank this device's roster from the cached signals — NO git re-probe.

    Reads the persisted ``focus5_repo_signals`` (the off-roster cache of *every*
    discovered repo), re-applies the hidden-repo filter + ranking strategy, and
    rewrites ``focus5_roster``. This is the cheap seam the schema was built for:
    after hiding or un-hiding a repo the board refills from already-probed
    candidates without walking the disk. Returns the new roster size.

    A no-op (returns 0) when the device has no cached signals yet — call
    :func:`sync_focus5` first to populate the cache.
    """
    dev = device_id or get_device_id()
    if mode is None:
        from rebalance.ingest.config import get_focus5_ranking_mode
        mode = get_focus5_ranking_mode()
    from rebalance.ingest.config import get_focus5_hidden_repos
    hidden = get_focus5_hidden_repos()

    now = datetime.now(timezone.utc)
    now_ts = int(now.timestamp())
    computed_at = now.isoformat()

    with db_connection(database_path) as conn:
        run_migrations(conn)
        rows = conn.execute(
            "SELECT * FROM focus5_repo_signals WHERE device_id=?", (dev,)
        ).fetchall()
        signals = [_row_to_signals(r) for r in rows]
        # resolve_ranking_strategy raises on a bad mode BEFORE we touch the roster.
        ranked = rank_repos(signals, mode=mode, now_ts=now_ts, limit=limit, hidden=hidden)
        conn.execute("DELETE FROM focus5_roster WHERE device_id=?", (dev,))
        conn.executemany(
            "INSERT INTO focus5_roster "
            "(device_id, local_path, position, rank_reason, ranking_mode, computed_at) "
            "VALUES (?,?,?,?,?,?)",
            [
                (dev, r.signals.local_path, r.position, r.reason, mode, computed_at)
                for r in ranked
            ],
        )
        conn.commit()

    logger.info(
        "focus5 re-rank from cache: %d candidates -> roster=%d (mode=%s, hidden=%d)",
        len(signals), len(ranked), mode, len(hidden),
    )
    return len(ranked)


# ---------------------------------------------------------------------------
# Read side — what the web view consumes
# ---------------------------------------------------------------------------

def vscode_url(local_path: str) -> str:
    """Build a ``vscode://file/...`` URL that opens the repo root in VS Code."""
    from urllib.parse import quote
    return f"vscode://file{quote(local_path, safe='/')}"


def recent_activity(local_path: str, *, limit: int = 3) -> list[dict[str, Any]]:
    """Return the repo's last *limit* commits (local-first activity), newest first.

    Live read of ``git log``; an inaccessible or empty repo yields ``[]`` rather
    than raising. Uses the unit-separator (0x1f) so commit subjects can contain
    any printable character without breaking the parse.
    """
    out = _git(
        Path(local_path), "log", f"-{limit}",
        "--format=%h%x1f%s%x1f%cI%x1f%ce",
    )
    items: list[dict[str, Any]] = []
    for line in (out or "").splitlines():
        parts = line.split("\x1f")
        if len(parts) == 4:
            items.append({
                "sha": parts[0], "subject": parts[1],
                "committed_at": parts[2], "author_email": parts[3],
            })
    return items


_LIVE_HEALTH_FIELDS = (
    "branch", "upstream", "has_upstream", "ahead", "behind",
    "modified_count", "untracked_count", "is_dirty",
)


def live_health(local_path: str) -> dict[str, Any]:
    """Re-probe just the working-tree health for one repo (single git call).

    This is the Phase 3 freshness path: roster *membership* may be a day old,
    but "did I forget to commit or push?" must be answered against the tree's
    current state. Returns the health fields plus ``health_probed_at``; a repo
    that can't be read yields ``health_available=False`` (never raises).
    """
    probed_at = datetime.now(timezone.utc).isoformat()
    out = _git(Path(local_path), "status", "--porcelain=v2", "--branch")
    if out is None:
        return {"health_available": False, "health_probed_at": probed_at}
    h = _parse_status(out)
    h["health_available"] = True
    h["health_probed_at"] = probed_at
    return h


def get_roster_meta(database_path: Path, *, device_id: str | None = None) -> dict[str, Any]:
    """Cheap roster freshness check (no git, no enrichment): when + how many.

    Lets the web route decide whether to lazily recompute on a stale TTL without
    paying for the full live-probe render first.
    """
    dev = device_id or get_device_id()
    try:
        with db_connection(database_path) as conn:
            row = conn.execute(
                "SELECT computed_at, ranking_mode FROM focus5_roster "
                "WHERE device_id=? ORDER BY position LIMIT 1",
                (dev,),
            ).fetchone()
            n = conn.execute(
                "SELECT COUNT(*) FROM focus5_roster WHERE device_id=?", (dev,)
            ).fetchone()[0]
    except Exception:  # noqa: BLE001 — table absent on a brand-new DB
        return {"computed_at": None, "ranking_mode": None, "roster_size": 0}
    return {
        "computed_at": row["computed_at"] if row else None,
        "ranking_mode": row["ranking_mode"] if row else None,
        "roster_size": n,
    }


def _newest_pr(conn: Any, repo_full_name: str | None) -> dict[str, Any] | None:
    """Newest remote PR (highest number) for *repo_full_name*, or None.

    Enrichment only: a missing corpus row, an unsynced repo, or a non-GitHub
    remote all yield None rather than breaking the card.
    """
    if not repo_full_name:
        return None
    try:
        row = conn.execute(
            "SELECT number, title, state, html_url, is_draft, is_merged "
            "FROM github_items "
            "WHERE repo_full_name=? AND item_type='pull_request' "
            "ORDER BY number DESC LIMIT 1",
            (repo_full_name,),
        ).fetchone()
    except Exception:  # noqa: BLE001 — corpus table may not exist yet
        return None
    if row is None:
        return None
    return {
        "number": row["number"], "title": row["title"], "state": row["state"],
        "html_url": row["html_url"],
        "is_draft": bool(row["is_draft"]), "is_merged": bool(row["is_merged"]),
    }


def _repo_path_live(local_path: Any) -> bool:
    """True if *local_path* is still a git repo on disk (the discovery predicate).

    Mirrors ``iter_git_repos`` (a repo is a dir containing ``.git``): a checkout or
    worktree removed from disk fails this, so a stale cached row can be dropped from
    a read-only ``summarize_focus5`` without waiting for the next full disk resync.
    """
    if not local_path:
        return False
    try:
        p = Path(local_path)
        return p.exists() and (p / ".git").exists()
    except OSError:
        return False


def _build_roster_card(
    conn: Any, base: dict[str, Any], *, with_activity: bool, with_live_health: bool,
) -> dict[str, Any]:
    """Finish one roster card: coerce flags, attach the open/PR/activity enrichments.

    *base* must already carry every signal column plus ``position``,
    ``rank_reason``, ``ranking_mode`` and ``computed_at`` — whether that came from
    the persisted ``focus5_roster`` join or an in-memory rerank. Shared so both
    the default (persisted) and transient (re-ranked) views render identically.
    """
    card = dict(base)
    card["is_dirty"] = bool(card["is_dirty"])
    card["has_upstream"] = bool(card["has_upstream"])
    card["vscode_url"] = vscode_url(card["local_path"])
    card["newest_pr"] = _newest_pr(conn, card.get("repo_full_name"))
    card["recent_activity"] = (
        recent_activity(card["local_path"]) if with_activity else []
    )
    # Overlay live working-tree health on top of the stored snapshot so "did I
    # forget to commit/push?" is answered against now.
    if with_live_health:
        lh = live_health(card["local_path"])
        if lh.get("health_available"):
            for k in _LIVE_HEALTH_FIELDS:
                card[k] = lh[k]
        card["health_available"] = lh.get("health_available", True)
        card["health_probed_at"] = lh["health_probed_at"]
    else:
        card["health_available"] = True
        card["health_probed_at"] = card.get("probed_at")
    return card


def summarize_focus5(
    database_path: Path, *, device_id: str | None = None,
    with_activity: bool = True, with_live_health: bool = True,
    mode: str | None = None, drop_missing_paths: bool = True,
) -> dict[str, Any]:
    """Return the roster cards, off-roster warnings, and snapshot metadata.

    This is the single read contract for the web view, and the one place that
    owns the repo-card shape. Each roster card carries local signals, a
    ``vscode_url`` open action, a ``newest_pr`` enrichment (None when the GitHub
    corpus can't supply it), and the last 3 local commits as ``recent_activity``.

    **Default view** (``mode=None``): roster *membership* comes from the persisted
    ``focus5_roster`` snapshot (the headline ``recent_activity`` ranking).

    **Transient view** (``mode`` given): the cached ``focus5_repo_signals`` are
    re-ranked in memory under *mode* and rendered **without rewriting the
    persisted roster** — this is how the **Dirty Five** view shows ``dirty_first``
    over the same snapshot while ``/focus-5`` still defaults to ``recent_activity``.
    Membership freshness then reflects the signals' ``probed_at`` (the last sync).

    Freshness split: roster *membership* comes from the snapshot, but each card's
    working-tree **health is re-probed live** here (``with_live_health``) and
    stamped with ``health_probed_at`` — so commit/push reminders reflect the tree
    right now, not the last sync. Off-roster warnings stay cached (we never
    live-sweep the whole machine per request).

    Both ``with_activity`` and ``with_live_health`` are bounded to the top-5 and
    can be disabled for a pure DB read.
    """
    dev = device_id or get_device_id()
    empty = {
        "roster": [], "off_roster_warnings": [], "dirty_banner": None,
        "computed_at": None, "ranking_mode": None,
        "summary": {"discovered": 0, "roster_size": 0,
                    "off_roster_attention": 0, "rank_cutoff_ts": None},
    }
    try:
        with db_connection(database_path) as conn:
            if mode is None:
                # Default view: membership from the persisted recent_activity snapshot.
                rows = conn.execute(
                    "SELECT r.position, r.rank_reason, r.ranking_mode, r.computed_at, s.* "
                    "FROM focus5_roster r JOIN focus5_repo_signals s "
                    "  ON s.device_id=r.device_id AND s.local_path=r.local_path "
                    "WHERE r.device_id=? ORDER BY r.position",
                    (dev,),
                ).fetchall()
                bases = [{k: row[k] for k in row.keys()} for row in rows]
            else:
                # Transient view (Dirty Five): re-rank the cached signals in memory
                # under *mode* — never writes focus5_roster, so the default snapshot
                # stays put. Freshness = the signals' probed_at (the last sync).
                from rebalance.ingest.config import get_focus5_hidden_repos
                signals = [
                    _row_to_signals(r) for r in conn.execute(
                        "SELECT * FROM focus5_repo_signals WHERE device_id=?", (dev,)
                    ).fetchall()
                ]
                now_ts = int(datetime.now(timezone.utc).timestamp())
                ranked = rank_repos(signals, mode=mode, now_ts=now_ts,
                                    hidden=get_focus5_hidden_repos())
                computed_at = signals[0].probed_at if signals else None
                bases = [
                    {**asdict(r.signals), "position": r.position, "rank_reason": r.reason,
                     "ranking_mode": mode, "computed_at": computed_at}
                    for r in ranked
                ]
            # Drop cached entries whose checkout/worktree was removed from disk
            # (GH-109): the Mac app's refresh is read-only and never re-scans, so a
            # deleted repo would otherwise linger until the next full sync. Off for
            # pure-ranking unit tests that seed synthetic (non-on-disk) signal rows.
            if drop_missing_paths:
                bases = [b for b in bases if _repo_path_live(b.get("local_path"))]
            roster = [
                _build_roster_card(conn, b, with_activity=with_activity,
                                   with_live_health=with_live_health)
                for b in bases
            ]

            roster_paths = {c["local_path"] for c in roster}
            # Hidden repos are suppressed from the off-roster attention strip too —
            # otherwise hiding a *dirty* repo would just relocate it from a card
            # into the nag strip, the opposite of what the ✕ promises.
            from rebalance.ingest.config import get_focus5_hidden_repos
            hidden = set(get_focus5_hidden_repos())
            warn_rows = conn.execute(
                "SELECT repo_name, local_path, repo_full_name, branch, ahead, "
                "       modified_count, untracked_count, is_dirty, probed_at, "
                "       my_local_commit_ts, recency_basis "  # GH-81 minimal explain
                "FROM focus5_repo_signals "
                "WHERE device_id=? AND (is_dirty=1 OR ahead>0) "
                "ORDER BY is_dirty DESC, ahead DESC, repo_name",
                (dev,),
            ).fetchall()
            off_roster = []
            for w in warn_rows:
                if w["local_path"] in roster_paths:
                    continue
                if drop_missing_paths and not _repo_path_live(w["local_path"]):  # GH-109
                    continue
                if (w["repo_full_name"] or w["local_path"]) in hidden:
                    continue
                wd = {**{k: w[k] for k in w.keys()}, "is_dirty": bool(w["is_dirty"])}
                wd["warning_reason"] = off_roster_reason(wd)
                off_roster.append(wd)

            discovered = conn.execute(
                "SELECT COUNT(*) FROM focus5_repo_signals WHERE device_id=?", (dev,)
            ).fetchone()[0]
    except Exception:  # noqa: BLE001 — tables absent on a brand-new DB
        return empty

    # GH-81 minimal explain: the #5 cutoff is the resolved local-commit recency of
    # the lowest-ranked rostered repo — the threshold an off-roster repo must beat
    # to make the board. Lets QA distinguish "fixed ranking" from a new silent bias
    # (read each off-roster repo's my_local_commit_ts + recency_basis against this).
    # Only meaningful for the headline recent_activity board: the explain copy
    # ("below the #5 cutoff", "Focus 5") is recent_activity-specific, so a transient
    # view (Dirty Five reranks under dirty_first) must NOT publish a cutoff that the
    # renderer would then mislabel with Focus 5 semantics. (Codex relay r2.)
    rank_cutoff_ts = roster[-1].get("my_local_commit_ts") if (roster and mode is None) else None
    # GH-105: single "BTW, this went dirty" nudge — headline board only. Like
    # rank_cutoff_ts above, a transient Dirty Five rerank (mode is not None)
    # already shows every dirty repo as a full card, so the banner would be
    # redundant there; gate it to the default recent_activity view.
    dirty_banner = pick_newest_dirty_off_roster(off_roster) if mode is None else None

    return {
        "roster": roster,
        "off_roster_warnings": off_roster,
        "dirty_banner": dirty_banner,
        "computed_at": roster[0]["computed_at"] if roster else None,
        "ranking_mode": roster[0]["ranking_mode"] if roster else None,
        "summary": {
            "discovered": discovered,
            "roster_size": len(roster),
            "off_roster_attention": len(off_roster),
            "rank_cutoff_ts": rank_cutoff_ts,
        },
    }
