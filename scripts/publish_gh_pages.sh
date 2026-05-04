#!/usr/bin/env bash
#
# Publish status.json + the static frontend to the orphan ``gh-pages`` branch.
#
# Designed for use inside ``.github/workflows/update-status.yml``. Skips the
# commit (and the push) when nothing has changed so cron ticks during quiet
# hours don't pollute git history.
#
# Usage:
#   GITHUB_TOKEN=... GITHUB_REPOSITORY=owner/repo \
#       scripts/publish_gh_pages.sh /tmp/status.json
#
# Required env:
#   GITHUB_TOKEN       — token with contents:write on the repo
#   GITHUB_REPOSITORY  — e.g. ``hypercart-dev-tools/rebalance-os``
#
# Optional env:
#   PAGES_COMMIT_NAME  — git author name  (default: github-actions[bot])
#   PAGES_COMMIT_EMAIL — git author email (default: 41898282+github-actions[bot]@users.noreply.github.com)

set -euo pipefail

if [[ $# -lt 1 ]]; then
    echo "usage: $0 <path-to-status.json>" >&2
    exit 2
fi
STATUS_JSON="$1"
if [[ ! -f "$STATUS_JSON" ]]; then
    echo "error: status JSON not found: $STATUS_JSON" >&2
    exit 1
fi
: "${GITHUB_TOKEN:?GITHUB_TOKEN is required}"
: "${GITHUB_REPOSITORY:?GITHUB_REPOSITORY is required}"

NAME="${PAGES_COMMIT_NAME:-github-actions[bot]}"
EMAIL="${PAGES_COMMIT_EMAIL:-41898282+github-actions[bot]@users.noreply.github.com}"

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DOCS_DIR="$REPO_ROOT/docs"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

REMOTE_URL="https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.git"

# Try to clone the existing gh-pages branch; if it doesn't exist yet, create
# a fresh orphan branch in a clean worktree.
if git clone --quiet --depth 1 --branch gh-pages "$REMOTE_URL" "$WORK" 2>/dev/null; then
    echo "checked out existing gh-pages branch"
else
    echo "gh-pages branch does not exist yet — initializing"
    git -c init.defaultBranch=gh-pages init --quiet "$WORK"
    git -C "$WORK" remote add origin "$REMOTE_URL"
    git -C "$WORK" checkout --quiet --orphan gh-pages
    # Ensure the orphan branch starts empty
    git -C "$WORK" rm -rf --quiet . 2>/dev/null || true
fi

# Copy frontend (humans edit ``main:/docs``; the orphan branch is a mirror)
mkdir -p "$WORK/data"
if [[ -d "$DOCS_DIR" ]]; then
    cp "$DOCS_DIR"/index.html "$WORK/" 2>/dev/null || true
    cp "$DOCS_DIR"/app.js     "$WORK/" 2>/dev/null || true
    cp "$DOCS_DIR"/app.css    "$WORK/" 2>/dev/null || true
fi
# Tell GH Pages to skip Jekyll processing (we ship raw HTML/JS).
touch "$WORK/.nojekyll"
cp "$STATUS_JSON" "$WORK/data/status.json"

git -C "$WORK" add -A
if git -C "$WORK" diff --cached --quiet; then
    echo "no change — skipping commit"
    exit 0
fi

git -C "$WORK" -c user.name="$NAME" -c user.email="$EMAIL" \
    commit --quiet -m "data: $(date -u +%Y-%m-%dT%H:%MZ)"

# Push, with a short retry loop for transient network errors.
for attempt in 1 2 3 4; do
    if git -C "$WORK" push --quiet origin gh-pages; then
        echo "pushed to gh-pages"
        exit 0
    fi
    delay=$((attempt * attempt * 2))
    echo "push attempt $attempt failed; retrying in ${delay}s" >&2
    sleep "$delay"
done

echo "error: push to gh-pages failed after 4 attempts" >&2
exit 1
