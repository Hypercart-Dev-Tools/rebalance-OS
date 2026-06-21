"""Shared Google OAuth credential loading for the calendar + gmail collectors.

Both collectors store an OAuth token in the keyring (interactive primary) with a
pickle-file fallback that launchd can read, and on expiry they refresh the access
token and write it back to BOTH stores. The control flow is identical; only these
differ per service and are passed in via :class:`OAuthService`:

  - the keyring getter/setter for the token JSON,
  - the launchd-reachable pickle ``token_path``,
  - the auth-log ``name`` (source label),
  - the scope-superset rule (``has_scopes``),
  - the exception raised on a missing token / insufficient scope.

Owning the keyring→pickle→refresh→persist-both flow once means there is a single
place to reason about (and fix) credential loading, instead of two copies that
drift apart.
"""

from __future__ import annotations

import json
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class OAuthService:
    name: str  # auth-log source label, e.g. "calendar" / "gmail"
    token_path: Path  # launchd-reachable pickle fallback
    get_token_json: Callable[[], str | None]
    set_token_json: Callable[..., bool]  # (token_json, *, source, record) -> bool
    has_scopes: Callable[[Any, list[str]], bool]
    missing_error: Callable[[str], Exception]  # (token_path_str) -> Exception
    scope_error: Callable[[Any, list[str]], Exception]  # (creds, required) -> Exception


def load_credentials(svc: OAuthService, required_scopes: list[str] | None = None) -> Any:
    """Load OAuth2 credentials — keyring first, pickle file as the launchd fallback.

    keyring (interactive primary) ↔ the pickle file (launchd reads this; the
    keychain is unreachable from the daily-sync's stripped environment). On
    refresh, the rotated access token is written back to BOTH so each stays
    current. Raises ``svc.missing_error`` if no token resolves and
    ``svc.scope_error`` if the token lacks a required scope.
    """
    from rebalance.ingest.auth_log import (
        log_token_missing,
        log_token_refresh_failed,
        log_token_refreshed,
    )

    creds = None
    blob = svc.get_token_json()
    if blob:
        try:
            from google.oauth2.credentials import Credentials
            creds = Credentials.from_authorized_user_info(json.loads(blob))
        except Exception:  # noqa: BLE001 — corrupt/legacy blob → fall back to pickle
            creds = None

    if creds is None:
        if not svc.token_path.exists():
            log_token_missing(str(svc.token_path), source=svc.name)
            raise svc.missing_error(str(svc.token_path))
        with open(svc.token_path, "rb") as f:
            creds = pickle.load(f)

    # Refresh if expired — persist the rotated access token to both stores.
    if creds.expired and creds.refresh_token:
        from google.auth.transport.requests import Request
        try:
            creds.refresh(Request())
            # record=False: an access-token refresh is not a re-authorization.
            svc.set_token_json(creds.to_json(), source="refresh", record=False)
            try:
                with open(svc.token_path, "wb") as f:
                    pickle.dump(creds, f)
                svc.token_path.chmod(0o600)  # ponytail: guard the pickle fallback's mode until Phase 3 swaps it for JSON
            except OSError:
                pass
            log_token_refreshed(
                expiry=creds.expiry.isoformat() if creds.expiry else None,
                token_path=str(svc.token_path),
                source=svc.name,
            )
        except Exception as exc:
            log_token_refresh_failed(error=str(exc), token_path=str(svc.token_path), source=svc.name)
            raise

    if required_scopes and not svc.has_scopes(creds, required_scopes):
        raise svc.scope_error(creds, required_scopes)

    return creds
