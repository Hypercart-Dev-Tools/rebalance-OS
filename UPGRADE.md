# UPGRADE — bring a device onto the keyring credential model

rebalance-OS now stores its three external credentials in the **OS keyring**
(macOS Keychain) as the primary, with a **launchd-reachable fallback** for each
(launchd's stripped environment can't read the keychain). This replaces the old
"loose secret files in `~/secrets/`" approach, which caused silent stalls when a
file was missing or in the wrong place.

> **Keyring is per-machine.** It does **not** sync across devices. Each device
> installs its secrets once. This guide is what you run on a device to catch up.

## Credential model (after upgrade)

| Credential | Primary | launchd fallback | Logged on (re)auth |
|---|---|---|---|
| GitHub PAT | keyring | `temp/rbos.config` | `auth_log` `token_set` + `token_meta` |
| Sleuth Web API | keyring | `temp/rbos.config` | same |
| Google Calendar OAuth | keyring | pickle file (`~/.config/rebalance-os/google-calendar-oauth`) | same |
| Gmail OAuth (oauth mode) | keyring | pickle file (`~/.config/rebalance-os/google-gmail-oauth`) | same |

Each (re)authorization is recorded in `temp/logs/auth_activity.jsonl` (event
stream) and `temp/logs/token_meta.json` (per-token sidecar with `first_added_at`,
so a credential's lifetime is measurable). The raw token value is never stored in
the sidecar — only a SHA-256 fingerprint.

## Steps (run on each device)

```bash
cd /path/to/rebalance-OS
git pull
.venv/bin/pip install -e .          # only if dependencies changed

# 1. Auto-migrate what can be migrated locally (calendar pickle, sleuth env file):
.venv/bin/rebalance config migrate-to-keyring

# 2. GitHub PAT — cannot be auto-migrated (it's a value only you hold).
#    Use the dedicated, NO-EXPIRATION classic PAT (scopes: repo, read:org).
.venv/bin/rebalance config set-github-token ghp_XXXXXXXX

# 3. Sleuth — only if migrate-to-keyring reported "no source found".
#    Non-secret values are fixed; supply the token from your secrets store.
.venv/bin/rebalance config set-sleuth \
    --base-url http://104.238.130.109:2020 \
    --token <SLEUTH_WEB_API_TOKEN> \
    --workspace neochrome-dev
#    NOTE: the example above is the DEV box (direct, public :2020). PRODUCTION is
#    tunnel-only — use --base-url http://127.0.0.1:12020 --workspace neochrome and
#    install the SSH tunnel agent (bash scripts/install_sleuth_tunnel_scheduler.sh).
#    If sleuth-sync fails with ECONNREFUSED on 127.0.0.1:12020, the tunnel is down,
#    not the token. Full setup + troubleshooting: SLEUTH_SYNC.md

# 4. Calendar — only if migrate reported "no token found" (no prior OAuth on this box):
.venv/bin/python scripts/setup_calendar_oauth.py     # opens a browser
.venv/bin/rebalance config migrate-to-keyring        # then re-run to keyring it

# 5. Gmail — only if you use oauth mode (autonomous/launchd sync) and migrate
#    reported "no token found". If you drive rebalance from an MCP host instead,
#    skip this and run: rebalance config set-gmail-method mcp
.venv/bin/python scripts/setup_gmail_oauth.py        # opens a browser (gmail.readonly)
.venv/bin/rebalance config migrate-to-keyring        # then re-run to keyring it

# 6. Verify everything is green:
.venv/bin/rebalance doctor
```

A healthy `rebalance doctor` shows, among the checks:

```
 OK  github token  — stored in keyring + config … · this token first added Nd ago (classic PAT)
 OK  sleuth        — configured (via keyring)
 OK  calendar      — OAuth token present (via keyring) · authorized Nd ago
 OK  gmail         — OAuth token present (via keyring)   # or: MCP mode — N messages ingested
```

## Notes for agents

- **Never echo a token/secret value** to chat, logs, or commits. This is a
  **public** repo. Print only fingerprints, lengths, statuses.
- `migrate-to-keyring` is **idempotent** — safe to re-run; it reports
  "already in keyring ✓" for anything done.
- The GitHub PAT dying "every few days" is almost always **expiry** or
  **regeneration elsewhere** (a shared PAT regenerated on another device
  invalidates the old value everywhere). Prefer a **no-expiration** PAT, or a
  **separate PAT per machine**. The sidecar `first_added_at` lets you measure the
  exact lifetime if it recurs.
- launchd jobs read the **config/file fallback**, not the keychain — so the set
  commands above intentionally write both. Don't delete the fallbacks.
