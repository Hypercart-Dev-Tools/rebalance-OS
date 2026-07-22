---
gh_issue: 190
source: https://github.com/Hypercart-Dev-Tools/rebalance-OS/issues/190
title: "Skill: rebalance live-signal-active-git — morning brief fusing HiQS signal + device-wide git activity"
status: "Built + validated (162 repos scanned, bash -n clean, freshness tags match reality). Retroactive capture of already-shipped tooling. Remaining: global symlink, /relay-xyz QA with agy, commit on a waived-PR branch."
created: 2026-07-22
doc_type: tooling
effort: 1
complexity: 2
risk: 1
phases: 1
---

# GH-190 — Skill: rebalance live-signal-active-git

## Why this exists

Every morning the operator asks one question — **"what am I actually working on right now?"** —
and answering it well requires reconciling two independent things that routinely disagree:

1. **What the day says to do** — the Rebalance/HiQS ranked "what's next" verdict (calendar,
   GitHub, Sleuth, vault, email).
2. **What the code shows is being built** — recent git activity across every repo on the device.

On 2026-07-22 these diverged sharply: HiQS ranked a wall of client meetings first, while the
actual hands-on-keyboard code was an `xyz-3-agents-swarm` installer marathon plus a fresh GH-281
Sentinel triage — in a different repo entirely, invisible to a meeting-centric read. A repeatable
skill that fuses both sources and **names the divergence** turns a manual, easy-to-get-wrong
morning scan into a deterministic brief.

A key framing correction is baked in: this is **recent git activity across the whole device, of
which worktrees are one facet** — not a worktree tool. A single-branch repo with fresh commits is
just as much "active git" as a repo carrying five linked worktrees.

## Key concepts

- **Two-source reconciliation.** `mcp__rebalance__get_next_actions` (cached HiQS verdict, no
  recompute) + a device-wide git scan, synthesized into one brief that leads with the
  reconciliation, not raw dumps.
- **Deterministic collector.** `collect.sh` scans fixed dev roots, dedupes repos by shared
  `git-common-dir`, and for every worktree reports branch, ahead/behind **vs trunk**, dirty
  count, age, and recent commits. Same tree state + window → same report shape.
- **Freshness tags** (from age + divergence-vs-trunk): `ACTIVE` (committed today), `WARM`
  (in-window, unmerged), `MERGED` (`ahead==0` → landed; cleanup candidate), `STALE` (parked).
- **Read-only by construction.** Runs only `find` + read-only `git`. Never `rm`/`mv`/`prune`/
  `gc`/`branch -D`/`--force`. Any cleanup it *suggests* is a separate operator-confirmed action
  routed through `WORKTREE-SAFETY.md`.
- **Portability guards learned in-build:** macOS bash 3.2 (no `declare -A`), no temp files
  (sandbox-safe), `--porcelain` parsing only (never the human table), CWD-independent (absolute
  scan roots).

## Provisional triage

| Dimension | Rating | Note |
|---|---|---|
| effort | 1 | Two small files; built and validated in one session. |
| complexity | 2 | Cross-repo scan + deterministic classification + bash 3.2/sandbox portability. |
| risk | 1 | Read-only; cannot mutate git. Only follow-on cleanup offers carry risk, and those are gated by `WORKTREE-SAFETY.md`. |

## What was built

- `.claude/skills/rebalance/live-signal-active-git/SKILL.md` — the synthesizing skill
  (procedure, freshness legend, fixed output structure, guardrails).
- `.claude/skills/rebalance/live-signal-active-git/collect.sh` — the deterministic, read-only
  device-wide git-activity collector.

## Phase 1 — Ship + integrate (this capture)

- [x] Author `collect.sh` (deterministic, read-only, porcelain, trunk-based ahead/behind).
- [x] Author `SKILL.md` (two-source reconciliation, freshness tags, safety, fixed brief shape).
- [x] Validate live: 162 repos scanned, `bash -n` clean, tags match manual analysis.
- [ ] Symlink into the global `~/.claude/skills` so it is available across projects.
- [ ] `/relay-xyz` QA pass with agy: UX, stated goals, and technical accuracy of the skill files.
- [ ] Commit on a new branch (operator waived the usual branch → PR flow for this small task).

## QA checklist (litmus)

- [ ] Skill resolves and runs from a foreign CWD / another repo (path-independence).
- [ ] Collector emits zero mutating git commands (grep the script for `rm|mv|prune|gc|--force|-D`).
- [ ] Freshness tags reconcile with `git worktree list --porcelain` + `rev-list` by hand on ≥2 repos.
- [ ] `mcp__rebalance__get_next_actions` failure path falls back to `ask(...).hiqs` as documented.

## Anti-goals

- Not a worktree manager — it never creates, moves, prunes, or removes worktrees.
- Not a replacement for `rebalance doctor` or the dashboard; it is a morning reconciliation read.
- Does not recompute the HiQS ranking (reads the cached verdict only).
