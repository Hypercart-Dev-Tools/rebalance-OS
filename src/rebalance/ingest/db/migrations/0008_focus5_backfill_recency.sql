-- 0008: backfill the GH-81 recency columns for rows that predate 0007.
--
-- 0007 added my_local_commit_ts + recency_basis as NULL on existing rows, to be
-- repopulated by the next focus5 sync (hourly). But rerank_focus5_from_cache()
-- (fired on every Focus 5 hide/unhide click) ranks recent_activity on the cached
-- my_local_commit_ts — so on a just-migrated machine that hasn't resynced yet, a
-- single hide could rerank every repo to ineligible (NULL recency) and blank the
-- board. (Found by Codex relay r2.)
--
-- Fix: backfill NULL rows to the OLD behavior — rank by the author-email match
-- (my_last_commit_ts), basis 'author_email'; 'none' when there was no match
-- either. This is exactly "never regress below today" for legacy rows, with no
-- second writer and no compute-on-read. The next real sync overwrites these with
-- the true reflog vector. rerank_focus5_from_cache() runs migrations before it
-- reads the cache, so this backfill always lands before any rerank.
--
-- Idempotent (WHERE recency_basis IS NULL) and additive. No BEGIN/COMMIT (the
-- runner owns the transaction; see migrations/README.md).

UPDATE focus5_repo_signals
   SET my_local_commit_ts = my_last_commit_ts,
       recency_basis = CASE
           WHEN my_last_commit_ts IS NOT NULL THEN 'author_email'
           ELSE 'none'
       END
 WHERE recency_basis IS NULL;
