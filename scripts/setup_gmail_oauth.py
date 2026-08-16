#!/usr/bin/env python3
"""
OAuth2 setup script for Gmail ingest.

Mirrors scripts/setup_calendar_oauth.py. Credentials are embedded as
Base64-encoded constants (Desktop/Installed app type). Per Google's own
documentation, the client_secret for installed apps is not security-sensitive —
it cannot access any user data without explicit browser consent. Encoded to
avoid GitHub's secret scanner, which does not distinguish between Desktop app
secrets (benign) and Web app secrets (sensitive).

Why this (and not ADC): gmail.readonly is a Google-RESTRICTED scope. A user's
own OAuth client with the consent screen in "Testing" mode (and their account
added as a test user) can request it without formal app verification. The shared
gcloud ADC client generally cannot, which is why `gcloud auth
application-default login --scopes=...gmail.readonly` yields tokens that 403 with
"insufficient authentication scopes". This flow is the portable path for cloners.

Usage:
  python scripts/setup_gmail_oauth.py
  python scripts/setup_gmail_oauth.py --test

The token is written to keyring + the JSON secret store in one pass — no
follow-up migrate step is needed.
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

GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
SECRET_STORE_KEY = "google-gmail-oauth"  # JSON fallback in the secret store


def authorize_gmail(scopes: list[str]):
    """Run OAuth2 browser consent and store the token in keyring + the JSON secret store.

    Phase 3: both durable stores are written in one pass — keyring (interactive
    primary) and the out-of-repo JSON fallback (`~/.config/rebalance-os/secrets/
    google-gmail-oauth`, `0600`). No pickle; no follow-up migrate step.
    """
    flow = InstalledAppFlow.from_client_config(
        build_google_oauth_client_config(),
        scopes=scopes,
    )

    log_flow_started(scopes, source="gmail")
    print("\n🔐 Opening browser for Google (Gmail) OAuth consent...\n")
    print("   If you see an 'unverified app' warning, click")
    print("   Advanced → Go to rebalance OS (unsafe). This is your own")
    print("   Testing-mode client requesting read-only Gmail access.\n")
    try:
        creds = flow.run_local_server(port=0, open_browser=True)
    except Exception as exc:
        log_flow_failed(str(exc), source="gmail")
        raise

    token_json = creds.to_json()
    config.set_gmail_oauth_token_json(token_json, source="manual", record=True)  # keyring
    token_path = resolve_oauth_token_path("gmail")                                # JSON fallback
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(token_json, encoding="utf-8")
    token_path.chmod(0o600)

    log_flow_succeeded(
        expiry=creds.expiry.isoformat() if creds.expiry else None,
        scopes=list(scopes),
        token_path=str(token_path),
        source="gmail",
    )
    print("\n✅ Token saved to keyring + secret store")
    print(f"   Fallback: {token_path}")
    print(f"   Expires: {creds.expiry}")
    print(f"   Scopes:  {', '.join(scopes)}")
    return creds


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Authorize this device for Gmail ingest (one-time setup)"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Fetch your inbox profile after authorizing to confirm setup",
    )
    args = parser.parse_args()

    try:
        scopes = [GMAIL_READONLY_SCOPE]
        creds = authorize_gmail(scopes)

        if args.test:
            print("\n🧪 Reading your Gmail profile...\n")
            from googleapiclient.discovery import build
            from google.auth.transport.requests import Request
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
            service = build("gmail", "v1", credentials=creds, cache_discovery=False)
            profile = service.users().getProfile(userId="me").execute()
            print(f"  • Address:        {profile.get('emailAddress')}")
            print(f"  • Total messages: {profile.get('messagesTotal')}\n")

        print("✅ Setup complete!\n")
        print("Next steps:")
        print("  1. rebalance config set-gmail-method oauth   # if currently on mcp")
        print("  2. rebalance doctor                          # verify gmail is green\n")

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
