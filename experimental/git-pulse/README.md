# git-pulse

Passive, always-on collector that appends locally-authored git commits from a fixed set of repos to per-device files in a private GitHub repo checkout. No agent invocation required. Any human or AI can read the synced files and reconstruct what you touched across devices and repos.

See [`git-pulse-plan.md`](./git-pulse-plan.md) for the background and design notes.

## TOC

- Recommended layout
- Happy path
- Install on another Mac
- What it does
- File format
- Files
- State lives outside this repo
- Known limitations
- Troubleshooting
- Uninstall

## Recommended layout

Keep code and sync data in separate repos:

1. Maintained code:
   `~/Documents/GitHub-Repos/rebalance-OS/experimental/git-pulse`
2. Private sync repo checkout:
   `~/.config/git-pulse/repo`

Recommended safe locations for the sync repo checkout:

- `~/.config/git-pulse/repo`
- `~/code/rebalance-git-pulse`
- any non-protected path outside `~/Documents`, `~/Desktop`, and `~/Downloads`

Avoid using `~/Documents/...` for `sync_repo_dir`. Manual terminal runs may work there, but unattended `launchd` runs can be denied write access by macOS.

## Happy path

If you want the most reliable setup with the fewest choices:

1. Keep the code in:
   ```text
   ~/Documents/GitHub-Repos/rebalance-OS/experimental/git-pulse
   ```
2. Clone the private sync repo to:
   ```text
   ~/.config/git-pulse/repo
   ```
3. Set `sync_repo_dir="$HOME/.config/git-pulse/repo"` in `~/.config/git-pulse/config.sh`
4. Run:
   ```bash
   ./install.sh
   ```
5. Verify:
   ```bash
   ~/bin/git-pulse --dry-run
   ~/bin/git-pulse-view --today
   ~/bin/git-pulse-view --days 14
   ~/bin/git-pulse-view --days 14 --include-local-unsynced
   launchctl list | grep git-pulse
   ```

That layout avoids the macOS protected-folder problem for unattended background writes.

## Install On Another Mac

1. Clone or update `rebalance-OS` on the new Mac.
   Example:
   ```bash
   git clone <your rebalance-OS remote>
   cd rebalance-OS/experimental/git-pulse
   ```

2. Make sure git can push to your private sync repo from this Mac before installing.
   One of these should already work:
   - `gh auth status`
   - `git ls-remote <your-private-sync-repo-url>`

3. Create the private sync repo once if needed:
   ```bash
   gh repo create --private git-pulse
   ```

4. Clone the sync repo into a safe local checkout.
   Recommended:
   ```bash
   git clone <private-sync-repo-url> ~/.config/git-pulse/repo
   ```

5. Run the installer once:
   ```bash
   ./install.sh
   ```
   First run creates `~/.config/git-pulse/config.sh` and exits.

6. Edit `~/.config/git-pulse/config.sh`.
   Minimal reliable example:
   ```bash
   repos=(
       "$HOME/Documents/GitHub-Repos/rebalance-OS"
       # "$HOME/code/other-project"
   )

   # Remote URL used only if install.sh needs to clone the sync repo.
   sync_repo="git@github.com:yourusername/git-pulse.git"

   # Working checkout of the sync repo.
   sync_repo_dir="$HOME/.config/git-pulse/repo"

   # Leave blank on first install if you want install.sh to generate/fill them.
   device_id=""
   device_name=""
   hostname=""
   ```

   Notes:
   - If `sync_repo_dir` already points at a git repo, `install.sh` uses it directly.
   - If `device_id` is blank or missing, `install.sh` defaults it to a slugified version of the Mac's computer name.
   - If `device_name` is blank or missing, `install.sh` defaults it to the Mac's computer name.

7. Re-run the installer:
   ```bash
   ./install.sh
   ```
   The installer:
   - creates `~/bin/git-pulse`
   - creates `~/bin/git-pulse-view`
   - installs `~/Library/LaunchAgents/com.user.git-pulse.plist`
   - loads the launchd job

8. Verify:
   ```bash
   ~/bin/git-pulse --dry-run
   ~/bin/git-pulse-view --today
   ~/bin/git-pulse-view --days 14
   ~/bin/git-pulse-view --days 14 --include-local-unsynced
   launchctl list | grep git-pulse
   tail -f ~/.config/git-pulse/logs/git-pulse.err
   ```

9. Optional one-time backfill:
   ```bash
   echo 0 > ~/.config/git-pulse/last-run
   ~/bin/git-pulse
   ```

10. If this `rebalance-OS` checkout lives under `~/Documents`, re-run `./install.sh` after future `git pull`s.
    In that case the installer uses copied launchers in `~/bin/` instead of live symlinks, because launchd cannot reliably execute scripts inside protected folders.

## What it does

Every hour, `collect.sh`:

1. Walks each watched repo's HEAD reflog via `git log -g`.
2. Keeps only reflog actions `commit:`, `commit (initial):`, and `commit (amend):`.
3. Filters to entries newer than `~/.config/git-pulse/last-run`.
4. Appends new rows to `pulse-<device_id>.md` in the sync repo, storing canonical UTC timestamps.
5. Refreshes `devices/<device_id>.yaml` with device metadata.
6. Commits and pushes.
7. Retries once after `pull --rebase` on push race.
8. Uses an on-disk lock so overlapping launchd/manual runs do not duplicate entries.

Each device owns its own pulse file, so merge conflicts are structurally unlikely even when all devices push to the same `main` branch.

## File format

`pulse-<device_id>.md` is append-only, oldest at top. Each entry is one tab-separated line:

```text
epoch_utc	timestamp_utc	repo	branch	short-sha	subject
```

Canonical storage time is UTC. `git-pulse-view` converts rows into local time on the machine doing the reading and emits one TSV header row followed by flat event rows:

```text
local_day	local_time	utc_time	device_id	device_name	repo	branch	short_sha	subject
```

Example unified read:

```bash
~/bin/git-pulse-view --today
~/bin/git-pulse-view --days 14
~/bin/git-pulse-view --days 14 --include-local-unsynced
~/bin/git-pulse-view --days 14 --include-local-unsynced --output "$HOME/.config/git-pulse/repo/reports/combined-14-days.tsv"
```

## Files

| File | Purpose |
|------|---------|
| `collect.sh` | Collector. Runs every hour via launchd and also supports `--dry-run`. |
| `view.sh` | Unified local reader across all registered device files. |
| `install.sh` | Creates local config, installs launchers, installs the launchd plist, and generates `device_id` if needed. |
| `com.user.git-pulse.plist.template` | launchd agent template used by `install.sh`. |
| `config.example.sh` | Seed config copied to `~/.config/git-pulse/config.sh` on first install. |

## State Lives Outside This Repo

| Path | What |
|------|------|
| `~/.config/git-pulse/config.sh` | Repo list, sync repo location, stable `device_id`, human `device_name`, optional hostname override. |
| `~/.config/git-pulse/last-run` | Epoch seconds of last successful run. |
| configured `sync_repo_dir` | Working checkout of the private sync repo. Defaults to `~/.config/git-pulse/repo` if unset. |
| configured `sync_repo_dir/devices/*.yaml` | Per-device metadata registry used by `git-pulse-view`. |
| `~/.config/git-pulse/logs/` | launchd stdout/stderr. |
| `~/bin/git-pulse` | Launchd entrypoint. Usually a symlink; falls back to a copied script when the code repo lives in a protected macOS folder. |
| `~/bin/git-pulse-view` | Unified read interface across all registered device files. |
| `~/Library/LaunchAgents/com.user.git-pulse.plist` | Installed launchd agent. |

## Known Limitations

- **macOS only.** Uses `launchd`, `scutil`, and BSD `date`.
- **Branch is best-effort.** For merged-and-deleted feature branches it may report the merge target.
- **Hourly cadence.** Default is one sync attempt per hour. Adjust `StartInterval` in the plist template if needed.
- **HEAD reflog only.** Commits made on detached HEADs or other refs can be missed.
- **Device IDs are the stable identity.** Hostnames can change; `device_id` should not.
- **Default IDs are now human-friendly slugs.** Apostrophes are omitted rather than split into extra separators, so a name like `Noel's device` becomes `noels-device`. If you rename a Mac later, keep the existing `device_id` in `config.sh` unless you intentionally want to migrate filenames.
- **Protected folders need copy mode.** If the code checkout lives under `~/Documents`, `~/Desktop`, or `~/Downloads`, launchd may be blocked from executing it directly. `install.sh` copies the launchers into `~/bin` in that case, so re-run `./install.sh` after code updates.
- **Protected folders can also block sync writes.** A `sync_repo_dir` under `~/Documents`, `~/Desktop`, or `~/Downloads` may work interactively but fail under unattended `launchd`. Prefer `~/.config/git-pulse/repo` or another non-protected path.
- **Credentials are external.** Sync push uses whatever git or `gh` auth is already configured on the Mac.

## Troubleshooting

**Agent isn't firing.**
Run:
```bash
launchctl list | grep git-pulse
```
No output means it is not loaded. Re-run `./install.sh`.

**Nothing shows up in the sync repo.**
Run:
```bash
~/bin/git-pulse --dry-run
tail -f ~/.config/git-pulse/logs/git-pulse.err
```
Then confirm:
- `sync_repo_dir` points at the checkout you expect
- that checkout is not inside `~/Documents`, `~/Desktop`, or `~/Downloads`
- git can push from this Mac

**Want a unified stream across devices?**
Run:
```bash
~/bin/git-pulse-view
~/bin/git-pulse-view --today
~/bin/git-pulse-view --days 14
~/bin/git-pulse-view --days 14 --include-local-unsynced
```

**Want to backfill from before install?**
Run:
```bash
echo 0 > ~/.config/git-pulse/last-run
~/bin/git-pulse
```

**Changed the code under `experimental/git-pulse/` but launchd is still running old behavior?**
Re-run:
```bash
cd /path/to/rebalance-OS/experimental/git-pulse
./install.sh
```
If the code checkout lives under `~/Documents`, the installed launchers are copied into `~/bin`, not live symlinks.

## Uninstall

```bash
launchctl unload ~/Library/LaunchAgents/com.user.git-pulse.plist
rm ~/Library/LaunchAgents/com.user.git-pulse.plist
rm ~/bin/git-pulse
rm ~/bin/git-pulse-view
rm -rf ~/.config/git-pulse
```

The sync repo on GitHub is yours to keep or delete.
