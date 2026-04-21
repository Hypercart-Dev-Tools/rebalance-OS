# Config for git-history collector.
# Copy to ~/.config/git-history/config.sh and edit before the first run.

# Absolute repo paths to monitor. Quote each entry so paths with spaces work.
repos=(
    "$HOME/Documents/GitHub-Repos/rebalance-OS"
    # "$HOME/code/other-project"
)

# URL of the private GitHub repo that stores synced history files.
# Create once with: gh repo create --private git-history
sync_repo="git@github.com:yourusername/git-history.git"

# Optional hostname override. Defaults to `scutil --get ComputerName`,
# falling back to $HOSTNAME. Change if you want a shorter tag in filenames.
hostname=""
