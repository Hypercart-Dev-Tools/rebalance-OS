#!/usr/bin/env python3
"""
OAuth2 setup script for Google Calendar integration.
Reads client_secret.json and stores the OAuth token at ~/.config/gcalcli/oauth (pickle format).

Usage:
  python scripts/setup_calendar_oauth.py --client-secret /path/to/client_secret.json
  python scripts/setup_calendar_oauth.py --client-secret /Users/noelsaw/secrets/client_secret_2_409298341985-1kub4u1b1bd0leea3b74d4vmo5cqv75t.apps.googleusercontent.com.json
"""

import json
import pickle
import argparse
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

# OAuth scope for calendar read-only access
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
TOKEN_PATH = Path.home() / ".config" / "gcalcli" / "oauth"


def authorize_calendar(client_secret_path: str) -> None:
    """Run OAuth2 flow and store the token."""
    client_secret_path = Path(client_secret_path).expanduser().resolve()
    
    if not client_secret_path.exists():
        raise FileNotFoundError(f"Client secret not found: {client_secret_path}")
    
    print(f"📋 Using client secret: {client_secret_path}")
    
    # Create token directory if needed
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    # Load client secret and run OAuth flow
    flow = InstalledAppFlow.from_client_secrets_file(
        client_secret_path,
        scopes=SCOPES,
    )
    
    print("\n🔐 Opening browser for Google OAuth consent...\n")
    creds = flow.run_local_server(port=0, open_browser=True)
    
    # Save the token in pickle format
    with open(TOKEN_PATH, "wb") as f:
        pickle.dump(creds, f)
    
    print(f"\n✅ Token saved to: {TOKEN_PATH}")
    print(f"   Expires: {creds.expiry}")
    print(f"\n✨ You can now run: rebalance calendar-sync --days-back 365\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Set up Google Calendar OAuth for rebalance"
    )
    parser.add_argument(
        "--client-secret",
        required=True,
        help="Path to client_secret.json from Google Cloud Console",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Test the setup by listing calendars",
    )
    args = parser.parse_args()

    try:
        authorize_calendar(args.client_secret)

        if args.test:
            print("\n🧪 Testing setup by listing calendars...\n")
            from googleapiclient.discovery import build
            creds = pickle.load(open(TOKEN_PATH, "rb"))
            service = build("calendar", "v3", credentials=creds)
            calendars_result = service.calendarList().list().execute()

            print(f"Found {len(calendars_result.get('items', []))} calendars:\n")
            for cal in calendars_result.get("items", []):
                cal_id = cal.get("id")
                summary = cal.get("summary")
                access_role = cal.get("accessRole")
                primary = " [PRIMARY]" if cal.get("primary") else ""
                print(f"  • {summary}{primary}")
                print(f"    ID: {cal_id}")
                print(f"    Access: {access_role}\n")

        print("✅ Setup complete!")
        print(f"\nNext steps:")
        print(f"  1. Copy temp/calendar_config.json.template to temp/calendar_config.json")
        print(f"  2. Edit temp/calendar_config.json with your calendar ID and preferences")
        print(f"  3. Run: rebalance calendar-sync --days-back 365")
        print(f"  4. Try: rebalance calendar-daily-report")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
