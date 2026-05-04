# Activity status dashboard (GitHub Pages)

Single static page that fuses GitHub remote activity (Claude Code cloud,
Codex Cloud, Lovable) with local VS Code agent work.  Hosted on GitHub
Pages at the orphan `gh-pages` branch and auto-refreshed every 10 min.

```
.github/workflows/update-status.yml   ─┐
scripts/build_status.py                │ runs every 15 min during 8am-8pm PT
scripts/publish_gh_pages.sh           ─┘ → commits to orphan gh-pages branch

docs/index.html, docs/app.{js,css}     ─→ copied into gh-pages by the Action

(GitHub Pages)                         ─→ serves https://<org>.github.io/<repo>/
```

## One-time setup

1. **Pages source** — Settings → Pages → "Build and deployment" →
   "Deploy from a branch" → branch `gh-pages` / `(root)`. Save.
   The branch will be created automatically by the first Action run.

2. **Status PAT** — create a fine-scoped Personal Access Token with
   `repo:read` on the orgs you want to monitor. Settings → Secrets and
   variables → Actions → New repository secret → name `STATUS_GH_TOKEN`,
   paste the token.

3. **(Optional) Watch list** — Settings → Secrets and variables →
   Actions → Variables → New repository variable →
   name `REBALANCE_WATCH_REPOS`, value `owner1/repo1,owner2/repo2,…`.
   When unset, the Action discovers repos from the user's events feed
   (last 14 days).

4. **(Optional) Local pulse data** — to pull device pulse markdown
   files into the data feed, add the device-pulse repo as a submodule
   under `experimental/git-pulse-mirror/`, then flip
   `submodules: false` → `submodules: recursive` in the workflow.

5. **First run** — Actions tab → "Update activity status" → "Run
   workflow". The first run creates the `gh-pages` branch and uploads
   `data/status.json` plus the static frontend.

## Local development

Generate a `status.json` against the live GitHub API and serve the page
locally — no Action involved:

```bash
GH_TOKEN=$(gh auth token) python scripts/build_status.py \
    --out docs/data/status.json --window-days 7
mkdir -p docs/data
python -m http.server -d docs 8080
# open http://localhost:8080
```

## Cron and budget

- Cron: `*/15 15-23,0-3 * * *` (UTC) — covers 8am–8pm Pacific year-round
  with ±1 h DST drift.
- Cost: ~52 runs/day × 30 days × ≤1 min each ≈ **1,560 min/month**, well
  under the 2,000 min/month free tier on a private repo.
- Skip-on-no-change: `publish_gh_pages.sh` runs `git diff --cached
  --quiet` and exits without committing if nothing changed, so quiet
  hours produce zero commits.
