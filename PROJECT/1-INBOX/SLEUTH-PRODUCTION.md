# Sleuth → rebalance-OS: Production Cutover Checklist

**Trigger:** Sleuth has been deployed to the **prod** Vultr server (`64.176.223.93`) on
a HEAD that includes commit `15725ec` (`Add rebalance reminders API export`) or later.

**Goal:** Switch the rebalance-OS daily sync from pulling dev reminders to pulling
prod reminders, while keeping the dev integration available for ad-hoc/manual use.

---

## 0. Pre-flight

- [ ] Confirm Sleuth prod is running the new reminders code:
  ```bash
  ssh root@64.176.223.93 'git -C /root/sleuth-app log --oneline -5 | grep 15725ec || echo "MISSING — deploy first"'
  ```
  Password is in `~/secrets/vultr-sleuth-production.env` (line 3).
- [ ] Confirm the systemd unit already references the runtime env file:
  ```bash
  ssh root@64.176.223.93 'grep EnvironmentFile /etc/systemd/system/sleuth-app.service'
  ```
  Expected: `EnvironmentFile = -/root/sleuth-app/.env.runtime`. If missing, deploy
  the updated `sleuth-app.service` first.
- [ ] Decide the prod **workspace name** (likely `neochrome`, not `neochrome-dev`):
  ```bash
  ssh root@64.176.223.93 'ls /root/sleuth-app/data/runtime/reminders/ 2>/dev/null'
  ```
  Look for `<name>_reminders.json` — that `<name>` is the workspace.

---

## 1. Server side: install the prod bearer token

You can ask Claude Code to do steps 1.1–1.5 in one SSH round-trip (it did this for
dev already), or run them by hand.

- [ ] **1.1** SSH into prod as root.
- [ ] **1.2** Generate a fresh token (do **not** reuse the dev token):
  ```bash
  TOKEN=$(openssl rand -hex 32)
  ```
- [ ] **1.3** Write the runtime env file:
  ```bash
  umask 077
  cat >/root/sleuth-app/.env.runtime <<EOF
  WEB_API_BEARER_TOKEN=$TOKEN
  WEB_API_PORT=2020
  EOF
  chmod 600 /root/sleuth-app/.env.runtime
  ```
- [ ] **1.4** Reload systemd and restart Sleuth:
  ```bash
  systemctl daemon-reload
  systemctl restart sleuth-app
  systemctl is-active sleuth-app
  ```
- [ ] **1.5** Verify on the server (replace `<workspace>` with the value from 0):
  ```bash
  curl -sS -H "Authorization: Bearer $TOKEN" http://127.0.0.1:2020/workspaces
  curl -sS -H "Authorization: Bearer test" http://127.0.0.1:2020/workspaces  # expect Forbidden
  curl -sS -H "Authorization: Bearer $TOKEN" \
    "http://127.0.0.1:2020/workspace/<workspace>/reminders?format=rebalance&activeOnly=false" | head -c 400
  ```
- [ ] **1.6** Capture the token value (you'll need it locally in step 2).

---

## 2. Local side: store prod connection info

- [ ] Create `~/secrets/sleuth-web-api-production.env` with mode 600:
  ```
  SLEUTH_WEB_API_BASE_URL=http://64.176.223.93:2020
  SLEUTH_WEB_API_TOKEN=<token from step 1.6>
  SLEUTH_WORKSPACE_NAME=<workspace from step 0>
  ```
  ```bash
  chmod 600 ~/secrets/sleuth-web-api-production.env
  ```
- [ ] Smoke test from the laptop:
  ```bash
  set -a; source ~/secrets/sleuth-web-api-production.env; set +a
  curl -sS -H "Authorization: Bearer $SLEUTH_WEB_API_TOKEN" \
    "$SLEUTH_WEB_API_BASE_URL/workspace/$SLEUTH_WORKSPACE_NAME/reminders?format=rebalance&activeOnly=false" \
    | python3 -m json.tool | head -40
  ```
- [ ] Confirm the dev file is still present and untouched:
  ```bash
  ls -la ~/secrets/sleuth-web-api-*.env
  ```

---

## 3. rebalance-OS code change: env switching

The dev-only loader has a TODO comment for this (planted during the original
implementation). Required changes:

- [ ] **3.1** In the secrets loader (sibling of the Google Calendar loader in
  `src/rebalance/cli.py`), accept an `env_name` parameter (`"development"` or
  `"production"`) and read `~/secrets/sleuth-web-api-{env_name}.env`. Default
  stays `"development"`.
- [ ] **3.2** Add `--env [development|production]` flag to `rebalance sleuth-sync`,
  default `development`. Pass through to the loader.
- [ ] **3.3** Add the same `env_name` arg to the `sleuth_sync_reminders` MCP tool
  in `src/rebalance/mcp_server.py`. Default `development`.
- [ ] **3.4** Tests: extend `tests/test_sleuth_reminders.py` to cover both env
  names — verify the loader picks the right file and raises clearly when the
  prod file is missing.
- [ ] **3.5** Manually run both:
  ```bash
  rebalance sleuth-sync --env development --json | head -20
  rebalance sleuth-sync --env production  --json | head -20
  ```
  Both should succeed. The shared `sleuth_reminders` SQLite table separates rows
  via the `workspace_name` column — no schema change needed.

---

## 4. launchd: switch daily sync to prod

- [ ] Edit `scripts/daily_sync.sh`. Find the existing `rebalance sleuth-sync`
  invocation and change it to:
  ```bash
  rebalance sleuth-sync --env production
  ```
  (No need to also pull dev — dev remains available for manual `rebalance
  sleuth-sync --env development` runs.)
- [ ] Reload the launchd plist if it caches anything (it shouldn't — the plist
  invokes the shell script, not the Python directly):
  ```bash
  launchctl unload ~/Library/LaunchAgents/com.rebalance-os.daily-sync.plist
  launchctl load   ~/Library/LaunchAgents/com.rebalance-os.daily-sync.plist
  ```
- [ ] Trigger a one-off run to confirm it works under launchd:
  ```bash
  launchctl start com.rebalance-os.daily-sync
  ```
  Then check the log file `daily_sync.sh` writes to.

---

## 5. Verification

- [ ] `sqlite3 <rebalance-db> "SELECT workspace_name, COUNT(*) FROM sleuth_reminders GROUP BY workspace_name;"`
  → expect rows for both `neochrome-dev` (historical, from earlier dev runs) and
  the prod workspace (new).
- [ ] `sqlite3 <rebalance-db> "SELECT MAX(last_synced_at) FROM sleuth_reminders WHERE workspace_name = '<prod-workspace>';"`
  → should be within minutes of "now".
- [ ] Spot-check one prod reminder by ID — open the corresponding Slack message
  and confirm the text matches.

---

## 6. Rollback

If prod sync misbehaves:

- [ ] Revert step 4 (`scripts/daily_sync.sh`) to `--env development` and reload
  the launchd plist.
- [ ] Manual prod runs still work via `rebalance sleuth-sync --env production`
  for debugging without affecting the daily job.
- [ ] To rotate the prod token: regenerate via step 1.2–1.5, update
  `~/secrets/sleuth-web-api-production.env`, re-test step 2 smoke test.
  No rebalance-OS code change needed.

---

## 7. Notes / decisions baked into this plan

- **Separate token per environment.** Never reuse dev token in prod.
- **Local SQLite keeps history.** The ingestor doesn't delete rows that vanish
  from the API response — completed/canceled reminders stay in the DB even when
  pulled with `activeOnly=true`.
- **Plain HTTP over the public internet.** Both dev and prod expose port 2020
  unencrypted. Token can be sniffed in transit. Acceptable for current data
  sensitivity; revisit (SSH tunnel, nginx+TLS, or firewall allowlist) if the
  reminder content ever includes anything more sensitive than today's mix.
- **Dev pull is preserved, not removed.** `rebalance sleuth-sync --env development`
  remains available for ad-hoc dev queries.
