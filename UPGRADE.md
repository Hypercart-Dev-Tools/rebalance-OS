# UPGRADE — bring a device onto the keyring credential model

> **Status note (2026-06-20).** This document describes the **currently shipped**
> keyring-plus-fallback operator workflow. For the newer audit of what actually
> landed, what was deferred, and the forward hardening plan that supersedes this
> model for future auth-storage work, see
> [PROJECT/2-WORKING/AUTH-AND-API-KEY-STORAGE-HARDENING.md](PROJECT/2-WORKING/AUTH-AND-API-KEY-STORAGE-HARDENING.md).

rebalance-OS now stores its external credentials in the **OS keyring**
(macOS Keychain) as the primary, with a **launchd-reachable fallback** for each
(launchd's stripped environment can't read the keychain). This replaces the old
"loose secret files in `~/secrets/`" approach, which caused silent stalls when a
file was missing or in the wrong place.

> **Keyring is per-machine.** It does **not** sync across devices. Each device
> installs its secrets once. This guide is what you run on a device to catch up.

> **DB migrations auto-apply.** After `git pull`, numbered migration files in
> `src/rebalance/ingest/db/migrations/` are applied automatically the first time
> any ingest or collector runs. No manual schema step required.

## Credential model (after upgrade)

> This table is the **current shipped state**, not the desired end-state. The
> hardening plan above tracks the follow-up work to remove plaintext repo-local
> fallbacks and pickle OAuth fallback files.

| Credential | Primary | launchd fallback | Logged on (re)auth |
|---|---|---|---|
| GitHub PAT | keyring | `temp/rbos.config` | `auth_log` `token_set` + `token_meta` |
| Sleuth sync source | keyring | `temp/rbos.config` | same |
| Google Calendar OAuth | keyring | pickle file (`~/.config/rebalance-os/google-calendar-oauth`) | same |
| Gmail OAuth (oauth mode) | keyring | pickle file (`~/.config/rebalance-os/google-gmail-oauth`) | same |
| Figma PAT (opt-in) | keyring | `temp/rbos.config` | — (not auth-logged; set manually) |

Each (re)authorization is recorded in `temp/logs/auth_activity.jsonl` (event
stream) and `temp/logs/token_meta.json` (per-token sidecar with `first_added_at`,
so a credential's lifetime is measurable). The raw token value is never stored in
the sidecar — only a SHA-256 fingerprint.

## Steps (run on each device)

```bash
cd /path/to/rebalance-OS
git pull
.venv/bin/pip install -e .          # run after every pull — dependencies change with new collectors

# 1. Auto-migrate what can be migrated locally (calendar pickle, sleuth env file):
.venv/bin/rebalance config migrate-to-keyring

# 2. GitHub PAT — cannot be auto-migrated (it's a value only you hold).
#    Use the dedicated, NO-EXPIRATION classic PAT (scopes: repo, read:org).
.venv/bin/rebalance config set-github-token ghp_XXXXXXXX

# 3. Sleuth — all devices should use the git-pulse-sync file-source method.
#    If this machine was previously pointed at the Web API, override it now.
git clone https://github.com/Hypercart-Dev-Tools/rebalance-git-pulse.git ~/git-pulse-sync
.venv/bin/rebalance config set-sleuth \
    --base-url "~/git-pulse-sync/sync/sleuth/reminders-neochrome.json" \
    --token file-source \
    --workspace neochrome
#    This reads the published Sleuth export directly from the companion repo —
#    no API auth, tunnel, or public :2020 endpoint. A file:// or local-path
#    base_url is read directly (token unused). Full setup + troubleshooting:
#    SLEUTH_SYNC.md

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
 OK  sleuth        — configured (via config/env file)
 OK  calendar      — OAuth token present (via keyring) · authorized Nd ago
 OK  gmail         — OAuth token present (via keyring)   # or: MCP mode — N messages ingested
```

## Opt-in integrations (per-device, as needed)

### Figma comments (`figma` scope)

Figma ingestion is PAT-gated and disabled by default. The collector skips cleanly
when unconfigured — no doctor warning, no error. To enable it on a device:

```bash
# No CLI command exists yet — write directly to temp/rbos.config (gitignored JSON):
# Set figma_token to a Figma personal access token (Settings → Personal access tokens).
# Set figma_file_keys to the list of Figma file keys you want to monitor
# (the alphanumeric ID from the Figma file URL: figma.com/file/<FILE_KEY>/...).
python3 -c "
import json, pathlib
cfg = pathlib.Path('temp/rbos.config')
d = json.loads(cfg.read_text()) if cfg.exists() else {}
d['figma_token'] = 'figd_XXXXXXXXXXXXXXXX'
d['figma_file_keys'] = ['FILEKEY1', 'FILEKEY2']
cfg.write_text(json.dumps(d, indent=2))
print('written')
"
# Then run migrate-to-keyring to lift the token into the keyring:
.venv/bin/rebalance config migrate-to-keyring
```

The Figma collector is `included_in_all=False` — it runs only when explicitly
scoped (`rebalance refresh --scope figma` or the registry scope list includes
`"figma"`). Comments are ingested into `figma_comments` and vectorized into the
unified semantic index.

### External GitHub repo watching

External repos are declared in the project registry (not via a credential). Add
`external: true` to a project block and list its repos under `repos:`. No new
token is required — the existing GitHub PAT covers public repos and any private
repos the PAT can read. External repos enter the canonical watched set and appear
in the pulse "Watched repos" section automatically on the next refresh.

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
