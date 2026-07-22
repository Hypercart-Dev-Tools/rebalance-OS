#!/usr/bin/env bash
# live-signal-active-git :: deterministic device-wide git-activity collector
# -----------------------------------------------------------------------------
# Emits a structured, machine-readable report of RECENT GIT ACTIVITY across every
# repo on this device. Worktrees are one facet of that activity, NOT the whole
# picture: branch tips, ahead/behind vs base, dirty state, and recent commits are
# reported for every active repo whether or not it has linked worktrees.
#
# SAFETY (see WORKTREE-SAFETY.md at repo root):
#   * READ-ONLY. Runs only read-only tools: find, git (rev-parse/log/status/
#     rev-list/worktree list), and read-only text/file utilities (ls, stat, awk,
#     grep, head, wc, tr, cut, sed, basename). NOTHING here mutates a tree.
#   * NEVER rm / mv / prune / gc / --force / branch -D, and NEVER executes a
#     repo-owned script (e.g. pdda.sh): the optional PDDA annotation below only
#     STATs and LISTs files — it never runs repo tooling.
#   * Parses `git worktree list --porcelain` (stable API), never the human table.
#   * No temp files (sandbox-safe); repo list is held in a shell variable.
#
# DETERMINISM: same tree state + same window => same GIT report shape. Freshness
# tags and skip rules are fixed thresholds; ordering is `sort -u` stable. The
# optional PDDA annotation (pdda=/inbox=/working=/working_doc lines) is EXCLUDED
# from this guarantee: it reflects advisory filesystem state (mtime), so a bare
# touch/checkout can change which docs appear, their order, and their shown time
# with no git/content change. It never feeds a freshness tag.
#
# Usage:
#   collect.sh [ROOT ...]            # override scan roots (default = dev roots below)
#   LSAG_WINDOW_DAYS=7 collect.sh    # "recent" horizon for commits/warm classification
# -----------------------------------------------------------------------------
set -uo pipefail

WINDOW_DAYS="${LSAG_WINDOW_DAYS:-7}"
# Uncommitted changes only count as "activity" if the repo was also touched
# recently; stray dirt in a long-abandoned clone is noise, not work.
DIRTY_GRACE_DAYS="${LSAG_DIRTY_GRACE_DAYS:-30}"

if [ "$#" -gt 0 ]; then
  ROOTS=("$@")
else
  ROOTS=(
    "$HOME/Documents"
    "$HOME/Local Sites"
    "$HOME/Valet-Sites"
    "$HOME/wt"
    "$HOME/bin"
    "$HOME/Library/Mobile Documents/com~apple~CloudDocs/Documents/05 - Local Installs"
    "$HOME/.claude"
  )
fi

now=$(date +%s)
cutoff=$(( now - WINDOW_DAYS * 86400 ))

echo "# LIVE-SIGNAL :: device git activity"
echo "generated_epoch=$now window_days=$WINDOW_DAYS"
echo

# --- 1. Discover unique repo/worktree toplevels (prune heavy vendor dirs) ------
repos=$(
  for r in "${ROOTS[@]}"; do
    [ -e "$r" ] || continue
    find "$r" \
      \( -name node_modules -o -name vendor -o -name .Trash -o -name Pods -o -name .venv \) -prune -o \
      -name .git -print 2>/dev/null
  done | while read -r g; do
    git -C "$(dirname "$g")" rev-parse --show-toplevel 2>/dev/null
  done | sort -u
)
echo "scanned_repos=$(printf '%s\n' "$repos" | grep -c .)"
echo

# --- helpers ------------------------------------------------------------------
# Pick the base ref for ahead/behind: the TRUNK, so ahead/behind measures how
# much unmerged work a branch carries (and ahead==0 => merged), not mere sync
# with the branch's own remote. Prefer origin's default branch, then common
# trunks. Empty => unknown (reported as ?).
base_ref() {
  local repo="$1" d c
  d=$(git -C "$repo" symbolic-ref -q refs/remotes/origin/HEAD 2>/dev/null | sed 's#refs/remotes/##')
  [ -n "$d" ] && { echo "$d"; return; }
  for c in origin/development origin/main origin/master development main master; do
    git -C "$repo" rev-parse --verify -q "$c" >/dev/null 2>&1 && { echo "$c"; return; }
  done
  echo ""
}

# Deterministic freshness tag from age + divergence-vs-trunk (ahead/behind).
#   ACTIVE  committed today (age_days <= 0)
#   WARM    carries unmerged commits (ahead>0), committed within the window
#   STALE   carries unmerged commits (ahead>0), older than the window
#   MERGED  no unmerged commits (ahead==0) AND behind trunk — work has landed
#   SYNCED  no unmerged commits and level with trunk — nothing outstanding
# NOTE: WARM/STALE require ahead>0. A branch level with (or merged into) the trunk
# never carries unmerged work, so it can never be WARM/STALE — it is SYNCED/MERGED.
fresh_tag() {
  local age_days="$1" ahead="$2" behind="$3"
  if [ "$age_days" -le 0 ]; then echo "ACTIVE"; return; fi
  if [ "${ahead:-0}" -gt 0 ]; then
    if [ "$age_days" -le "$WINDOW_DAYS" ]; then echo "WARM"; else echo "STALE"; fi
    return
  fi
  if [ "${behind:-0}" -gt 0 ]; then echo "MERGED"; else echo "SYNCED"; fi
}

# mtime of a file as a stable "YYYY-MM-DD HH:MM" string, for the optional PDDA
# annotation. macOS ships BSD stat (-f format string); GNU/Linux ships GNU stat
# (-c format) — and a BSD-style `-f` on GNU means --file-system and would emit
# garbage, so SELECT the implementation by OS rather than probe-and-fallback.
# Advisory only (see DETERMINISM note); any failure yields an empty string.
case "$(uname -s)" in
  Darwin|*BSD) pdda_mtime() { stat -f '%Sm' -t '%Y-%m-%d %H:%M' "$1" 2>/dev/null; } ;;
  *)           pdda_mtime() { stat -c '%y' "$1" 2>/dev/null | cut -c1-16; } ;;
esac

# --- 2. Group by shared object store (git-common-dir) so each worktree set is
#        reported exactly once, with per-worktree detail.
#        (bash 3.2 on macOS has no `declare -A`, so dedup via a newline list.) --
SEEN_LIST=""
while IFS= read -r repo; do
  [ -z "$repo" ] && continue
  common=$(git -C "$repo" rev-parse --git-common-dir 2>/dev/null) || continue
  case "$common" in /*) : ;; *) common=$(cd "$repo" && cd "$common" 2>/dev/null && pwd -P) ;; esac
  [ -z "$common" ] && continue
  case $'\n'"$SEEN_LIST"$'\n' in *$'\n'"$common"$'\n'*) continue ;; esac
  SEEN_LIST="$SEEN_LIST"$'\n'"$common"

  # Enumerate this group's worktrees from porcelain (path\tbranch pairs).
  wt_pairs=$(git -C "$repo" worktree list --porcelain 2>/dev/null | awk '
    /^worktree /{p=substr($0,10)}
    /^branch /{b=$2; print p "\t" b; p=""}
    /^detached/{print p "\t(detached)"; p=""}')
  wt_n=$(printf '%s\n' "$wt_pairs" | grep -c .)

  # Decide whether this group is worth reporting: more than one worktree
  # (topology is itself signal), OR any worktree committed within the window,
  # OR uncommitted work in a repo that is at least recent-ish (dirty grace).
  dirty_grace_cut=$(( now - DIRTY_GRACE_DAYS * 86400 ))
  report=0
  [ "$wt_n" -gt 1 ] && report=1
  while IFS=$'\t' read -r wpath wbranch; do
    [ -z "$wpath" ] && continue
    e=$(git -C "$wpath" log -1 --format=%ct 2>/dev/null || echo 0)
    d=$(git -C "$wpath" status --porcelain 2>/dev/null | wc -l | tr -d ' ')
    [ "${e:-0}" -ge "$cutoff" ] && report=1
    # Dirty counts as activity if the repo is recent-ish OR brand-new (e==0, no
    # commits yet — git log failed, so the grace-window test would wrongly skip it).
    { [ "${d:-0}" -gt 0 ] && { [ "${e:-0}" -eq 0 ] || [ "${e:-0}" -ge "$dirty_grace_cut" ]; }; } && report=1
  done <<< "$wt_pairs"
  [ "$report" -eq 0 ] && continue

  # Repo label = parent working dir of the common .git (the primary worktree root).
  primary=$(printf '%s\n' "$wt_pairs" | head -1 | cut -f1)
  echo "## REPO $primary"
  echo "common_dir=$common worktrees=$wt_n"

  # --- optional PDDA lifecycle annotation (structural, advisory; GH-193) -------
  # Emitted ONLY when the PDDA-unique contract file PROJECT/PDDA.md exists, so a
  # non-PDDA repo (even one that merely carries a ROUTER.md) stays byte-for-byte
  # unchanged. Filesystem probes only — never runs pdda.sh or any repo script,
  # never affects the freshness tag. Order/membership are mtime-derived and thus
  # advisory (see DETERMINISM). Counts every *.md so the label matches the count.
  if [ -f "$primary/PROJECT/PDDA.md" ]; then
    inbox_n=$(ls "$primary"/PROJECT/1-INBOX/*.md 2>/dev/null | grep -c .)
    working_n=$(ls "$primary"/PROJECT/2-WORKING/*.md 2>/dev/null | grep -c .)
    echo "  pdda=yes inbox=$inbox_n working=$working_n"
    ls -t "$primary"/PROJECT/2-WORKING/*.md 2>/dev/null | head -3 | while read -r wd; do
      echo "    working_doc=$(basename "$wd") mtime=$(pdda_mtime "$wd")"
    done
  fi

  while IFS=$'\t' read -r wpath wbranch; do
    [ -z "$wpath" ] && continue
    e=$(git -C "$wpath" log -1 --format=%ct 2>/dev/null || echo 0)
    last=$(git -C "$wpath" log -1 --format='%h %ci %s' 2>/dev/null)
    dirty=$(git -C "$wpath" status --porcelain 2>/dev/null | wc -l | tr -d ' ')
    base=$(base_ref "$wpath")
    behind=0; ahead=0
    if [ -n "$base" ]; then
      read -r behind ahead < <(git -C "$wpath" rev-list --left-right --count "$base"...HEAD 2>/dev/null || echo "0 0")
    fi
    # Brand-new repo (no commits): e==0 would make age_days absurd. Treat as
    # freshly-active WIP so its uncommitted work is surfaced, not buried as STALE.
    if [ "${e:-0}" -eq 0 ]; then age_days=0; else age_days=$(( (now - e) / 86400 )); fi
    tag=$(fresh_tag "$age_days" "${ahead:-0}" "${behind:-0}")
    [ -z "$last" ] && last="(no commits yet)"
    linked="primary"; [ "$wpath" != "$primary" ] && linked="linked"
    echo "  - WORKTREE $wpath"
    echo "    kind=$linked branch=$wbranch fresh=$tag base=${base:-?} behind=${behind:-?} ahead=${ahead:-?} dirty=$dirty age_days=$age_days"
    echo "    last_commit=$last"
    # Recent commits on this worktree's branch within the window (topology-agnostic activity).
    rc=$(git -C "$wpath" log --since="@$cutoff" --format='      %h %ci %s' 2>/dev/null | head -12)
    if [ -n "$rc" ]; then
      echo "    recent_commits(<=${WINDOW_DAYS}d):"
      printf '%s\n' "$rc"
    fi
  done <<< "$wt_pairs"
  echo
done <<< "$repos"

echo "# END"
