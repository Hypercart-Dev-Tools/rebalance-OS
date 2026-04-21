# git-history

Passive, always-on collector that appends locally-authored git commits from a fixed set of repos to a per-machine markdown file in a private GitHub repo. No agent invocation required — any human or AI can read the file and know what you've been doing across machines and projects.

See [`git-history-plan.md`](./git-history-plan.md) for the motivating problem and architecture decisions.

## Quick start

1. Create a private sync repo (one-time, any machine):
   ```
   gh repo create --private git-history
   ```

2. On each machine, run the installer once:
   ```
   ./install.sh
   ```
   First run creates `~/.config/git-history/config.sh` and exits. Edit that file to set your `repos` array and `sync_repo` URL, then re-run:
   ```
   ./install.sh
   ```

3. Verify:
   ```
   ./collect.sh --dry-run
   tail -f ~/.config/git-history/logs/git-history.err
   ```

## What it does

Every 10 minutes (driven by launchd), `collect.sh`:

1. Walks each repo's HEAD reflog via `git log -g`.
2. Keeps only reflog entries whose action is `commit:` or `commit (initial):` — this filters out `pull`/`fetch`/`merge`/`rebase`/`cherry-pick` noise, so only commits *authored on this machine* are logged.
3. Filters further to entries newer than the stored watermark (`~/.config/git-history/last-run`, stored as epoch seconds).
4. Appends new entries to `history-<hostname>.md` in the synced repo.
5. Commits and pushes. Retries once after `pull --rebase` on push race.

Each machine owns its own file, so merge conflicts are structurally impossible.

## File format

`history-<hostname>.md` is append-only, oldest at top. Each entry is one tab-separated line:

```
YYYY-MM-DD HH:MM	repo	branch	short-sha	subject
```

Optimized for `grep` and AI-agent ingestion, not pretty markdown rendering. To read across machines:

```
cat ~/.config/git-history/repo/history-*.md | sort
```

## Files

| File | Purpose |
|------|---------|
| `collect.sh` | The collector. Runs every 10 min via launchd; also runnable manually with `--dry-run`. |
| `install.sh` | Sets up `~/.config/git-history/`, clones the sync repo, installs and loads the launchd plist. Idempotent. |
| `com.user.git-history.plist.template` | launchd agent template. Placeholders substituted by `install.sh`. |
| `config.example.sh` | Copied to `~/.config/git-history/config.sh` on first install. |

## State lives outside this repo

| Path | What |
|------|------|
| `~/.config/git-history/config.sh` | Repo list, sync repo URL, optional hostname override. |
| `~/.config/git-history/last-run` | Epoch seconds of last successful run. Used as `--since` watermark. |
| `~/.config/git-history/repo/` | Clone of the private sync repo. |
| `~/.config/git-history/logs/` | launchd stdout/stderr. |
| `~/Library/LaunchAgents/com.user.git-history.plist` | launchd agent. |

## Known limitations (spike scope)

- **macOS only.** Uses `launchd`, `scutil`, and BSD `date`. A Linux cron equivalent is Phase 2.
- **Branch is best-effort.** The recorded branch is the first current branch that contains the commit. For merged-then-deleted feature branches, this reports the merge target (usually `main`). Accurate enough for a passive log.
- **10-min push cadence.** That's ~144 sync-repo commits per machine per day. Acceptable because nobody reads the sync repo's log. Adjust `StartInterval` in the plist template if you want a different cadence.
- **HEAD reflog only.** Commits made on a detached HEAD or on a non-HEAD ref (rare in practice) are missed.
- **Credentials.** The sync push uses whatever auth your `gh`/git is already configured with. Easiest is SSH (`git@github.com:...`). If using HTTPS, make sure the osxkeychain credential helper has the token cached before loading the agent.

## Troubleshooting

**Agent isn't firing.** `launchctl list | grep git-history`. No output means it's not loaded — re-run `install.sh`.

**Nothing shows up in the sync repo.** Run `./collect.sh --dry-run` in a terminal. If it prints entries but nothing lands in the repo, check `~/.config/git-history/logs/git-history.err` — most likely a push-auth problem.

**Commits on other machines aren't in *this* machine's file.** That's by design. Each machine logs only its own commits. `cat history-*.md | sort` to see the combined view.

**Want to backfill from before install?** Set `last-run` to `0`:
```
echo 0 > ~/.config/git-history/last-run
./collect.sh
```
The first run will walk the full reflog of every watched repo.

## Uninstall

```
launchctl unload ~/Library/LaunchAgents/com.user.git-history.plist
rm ~/Library/LaunchAgents/com.user.git-history.plist
rm -rf ~/.config/git-history
```

The sync repo on GitHub is yours to delete or keep.
