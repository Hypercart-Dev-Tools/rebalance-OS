**Phase 0 Spike**
1. Confirm GitHub API supports the needed conditional/delta paths for this repo set: `/issues?since=`, `/pulls?sort=updated`, comments endpoints, commits endpoints, check-runs, branches, labels, releases, milestones.
2. Measure one current refresh with `rebalance profile-sync --top 10` after the new dashboard profiling lands.
3. Pick 2 repos: one small, one slow. Record request counts, elapsed time, and which endpoints dominate.
4. Validate whether ETags/`If-None-Match` are reliable for repo metadata/list endpoints with the current PAT.

**Phase 1: Add Sync State**
1. Add a `github_sync_state` table keyed by `repo_full_name + endpoint_key`.
2. Store `last_success_at`, `last_seen_updated_at`, `etag`, `last_status`, `last_error`, `request_count`, and `elapsed_seconds`.
3. Use one writer: `sync_github_repo()` owns this contract.
4. Add tests for first sync, unchanged second sync, changed item sync, and failed sync preserving previous state.

**Phase 2: True Delta Fetching**
1. For issues: keep `since=<last_seen_updated_at - safety_overlap>` instead of fixed `since_days`.
2. For PRs: stop paging when `updated_at < high_watermark - safety_overlap`.
3. For comments/reviews/commits/checks: only fetch child resources for items whose parent changed or is not locally present.
4. For metadata endpoints: use ETag/`If-None-Match` where supported; skip DB rewrites on `304`.
5. Keep a small overlap window, likely 10-30 minutes, to avoid clock/API ordering gaps.

**Phase 3: Correctness Guards**
1. Never advance high-water marks until the repo sync completes successfully.
2. If a repo errors mid-sync, keep old state and mark the repo degraded.
3. Preserve full refresh escape hatch: `force_full=True` or CLI flag `--full`.
4. Add dry-run/profile output showing “would fetch” endpoints before network calls.
5. Add stale-state detection: if a repo has not had a full sync in N days, force a full metadata refresh.

**Phase 4: Performance + UX**
1. Add per-endpoint timings inside each repo result, not just per-repo elapsed time.
2. Show slowest repo and slowest endpoint in dashboard footer/profile table.
3. Make dashboard refresh use a shorter default GitHub window once high-water marks exist.
4. Consider bounded parallelism only after delta correctness is proven; 3-5 concurrent repos max, with rate-limit backoff.

**Definition Of Done**
1. Second refresh after a clean full sync makes materially fewer GitHub requests.
2. Slow repos show which endpoint is slow.
3. `database is locked` is not worsened; writes remain short and scoped.
4. Tests cover unchanged, changed, failed, ignored, and force-full paths.
5. Changelog/version bump included at merge.

---

**Phase 0 Spike Findings — 2026-05-04**

**Baseline**
1. Latest usable full GitHub timing logs:
   - `daily_sync_2026-05-03.log`: GitHub artifact sync total `9.4m`; full run `12.4m`.
   - `daily_sync_2026-05-02.log`: GitHub artifact sync total `10.0m`; full run `14.6m`.
2. Slow repo: `BinoidCBD/universal-child-theme-oct-2024`.
   - May 3: `5.5m`, 58.7% of GitHub time, `162` issues, `86` PRs, `403` commits, `458` comments, `1028` docs.
   - May 2: `6.0m`, 60.2% of GitHub time, similar counts.
3. Small comparison repo: `Hypercart-Dev-Tools/WP-Code-Check`.
   - May 3: `4.5s`, `1` issue, `0` PRs, `0` commits, `1` comment, `2` docs.
   - May 2: `4.4s`, similar counts.
4. Current dashboard process `PID 55467` was holding `rebalance.db` during the spike. The May 4 daily sync log failed GitHub/calendar/sleuth with `database is locked`, so it was not useful for profiling.

**API Capability Checks**
1. GitHub docs confirm `/repos/{owner}/{repo}/issues` supports `since` for updated-after filtering.
   - Source: https://docs.github.com/en/rest/issues/issues
2. GitHub docs confirm `/repos/{owner}/{repo}/pulls` supports `sort=updated` and `direction=desc`, but not a native `since` parameter. We must keep the current stop-when-older-than-high-watermark paging behavior.
   - Source: https://docs.github.com/en/rest/pulls/pulls
3. GitHub docs confirm both repo-wide issue comments and per-issue comments support `since`.
   - Source: https://docs.github.com/en/rest/issues/comments
4. GitHub docs recommend conditional requests with ETags; authenticated `304 Not Modified` responses do not count against the primary rate limit.
   - Source: https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api

**Live PAT Probe**
1. ETag/`If-None-Match` returned `304` for these probed endpoints on both slow and small repos:
   - repo metadata
   - branches
   - labels
   - milestones
   - releases
   - issues list with `since`
   - pulls list sorted by `updated`
   - representative PR detail
   - representative PR issue comments
   - representative PR reviews
   - representative PR review comments
   - representative PR commits
   - representative check-runs
2. First-page timings were mostly `0.3s–1.8s`; no single endpoint was inherently slow enough to explain the multi-minute run. The slow path is request count.
3. Repo-wide delta endpoints worked in the probe:
   - `/issues/comments?sort=updated&direction=desc&since=<24h>` returned `4` rows for the slow repo and `0` for the small repo.
   - `/pulls/comments?sort=updated&direction=desc&since=<24h>` returned `0` rows for both.
   - `/commits?since=<24h>` returned `0` rows for both.

**Request Count Driver**
1. Current `sync_github_repo()` does this for every updated issue:
   - fetch per-issue comments.
2. Current `sync_github_repo()` does this for every updated PR:
   - fetch PR detail
   - fetch issue comments
   - fetch reviews
   - fetch review comments
   - fetch commits
   - fetch check-runs
3. For the slow repo, the May 3 profile implies a request floor around:
   - `162` issue comment requests
   - `86 * 6 = 516` PR child requests
   - plus metadata and parent-list pages
   - Rough floor: `~680+` GitHub requests before pagination inside child lists.
4. For `WP-Code-Check`, the May 3 profile implies roughly:
   - metadata and parent-list pages
   - `1` issue comment request
   - no PR child fanout
   - Rough floor: under `10` GitHub requests.

**Conclusion**
1. Delta sync is viable.
2. The first implementation should prioritize reducing child fanout, not only adding ETags.
3. Highest-impact change: only fetch PR child endpoints when the PR itself changed, is missing locally, or a repo-wide delta endpoint says a child collection changed.
4. ETags should still be added for stable metadata/list endpoints because they are easy wins and protect the rate limit, but they will not solve the slow repo alone.
5. Use a per-repo high-water mark plus a `10–30m` safety overlap. Do not advance it until the full repo sync succeeds.

**Recommended Phase 1 Adjustment**
1. `github_sync_state` should include endpoint state for both parent and child families:
   - `repo_meta`
   - `branches`
   - `labels`
   - `milestones`
   - `releases`
   - `issues`
   - `pulls`
   - `repo_issue_comments`
   - `repo_review_comments`
   - `repo_commits`
   - child endpoint keys only when per-item fetches are still needed.
2. Add per-endpoint request count and elapsed timing to `GitHubKnowledgeSyncResult`.
3. Add a sync mode decision per item:
   - `full`: first sync, stale full-refresh interval, or `--full`.
   - `parent_changed`: parent row updated; fetch child endpoints.
   - `child_delta_only`: parent unchanged but repo-wide comments/reviews/commits endpoint has new rows.
   - `skip_children`: parent unchanged and no child delta signal.

**Open Blocker**
1. SQLite locking needs a separate guard before increasing refresh cadence or adding parallelism. Current dashboard refresh can hold the DB long enough for scheduled jobs to fail with `database is locked`.
