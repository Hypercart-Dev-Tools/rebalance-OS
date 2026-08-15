"""Google OAuth 2.0 Desktop client credentials — supplied by the operator.

Both setup scripts (setup_calendar_oauth.py and setup_gmail_oauth.py) use the
same Desktop/Installed app client. rebalance does **not** ship one: you create
an OAuth client in your own Google Cloud project and point rebalance at it.

Why bring-your-own rather than a bundled client:

- A bundled client belongs to whoever published it. Its consent screen, its
  verification status, its quota and its rotation are all that publisher's —
  and its audience setting decides who can authenticate at all. An "Internal"
  consent screen restricts sign-in to the publisher's own Workspace domain,
  which silently locks out every other user.
- With your own client, your organization owns consent, scope review, quota,
  audit trail and revocation. Nothing about your Google data routes through
  someone else's project.

Setup (once):

1. Google Cloud Console → create or pick a project.
2. APIs & Services → Enable **Google Calendar API** and **Gmail API** (only
   the ones you intend to use).
3. APIs & Services → OAuth consent screen. Pick the audience that matches your
   situation: **Internal** if every user is in your own Workspace domain,
   **External** otherwise. Add the scopes you enabled above.
4. Credentials → Create credentials → **OAuth client ID** → application type
   **Desktop app**. Download the JSON.
5. Save it where rebalance looks, or point at it explicitly::

       # option A — default location
       mkdir -p ~/secrets && mv ~/Downloads/client_secret_*.json \\
           ~/secrets/google_oauth_client.json

       # option B — anywhere, named explicitly
       export GOOGLE_OAUTH_CLIENT_FILE=/path/to/client_secret.json

A template with the expected shape ships at
``google_oauth_client.example.json`` in the repo root.

Resolution order: ``GOOGLE_OAUTH_CLIENT_FILE`` → ``google_oauth_client.json``
in the resolved secrets dir (``REBALANCE_SECRETS_DIR`` / user config /
``~/secrets``). Missing or malformed files raise
:class:`GoogleOAuthClientNotConfigured` naming every path that was tried.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from rebalance.paths import resolve_secret_path

CLIENT_FILE_ENV = "GOOGLE_OAUTH_CLIENT_FILE"
CLIENT_FILE_NAME = "google_oauth_client.json"

_OAUTH_AUTH_URI = "https://accounts.google.com/o/oauth2/auth"
_OAUTH_TOKEN_URI = "https://oauth2.googleapis.com/token"

_SETUP_HINT = (
    "Create a Desktop-app OAuth client in your own Google Cloud project "
    "(Console → APIs & Services → Credentials → OAuth client ID → Desktop app), "
    f"then either save the downloaded JSON as the path above or set {CLIENT_FILE_ENV} "
    "to point at it. See google_oauth_client.example.json for the expected shape, "
    "and GOOGLE_CALENDAR.md / GMAIL.md for the full walkthrough."
)


class GoogleOAuthClientNotConfigured(RuntimeError):
    """Raised when no operator-supplied OAuth client can be resolved."""


def client_file_candidates() -> list[Path]:
    """Every path consulted, in order. Public so errors and `doctor` agree."""
    candidates: list[Path] = []
    explicit = os.environ.get(CLIENT_FILE_ENV)
    if explicit:
        candidates.append(Path(explicit).expanduser())
    candidates.append(resolve_secret_path(CLIENT_FILE_NAME))
    return candidates


def resolve_client_file() -> Path:
    """Return the first existing candidate, or raise naming all of them."""
    candidates = client_file_candidates()
    for path in candidates:
        if path.is_file():
            return path
    tried = "\n".join(f"  - {p}" for p in candidates)
    raise GoogleOAuthClientNotConfigured(
        f"No Google OAuth client credentials found. Tried:\n{tried}\n\n{_SETUP_HINT}"
    )


def build_google_oauth_client_config() -> dict:
    """Return the installed-app client config dict for Google OAuth flows.

    Reads the operator's own downloaded client JSON. Google writes it under an
    ``installed`` key for Desktop apps; a ``web`` key means the wrong
    application type was chosen, which is worth saying plainly rather than
    failing later inside the flow with a redirect-URI mismatch.
    """
    path = resolve_client_file()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GoogleOAuthClientNotConfigured(
            f"Could not read Google OAuth client credentials at {path}: {exc}\n\n{_SETUP_HINT}"
        ) from exc

    if "web" in raw and "installed" not in raw:
        raise GoogleOAuthClientNotConfigured(
            f"{path} holds a **Web application** OAuth client; rebalance needs a "
            "**Desktop app** client. Create one of type 'Desktop app' and download it again."
        )

    section = raw.get("installed") or raw
    client_id = section.get("client_id")
    client_secret = section.get("client_secret")
    if not client_id or not client_secret:
        raise GoogleOAuthClientNotConfigured(
            f"{path} is missing client_id and/or client_secret.\n\n{_SETUP_HINT}"
        )

    redirect_uris = section.get("redirect_uris") or ["http://localhost"]
    if "http://localhost" not in redirect_uris:
        redirect_uris = [*redirect_uris, "http://localhost"]

    return {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": section.get("auth_uri") or _OAUTH_AUTH_URI,
            "token_uri": section.get("token_uri") or _OAUTH_TOKEN_URI,
            "redirect_uris": redirect_uris,
        }
    }
