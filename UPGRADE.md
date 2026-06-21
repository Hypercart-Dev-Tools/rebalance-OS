# UPGRADE — bring a device onto the keyring credential model

> **Status note (updated 2026-06-21).** The auth-storage hardening **Phases 0–3 have
> landed**: keyring stays the interactive primary, but every launchd fallback now
> lives in the permission-enforced out-of-repo **secret store**
> (`~/.config/rebalance-os/secrets/`, `0600`) — no plaintext secrets in `temp/rbos.config`,
> no pickle OAuth files. This guide reflects that model. Full audit, rationale, and the
> deferred (multi-operator) work:
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

> This table reflects the **auth-storage hardening (Phases 0–3, landed 2026-06-21)**:
> every launchd fallback now lives in the permission-enforced out-of-repo **secret
> store** — no plaintext in `temp/rbos.config`, no pickle OAuth files. The only
> remaining work is multi-operator/fleet machinery, deferred in the plan.

| Credential | Primary | launchd fallback | Logged on (re)auth |
|---|---|---|---|
| GitHub PAT | keyring | secret store (`~/.config/rebalance-os/secrets/github_token`, `0600`) | `auth_log` `token_set` + `token_meta` |
| Sleuth sync source | keyring | secret store (`~/.config/rebalance-os/secrets/sleuth_web_api`, `0600`) | same |
| Google Calendar OAuth | keyring | secret store JSON (`~/.config/rebalance-os/secrets/google-calendar-oauth`, `0600`) | same |
| Gmail OAuth (oauth mode) | keyring | secret store JSON (`~/.config/rebalance-os/secrets/google-gmail-oauth`, `0600`) | same |
| Figma PAT (opt-in) | keyring | secret store (`~/.config/rebalance-os/secrets/figma_token`, `0600`) | — (not auth-logged; set manually) |

### What changed (auth-storage hardening, 2026-06-21)

- **Secrets left the repo.** GitHub / Figma / Sleuth fallbacks no longer write to
  repo-local `temp/rbos.config`; they live in the secret store. A repo checkout now
  carries **no live credentials** — it can be copied or archived safely.
- **Google OAuth fallback is JSON, not pickle**, in the same secret store. (Pickle is
  code-executing on load; JSON is data-only and inspectable.)
- **Permissions are enforced** — every secret file is `0600`, its directory `0700`;
  `doctor` warns if anything drifts broader.

**What to do on each device (after `git pull`):**

```bash
rebalance config migrate-secrets   # lifts existing secrets out of rbos.config AND
                                   # retires legacy OAuth pickle files → JSON
rebalance doctor                   # expect "repo-local secrets — … no live secrets"
```

`migrate-secrets` is **idempotent** (safe to re-run) and **per-machine** — until a
device runs it, it keeps working via the legacy read fallback, so there is no flag
day and no rush. There is nothing to copy between machines; each device migrates its
own local secrets in place.

Each (re)authorization is recorded in `temp/logs/auth_activity.jsonl` (event
stream) and `temp/logs/token_meta.json` (per-token sidecar with `first_added_at`,
so a credential's lifetime is measurable). The raw token value is never stored in
the sidecar — only a SHA-256 fingerprint.

## Steps (run on each device)

```bash
cd /path/to/rebalance-OS
git pull
.venv/bin/pip install -e .          # run after every pull — dependencies change with new collectors

# 1. Adopt keyring + move secrets out of the repo (both idempotent, safe to re-run):
.venv/bin/rebalance config migrate-to-keyring   # sleuth env file / any legacy → keyring
.venv/bin/rebalance config migrate-secrets       # rbos.config secrets + OAuth pickle → secret store

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

# 4. Calendar — only if doctor reports "no Calendar OAuth credentials" (no prior OAuth here):
.venv/bin/python scripts/setup_calendar_oauth.py     # opens a browser; writes keyring + JSON fallback in one pass

# 5. Gmail — only if you use oauth mode (autonomous/launchd sync) and doctor
#    reports "no Gmail OAuth credentials". If you drive rebalance from an MCP host
#    instead, skip this and run: rebalance config set-gmail-method mcp
.venv/bin/python scripts/setup_gmail_oauth.py        # opens a browser (gmail.readonly); writes keyring + JSON fallback

# 6. Verify everything is green:
.venv/bin/rebalance doctor
```

A healthy `rebalance doctor` shows, among the checks:

```
 OK  github token       — stored in keyring + secret store (reachable by launchd) · first added Nd ago (classic PAT)
 OK  secret permissions — N secret file(s)/dir(s) at 0600/0700
 OK  repo-local secrets — temp/rbos.config holds no live secrets
 OK  sleuth             — configured (via file source)
 OK  calendar           — OAuth token present (via keyring) · authorized Nd ago
 OK  gmail              — OAuth token present (via keyring)   # or: MCP mode — N messages ingested
```

## Opt-in integrations (per-device, as needed)

### Figma comments (`figma` scope)

Figma ingestion is PAT-gated and disabled by default. The collector skips cleanly
when unconfigured — no doctor warning, no error. To enable it on a device:

```bash
# figma_file_keys is plain (non-secret) config; the PAT goes to the keyring +
# secret store, never the repo. First set the file keys you want to monitor
# (the alphanumeric ID from figma.com/file/<FILE_KEY>/...):
python3 -c "
import json, pathlib
cfg = pathlib.Path('temp/rbos.config')
d = json.loads(cfg.read_text()) if cfg.exists() else {}
d['figma_file_keys'] = ['FILEKEY1', 'FILEKEY2']
cfg.write_text(json.dumps(d, indent=2))
print('file keys written')
"
# Then store the PAT securely — keyring primary + secret-store fallback, never the
# repo (no CLI wrapper yet, so call the setter directly):
.venv/bin/python -c "from rebalance.ingest import config; config.set_figma_token('figd_XXXXXXXXXXXXXXXX')"
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
