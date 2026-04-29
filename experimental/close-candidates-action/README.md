# Close Candidates Action

A single-purpose GitHub Action that posts an idempotent PR comment listing **open issues this PR likely closes**, after the PR is merged. Designed to catch the case GitHub itself misses: when a PR with `Closes #N` in its body merges into a non-default branch (e.g. `development`), GitHub does *not* auto-close the referenced issues.

This is **not** a CI/CD system — it's a single deterministic suggestion. No build, no test, no deploy. No mutation of GitHub state beyond one PR comment.

## Three ways to use it

### 1. As an Action reference (easiest)

In the calling repo, drop this into `.github/workflows/close-candidates.yml`:

```yaml
name: Close Candidates
on:
  pull_request:
    types: [closed]
permissions:
  pull-requests: write
  issues: read
jobs:
  suggest:
    if: github.event.pull_request.merged == true
    runs-on: ubuntu-latest
    steps:
      - uses: Hypercart-Dev-Tools/rebalance-OS/experimental/close-candidates-action@main
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
```

That's the whole integration. No vendoring, no Python in the calling repo.

### 2. Vendored copy (no external dependency)

If you'd rather not depend on this repo, copy these two files into the target repo:

- `experimental/close-candidates-action/entrypoint.py` → anywhere (e.g. `.github/scripts/close-candidates.py`)
- `experimental/close-candidates-action/workflow-template.yml` → `.github/workflows/close-candidates.yml`, with the `uses:` line replaced by:
  ```yaml
        - run: python .github/scripts/close-candidates.py --repo "${{ github.repository }}" --pr "${{ github.event.pull_request.number }}"
          env:
            GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
  ```

`entrypoint.py` is intentionally stdlib-only (no `requests`, no `pydantic`, nothing) so it runs on the default ubuntu runner with zero install steps.

### 3. From rebalance (centralized orchestration)

The same script runs locally with no GitHub Actions context:

```bash
GITHUB_TOKEN=$(...) python experimental/close-candidates-action/entrypoint.py \
  --repo BinoidCBD/universal-child-theme-oct-2024 \
  --pr 798 \
  --dry-run
```

Add `--json` for a machine-readable summary. Drop `--dry-run` to actually post.

This is how rebalance's MCP layer can call the same logic across many repos without each repo needing the workflow installed.

## What it does

1. Fetches the merged PR's title + body.
2. Pulls the repo's open issues.
3. Scores each open issue against the PR using:
   - **Explicit closes-keyword** — `closes #N`, `fixes #N`, `resolves #N` in PR body → confidence 0.99
   - **Body reference** — bare `#N` in body → +0.45
   - **Branch-name match** — PR head ref contains the issue number → +0.30
   - **Title similarity (Jaccard, stopwords removed)** — ≥ 0.6 → +0.30, ≥ 0.35 → +0.18
4. Filters by `--min-confidence` (default 0.5).
5. Posts (or updates) a single PR comment marked with `<!-- close-candidates-bot v1 -->` — re-runs of the workflow update the same comment instead of creating new ones.

## Inputs

| input | default | what |
|---|---|---|
| `github-token` | required | `${{ secrets.GITHUB_TOKEN }}` is enough — needs `pull-requests: write`, `issues: read` |
| `pr-number` | triggering PR | Override to analyze a different PR |
| `min-confidence` | `0.5` | Lower to surface more borderline matches; raise to only show explicit closes |
| `dry-run` | `false` | Print the would-be comment instead of posting |

## What it intentionally doesn't do

- **Doesn't close issues.** It surfaces candidates; you decide.
- **Doesn't comment on the linked issues.** Only on the PR. Less noise.
- **Doesn't read SQLite, run embeddings, or call any LLM.** Pure determinism — same PR + same open issues = same comment.
- **Doesn't replace `closes` keyword auto-closure on default-branch merges.** GitHub already does that. This Action targets the gap when the PR merges into a non-default branch.

## Limitations

- Title-similarity is rough (Jaccard over tokens). Works well when both sides use overlapping vocabulary; fails when titles are paraphrased.
- Only considers currently *open* issues. If GitHub already auto-closed an issue, the Action won't surface it.
- The `/issues` endpoint is paginated 100 at a time. Repos with thousands of open issues will incur extra API calls; rate-limit pressure is real but bounded by the runner's lifetime.
- Idempotency is per-PR — re-running the workflow updates the existing comment. But editing the PR body and re-merging won't trigger the workflow on its own.

## Related

- [`experimental/gh_close_candidates_action.py`](../gh_close_candidates_action.py) — the original repo-wide scheduled variant. Different scope (scans all merged PRs vs all open issues every few days). Same scoring algorithm.
- [`src/rebalance/ingest/github_reconciliation.py`](../../src/rebalance/ingest/github_reconciliation.py) — the local SQLite-backed inference rebalance uses for cross-repo orchestration.
