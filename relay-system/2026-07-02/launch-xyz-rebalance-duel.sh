#!/usr/bin/env bash
# launch-xyz-rebalance-duel.sh — set up the XYZ⇄Rebalance integration brainstorm duel.
#
# What it does (idempotent, safe):
#   1. Preflights the rebalance-hosted paths (vendored poll.sh, tick, relay thread).
#   2. Commits the relay thread in REBALANCE, path-scoped, no push — so the first turn
#      isn't parked by the scope-clean gate (a dirty/untracked artifact => poll idles).
#   3. Computes the deadline ONCE (literal) and prints the two paste-ready /loop strings.
#
# It launches nothing itself — /loop is an interactive Claude Code command. Paste each
# printed block into its window. Nothing here writes to the XYZ repo.
set -euo pipefail

REB="/Users/noelsaw/Documents/rebalance-OS"
XYZ="/Users/noelsaw/Documents/GH Repos/xyz-3-agents-swarm"
POLL="$REB/.xyz/relay-automation/poll.sh"
RELAY="$REB/relay-system/2026-07-02/xyz-rebalance-integration.md"
REL_RELAY="relay-system/2026-07-02/xyz-rebalance-integration.md"   # path-scoped, relative to $REB
MINUTES="${1:-90}"                                                 # brainstorm window; override: launch ... 120

# --- 1. preflight -----------------------------------------------------------
for p in "$POLL" "$REB/.xyz/bin/tick" "$RELAY"; do
  [[ -e "$p" ]] || { echo "PREFLIGHT FAIL: missing $p" >&2; exit 1; }
done
echo "preflight ok · poll=$POLL"

# --- 2. commit the thread in rebalance (path-scoped, no push) ---------------
# Only stages THIS file, so rebalance's other uncommitted work is untouched.
if [[ -n "$(git -C "$REB" status --porcelain -- "$REL_RELAY")" ]]; then
  git -C "$REB" add "$REL_RELAY"
  git -C "$REB" commit -q -m "duel(xyz-reb): scaffold integration brainstorm thread"
  echo "committed thread in rebalance ($(git -C "$REB" rev-parse --short HEAD)) — not pushed"
else
  echo "thread already clean in rebalance — no commit needed"
fi

# --- 3. deadline + paste-ready loops ---------------------------------------
DEADLINE=$(date -v+"${MINUTES}"M +%s 2>/dev/null || date -d "+${MINUTES} minutes" +%s)
echo "deadline epoch: $DEADLINE  (~${MINUTES} min from now)"
echo
echo "================= WINDOW A — claude-xyz (XYZ-harness seat) ================="
echo "Open on the XYZ repo for context if you like; it writes ONLY to rebalance."
cat <<LOOP_A

/loop 60s run env POLL_GIT_ROOT="$REB" "$POLL" --mode relay --turn-source file --agent claude-xyz --claude-agents "claude-xyz,claude-reb" --relay-file "$RELAY" --deadline $DEADLINE --dry-run ; if it printed "DECISION: run-runner", take your claude-xyz turn on "$RELAY" per its Deliverable + TAKE YOUR TURN blocks: you are the XYZ-harness maintainer — propose/refine XYZ⇄Rebalance integration seams, reading "$XYZ" by ABSOLUTE path for reference but WRITING ONLY to the rebalance relay file; update the Top-3 Candidates table, append a tight round block, set "NEXT: claude-reb", then commit ONLY the relay file in rebalance and DO NOT push: git -C "$REB" add "$REL_RELAY" && git -C "$REB" commit -m "duel(xyz-reb): claude-xyz round" (NEVER git-add anything under "$XYZ"). On "DECISION: stop", CronList + CronDelete this loop, then stop. Else do nothing.
LOOP_A
echo
echo "================= WINDOW B — claude-reb (Rebalance seat) ==================="
echo "Open on rebalance-OS."
cat <<LOOP_B

/loop 60s run env POLL_GIT_ROOT="$REB" "$POLL" --mode relay --turn-source file --agent claude-reb --claude-agents "claude-xyz,claude-reb" --relay-file "$RELAY" --deadline $DEADLINE --dry-run ; if it printed "DECISION: run-runner", take your claude-reb turn on "$RELAY": you are the Rebalance maintainer — ground and challenge each seam with Rebalance's real architecture (its DB/registry, Focus5Float, reminders/pulse, DASHBOARD, its vendored .xyz); update the Top-3 Candidates table, append a tight round block; if the Top-3 are agreed and stable set "STATUS: Closed", otherwise set "NEXT: claude-xyz". Then commit ONLY the relay file in rebalance and DO NOT push: git -C "$REB" add "$REL_RELAY" && git -C "$REB" commit -m "duel(xyz-reb): claude-reb round". On "DECISION: stop", CronList + CronDelete this loop, then stop. Else do nothing.
LOOP_B
echo
echo "The duel self-closes on STATUS: Closed (reb sets it) or the deadline. Review the final"
echo "Top-3 Candidates table in: $RELAY"
