# Config for git-pulse collector.
# Copy to ~/.config/git-pulse/config.sh and edit before the first run.

# Absolute repo paths to monitor. Quote each entry so paths with spaces work.
# `install.sh` can auto-discover additional local GitHub repos and merge them
# into this list.
repos=(
    "$HOME/Documents/GitHub-Repos/rebalance-OS"
    # "$HOME/code/other-project"
)

# Roots scanned by `install.sh` when repo discovery is enabled.
repo_roots=(
    "$HOME/Documents/GH Repos"
    "$HOME/Documents/GitHub-Repos"
    "$HOME/Documents"
)

# Repo discovery mode:
#   append        -> merge discovered local GitHub repos into repos=()
#   replace       -> overwrite repos=() with discovered local GitHub repos
#   fill-if-empty -> only discover when repos=() is empty
#   off           -> never auto-discover
repo_discovery_mode="append"

# URL of the private GitHub repo that stores synced history files.
# Create once with: gh repo create --private git-pulse
sync_repo="git@github.com:yourusername/git-pulse.git"

# Optional local checkout location for the sync repo.
# If this already points at a git repo, install.sh will use it directly.
# Example:
# sync_repo_dir="$HOME/Documents/GitHub-Repos/rebalance-git-pulse"
sync_repo_dir=""

# Stable per-machine identity used in filenames and device metadata.
# `install.sh` will generate this automatically if omitted.
device_id=""

# Human-friendly label shown by `git-pulse-view`.
device_name=""

# Optional hostname override. Defaults to `scutil --get ComputerName`,
# falling back to $HOSTNAME. Change if you want a shorter tag in filenames.
hostname=""
