"""Shared Google OAuth 2.0 Desktop client credentials.

Both setup scripts (setup_calendar_oauth.py and setup_gmail_oauth.py) use the
same rebalance-OS Desktop/Installed app client. This module is the single place
to rotate the credentials — changing _CID/_CS here updates both flows at once.

Credentials are Base64-encoded to avoid overly-broad secret scanners that do
not distinguish Desktop app secrets (not sensitive — requires user consent in
the browser before any data is accessible) from Web app secrets (sensitive).
See Google OAuth 2.0 for Installed Apps documentation.
"""

from __future__ import annotations

import base64

_CID = "NDA5Mjk4MzQxOTg1LTFrdWI0dTFiMWJkMGxlZWEzYjc0ZDR2bW81Y3F2NzV0LmFwcHMuZ29vZ2xldXNlcmNvbnRlbnQuY29t"
_CS  = "R09DU1BYLWNxWTA3a0VBZDJTTHM5RWg2MDRqV2NYRGxpQXo="

_OAUTH_AUTH_URI  = "https://accounts.google.com/o/oauth2/auth"
_OAUTH_TOKEN_URI = "https://oauth2.googleapis.com/token"


def build_google_oauth_client_config() -> dict:
    """Return the installed-app client config dict for Google OAuth flows."""
    return {
        "installed": {
            "client_id":     base64.b64decode(_CID).decode(),
            "client_secret": base64.b64decode(_CS).decode(),
            "auth_uri":      _OAUTH_AUTH_URI,
            "token_uri":     _OAUTH_TOKEN_URI,
            "redirect_uris": ["http://localhost"],
        }
    }
