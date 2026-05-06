# Email Ingestion — Simple Newest-100 Plan

Status: planning
Owner: noel
Created: 2026-05-04
Revised: 2026-05-04 (post-review — see Revision Notes at bottom)

---

## Goal

Ingest the newest ~100 messages from the user's Gmail inbox into the rebalance-OS SQLite knowledge base on a recurring basis, so email signal participates in `semantic_query()` alongside vault and GitHub on day one. Optimized for "easy to ship" over completeness.

## Non-goals

1. Full mailbox backfill.
2. Sent/Drafts/All Mail ingestion.
3. Write operations (label, archive, send) — read-only only.
4. Multi-user / multi-account support.
5. Real-time push (Gmail watch + Pub/Sub) — polling is fine.
6. Full MIME body parsing in v1 (snippet is enough — see Phase 1 schema).

---

## Auth path (documented as current default)

1. Use `gcloud auth application-default login --scopes=https://www.googleapis.com/auth/gmail.readonly,https://www.googleapis.com/auth/cloud-platform`.
2. Enable the API once: `gcloud services enable gmail.googleapis.com`.
3. Document in `README.md` and `MCP.md` that this is the current path because it skips OAuth client / consent screen setup and works for a single-user repo.
4. Note in docs: if there is community demand for multi-user, we will add a proper Desktop OAuth Client ID flow (mirrors how `setup_github_token` works today).
5. Token lives at `~/.config/gcloud/application_default_credentials.json` — no copy, no `setup_gmail` tool. `refresh_index(scope=["email"])` probes it at runtime and fails loudly with the exact `gcloud` command if missing.

---

## Phase 1: Newest-100 Inbox Snapshot (semantic-participating)

**Scope**

1. One Gmail query per run: `q=<gmail_query_filter> maxResults=100`. Default filter is `in:inbox`; user-overridable via `temp/rbos.config` key `gmail_query_filter`.
2. For each message ID returned: call `users().messages().get(format="metadata", metadataHeaders=["From","To","Subject","Date"])`. The response also carries `snippet` and `labelIds` for free.
3. Each run re-checks the same 100 IDs and upserts. No body fetch in v1.

**Schema (one new table)**

1. `email_messages`:
   - `message_id TEXT PRIMARY KEY` (Gmail message id)
   - `thread_id TEXT`
   - `from_address TEXT`, `from_name TEXT`
   - `subject TEXT`
   - `snippet TEXT` (Gmail-provided, ~200 chars, no MIME parsing required)
   - `received_at TIMESTAMP` (parsed from `Date` header or `internalDate`)
   - `labels_json TEXT`
   - `synced_at TIMESTAMP`
2. **No `email_sync_state` table in v1.** `index_status()` derives freshness from `MAX(synced_at)` and `COUNT(*)` exactly the way it does for other sources at [src/rebalance/ingest/index_ops.py:94](src/rebalance/ingest/index_ops.py#L94).
3. `to_addresses`, `body_text`, and per-account state move to Phase 2.

**Write pattern**

1. Use `INSERT OR REPLACE INTO email_messages` keyed on `message_id`, matching the GitHub upsert convention at [src/rebalance/ingest/db.py:384](src/rebalance/ingest/db.py#L384).
2. Do not delete rows that fall out of the newest-100 window — they stay in the DB so historical search still works. The newest-100 query is a *fetch* scope, not a *retention* scope.

**Semantic participation (required in v1)**

1. Reuse the existing `semantic_documents` table. Do not create `email_documents`.
2. Embed `subject + "\n" + snippet` per message; one semantic doc per email row.
3. Wire email into `backfill_semantic_documents()` at [src/rebalance/ingest/semantic_index.py:379](src/rebalance/ingest/semantic_index.py#L379) under `source_type="email"`.
4. **Three small edits required so email actually shows up in default queries:**
   - [src/rebalance/ingest/semantic_index.py:65](src/rebalance/ingest/semantic_index.py#L65) — extend `_normalize_sources` default + `"all"` mapping to include `"email"`.
   - [src/rebalance/ingest/semantic_index.py:75](src/rebalance/ingest/semantic_index.py#L75) — add `"email"` to the allowed-source set.
   - [src/rebalance/ingest/index_ops.py:25](src/rebalance/ingest/index_ops.py#L25) — add `"email"` to `SCOPE_VALUES` and the `"all"` expansion at line 71.

**MCP / CLI surface**

1. Extend `refresh_index(scope=[...])` to accept `"email"` ([src/rebalance/mcp_server.py:499](src/rebalance/mcp_server.py#L499)).
2. Extend `index_status()` output with an `email` block: `count`, `last_synced_at`, `oldest_received_at`, `newest_received_at`.
3. `semantic_query(sources=["email"])` works for free once the three edits above land.

**Definition of done**

1. Running `refresh_index(scope=["email"])` populates `email_messages` with up to 100 rows on first run and embeds them into `semantic_documents`.
2. Second run is idempotent: same row count, label/snippet changes upserted.
3. `index_status()` shows email freshness derived from the `email_messages` table.
4. `semantic_query("...")` with no `sources=` argument returns email hits alongside vault and github.
5. README documents the gcloud ADC setup and the `gmail_query_filter` config key.
6. Tests cover: first sync, repeat sync with no new mail, repeat sync with N new messages, label-only change on existing message, missing-auth probe error message.

---

## Phase 2: Light Delta + Body Parsing

Defer everything in this phase until Phase 1 has been running long enough to know the signal is worth the complexity.

**Scope**

1. Add `email_sync_state(account_email PK, last_history_id, last_full_scan_at, last_success_at, last_error)`.
2. Use `users().history.list(startHistoryId=...)` for delta fetch when watermark is valid (Gmail history expires after ~7 days).
3. Fall back to Phase 1 newest-100 path when `historyId` is missing or expired. Force a Phase 1 pass when `last_full_scan_at` is older than N days (default 7).
4. Never advance `last_history_id` until the run completes successfully (same correctness rule as Phase 3 of GH-SYNC-DELTA).
5. Add MIME body extraction: prefer `text/plain` parts, fall back to stripped `text/html`. Store in new `email_messages.body_text` column. Re-embed semantic docs as `subject + "\n" + body_text` when body is available.
6. Optional: `to_addresses TEXT` (JSON), attachment metadata (filename + size + mimetype, no content).

**Definition of done**

1. After a successful Phase 1 baseline, the next run uses `history.list` and makes materially fewer Gmail API calls when there is no new mail.
2. History expiry triggers automatic fallback without manual intervention.
3. Force-full path: `refresh_index(scope=["email"], full=True)` works.
4. Body parsing handles plain, HTML, multipart, and quoted-reply trimming.
5. Tests cover: history hit, history expired, history-then-full fallback, multipart body extraction.

---

## Open questions

1. Body redaction policy — defer until Phase 2 since v1 doesn't store bodies.
2. Embedding signal quality of `subject + snippet` alone — measure after Phase 1 ships before committing to body parsing.
3. Multi-account — defer until ADC is replaced with proper OAuth client flow.

---

## Risk notes

1. Public repo + ADC means contributors who clone and run will be prompted to consent with their own Google account. That is the intended behavior, but call it out in the README so nobody is surprised.
2. SQLite locking risk is the same as the GH-SYNC-DELTA blocker — keep email writes short and scoped, do not add parallel polling until that lock issue is resolved.
3. Gmail rate limits are generous (~250 quota units/user/sec); Phase 1 at 100 messages/run is well under that.
4. The three semantic-index edits are easy to forget — without them, email rows exist in the DB but never appear in default `semantic_query()` results.

---

## Revision notes (2026-05-04)

Rewritten after review feedback. Changes from v1:

1. Dropped `setup_gmail()` MCP tool — ADC path is conventional, runtime probe is enough.
2. Dropped `email_sync_state` table from Phase 1 — derive freshness from `email_messages` like other sources do.
3. Dropped `body_text` from Phase 1 — subject + snippet avoids MIME parsing entirely.
4. Moved `historyId` delta to Phase 2; promoted `gmail_query_filter` to Phase 1.
5. Committed to semantic participation on day one via `semantic_documents` with `source_type="email"`. No separate `email_documents` table.
6. Added the three explicit edits required so email appears in default semantic queries (otherwise it would silently be excluded).
