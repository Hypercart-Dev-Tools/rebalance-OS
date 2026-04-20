# GH Close Candidates Action Plan

## TOC
- Overview
- Phase 0 Spike
- Deliverables
- Deterministic Scoring
- Output Contract
- Risks
- Next Steps

## Overview

Goal: build a deterministic GitHub Action that runs every 2-3 days, scans open issues against merged PRs, and produces a conservative list of recommended issues to close.

This first pass is intentionally isolated in `/experimental`:
- no live workflow activation yet
- no automatic issue closing
- no hosted LLM dependency
- no semantic embedding dependency

The weekly VS Code agent review remains the higher-context path for medium-confidence cases.

## Phase 0 Spike

### Checklist
- [x] Define a narrow deterministic signal set
- [x] Build a standalone script runnable in GitHub Actions
- [x] Emit machine-readable JSON and human-readable Markdown
- [x] Add a focused test for high/medium-confidence matching
- [ ] Validate against one private repo using a real GitHub Actions token
- [ ] Decide how results should be surfaced: artifact only, summary comment, or labels

### Scope

1-2 hour spike to validate:
- GitHub API availability inside Actions
- enough list-endpoint data exists to score candidates without N+1 per-item fetches
- output format is useful for both bot workflows and weekly human review

## Deliverables

### First-pass files
- `experimental/gh_close_candidates_action.py`
- `experimental/gh-close-candidates-action-plan.md`

### Out of scope for this pass
- auto-closing issues
- posting comments to issues
- label mutation
- PR/issue reconciliation through comments, reviews, or commit lists
- Slack/Sleuth ingestion

## Deterministic Scoring

### High confidence
- explicit closing keyword in merged PR title/body referencing the issue
- issue body references a PR number and that merged PR branch also contains the issue number

### Medium confidence
- explicit issue reference in merged PR without closing keyword
- issue body references the PR
- branch name contains issue number
- moderate title overlap

### Signals used
- merged PR state
- PR title/body
- PR head branch name
- issue title/body
- issue number / PR number cross-references
- default branch context

### Signals deferred
- issue comments
- PR review comments
- PR commits
- milestone alignment
- semantic similarity / embeddings

Those can be added later, but they increase complexity and API cost.

## Output Contract

### JSON
- repo name
- generated timestamp
- counts
- high-confidence candidates
- medium-confidence candidates
- unmatched open issue count

Each candidate should include:
- issue number/title/url
- PR number/title/url
- confidence
- confidence band
- recommendation
- evidence list

### Markdown
- summary counts
- high-confidence section
- medium-confidence section
- explicit evidence bullets

This Markdown can later feed:
- `GITHUB_STEP_SUMMARY`
- a single report issue/comment
- weekly manual review in VS Code

## Risks

- Private repo access may differ between local PATs, `gh` auth, and Actions tokens.
- List endpoints may not expose enough detail for stronger deterministic matching.
- Title overlap alone is too weak; the script must stay conservative.
- Repo conventions vary, especially branch naming and issue hygiene.

## Next Steps

### Phase 1
- Run the script in a private repo Action with `GITHUB_TOKEN`
- save JSON artifact
- write Markdown to step summary

### Phase 2
- optionally add labels like `candidate:close-high` and `candidate:close-review`
- add comments only on the central report artifact, not every issue

### Phase 3
- feed deterministic output into the weekly local agent review
- combine with the local SQLite GitHub corpus for semantic/contextual triage
