# Gmail — Inbox Ingest

Pull your inbox metadata + Gmail snippets into rebalance so email participates
in semantic search and the daily briefing. Message **bodies are never parsed or
stored** — only metadata (from/to/subject/date), Gmail's own snippet, and labels.

## Table of Contents

1. [Two ingest methods](#two-ingest-methods)
2. [Quick Start](#quick-start)
3. [Prerequisites](#prerequisites)
4. [Method A — `oauth` (autonomous / launchd)](#method-a--oauth-autonomous--launchd)
   - [Step 1: Authorize your device](#step-1-authorize-your-device)
   - [Step 2: Move the token into keyring](#step-2-move-the-token-into-keyring)
   - [Step 3: Select the method, narrow the query, sync](#step-3-select-the-method-narrow-the-query-sync)
   - [Durable tokens — make the consent screen Internal](#durable-tokens--make-the-consent-screen-internal)
5. [Method B — `mcp` (Gmail MCP connector)](#method-b--mcp-gmail-mcp-connector)
6. [Claude Code Setup](#claude-code-setup)
7. [Keeping Email Up to Date](#keeping-email-up-to-date)
8. [Troubleshooting](#troubleshooting)
9. [Common Questions](#common-questions)

---

## Two ingest methods

rebalance can feed `email_messages` two ways. Pick one with
`rebalance config set-gmail-method`:

| Method | When to use | Credential | Autonomous? |
|--------|-------------|------------|-------------|
| `oauth` *(default)* | You want scheduled, hands-off sync (launchd/cron) | Desktop OAuth token in keyring (pickle fallback for launchd) | ✅ Yes |
| `mcp` | You drive rebalance from an MCP host (e.g. Claude) | None — an agent calls `ingest_gmail_messages` | ❌ Needs an agent to trigger |

> Why a desktop OAuth token instead of `gcloud` ADC? `gmail.readonly` is a
> Google-**restricted** scope. The shared gcloud ADC client generally cannot
> grant it (tokens 403 with "insufficient authentication scopes"), but your own
> Desktop OAuth client can. That's why `oauth` mode uses the browser flow below.

---

## Quick Start

Already set up on `oauth`? Day-to-day there's nothing to run — the launchd
refresh pipeline already syncs email. To pull manually:

```bash
rebalance refresh                    # full pipeline (includes email in oauth mode)
rebalance doctor                     # confirm gmail is green
```

> Email-only sync isn't a standalone CLI command — it runs as part of
> `rebalance refresh`. From an MCP host/agent you can scope it with
> `refresh_index(scope=["email"])`.

On `mcp`? Ask your agent (e.g. Claude) to refresh email — it calls
`ingest_gmail_messages` via the Gmail MCP connector.

---

## Prerequisites

**Python 3.12+** and the project installed with Google API deps:

```bash
python3 -m venv .venv
source .venv/bin/activate            # macOS / Linux
pip install -e ".[calendar,embeddings]"   # [calendar] pulls the google-auth libs; [embeddings] adds semantic participation
```

`rebalance --help` should now work inside the venv.

---

## Method A — `oauth` (autonomous / launchd)

### Step 1: Authorize your device

Enable the Gmail API once in your Google Cloud project, then run the browser
consent flow. The Desktop OAuth client is **already bundled in the repo** — you
do **not** need your own `client_secret.json`.

```bash
gcloud services enable gmail.googleapis.com          # once, in your GCP project
python scripts/setup_gmail_oauth.py --test           # opens a browser
```

Pick your Google account and approve **read-only** Gmail access. If you see an
"unverified app" warning (consent screen in *Testing* mode), click
**Advanced → Go to rebalance OS (unsafe)** — it's your own client. The `--test`
flag reads your Gmail profile afterward to confirm it worked.

> Your token is saved locally at `~/.config/rebalance-os/google-gmail-oauth`
> (a launchd-reachable pickle) and is never stored in the repo.

### Step 2: Move the token into keyring

rebalance stores credentials in the OS **keyring** as the primary, with the
pickle file as a launchd-reachable fallback (launchd's stripped environment
can't read the Keychain). Adopt the keyring model with:

```bash
rebalance config migrate-to-keyring
```

This is idempotent and also picks up a **freshly re-authed** token — if you re-run
`setup_gmail_oauth.py` later, run `migrate-to-keyring` again to push the new
token into keyring.

### Step 3: Select the method, narrow the query, sync

```bash
rebalance config set-gmail-method oauth
```

Optionally narrow which messages are pulled by adding `gmail_query_filter` to
`temp/rbos.config` (default: `in:inbox`):

```json
{ "gmail_query_filter": "in:inbox -category:promotions -category:social" }
```

> **Freshness tip:** the dashboard's "email data stale" check keys on each
> message's `received_at`. A very narrow filter (e.g. `is:starred is:important`)
> can read as perpetually stale because no *recent* mail matches it. Use a
> broader filter if you want the freshness signal to track your actual inbox.

Then sync and verify:

```bash
rebalance refresh                    # full pipeline; syncs email in oauth mode
rebalance doctor                     # gmail → OK (via keyring)
```

### Durable tokens — make the consent screen Internal

Google **revokes OAuth refresh tokens after 7 days** for apps whose consent
screen is in **"Testing"** status. If you have to re-authorize every few days,
this is almost certainly why.

- **Google Workspace accounts:** set the consent screen **User Type → Internal**
  in the Cloud Console
  (`https://console.cloud.google.com/auth/audience?project=YOUR_PROJECT`).
  Internal apps have **no 7-day expiry**, need **no verification** (even for
  restricted scopes), and need **no test-user whitelist**. This is console-only —
  there is no `gcloud` command for it.
- **Personal Gmail accounts:** you can't use Internal; instead publish the app
  ("In production") to stop the 7-day clock, or accept periodic re-auth.

After flipping to Internal, re-mint once so the token is issued under the new
status:

```bash
python scripts/setup_gmail_oauth.py --test
rebalance config migrate-to-keyring
```

---

## Method B — `mcp` (Gmail MCP connector)

No local credential needed. `email_messages` is populated by an agent (e.g.
Claude) using the Gmail MCP connector, which calls the `ingest_gmail_messages`
tool.

```bash
rebalance config set-gmail-method mcp
```

Then ask your agent to refresh email. A scheduled job **cannot** trigger this —
an agent has to — so `mcp` mode is best when you're working interactively through
an MCP host rather than relying on background sync.

---

## Claude Code Setup

If you use Claude Code, open this file in an editor pane, select it, and prompt:

> Please scan the highlighted document, install dependencies, and set up Gmail
> ingest on this device using the `oauth` method including browser authorization.

Claude Code will: check prerequisites → enable the Gmail API → run
`python scripts/setup_gmail_oauth.py --test` → `rebalance config migrate-to-keyring`
→ `rebalance config set-gmail-method oauth` → `rebalance refresh --scope email` →
`rebalance doctor` to verify.

**Notes for Claude Code:**

- Never echo a token/secret value to chat, logs, or commits — this is a public
  repo. Print only statuses, lengths, fingerprints.
- Always run inside the project venv. If `rebalance` is not found, `source
  .venv/bin/activate` first.

---

## Keeping Email Up to Date

On `oauth` mode, the existing launchd refresh pipeline already syncs email on
its schedule — no separate job is needed. If you run rebalance without those
launchd jobs, automate the full refresh via cron:

```
0 * * * * cd /path/to/rebalance-OS && .venv/bin/rebalance refresh --no-publish
```

On `mcp` mode, ask your agent to refresh whenever you want fresh email.

---

## Troubleshooting

| Problem | What to do |
|---------|-----------|
| `doctor`: `gmail — no OAuth credentials` | Run `python scripts/setup_gmail_oauth.py --test` then `rebalance config migrate-to-keyring` |
| `scope_insufficient` in the auth log | The token lacks `gmail.readonly` (or you're on leftover gcloud ADC). Re-run the OAuth flow above; don't use `gcloud auth application-default login` for Gmail |
| Re-authorizing every few days | Consent screen is in *Testing* (7-day refresh-token expiry). Make it **Internal** (Workspace) or publish to production — see [Durable tokens](#durable-tokens--make-the-consent-screen-internal) |
| `email data — stale` but you just synced | Your `gmail_query_filter` is too narrow; freshness keys on `received_at`. Broaden it in `temp/rbos.config` |
| "Gmail API has not been used in project" (403) | Run `gcloud services enable gmail.googleapis.com` in your project |
| Browser didn't open | Re-run with `python -u scripts/setup_gmail_oauth.py --test` to see the consent URL and open it manually |
| On `mcp` mode, email isn't updating | A scheduled job can't ingest in MCP mode — ask your agent to call `ingest_gmail_messages`, or switch to `oauth` |

---

## Common Questions

- **Is my email stored or uploaded anywhere?** No. Only metadata, Gmail's own
  snippet, and labels are saved to your local SQLite DB. Message bodies are never
  parsed or uploaded.
- **Do I need my own Google Cloud app or `client_secret.json`?** No — the repo
  bundles the Desktop OAuth client. You authorize your own account locally; the
  token belongs to you and stays on your machine.
- **Where is my token stored?** Keyring (primary) + `~/.config/rebalance-os/google-gmail-oauth`
  (launchd fallback). Never in the repo.
- **Why read-only?** rebalance only reads. The requested scope is
  `gmail.readonly` and nothing else.
- **Can I switch methods later?** Yes — `rebalance config set-gmail-method oauth|mcp`
  any time.
