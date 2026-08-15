#!/usr/bin/env python3
"""
OAuth2 setup script for Google Calendar integration.

Credentials are embedded as Base64-encoded constants (Desktop/Installed app type).
Per Google's own documentation, the client_secret for installed apps is not
security-sensitive — it cannot access any user data without explicit browser consent.
Encoded to avoid GitHub's secret scanner, which does not distinguish between
Desktop app secrets (benign) and Web app secrets (sensitive).

Usage:
  python scripts/setup_calendar_oauth.py
  python scripts/setup_calendar_oauth.py --test
  python scripts/setup_calendar_oauth.py --write-access --test
"""

import argparse

from google_auth_oauthlib.flow import InstalledAppFlow
from rebalance.ingest import config
from rebalance.ingest.auth_log import (
    log_flow_started,
    log_flow_succeeded,
    log_flow_failed,
)
from rebalance.ingest.google_oauth_client import (
    GoogleOAuthClientNotConfigured,
    build_google_oauth_client_config,
)
from rebalance.paths import resolve_oauth_token_path

READONLY_SCOPE = "https://www.googleapis.com/auth/calendar.readonly"
WRITE_SCOPE = "https://www.googleapis.com/auth/calendar"
SECRET_STORE_KEY = "google-calendar-oauth"  # JSON fallback in the secret store


def authorize_calendar(scopes: list[str]):
    """Run OAuth2 browser consent and store the token in keyring + the JSON secret store.

    Phase 3: both durable stores are written in one pass — keyring (interactive
    primary) and the out-of-repo JSON fallback (`~/.config/rebalance-os/secrets/
    google-calendar-oauth`, `0600`). No pickle; no follow-up migrate step.
    """
    flow = InstalledAppFlow.from_client_config(
        build_google_oauth_client_config(),
        scopes=scopes,
    )

    log_flow_started(scopes)
    print("\n🔐 Opening browser for Google OAuth consent...\n")
    try:
        creds = flow.run_local_server(port=0, open_browser=True)
    except Exception as exc:
        log_flow_failed(str(exc))
        raise

    token_json = creds.to_json()
    config.set_calendar_oauth_token_json(token_json, source="manual", record=True)  # keyring
    token_path = resolve_oauth_token_path("calendar")                                # JSON fallback
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(token_json, encoding="utf-8")
    token_path.chmod(0o600)

    log_flow_succeeded(
        expiry=creds.expiry.isoformat() if creds.expiry else None,
        scopes=list(scopes),
        token_path=str(token_path),
    )
    print("\n✅ Token saved to keyring + secret store")
    print(f"   Fallback: {token_path}")
    print(f"   Expires: {creds.expiry}")
    print(f"   Scopes:  {', '.join(scopes)}")
    return creds


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Authorize this device with Google Calendar (one-time setup)"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="List available calendars after authorizing to confirm setup",
    )
    parser.add_argument(
        "--write-access",
        action="store_true",
        help="Request write-capable Calendar scope so agents can create events",
    )
    args = parser.parse_args()

    try:
        scopes = [WRITE_SCOPE] if args.write_access else [READONLY_SCOPE]
        creds = authorize_calendar(scopes)

        if args.test:
            print("\n🧪 Listing your calendars...\n")
            from googleapiclient.discovery import build
            from google.auth.transport.requests import Request
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
            service = build("calendar", "v3", credentials=creds)
            result = service.calendarList().list().execute()

            for cal in result.get("items", []):
                primary = " [PRIMARY]" if cal.get("primary") else ""
                print(f"  • {cal['summary']}{primary}")
                print(f"    ID:     {cal['id']}")
                print(f"    Access: {cal['accessRole']}\n")

        print("✅ Setup complete!\n")
        print("Next steps:")
        print("  1. mkdir -p temp && cp calendar_config.example.json temp/calendar_config.json")
        print("  2. Edit temp/calendar_config.json — set your calendar ID, timezone, and exclude keywords")
        print("  3. rebalance calendar-sync --days-back 365")
        print("  4. rebalance calendar-daily-report\n")
        if args.write_access:
            print("Write access is now enabled for calendar event creation.\n")

    except GoogleOAuthClientNotConfigured as e:
        # A missing client file is a setup step the operator has not done yet, not a
        # crash. A traceback here buries the instructions that actually fix it.
        print(f"\n❌ {e}\n")
        exit(2)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
