# Calendar Timesheet Setup — Portability Summary

## ✅ FULLY PORTABLE FOR OTHER USERS

The calendar daily/weekly report feature is **production-ready for distribution**. Any new user can clone, install, and run in ~15 minutes with zero shared credentials.

---

## What's Portable

| Component | Status | Details |
|-----------|--------|---------|
| **Code** | ✅ Shared | All in `src/`, `scripts/`, shared across users |
| **Dependencies** | ✅ Pinned | Listed in `pyproject.toml`, installable via `pip` |
| **OAuth app** | ✅ Per-user | Each user creates own credentials in Google Cloud |
| **OAuth token** | ✅ Device-local | Stored at `~/.config/gcalcli/oauth`, never in repo |
| **Config** | ✅ User-editable | `temp/calendar_config.json` (gitignored, template provided) |
| **Database** | ✅ Generated locally | `rebalance.db` created by user, never shared |
| **Documentation** | ✅ Complete | Setup guides provided for each step |

---

## What's NOT in the Repo

❌ OAuth credentials (user creates own)  
❌ OAuth tokens (stored locally on each device)  
❌ User-specific calendars (configured per user)  
❌ Exclude keywords (user-defined in config)  
❌ Database files (generated locally)  
❌ Any hardcoded calendar IDs or secrets  

---

## New User Workflow

### 1. Clone & Install (5 min)
```bash
git clone <repo>
python3 -m venv .venv
pip install -e .
```

### 2. Create Google OAuth App (5 min)
- Go to Google Cloud Console
- Create project, enable Calendar API
- Create OAuth desktop credentials
- Download `client_secret.json`

### 3. Authorize Device (3 min)
```bash
python scripts/setup_calendar_oauth.py --client-secret /path/to/client_secret.json --test
```

### 4. Configure (2 min)
```bash
cp temp/calendar_config.json.template temp/calendar_config.json
# Edit calendar_id, exclude_keywords, timezone
```

### 5. Test (1 min)
```bash
rebalance calendar-sync --days-back 365
rebalance calendar-daily-report
```

**Total time: ~15 minutes**

---

## Documentation for New Users

Start here in order:

1. **[CALENDAR_NEW_USER_SETUP.md](./CALENDAR_NEW_USER_SETUP.md)** ← START HERE
   - Step-by-step setup guide
   - Troubleshooting
   - FAQ

2. **[README.md Step 4](./README.md#step-4--connect-google-calendar-optional)**
   - Quick overview

3. **[CALENDAR_SETUP_GUIDE.md](./CALENDAR_SETUP_GUIDE.md)**
   - Quick reference
   - CLI commands

4. **[CALENDAR_REPORTS.md](./CALENDAR_REPORTS.md)**
   - Report format and customization

5. **[CALENDAR_PORTABILITY_AUDIT.md](./CALENDAR_PORTABILITY_AUDIT.md)**
   - Technical audit
   - Detailed portability analysis

---

## Key Design Decisions

**No shared credentials:**
- Each user creates own Google OAuth app in their account
- OAuth tokens stored locally on their device, never in repo

**Config per user:**
- Calendar selection, exclude keywords, timezone all editable
- `temp/calendar_config.json` is gitignored
- Template provided for copy-paste

**Zero magic:**
- Script explicitly shows OAuth flow in browser
- Token location is clear and documented
- Calendar IDs listed at setup time
- All paths use user's home directory (`~`)

**Graceful degradation:**
- Works without sqlite-vec extension (tested on Python 3.9)
- Provides sensible defaults if config missing
- Clear error messages with recovery steps

---

## Verification Checklist

For each new user:

- [ ] Clone successful
- [ ] `pip install -e .` successful
- [ ] OAuth script runs, opens browser
- [ ] User consents in Google auth screen
- [ ] Token saved to `~/.config/gcalcli/oauth`
- [ ] Config file created at `temp/calendar_config.json`
- [ ] `calendar-sync` completes without errors
- [ ] `calendar-daily-report` shows events
- [ ] `calendar-weekly-report` shows full week

**If all ✅ → ready for production use**

---

## Troubleshooting Common Issues

### "OAuth token not found"
→ Re-run setup script with `--test` flag

### "calendar_id not valid"
→ Run setup script with `--test` to list calendars
→ Copy ID from output into config

### "Python 3.12 required"
→ Use pyenv or conda to install Python 3.12+
→ Or: Some features work on 3.9+, but `pip install -e .` needs 3.12+

### "sqlite-vec error"
→ Not critical — feature works without it
→ Only affects semantic search (not calendar)

---

## Distribution Notes

**For sharing with others:**

1. Provide link to this repo
2. Point them to `CALENDAR_NEW_USER_SETUP.md`
3. They follow 5 steps to get running
4. **No credentials to share** — they use their own Google account

**For team setups:**

- Each team member uses own Google account
- Separate `temp/calendar_config.json` per user
- Shared code, separate data
- No centralized OAuth secrets

---

## Ready for Distribution

✅ **Code quality:** DRY, SOLID, well-documented  
✅ **Security:** No credentials in repo, OAuth per-user  
✅ **Usability:** Step-by-step guides for new users  
✅ **Robustness:** Graceful error handling, tested on multiple Python versions  
✅ **Portability:** Zero user-specific data in repo  

**Status: PRODUCTION-READY**

---

Created: 2026-04-07
