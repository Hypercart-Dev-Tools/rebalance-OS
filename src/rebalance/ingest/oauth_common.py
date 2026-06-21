"""Shared Google OAuth credential loading for the calendar + gmail collectors.

Both collectors store an OAuth token in the keyring (interactive primary) with a
launchd-reachable file fallback, and on expiry they refresh the access token and
write it back to BOTH stores. The control flow is identical; only these differ
per service and are passed in via :class:`OAuthService`:

  - the keyring getter/setter for the token JSON,
  - the legacy pickle ``token_path`` (read-once for migration; no longer written),
  - the auth-log ``name`` (source label),
  - the scope-superset rule (``has_scopes``),
  - the exception raised on a missing token / insufficient scope.

Phase 3 (auth-storage hardening): the launchd fallback is now a **JSON
authorized-user blob in the out-of-repo secret store** (``~/.config/rebalance-os/
secrets/google-<svc>-oauth``, ``0600``), not a pickle file. Pickle deserialization
is code-executing and opaque; JSON is data-only and inspectable. A pre-existing
pickle fallback is migrated to JSON on first read and retired — no manual step,
so unattended jobs self-heal. ``pickle.load`` survives only in the one-time
legacy migration path (no ``pickle.dump`` remains).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class OAuthService:
    name: str  # auth-log source label, e.g. "calendar" / "gmail"
    token_path: Path  # legacy pickle fallback (read-once for migration; no longer written)
    get_token_json: Callable[[], str | None]
    set_token_json: Callable[..., bool]  # (token_json, *, source, record) -> bool
    has_scopes: Callable[[Any, list[str]], bool]
    missing_error: Callable[[str], Exception]  # (token_path_str) -> Exception
    scope_error: Callable[[Any, list[str]], Exception]  # (creds, required) -> Exception


def secret_store_key(svc: OAuthService) -> str:
    """Secret-store filename for *svc*'s JSON fallback (mirrors the legacy basename)."""
    return f"google-{svc.name}-oauth"


def _creds_from_json(blob: str) -> Any:
    from google.oauth2.credentials import Credentials  # noqa: PLC0415

    return Credentials.from_authorized_user_info(json.loads(blob))


def _migrate_legacy_pickle(svc: OAuthService, store_key: str) -> Any | None:
    """Read a legacy pickle token once, persist it as JSON (keyring + secret store),
    then retire the pickle file. Transitional — removed once every device migrates.

    Returns the credentials, or None if the pickle can't be read.
    """
    import pickle  # noqa: PLC0415 — legacy-only: the sole remaining pickle.load (no pickle.dump)

    from rebalance.ingest import secret_store  # noqa: PLC0415

    try:
        with open(svc.token_path, "rb") as f:
            creds = pickle.load(f)
    except Exception:  # noqa: BLE001 — corrupt/unreadable legacy pickle
        return None
    try:
        token_json = creds.to_json()
        svc.set_token_json(token_json, source="migrate", record=False)  # keyring (best-effort)
        secret_store.write_secret_file(store_key, token_json)            # JSON fallback
    except Exception:  # noqa: BLE001 — if JSON persist fails, keep the pickle for a retry
        return creds
    try:
        svc.token_path.unlink()  # data is now safely in JSON
    except OSError:
        pass
    return creds


def load_credentials(svc: OAuthService, required_scopes: list[str] | None = None) -> Any:
    """Load OAuth2 credentials — keyring first, then the JSON secret-store fallback.

    keyring (interactive primary) ↔ the out-of-repo secret-store JSON file (launchd
    reads this; the keychain is unreachable from the daily-sync's stripped
    environment). A legacy pickle file is migrated to JSON on first read and
    retired. On refresh, the rotated access token is written back to BOTH keyring
    and the JSON fallback. Raises ``svc.missing_error`` if no token resolves and
    ``svc.scope_error`` if the token lacks a required scope.
    """
    from rebalance.ingest import secret_store  # noqa: PLC0415
    from rebalance.ingest.auth_log import (  # noqa: PLC0415
        log_token_missing,
        log_token_refresh_failed,
        log_token_refreshed,
    )

    store_key = secret_store_key(svc)
    creds = None

    # 1) keyring (interactive primary)
    blob = svc.get_token_json()
    if blob:
        try:
            creds = _creds_from_json(blob)
        except Exception:  # noqa: BLE001 — corrupt blob → try the file fallback
            creds = None

    # 2) JSON secret-store fallback (launchd-reachable)
    if creds is None:
        stored = secret_store.read_secret_file(store_key)
        if stored:
            try:
                creds = _creds_from_json(stored)
            except Exception:  # noqa: BLE001 — corrupt JSON fallback → try legacy pickle
                creds = None

    # 3) legacy pickle → JSON migration (read once, convert, retire)
    if creds is None and svc.token_path.exists():
        creds = _migrate_legacy_pickle(svc, store_key)

    if creds is None:
        log_token_missing(str(svc.token_path), source=svc.name)
        raise svc.missing_error(str(svc.token_path))

    # Refresh if expired — persist the rotated access token to keyring + JSON fallback.
    if creds.expired and creds.refresh_token:
        from google.auth.transport.requests import Request  # noqa: PLC0415
        try:
            creds.refresh(Request())
            # record=False: an access-token refresh is not a re-authorization.
            svc.set_token_json(creds.to_json(), source="refresh", record=False)
            try:
                secret_store.write_secret_file(store_key, creds.to_json())
            except OSError:
                pass
            log_token_refreshed(
                expiry=creds.expiry.isoformat() if creds.expiry else None,
                token_path=store_key,
                source=svc.name,
            )
        except Exception as exc:
            log_token_refresh_failed(error=str(exc), token_path=str(svc.token_path), source=svc.name)
            raise

    if required_scopes and not svc.has_scopes(creds, required_scopes):
        raise svc.scope_error(creds, required_scopes)

    return creds
