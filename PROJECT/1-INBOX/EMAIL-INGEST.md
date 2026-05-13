# Email Ingest

> Status: Shipped on `main` as Phase 1 on 2026-05-12
> Scope: Gmail ingest via Application Default Credentials, newest 100 matching messages, semantic participation via subject + snippet

## TOC

- Current state
- Setup checklist
- Workspace / custom OAuth path
- Query filter behavior
- Validation
- Current data contract
- Phase 2 backlog

## Current state

Phase 1 is live in `main`.

What shipped:

- `refresh_index(scope=["email"])` syncs the newest 100 Gmail messages matching the active Gmail search filter
- messages are stored in `email_messages`
- email participates in the unified semantic index and default `semantic_query()` results
- `index_status()` reports an `email` source block
- auth uses Google Application Default Credentials, not a repo-managed token file

Shipped product default:

- if `gmail_query_filter` is unset, the runtime defaults to `in:inbox`

Current operator-local state on Noel's machine:

- `temp/rbos.config` is set to `in:inbox is:starred is:important`
- the local SQLite store was manually cleaned once on 2026-05-12 so only rows matching both labels remain
- that cleanup was an operator action, not current product behavior

Current implementation entry points:

- [src/rebalance/ingest/gmail.py](../../src/rebalance/ingest/gmail.py)
- [src/rebalance/ingest/index_ops.py](../../src/rebalance/ingest/index_ops.py)
- [src/rebalance/ingest/semantic_index.py](../../src/rebalance/ingest/semantic_index.py)
- [tests/test_email_ingest.py](../../tests/test_email_ingest.py)

## Setup checklist

- [ ] Install repo deps: `.venv/bin/pip install -e ".[embeddings,calendar]"`
- [ ] Enable Gmail API in the target Google Cloud project
- [ ] Authorize ADC with `gmail.readonly`
- [ ] Optionally set `gmail_query_filter` in `temp/rbos.config`
- [ ] Run `refresh_index(scope=["email"], dry_run=True)`
- [ ] Run `refresh_index(scope=["email"])`
- [ ] Verify `index_status()` shows `sources.email`
- [ ] Verify `semantic_query(..., sources=["email"])` returns hits

## Workspace / custom OAuth path

Default auth command:

```bash
gcloud auth application-default login \
  --scopes=https://www.googleapis.com/auth/gmail.readonly,https://www.googleapis.com/auth/cloud-platform
```

For Google Workspace tenants, the practical path may require a custom GCP OAuth client instead of the stock `gcloud` client.

Recommended operator path:

### Phase 0 spike

Spend 30-60 minutes validating the auth path before broad rollout:

1. Create or pick a GCP project.
2. Enable `gmail.googleapis.com`.
3. Configure the OAuth consent screen.
4. Create a Desktop OAuth client.
5. If Workspace policy is restrictive, have an admin trust/allow the OAuth client ID.
6. Run ADC login using the client file:

```bash
gcloud auth application-default login \
  --client-id-file=/absolute/path/to/client_secret_<id>.json \
  --scopes=https://www.googleapis.com/auth/gmail.readonly,https://www.googleapis.com/auth/cloud-platform
```

If Phase 0 fails because of Workspace policy, stop there and fix admin allowlisting first.

Notes:

- ADC is what the runtime reads from `google.auth.default(...)`
- the runtime does not use a repo-local `client_secret.json`
- the token is stored under `~/.config/gcloud/application_default_credentials.json`
- the shared Desktop OAuth client can be cached on disk at `~/secrets/google-workspace-oauth-client.json` and optionally sourced from Google Secret Manager for refresh consistency

### Optional Secret Manager source of truth

If you want the Desktop OAuth client JSON to be refreshable from GCP instead of hand-managed on disk, use:

- project: `named-equator-493617-e5`
- secret name: `google-workspace-oauth-client`
- local cache path: `~/secrets/google-workspace-oauth-client.json`

One-time bootstrap if the secret does not exist yet:

```bash
/opt/homebrew/bin/gcloud secrets create google-workspace-oauth-client \
  --replication-policy=automatic \
  --project=named-equator-493617-e5

/opt/homebrew/bin/gcloud secrets versions add google-workspace-oauth-client \
  --data-file=/Users/noelsaw/secrets/google-workspace-oauth-client.json \
  --project=named-equator-493617-e5
```

Repeatable refresh to local disk:

```bash
/opt/homebrew/bin/gcloud secrets versions access latest \
  --secret=google-workspace-oauth-client \
  --project=named-equator-493617-e5 \
  > /Users/noelsaw/secrets/google-workspace-oauth-client.json && \
  chmod 600 /Users/noelsaw/secrets/google-workspace-oauth-client.json
```

## Query filter behavior

The Gmail collector accepts any Gmail search query through `gmail_query_filter` in `temp/rbos.config`.

Examples:

- default inbox: `in:inbox`
- inbox minus bulk categories: `in:inbox -category:promotions -category:social`
- starred or important: `in:inbox {is:starred is:important}`
- starred and important: `in:inbox is:starred is:important`

Important behavior in Phase 1:

- the fetch window is capped at the newest `100` matching messages
- sync is additive and upsert-based
- narrowing the filter later does not automatically delete older email rows that were ingested under a broader filter
- if you want the local DB to contain only the narrower scope, do a one-time cleanup of non-matching `email_messages` rows and matching `semantic_documents` rows for `source_type='email'`

## Validation

After auth succeeds, validate in this order:

1. Dry run the email refresh:

```python
refresh_index(scope=["email"], dry_run=True)
```

2. Run the real refresh:

```python
refresh_index(scope=["email"])
```

3. Confirm source visibility:

```python
index_status()
```

Expected:

- `sources.email.messages`
- `sources.email.last_synced_at`
- `sources.email.newest_received_at`

4. Confirm retrieval:

```python
semantic_query("recent subject text", sources=["email"])
semantic_query("recent subject text")
```

The second query should include email by default.

## Current data contract

Phase 1 stores metadata plus snippet only.

Table: `email_messages`

- `message_id`
- `thread_id`
- `from_address`
- `from_name`
- `subject`
- `snippet`
- `received_at`
- `labels_json`
- `synced_at`

Current fetch behavior:

- shipped default filter: `in:inbox`
- override key: `gmail_query_filter` in `temp/rbos.config`
- current operator-local filter on Noel's machine: `in:inbox is:starred is:important`
- max fetch per run: 100 messages
- upsert key: Gmail `message_id`
- no automatic pruning when the filter changes

Current non-goals:

- full mailbox backfill
- full MIME body parsing
- send/archive/label mutation
- multi-account support
- push notifications / watch subscriptions

## Phase 2 backlog

- Add light delta sync via Gmail `history.list`
- Add body extraction beyond Gmail snippet
- Decide on redaction policy before body storage
- Add stronger Workspace/operator docs if custom OAuth becomes the common path
- Consider email-to-project correlation once raw signal quality is proven
