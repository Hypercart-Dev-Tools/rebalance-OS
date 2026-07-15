#!/usr/bin/env python3
"""
cc_cloud_jobs.py — read Claude Code Cloud (web) sessions + their status.

POC ingest utility. Standalone: no rebalance package import, stdlib only. This is
the surface behind the VS Code "Claude Code > Web" sessions list — ad-hoc cloud
coding jobs launched from claude.ai / the iOS app / the web.

  Endpoint : GET https://api.anthropic.com/v1/code/sessions   (paginate: limit + cursor -> next_cursor)
  Auth     : subscription OAuth bearer token, read from the macOS keychain
             (service "Claude Code-credentials" -> claudeAiOauth.accessToken),
             falling back to ~/.claude/.credentials.json. No API key, no beta header.

Related surfaces (NOT covered here — see PROJECT/1-INBOX/GH-*-CC-CLOUD-JOBS-INGEST.md):
  - scheduled triggers/routines: /v1/code/triggers (reachable only via the Claude Code
    RemoteTrigger tool; host is not public api.anthropic.com).
  - Managed Agents (/v1/deployment_runs, /v1/sessions): API-key-only; subscription
    tokens are rejected (401). Not usable on a Pro/Max subscription.

Two passes:
  PASS 1 — raw normalized records (also saved to temp/ for downstream ingest)
  PASS 2 — synthesized, human-readable status summary for the target day

Usage:
  python3 scripts/cc_cloud_jobs.py                    # today (local)
  python3 scripts/cc_cloud_jobs.py --day 2026-07-14
  python3 scripts/cc_cloud_jobs.py --since 2026-07-01 # everything on/after a date
  python3 scripts/cc_cloud_jobs.py --all              # no date filter (fetched window)
  python3 scripts/cc_cloud_jobs.py --raw-only | --summary-only
  python3 scripts/cc_cloud_jobs.py --out-dir ./somewhere
"""

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://api.anthropic.com"
KEYCHAIN_SERVICE = "Claude Code-credentials"
CREDS_FILE = os.path.expanduser("~/.claude/.credentials.json")
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_OUT_DIR = os.path.join(REPO_ROOT, "temp", "cc-cloud-jobs")  # temp/ is gitignored


# ---------------------------------------------------------------- auth

def get_token():
    """Return the subscription OAuth access token (keychain first, then creds file)."""
    for blob in (_keychain_blob(), _file_blob()):
        if blob.get("accessToken"):
            _warn_if_expired(blob)
            return blob["accessToken"]
    sys.exit("ERROR: no subscription OAuth token found (keychain or ~/.claude/.credentials.json). "
             "Run any `claude` command to log in / refresh.")


def _keychain_blob():
    try:
        raw = subprocess.check_output(
            ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-w"],
            stderr=subprocess.DEVNULL, text=True).strip()
        return json.loads(raw).get("claudeAiOauth", {})
    except Exception:
        return {}


def _file_blob():
    try:
        return json.load(open(CREDS_FILE)).get("claudeAiOauth", {})
    except Exception:
        return {}


def _warn_if_expired(blob):
    exp = blob.get("expiresAt")
    if exp and exp / 1000 < dt.datetime.now(dt.timezone.utc).timestamp():
        print("WARN: subscription token appears expired; run a `claude` command to refresh.",
              file=sys.stderr)


# ---------------------------------------------------------------- fetch

def fetch_sessions(token, hard_cap=500):
    """Page through /v1/code/sessions (newest first) up to hard_cap records."""
    out, cursor = [], None
    while len(out) < hard_cap:
        params = {"limit": 100}
        if cursor:
            params["cursor"] = cursor
        url = f"{BASE}/v1/code/sessions?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("anthropic-version", "2023-06-01")
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                body = json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            raise SystemExit(
                f"HTTP {e.code} on GET /v1/code/sessions\n{e.read().decode()[:300]}\n"
                "401 -> token expired/invalid (refresh via any `claude` command).")
        out.extend(body.get("data", []))
        cursor = body.get("next_cursor")
        if not cursor:
            break
    return out


# ---------------------------------------------------------------- normalize

def parse_ts(ts):
    if not ts:
        return None
    try:
        return dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        try:
            return dt.datetime.fromisoformat(ts.split(".")[0] + "+00:00")
        except Exception:
            return None


def norm(s):
    """Flatten a session record to the fields we report on."""
    cfg = s.get("config") or {}
    meta = s.get("external_metadata") or {}
    branches = meta.get("current_branches") or {}
    branch = next((v for v in branches.values() if v), None)
    if not branch:
        for oc in cfg.get("outcomes") or []:
            b = (oc.get("git_info") or {}).get("branches") or []
            if b:
                branch = b[0]
                break
    pts = meta.get("post_turn_summary") or {}
    if isinstance(pts, str):
        pts = {"status_detail": pts}
    return {
        "id": s.get("id"),
        "title": s.get("title"),
        "status": s.get("status"),
        "status_bucket": s.get("status_bucket"),
        "worker_status": s.get("worker_status"),
        "connection_status": s.get("connection_status"),
        "environment_kind": s.get("environment_kind"),
        "created_at": s.get("created_at"),
        "last_event_at": s.get("last_event_at"),
        "user_message_count": s.get("user_message_count"),
        "unread": s.get("unread"),
        "model": cfg.get("model") or meta.get("last_served_model"),
        "effort_level": cfg.get("effort_level"),
        "origin": cfg.get("origin"),
        "branch": branch,
        "summary": (pts.get("status_detail") or "").strip() or None,
        "needs_action": (pts.get("needs_action") or "").strip() or None,
    }


# ---------------------------------------------------------------- window

def in_window(r, since_date, until_date):
    d = parse_ts(r["created_at"])
    if not d:
        return False
    local = d.astimezone().date()
    if since_date and local < since_date:
        return False
    if until_date and local > until_date:
        return False
    return True


# ---------------------------------------------------------------- synthesis

def hhmm(ts):
    d = parse_ts(ts)
    return d.astimezone().strftime("%H:%M") if d else "-"


def dur(r):
    a, b = parse_ts(r["created_at"]), parse_ts(r["last_event_at"])
    if not a or not b:
        return "-"
    s = int((b - a).total_seconds())
    return f"{s // 3600}h{(s % 3600) // 60:02d}m" if s >= 3600 else f"{s // 60}m{s % 60:02d}s"


# status_bucket -> plain english
BUCKET = {
    "review_ready": "done · review ready",
    "working": "running",
    "running": "running",
    "failed": "FAILED",
    "error": "ERROR",
    "blocked": "blocked / needs input",
}


def synthesize(rows, label):
    L = [f"CLAUDE CODE CLOUD — WEB SESSIONS ({label})", "=" * 70]
    if not rows:
        L.append("\n(no web sessions created in this window)")
        return "\n".join(L)

    buckets = {}
    for r in rows:
        buckets[r["status_bucket"]] = buckets.get(r["status_bucket"], 0) + 1
    L.append(f"\n{len(rows)} session(s).  buckets: " +
             "  ".join(f"{k}={v}" for k, v in sorted(buckets.items(), key=lambda x: str(x[0]))))

    L.append("")
    L.append(f"  {'START':<7}{'DUR':<8}{'STATUS':<22}{'MODEL':<16}TITLE")
    L.append("  " + "-" * 84)
    for r in sorted(rows, key=lambda x: x["created_at"] or ""):
        st = BUCKET.get(r["status_bucket"], r["status_bucket"] or "?")
        worker = "" if r["worker_status"] in ("idle", None) else f" ({r['worker_status']})"
        L.append(f"  {hhmm(r['created_at']):<7}{dur(r):<8}{(st + worker)[:21]:<22}"
                 f"{str(r['model'] or '-')[:15]:<16}{(r['title'] or '(untitled)')[:34]}")

    L.append("\nDETAIL:")
    for r in sorted(rows, key=lambda x: x["created_at"] or ""):
        L.append(f"\n  • {r['title'] or '(untitled)'}   [{r['id']}]")
        L.append(f"      {hhmm(r['created_at'])}–{hhmm(r['last_event_at'])} ({dur(r)})  "
                 f"bucket={r['status_bucket']}  worker={r['worker_status']}  "
                 f"effort={r['effort_level']}  origin={r['origin']}")
        if r["branch"]:
            L.append(f"      branch: {r['branch']}")
        if r["summary"]:
            sm = r["summary"].replace("\n", " ")
            L.append(f"      summary: {sm[:300]}{'…' if len(sm) > 300 else ''}")
        if r["needs_action"]:
            L.append(f"      NEEDS ACTION: {r['needs_action']}")

    done = sum(1 for r in rows if r["status_bucket"] == "review_ready")
    running = sum(1 for r in rows if r["worker_status"] not in ("idle", None))
    failed = sum(1 for r in rows if (r["status_bucket"] or "") in ("failed", "error"))
    L.append("\n" + "=" * 70)
    L.append(f"BOTTOM LINE: {len(rows)} web session(s) — {done} done/review-ready, "
             f"{running} still running, {failed} failed.")
    return "\n".join(L)


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description="Read Claude Code Cloud web sessions + status.")
    ap.add_argument("--day", help="YYYY-MM-DD (single local day; default = today)")
    ap.add_argument("--since", help="YYYY-MM-DD lower bound (local)")
    ap.add_argument("--all", action="store_true", help="no date filter")
    ap.add_argument("--raw-only", action="store_true")
    ap.add_argument("--summary-only", action="store_true")
    ap.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = ap.parse_args()

    if args.all:
        since = until = None
        label = "all recent"
    elif args.since:
        since, until = dt.date.fromisoformat(args.since), None
        label = f"since {since}"
    else:
        day = dt.date.fromisoformat(args.day) if args.day else dt.date.today()
        since = until = day
        label = f"{day}"

    token = get_token()
    allrows = [norm(s) for s in fetch_sessions(token)]
    rows = allrows if args.all else [r for r in allrows if in_window(r, since, until)]

    os.makedirs(args.out_dir, exist_ok=True)
    stamp = (args.day or args.since or dt.date.today().isoformat())
    raw_path = os.path.join(args.out_dir, f"cc_cloud_jobs_{stamp}.json")
    with open(raw_path, "w") as fh:
        json.dump(rows, fh, indent=2)

    if not args.summary_only:
        print("=" * 70)
        print(f"PASS 1 — RAW  ({len(rows)} of {len(allrows)} fetched match {label})")
        print(f"saved: {raw_path}")
        print("=" * 70)
        print(json.dumps(rows, indent=2))

    if not args.raw_only:
        print("\n" + "=" * 70)
        print("PASS 2 — SYNTHESIZED")
        print("=" * 70)
        print(synthesize(rows, label))


if __name__ == "__main__":
    main()
