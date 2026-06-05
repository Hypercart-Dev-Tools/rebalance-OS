# Sleuth reminder sync

`rebalance sleuth-sync` pulls reminders from the Sleuth Web API into the local
`sleuth_reminders` SQLite table (consumed by the morning brief, dashboard, and
the `sleuth_sync_reminders` MCP tool). This doc covers the one piece that is easy
to miss when setting up a new device: **production is reachable only through an
SSH tunnel.**

## TL;DR — "connection refused on 127.0.0.1:12020"

That is **not** a credential problem. The production Sleuth API port is firewalled
from the public internet, so `http://127.0.0.1:12020` only resolves while an SSH
port-forward to the prod box is up. If the tunnel is down you get `ECONNREFUSED`
(connection refused), regardless of how correct your token is.

**Fix (durable):**
```bash
bash scripts/install_sleuth_tunnel_scheduler.sh
```
This installs a launchd agent that keeps the forward `127.0.0.1:12020 → prod
127.0.0.1:2020` up across logins and reconnects if it drops. Then:
```bash
rebalance sleuth-sync --env production --json | head -20   # should succeed
```

**Fix (one-off, current shell only):**
```bash
ssh -fN -L 12020:127.0.0.1:2020 root@<prod-host>
```

## Why it's built this way (short token + localhost are intentional)

Yes — a short token and a `127.0.0.1` base URL are **by design**, not a
misconfiguration:

- **Firewall + tunnel, not public HTTP.** Port `2020` on the prod box is blocked
  at the firewall. The only way in is an authenticated SSH tunnel, so the API is
  never exposed to the internet. A direct request to `<prod-host>:2020` times out.
- **`base_url = http://127.0.0.1:12020`.** Your machine talks to its own loopback;
  SSH carries the bytes (encrypted) to the server's loopback `:2020`. There is no
  plaintext API traffic on the wire — the token rides inside the SSH session.
- **Token length isn't the security boundary.** Because the listener is
  loopback-only behind SSH key auth, the bearer token is a secondary check, not
  the perimeter. (Still: if port 2020 is ever exposed publicly, rotate to a
  high-entropy `WEB_API_BEARER_TOKEN` on the server first.)

Dev is different: `--env development` points at the dev box's **public**
`:2020` directly (no tunnel needed). Only **production** is tunnel-gated.

## How the pieces fit

```
rebalance sleuth-sync --env production
        │  reads base_url=http://127.0.0.1:12020, token, workspace=neochrome
        ▼
   127.0.0.1:12020  ──SSH port-forward (launchd: com.rebalance-os.sleuth-tunnel)──►  prod 127.0.0.1:2020
                                                                                      (firewalled; Sleuth Web API)
```

## First-time setup on a new device

1. **Credentials** (keyring + launchd fallback) — production values:
   ```bash
   rebalance config set-sleuth \
       --base-url http://127.0.0.1:12020 \
       --token <SLEUTH_WEB_API_TOKEN> \
       --workspace neochrome
   ```
   (Dev uses `--base-url http://<dev-host>:2020 --workspace neochrome-dev`.)

2. **Key-based SSH to the prod box** — launchd can't answer a password prompt, so
   the tunnel agent requires key auth. Add your public key to the server once:
   ```bash
   ssh-copy-id -i ~/.ssh/id_ed25519.pub root@<prod-host>
   ssh -i ~/.ssh/id_ed25519 root@<prod-host> 'echo ok'   # must print ok, no prompt
   ```

3. **Install the tunnel agent:**
   ```bash
   bash scripts/install_sleuth_tunnel_scheduler.sh
   ```
   The host is read from `--host`, `$SLEUTH_PROD_HOST`, or
   `~/secrets/sleuth/vultr-sleuth-production.env` (never committed — public repo).

4. **Verify:**
   ```bash
   nc -z 127.0.0.1 12020 && echo "tunnel up" || echo "tunnel down"
   rebalance doctor
   rebalance sleuth-sync --env production --json | head -20
   ```

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `ECONNREFUSED` / connection refused on `127.0.0.1:12020` | Tunnel not running | `launchctl list \| grep sleuth-tunnel`; if absent, `bash scripts/install_sleuth_tunnel_scheduler.sh`; if present, `launchctl unload && load` the plist |
| Tunnel agent loaded but port still dead | Key auth failing at launchd time (no password prompt possible) | Confirm `ssh -i ~/.ssh/id_ed25519 root@<prod-host> 'echo ok'` works keyless; check `temp/logs/sleuth_tunnel_stderr.log` |
| `{"success":false,"data":"Forbidden."}` (HTTP **200**) | Wrong/missing token | Re-run `rebalance config set-sleuth` with the correct token. Note: the API returns 200 even on auth failure — check the JSON body, not the status code |
| Direct `curl <prod-host>:2020` times out | Working as intended — port is firewalled | Use the tunnel + `127.0.0.1:12020`, not the public host |

## Related

- `scripts/com.rebalance-os.sleuth-tunnel.plist.template` — the launchd agent (rendered by the install script)
- `scripts/install_sleuth_tunnel_scheduler.sh` — installer + keyless-SSH preflight
- `UPGRADE.md` — full credential migration (keyring + fallback) for a device
- `PROJECT/3-DONE/SLEUTH-PRODUCTION.md` — original cutover checklist (predates the firewall+tunnel move; see this doc for current reality)
