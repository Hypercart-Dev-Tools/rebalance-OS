-- 0007: focus5 identity-agnostic ranking vector (GH-81).
--
-- The headline Focus 5 board (rank_recent_activity) previously ranked on a single
-- `user.email` match (my_last_commit_ts). The operator commits under multiple
-- author emails (CLI vs web-merge noreply), so recent local work authored under a
-- non-matching email silently dropped off the roster. The durable signal is "did
-- MY local checkout commit recently?" — the HEAD reflog, filtered to local-commit
-- ops — resolved into:
--
--   my_local_commit_ts — epoch of the resolved local-commit recency the headline
--     board now ranks on (NULL ⇔ ineligible). Distinct from my_last_commit_ts,
--     which stays as the author-email fallback input + diagnostic.
--   recency_basis      — which rung produced it: local_reflog | author_email |
--     any_commit | none. Recorded (never silent) so a fallback is inspectable
--     without re-probing git (explain/QA reads it straight from the row).
--
-- Additive + NULL-tolerant: legacy rows read NULL until the next focus5 sync
-- (hourly) re-probes and backfills them. Same single writer (the focus5 probe)
-- owns these columns as it owns the others — no second write path. No BEGIN/COMMIT
-- (the runner owns the transaction; see migrations/README.md).

ALTER TABLE focus5_repo_signals ADD COLUMN my_local_commit_ts INTEGER;
ALTER TABLE focus5_repo_signals ADD COLUMN recency_basis TEXT;
