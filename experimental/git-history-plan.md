# Git History Plan

## Problem Statement

A coder juggling 6-7 active projects across 2-3 machines loses the thread of their own work. Context lives in scattered places: terminal scrollback on whichever laptop was nearest, VS Code recent-files lists that don't cross machines, GitHub activity feeds that conflate meaningful local work with noise, and commit histories that require walking repo-by-repo to reconstruct.

The usual fix is an orchestration script that every AI agent or workflow is supposed to invoke. That fails in practice: it relies on remembering to tell each agent to run it, every session, every machine. The friction is the failure mode.

This project explores whether a **passive, always-on collector** — running in the background on each machine, writing to a single synced markdown file — can replace that active discipline. If any agent or human can read `GIT-HISTORY.md` without being asked to run anything, the context problem gets solved once rather than every session.

The open question is whether a file this simple is actually enough to be useful, or whether the real value requires richer structure (issue/PR activity, intent capture, cross-referencing). Phase 0 deliberately starts minimal to find out.

## TOC
- Problem Statement
- Overview
- Phase 0 Spike
- Architecture
- Commit Attribution
- File Format
- Sync Strategy
- State & Config
- Registry Integration
- Deliverables
- Out of Scope
- Risks
- Success Criteria
- Next Steps

## Overview

Goal: passively build a personal, cross-machine log of local git commits across 6-7 active projects, so that any AI agent or future-me can answer "what did I touch on Tuesday" without being told to look.

Motivating friction: asking each VS Code agent to invoke an orchestration script is easy to forget. A background collector avoids that entirely — agents (and humans) just read a file.

This first pass is intentionally isolated in `/experimental/git-history/`:
- no agent invocation required
- no commit-message mutation
- no external service beyond a private GitHub repo the user already owns
- no dependency on rebalance-OS internals yet (see Registry Integration)

## Phase 0 Spike

### Checklist
- [ ] Bash collector script that walks a known list of repo paths and appends new local commits to a per-machine markdown file
- [ ] Reflog-based attribution so only locally-authored commits are logged
- [ ] launchd agent that runs the script every 10 min
- [ ] Private GitHub repo (not gist) as the sync target, one file per machine
- [ ] One-shot `install.sh` that sets up the launchd plist, config dir, and private repo
- [ ] Dry-run mode that prints what would be appended without writing

### Scope

~2-3 hour spike to validate:
- `git reflog` reliably distinguishes local commits from pulled/fetched ones
- launchd cadence is sufficient (no missed commits between runs)
- per-machine files eliminate the merge-conflict problem without losing readability
- the resulting file is actually useful to the user during a real week of work

## Architecture

### Components
- **Collector** (`collect.sh`) — idempotent bash script. Reads repo list, checks each for new local commits since last run, appends to `history-<hostname>.md`, commits & pushes to the private repo.
- **launchd agent** (`com.user.git-history.plist`) — triggers collector every 10 min. Uses `StartInterval`, not `StartCalendarInterval`, so it fires on wake after sleep.
- **Sync repo** — private GitHub repo, one `history-<hostname>.md` per machine, plus an optional `README.md` describing aggregation.
- **Installer** (`install.sh`) — provisions config dir, writes plist to `~/Library/LaunchAgents/`, clones the sync repo, runs first collection.

### Data flow
```
  launchd (every 10m)
    → collect.sh
        → for each repo in list:
            git reflog --since=<last-run> --pretty=...
            filter to entries where the reflog action is "commit" or "commit (initial)"
            append entries to history-<hostname>.md
        → git add/commit/push in the sync repo
    → write last-run timestamp
```

## Commit Attribution

### Reflog-based (preferred)
`git reflog show --date=iso --pretty='%H %gs %s'` lists every ref update. The `%gs` field (reflog subject) starts with `commit:` or `commit (initial):` for locally-authored commits, and `pull:` / `fetch:` / `merge:` for ones brought in from elsewhere.

Only entries matching `^commit` get logged, and they are tagged with `$(scutil --get ComputerName)` (or `$HOSTNAME` as fallback) in the output.

### Why not a prepare-commit-msg hook
- mutates commit messages forever
- requires install in every repo (including newly cloned ones)
- doesn't cover commits made before the hook was installed

### Why not committer email
- feasible but fragile: users often forget to override `user.email` per machine
- conflates identity with location

## File Format

Each machine's `history-<hostname>.md` is append-only, reverse-chronological within each run block, flat across repos:

```markdown
# Git history — mac-studio

## 2026-04-20

### 14:32  rebalance-OS  main
- `a1b2c3d` Add experimental GH close-candidates action spike

### 11:07  neochrome-site  feature/pricing
- `9f8e7d6` Tweak pricing grid spacing
- `5c4b3a2` Fix mobile nav overflow

## 2026-04-19

### 22:15  dotfiles  main
- `7e6d5c4` Bump neovim plugin pins
```

Grouping: day header → time+repo+branch subheader → one bullet per commit. Branch recorded as `HEAD`'s branch at reflog time. Short SHA + subject line only; full details live in the repo itself.

## Sync Strategy

Private GitHub repo via `gh repo create --private git-history`. Each machine:
- clones to `~/.config/git-history/repo/`
- owns one file (`history-<hostname>.md`)
- pulls before append, pushes after

Merge conflicts are effectively impossible because each machine only edits its own file. If two machines race on a push, the losing one retries after a pull — trivial since nothing else touches its file.

Aggregated view is `cat history-*.md | sort` or a small `view.sh` that merges and re-sorts chronologically.

## State & Config

Outside the rebalance-OS repo, in `~/.config/git-history/`:
- `config.toml` — list of repo paths, sync repo URL, hostname override (if desired)
- `last-run` — ISO timestamp of last successful run (used as `--since` for reflog)
- `repo/` — checked-out sync repo

Rationale: the *script* is experimental and versioned with rebalance-OS; the *data and state* are personal and cross-machine, so they live in the user's home.

## Registry Integration

rebalance-OS already maintains a project registry with repo paths. Phase 0 hardcodes the repo list in `config.toml`. If the tool survives the 4x-in-a-week test, Phase 2 reads repos directly from the rebalance registry — which then becomes a real reason to keep it in this monorepo rather than spin it off.

## Deliverables

### First-pass files
- `experimental/git-history/collect.sh`
- `experimental/git-history/install.sh`
- `experimental/git-history/com.user.git-history.plist.template`
- `experimental/git-history/config.example.toml`
- `experimental/git-history/README.md`
- `experimental/git-history-plan.md` (this file)

### Deferred
- Linux/cron variant of the launchd agent
- Pulling repo list from rebalance-OS registry
- Richer per-commit context (files changed, diff stats)
- Web viewer / dashboard
- LLM summarization over the history file

## Out of Scope

- capturing commits authored on other machines (redundant — those machines will log them)
- GitHub issue / PR activity (separate concern; gh-close-candidates already covers some of this)
- Obsidian vault note generation
- any write-back into project repos

## Risks

- **launchd sleep behavior** — `StartInterval` fires on wake, but if the machine is asleep for days the reflog may have aged past any sensible `--since` window. Mitigate by using `last-run` timestamp, not a fixed window.
- **Repo deletion / re-clone** — if a repo is deleted and re-cloned, reflog resets and old commits won't be re-logged. Acceptable; the history already captured them.
- **Push-race on shared file** — impossible by design (per-machine file), but worth a test.
- **Private repo PAT scope** — sync push requires `repo` scope, broader than the `repo:read` PAT rebalance-OS already asks for. Keep them as separate tokens.
- **Hostname drift** — renaming a mac means a new file starts. Tolerable, but document it.

## Success Criteria

The user touches, reads, greps, or extends the tool **more than 4 times in the first week** after install. If yes: spin off into its own repo, wire it into the rebalance-OS project registry, and upgrade the data format. If no: delete `experimental/git-history/`, keep this plan as a record of the attempt.

## Next Steps

### Phase 1 — spike
- write `collect.sh` + `install.sh`
- run on one machine against 2-3 repos
- verify reflog attribution is correct under pull/rebase/cherry-pick

### Phase 2 — multi-machine
- install on second machine
- verify per-machine file isolation
- add `view.sh` aggregator

### Phase 3 — integration (only if 4x threshold met)
- source repo list from rebalance-OS project registry
- expose a single MCP tool (`recent_commits(days=7)`) so agents can read the history without file access
- consider folding into rebalance-OS proper, out of `/experimental`
