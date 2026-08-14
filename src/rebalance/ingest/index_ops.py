"""Index operations: status snapshot and orchestrated refresh.

This module is the single entry point that MCP tools (and any agent embedding
the SDK) should use instead of the discrete CLI commands. It composes the
underlying ingest pipelines so callers do not have to know the order of
``github-scan`` -> ``github-sync-artifacts`` -> ``semantic-backfill`` ->
``semantic-embed`` etc.
"""

from __future__ import annotations

import logging
import sqlite3
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from rebalance.ingest.config import (
    get_figma_file_keys,
    get_figma_token,
    get_github_token,
    get_vault_path,
)
from rebalance.ingest.db import db_connection, ensure_semantic_schema, run_migrations
from rebalance.ingest.registry import get_projects
from rebalance.ingest.semantic_index import SemanticDoc

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Collector:
    """A single data-source ingest pipeline registered with :data:`COLLECTORS`.

    External integrators add new data sources by constructing a :class:`Collector`
    and calling :func:`register_collector`. The dispatcher in :func:`refresh_index`
    routes the user's ``scope=[...]`` list through the registry — no edits to
    the dispatch chain are required.

    Fields
    ------
    name:
        The user-facing scope key. Must be unique. Reserved: ``"all"``.
    refresh:
        Callable executed for live runs. Receives ``(db_path, **opts)`` where
        ``opts`` includes every refresh_index kwarg the collector might want
        (since_days, vault_path, token, repos, ...). Unknown
        keys must be ignored. Must return a ``dict`` whose first key is
        ``"scope": "<name>"`` so the caller can correlate results.
    requires:
        Optional iterable of precondition names — currently ``"vault_path"``,
        ``"github_token"``. Failures surface as structured errors rather than
        exceptions, mirroring the legacy refresh_index error envelope.
    included_in_all:
        If True (default), the collector is part of the default refresh recipe
        (a no-scope `rebalance refresh`). For raw sources this also makes them
        part of the ``all`` token. Set False for opt-in collectors (e.g. figma,
        focus5, ask_self) that must be requested by name.
    kind:
        Architectural classification — one of ``raw_source`` / ``derived_scan``
        / ``projection`` / ``export`` (see COLLECTOR-PATH-AND-PORTABILITY-AUDIT).
        Only ``raw_source`` collectors are raw incoming data; derived scans,
        projections, and exports are *stages*, not sources. ``raw_source`` is the
        default so external integrations register a source unless they say otherwise.
    semantic_docs:
        Optional registry-driven provider that yields :class:`SemanticDoc`
        rows for the unified semantic index. When present, the source becomes
        a *SourceModule*: the flag-gated provider path in
        ``backfill_semantic_documents`` iterates it instead of an if-ladder
        branch. ``None`` (default) preserves the legacy vault/github/email/code
        ladder unchanged.
    candidates:
        Optional registry-driven provider that yields deterministic
        next-action candidate dicts (each carrying ``rank_key``, ``source``,
        non-empty ``evidence``, and ``why``) from a day bundle. This is the
        SECOND use of the same registry seam as ``semantic_docs``:
        ``next_actions._operator_candidates`` walks the registry and calls each
        provider instead of hand-dispatching per source, so a new work signal
        reaches the ranked verdict by registering a collector — never by editing
        the ranker's dispatch chain (GUIDING-PRINCIPLES Principle 3). ``None``
        (default) means the source contributes no next-action candidates.
    """

    name: str
    refresh: Callable[..., dict[str, Any]]
    requires: tuple[str, ...] = ()
    included_in_all: bool = True
    kind: str = "raw_source"
    semantic_docs: Callable[[Any], Iterable["SemanticDoc"]] | None = None
    candidates: Callable[[Any], Iterable[dict[str, Any]]] | None = None


# A Collector that also exposes a ``semantic_docs`` provider is the spine of a
# registry-driven SourceModule (the strangler path). The alias names that role
# without forking the dataclass.
SourceModule = Collector


# Architectural classification for collectors (COLLECTOR-PATH-AND-PORTABILITY-AUDIT).
_COLLECTOR_KINDS = {"raw_source", "derived_scan", "projection", "export"}

COLLECTORS: dict[str, Collector] = {}


def register_collector(collector: Collector, *, replace: bool = False) -> None:
    """Add a :class:`Collector` to the registry.

    Set ``replace=True`` when an external integrator deliberately overrides a
    built-in. Otherwise duplicate names raise to surface accidental shadowing.
    """
    if not collector.name or collector.name != collector.name.lower():
        raise ValueError(
            f"Collector name must be non-empty and lowercase: {collector.name!r}"
        )
    if collector.name == "all":
        raise ValueError(f"Reserved collector name: {collector.name!r}")
    if collector.kind not in _COLLECTOR_KINDS:
        raise ValueError(
            f"Collector {collector.name!r} has invalid kind {collector.kind!r}; "
            f"expected one of {sorted(_COLLECTOR_KINDS)}."
        )
    if collector.name in COLLECTORS and not replace:
        raise ValueError(
            f"Collector {collector.name!r} already registered; pass replace=True to override."
        )
    COLLECTORS[collector.name] = collector
    logger.debug("Registered collector: %s (requires=%s)", collector.name, collector.requires)


def _scope_values() -> tuple[str, ...]:
    """Return the supported scope keys, plus the meta-scope ``"all"``."""
    return tuple(COLLECTORS.keys()) + ("all",)


def _raw_source_scopes() -> list[str]:
    """The raw incoming sources — the only ``kind == "raw_source"`` collectors
    that are all-eligible. This is what the ``all`` token expands to (Decision A);
    derived scans / projections / exports are stages, attached intentionally."""
    return [n for n, c in COLLECTORS.items() if c.kind == "raw_source" and c.included_in_all]


def _default_refresh_scopes() -> list[str]:
    """The default full-refresh recipe (registration order): all raw sources plus
    the all-eligible follow-on stages (code, semantic, sync). This is what a
    no-scope `rebalance refresh` / `refresh_index(scope=None)` runs — raw sources
    first, then the derived/projection/export stages that read them."""
    return [name for name, c in COLLECTORS.items() if c.included_in_all]


def _all_scope_names() -> list[str]:
    """Collectors the ``all`` token expands to — the raw incoming sources only
    (Decision A). Derived scans / projections / exports are NOT in ``all``; they
    run as named follow-on stages in the default recipe (:func:`_default_refresh_scopes`)."""
    return _raw_source_scopes()


def _semantic_source_names() -> list[str]:
    """Return registered collectors that expose a ``semantic_docs`` provider."""
    return [n for n, c in COLLECTORS.items() if c.semantic_docs is not None]


# Legacy SCOPE_VALUES: retained so callers importing the constant continue to
# work. New code should call _scope_values() since registered collectors may
# extend the set at runtime.
SCOPE_VALUES = ("vault", "github", "calendar", "sleuth", "email", "semantic", "all")


def _safe_count(conn: Any, table: str) -> int | None:
    try:
        row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        return int(row[0]) if row else 0
    except Exception:
        return None


def _safe_max(conn: Any, table: str, column: str) -> str | None:
    try:
        row = conn.execute(f"SELECT MAX({column}) FROM {table}").fetchone()
        return row[0] if row and row[0] else None
    except Exception:
        return None


def _safe_count_where(conn: Any, table: str, where: str) -> int | None:
    try:
        row = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}").fetchone()
        return int(row[0]) if row else 0
    except Exception:
        return None


# GH-166: how far behind the vault writer the ingester is allowed to drift
# before signal_health.vault trips, in minutes. com.rebalance-os.vault-sync
# runs hourly (:15 past the hour); a healthy install clears any edit within
# that same run, well under the 60-minute cadence. 2x cadence (missed one
# full cycle) warns; 3x cadence (missed two) degrades. Both are still far
# tighter than the old 7-day freshness window, which never caught the
# ~51-90 minute drift this fixes (#166).
_VAULT_INGEST_LAG_WARN_MINUTES = 120
_VAULT_INGEST_LAG_DEGRADED_MINUTES = 180

# GH-166: a semantic_documents row still pending embed past this many minutes
# is flagged "stuck" rather than counted as an in-flight run's normal tail.
# See the comment at the pending-embed drift computation in get_index_status
# for why 30 minutes is well past a healthy run's expected completion time.
_PENDING_EMBED_STUCK_MINUTES = 30

_SIGNAL_HEALTH_RULES: dict[str, dict[str, Any]] = {
    "vault": {
        "freshness_key": "last_ingested_at",
        "window_days": 7,
        "zero_status": "degraded",
        # GH-166: a fresh last_ingested_at only proves *some* ingest ran
        # recently — it says nothing about whether the writer has since
        # moved further ahead. lag_key names a computed field on the
        # source payload (last_modified_in_vault - last_ingested_at) that
        # this rule's warn/degraded minutes are checked against below.
        "lag_key": "ingest_lag_minutes",
        "lag_warn_minutes": _VAULT_INGEST_LAG_WARN_MINUTES,
        "lag_degraded_minutes": _VAULT_INGEST_LAG_DEGRADED_MINUTES,
    },
    "github": {
        "freshness_key": "activity_last_scanned_at",
        "window_days": 7,
        "zero_status": "degraded",
        # GH-127 content-quality check. github_activity (the table
        # recent_row_count_7d windows above) is a pure per-day counters
        # rollup with no per-item content, so the predicate targets
        # github_items instead — windowed on fetched_at (the collector's own
        # sync timestamp, mirroring how recent_row_count_7d windows
        # github_activity on scanned_at) rather than the item's own
        # created_at/updated_at, so a burst of newly-synced-but-empty items
        # is caught the same run they land.
        "content_predicate": "title IS NOT NULL AND TRIM(title) != ''",
        "content_table": "github_items",
        "content_window_column": "fetched_at",
        "content_label": "a title",
    },
    "calendar": {"freshness_key": "last_fetched_at", "window_days": 7, "zero_status": "degraded"},
    "sleuth": {"freshness_key": "last_synced_at", "window_days": 7, "zero_status": "warn"},
    "apple_reminders": {
        "freshness_key": "last_synced_at",
        "window_days": 7,
        "zero_status": "warn",
    },
    "email": {
        "freshness_key": "last_synced_at",
        "window_days": 7,
        "zero_status": "degraded",
        # GH-145 / GH-141: this source is narrowed by an operator-configured
        # Gmail query. When the collector runs successfully and that query
        # matches nothing, zero rows is the CONFIGURED outcome, not a failure —
        # so a quiet window reports `ok` and names the filter instead of
        # applying zero_status. Freshness is already known-current at the point
        # this is consulted, which is what proves the collector actually ran;
        # a stale or missing timestamp is still caught above and still degrades.
        #
        # Without this, the live filter `in:inbox is:starred is:important` (a
        # three-way AND matching ~1-3 messages a month) marked email degraded
        # permanently by design, and contradicted doctor's own `email data`
        # check in the same output.
        #
        # Declarative: any other filtered source adds this key. No new branch.
        "quiet_filter": "describe_gmail_query_filter",
        # GH-127 content-quality check — the exact defect that hid 119/124
        # dead rows for 3 weeks (#125). Same table + window email already
        # uses for recent_row_count_7d (email_messages / received_at).
        "content_predicate": (
            "(from_address IS NOT NULL AND TRIM(from_address) != '') "
            "OR (subject IS NOT NULL AND TRIM(subject) != '')"
        ),
        "content_table": "email_messages",
        "content_window_column": "received_at",
        "content_label": "a sender or subject",
    },
    "figma": {"freshness_key": "last_synced_at", "window_days": 7, "zero_status": "warn"},
    "ask_self": {"freshness_key": "last_scanned_at", "window_days": 7, "zero_status": "warn"},
}

_SIGNAL_HEALTH_TOTAL_KEYS: dict[str, tuple[str, ...]] = {
    "vault": ("files", "chunks"),
    "github": ("activity_records", "items", "documents"),
    "calendar": ("events",),
    "sleuth": ("reminders",),
    "apple_reminders": ("reminders",),
    "email": ("messages",),
    "figma": ("comments",),
    "ask_self": ("repos",),
}


def _parse_status_timestamp(raw: Any) -> datetime | None:
    from rebalance.lib.time_ops import _parse_iso as common_parse_iso
    return common_parse_iso(raw, force_utc=True)


def _vault_ingest_lag_minutes(last_modified_in_vault: Any, last_ingested_at: Any) -> float | None:
    """Minutes the ingester is behind the vault writer, clamped to >= 0.

    None when either timestamp is missing or unparseable — the caller
    already surfaces a missing-timestamp verdict via the freshness check,
    so this stays silent rather than inventing a number.
    """
    modified = _parse_status_timestamp(last_modified_in_vault)
    ingested = _parse_status_timestamp(last_ingested_at)
    if modified is None or ingested is None:
        return None
    lag = (modified - ingested).total_seconds() / 60
    return max(0.0, lag)


def _minutes_since(raw_timestamp: Any, now: datetime) -> float | None:
    """Minutes between *now* and *raw_timestamp*, or None if unparseable."""
    ts = _parse_status_timestamp(raw_timestamp)
    if ts is None:
        return None
    return (now - ts).total_seconds() / 60


def _source_total_rows(source_name: str, source_payload: dict[str, Any]) -> int:
    for key in _SIGNAL_HEALTH_TOTAL_KEYS.get(source_name, ()):
        value = source_payload.get(key)
        if isinstance(value, int):
            return value
    return 0


def _quiet_filter_description(rule: dict[str, Any]) -> str | None:
    """Describe *rule*'s configured narrowing filter, or None if it declares none.

    GH-145. The rule names a formatter in ``rebalance.ingest.config`` rather than
    embedding a filter string, so the filter has exactly one home and no health
    surface can drift from it. A source with no ``quiet_filter`` key is
    unaffected, and a formatter that fails is treated as "no filter declared" —
    a health check must never crash the status it is reporting on.
    """
    name = rule.get("quiet_filter")
    if not name:
        return None
    try:
        from rebalance.ingest import config as _config  # noqa: PLC0415

        formatter = getattr(_config, str(name), None)
        if formatter is None:
            return None
        described = formatter()
    except Exception:  # noqa: BLE001 — never let a description break the verdict
        return None
    described = str(described).strip()
    return described or None


def _derive_signal_health(sources: dict[str, dict[str, Any]]) -> dict[str, dict[str, str]]:
    now = datetime.now(timezone.utc)
    signal_health: dict[str, dict[str, str]] = {}

    for source_name, rule in _SIGNAL_HEALTH_RULES.items():
        source_payload = sources.get(source_name)
        if not source_payload:
            continue

        recent_rows = int(source_payload.get("recent_row_count_7d") or 0)
        total_rows = _source_total_rows(source_name, source_payload)
        status_entry: dict[str, str] = {"status": "ok"}
        freshness_value = _parse_status_timestamp(source_payload.get(rule["freshness_key"]))
        stale_after = timedelta(days=int(rule["window_days"]))

        if freshness_value is None:
            if total_rows == 0:
                status_entry = {"status": "warn", "reason": "no data has been observed yet"}
            else:
                status_entry = {
                    "status": "degraded",
                    "reason": f"freshness timestamp {rule['freshness_key']} is missing",
                }
        else:
            age = now - freshness_value
            if age > stale_after * 2:
                status_entry = {
                    "status": "degraded",
                    "reason": f"last refresh advanced {age.days}d ago (window {rule['window_days']}d)",
                }
            elif age > stale_after:
                status_entry = {
                    "status": "warn",
                    "reason": f"last refresh advanced {age.days}d ago (window {rule['window_days']}d)",
                }
            elif recent_rows == 0:
                zero_status = str(rule["zero_status"])
                quiet_filter = _quiet_filter_description(rule)
                if total_rows == 0:
                    status_entry = {
                        "status": "warn",
                        "reason": "freshness timestamp is current but the source has no rows yet",
                    }
                elif quiet_filter is not None:
                    # GH-145 / GH-141: freshness is current, so the collector
                    # ran. A narrowing filter that matched nothing is the
                    # configured outcome, not silent data loss.
                    status_entry = {
                        "status": "ok",
                        "reason": f"no rows matched in the last {rule['window_days']}d ({quiet_filter})",
                    }
                else:
                    status_entry = {
                        "status": zero_status,
                        "reason": "freshness timestamp is current but 0 rows landed in the last 7d",
                    }

        # GH-166 ingest-lag override: last_ingested_at can be fresh (a sync
        # ran recently) while the vault writer has still moved further
        # ahead than the ingester has caught up to. Only overrides an
        # otherwise-ok verdict — a source already flagged warn/degraded by
        # freshness/zero-rows above keeps that verdict and reason, same
        # precedence rule the content-quality override below follows.
        lag_key = rule.get("lag_key")
        if lag_key and status_entry["status"] == "ok":
            lag_minutes = source_payload.get(lag_key)
            if isinstance(lag_minutes, (int, float)):
                degraded_after = rule.get("lag_degraded_minutes")
                warn_after = rule.get("lag_warn_minutes")
                if degraded_after is not None and lag_minutes > degraded_after:
                    status_entry = {
                        "status": "degraded",
                        "reason": (
                            f"ingest is {round(lag_minutes)}m behind the vault "
                            f"writer (threshold {degraded_after}m)"
                        ),
                    }
                elif warn_after is not None and lag_minutes > warn_after:
                    status_entry = {
                        "status": "warn",
                        "reason": (
                            f"ingest is {round(lag_minutes)}m behind the vault "
                            f"writer (threshold {warn_after}m)"
                        ),
                    }

        # GH-127 content-quality override: rows can be structurally valid
        # (present, on-time) but semantically empty — no sender/subject on an
        # email, no title on a github item. This is what let 119/124 dead
        # email rows sit "ok" for 3 weeks (#125). Only sources with a
        # content_predicate in the rule are checked (currently email +
        # github); every other source's verdict is untouched by this block.
        # Only overrides an otherwise-`ok` verdict — a source already flagged
        # warn/degraded by freshness keeps that verdict and reason.
        content_predicate = rule.get("content_predicate")
        if content_predicate and status_entry["status"] == "ok":
            content_total = int(source_payload.get("content_total_count_7d") or 0)
            content_fail = int(source_payload.get("content_fail_count_7d") or 0)
            if content_total > 0:
                fail_fraction = content_fail / content_total
                if fail_fraction > 0.5:
                    pct = round(fail_fraction * 100)
                    label = rule.get("content_label", "meaningful content")
                    status_entry = {
                        "status": "degraded",
                        "reason": f"{pct}% of recent rows lack {label}",
                    }

        signal_health[source_name] = status_entry

    return signal_health


def _apple_reminders_health_status(database_path: Path) -> str | None:
    """Cheap apple_reminders health status (ok | drift | never_synced) for the
    status payload. None if the probe itself fails — never crashes status."""
    try:
        from rebalance.ingest.apple_reminders import apple_reminders_health
        return apple_reminders_health(database_path).get("status")
    except Exception:
        return None


def _safe_meta(conn: Any, table: str) -> dict[str, str]:
    try:
        rows = conn.execute(f"SELECT key, value FROM {table}").fetchall()
        return {r["key"]: r["value"] for r in rows}
    except Exception:
        return {}


def _normalize_scope(scope: Iterable[str] | str | None) -> list[str]:
    if scope is None:
        return _default_refresh_scopes()
    if isinstance(scope, str):
        items = [scope]
    else:
        items = list(scope)
    cleaned: list[str] = []
    valid = _scope_values()
    for raw in items:
        v = (raw or "").strip().lower()
        if not v:
            continue
        if v not in valid:
            raise ValueError(f"Unsupported scope: {raw!r}. Expected one of {valid}.")
        if v not in cleaned:
            cleaned.append(v)
    if not cleaned:
        return _default_refresh_scopes()
    if "all" in cleaned:
        return _all_scope_names()
    return cleaned


def get_index_status(database_path: Path) -> dict[str, Any]:
    """Return a structured snapshot of every source + the unified semantic index.

    Read-only. Safe to call frequently; no schema migrations beyond the standard
    semantic schema bootstrap done elsewhere.
    """
    db_path = Path(database_path).expanduser().resolve()
    payload: dict[str, Any] = {
        "database_path": str(db_path),
        "database_exists": db_path.exists(),
        "sources": {},
        "semantic_index": {},
        "freshness": {},
    }

    if not db_path.exists():
        payload["error"] = "database file does not exist"
        return payload

    with db_connection(db_path, ensure_semantic_schema) as conn:
        payload["sources"]["vault"] = {
            "files": _safe_count(conn, "vault_files"),
            "chunks": _safe_count(conn, "chunks"),
            "last_ingested_at": _safe_max(conn, "vault_files", "ingested_at"),
            "last_modified_in_vault": _safe_max(conn, "vault_files", "last_modified"),
            "recent_row_count_7d": _safe_count_where(
                conn, "vault_files", "julianday(last_modified) >= julianday('now', '-7 days')"
            ) or 0,
        }
        # GH-166: how far the ingester is behind the vault writer, in minutes.
        # Positive means the newest edit on disk hasn't been ingested yet;
        # clamped at 0 so a normal ingest-after-edit ordering never reports a
        # negative lag. None when either timestamp is missing/unparseable.
        payload["sources"]["vault"]["ingest_lag_minutes"] = _vault_ingest_lag_minutes(
            payload["sources"]["vault"]["last_modified_in_vault"],
            payload["sources"]["vault"]["last_ingested_at"],
        )

        payload["sources"]["github"] = {
            "items": _safe_count(conn, "github_items"),
            "documents": _safe_count(conn, "github_documents"),
            "activity_records": _safe_count(conn, "github_activity"),
            "activity_last_scanned_at": _safe_max(conn, "github_activity", "scanned_at"),
            "documents_last_fetched_at": _safe_max(conn, "github_documents", "fetched_at"),
            "documents_last_updated_at": _safe_max(conn, "github_documents", "updated_at"),
            "recent_row_count_7d": _safe_count_where(
                conn, "github_activity", "julianday(scanned_at) >= julianday('now', '-7 days')"
            ) or 0,
        }

        payload["sources"]["calendar"] = {
            "events": _safe_count(conn, "calendar_events"),
            "last_fetched_at": _safe_max(conn, "calendar_events", "fetched_at"),
            "earliest_event_start": _safe_max(conn, "calendar_events", "start_time"),
            "recent_row_count_7d": _safe_count_where(
                conn, "calendar_events", "julianday(start_time) >= julianday('now', '-7 days') AND julianday(start_time) <= julianday('now', '+7 days')"
            ) or 0,
        }

        payload["sources"]["sleuth"] = {
            "reminders": _safe_count(conn, "sleuth_reminders"),
            "last_synced_at": _safe_max(conn, "sleuth_reminders", "last_synced_at"),
            "recent_row_count_7d": _safe_count_where(
                conn, "sleuth_reminders", "julianday(created_on) >= julianday('now', '-7 days')"
            ) or 0,
        }

        payload["sources"]["apple_reminders"] = {
            "reminders": _safe_count(conn, "apple_reminders"),
            "active": _safe_count_where(
                conn, "apple_reminders", "is_active=1 AND is_completed=0"
            ),
            "last_synced_at": _safe_max(conn, "apple_reminders", "last_synced_at"),
            "health": _apple_reminders_health_status(database_path),
            "recent_row_count_7d": _safe_count_where(
                conn, "apple_reminders", "julianday(last_synced_at) >= julianday('now', '-7 days')"
            ) or 0,
        }

        payload["sources"]["email"] = {
            "messages": _safe_count(conn, "email_messages"),
            "last_synced_at": _safe_max(conn, "email_messages", "synced_at"),
            "newest_received_at": _safe_max(conn, "email_messages", "received_at"),
            "recent_row_count_7d": _safe_count_where(
                conn, "email_messages", "julianday(received_at) >= julianday('now', '-7 days')"
            ) or 0,
        }

        payload["sources"]["figma"] = {
            "comments": _safe_count(conn, "figma_comments"),
            "last_synced_at": _safe_max(conn, "figma_comments", "synced_at"),
            "newest_comment_at": _safe_max(conn, "figma_comments", "created_at"),
            "recent_row_count_7d": _safe_count_where(
                conn, "figma_comments", "julianday(created_at) >= julianday('now', '-7 days')"
            ) or 0,
        }

        try:
            built = conn.execute(
                "SELECT COUNT(*) FROM ask_self_indexes WHERE index_built = 1"
            ).fetchone()[0]
        except Exception:
            built = None
        payload["sources"]["ask_self"] = {
            "repos": _safe_count(conn, "ask_self_indexes"),
            "built_indexes": built,
            "last_scanned_at": _safe_max(conn, "ask_self_indexes", "scanned_at"),
            "recent_row_count_7d": _safe_count_where(
                conn, "ask_self_indexes", "julianday(scanned_at) >= julianday('now', '-7 days')"
            ) or 0,
        }

        # GH-127 content-quality check. Registry-driven off
        # _SIGNAL_HEALTH_RULES: sources that declare a content_predicate get a
        # materialized content_total_count_7d / content_fail_count_7d pair
        # that _derive_signal_health reads generically. Adding a source's
        # predicate is a dict-entry addition to the rules above — no new
        # branch is needed here or in _derive_signal_health.
        for source_name, rule in _SIGNAL_HEALTH_RULES.items():
            predicate = rule.get("content_predicate")
            content_table = rule.get("content_table")
            window_column = rule.get("content_window_column")
            if not predicate or not content_table or not window_column:
                continue
            source_payload = payload["sources"].get(source_name)
            if source_payload is None:
                continue
            window_clause = f"julianday({window_column}) >= julianday('now', '-7 days')"
            source_payload["content_total_count_7d"] = _safe_count_where(
                conn, content_table, window_clause
            ) or 0
            source_payload["content_fail_count_7d"] = _safe_count_where(
                conn, content_table, f"{window_clause} AND NOT ({predicate})"
            ) or 0

        # Semantic index
        sem_total = _safe_count(conn, "semantic_documents")
        sem_meta = _safe_meta(conn, "semantic_embedding_meta")
        by_source: dict[str, dict[str, int]] = {}
        try:
            rows = conn.execute(
                """
                SELECT source_type,
                       COUNT(*) AS docs,
                       SUM(CASE WHEN embedded_hash IS NOT NULL
                                 AND embedded_hash = content_hash
                                THEN 1 ELSE 0 END) AS embedded
                FROM semantic_documents
                GROUP BY source_type
                """
            ).fetchall()
            for r in rows:
                by_source[r["source_type"]] = {
                    "documents": int(r["docs"] or 0),
                    "embedded": int(r["embedded"] or 0),
                    "pending": int((r["docs"] or 0) - (r["embedded"] or 0)),
                }
        except Exception:
            pass

        try:
            embeddings_rows = conn.execute(
                "SELECT COUNT(*) FROM semantic_embeddings"
            ).fetchone()[0]
        except Exception:
            embeddings_rows = None

        payload["semantic_index"] = {
            "total_documents": sem_total,
            "by_source": by_source,
            "embeddings_rows": embeddings_rows,
            "model_name": sem_meta.get("model_name"),
            "embedding_dim": sem_meta.get("embedding_dim"),
            "embedder_version": sem_meta.get("embedder_version"),
            "last_embedded_at": sem_meta.get("last_embed_at"),
        }

        # Freshness drift checks: source rows that are NOT in semantic_documents
        drift: dict[str, Any] = {}
        try:
            vault_drift = conn.execute(
                """
                SELECT COUNT(*) FROM chunks c
                LEFT JOIN semantic_documents sd
                  ON sd.source_type = 'vault' AND sd.source_pk = CAST(c.id AS TEXT)
                WHERE sd.id IS NULL
                """
            ).fetchone()[0]
            drift["vault_chunks_missing_from_semantic"] = int(vault_drift)
        except Exception:
            drift["vault_chunks_missing_from_semantic"] = None

        try:
            # GH-167: mirror the ignored-repo exclusion that
            # ``github_documents_for_semantic()`` applies to the projection
            # itself. Without this, a doc in an ignored repo is correctly never
            # projected but still counts as "missing" here forever — a
            # permanent false-positive drift reading, not a real gap.
            from rebalance.ingest.config import get_github_ignored_repos

            ignored_repos = sorted(get_github_ignored_repos())
            if ignored_repos:
                placeholders = ", ".join("?" for _ in ignored_repos)
                gh_drift = conn.execute(
                    f"""
                    SELECT COUNT(*) FROM github_documents gd
                    LEFT JOIN semantic_documents sd
                      ON sd.source_type = 'github' AND sd.source_pk = gd.source_key
                    WHERE sd.id IS NULL
                      AND LOWER(gd.repo_full_name) NOT IN ({placeholders})
                    """,
                    ignored_repos,
                ).fetchone()[0]
            else:
                gh_drift = conn.execute(
                    """
                    SELECT COUNT(*) FROM github_documents gd
                    LEFT JOIN semantic_documents sd
                      ON sd.source_type = 'github' AND sd.source_pk = gd.source_key
                    WHERE sd.id IS NULL
                    """
                ).fetchone()[0]
            drift["github_documents_missing_from_semantic"] = int(gh_drift)
        except Exception:
            drift["github_documents_missing_from_semantic"] = None

        try:
            pending_rows = conn.execute(
                """
                SELECT updated_at FROM semantic_documents
                WHERE embedded_hash IS NULL OR embedded_hash != content_hash
                """
            ).fetchall()
            pending_total = len(pending_rows)
            now = datetime.now(timezone.utc)
            oldest_minutes: float | None = None
            stuck_count = 0
            for row in pending_rows:
                age_minutes = _minutes_since(row["updated_at"], now)
                if age_minutes is None:
                    continue
                if oldest_minutes is None or age_minutes > oldest_minutes:
                    oldest_minutes = age_minutes
                if age_minutes > _PENDING_EMBED_STUCK_MINUTES:
                    stuck_count += 1

            drift["semantic_documents_pending_embed"] = pending_total
            # GH-166: embed_chunks() runs synchronously right after ingest_vault()
            # within the same refresh job (see _refresh_vault below), so a
            # pending-embed row should clear within that one run — well under
            # the ~60-minute vault-sync cadence. A row still pending past
            # _PENDING_EMBED_STUCK_MINUTES is not an in-flight run's normal
            # tail; it is evidence the embed step stalled or failed on that row.
            drift["semantic_documents_pending_embed_stuck"] = stuck_count
            drift["semantic_documents_pending_embed_oldest_minutes"] = (
                round(oldest_minutes, 1) if oldest_minutes is not None else None
            )
            if stuck_count:
                drift["semantic_documents_pending_embed_reason"] = (
                    f"{stuck_count} of {pending_total} pending-embed row(s) unembedded "
                    f"for over {_PENDING_EMBED_STUCK_MINUTES}m (oldest "
                    f"{round(oldest_minutes, 1) if oldest_minutes is not None else '?'}m) "
                    "— likely a stuck/failed embed run, not just an in-flight tail"
                )
        except Exception:
            drift["semantic_documents_pending_embed"] = None
            drift["semantic_documents_pending_embed_stuck"] = None
            drift["semantic_documents_pending_embed_oldest_minutes"] = None

        # GH-169 Phase 3: commit-corpus completeness, anchored on the remote.
        # Cheap (local git + one ls-remote per repo, no REST API) so it can run
        # on every status call. Reported as three separate quantities that are
        # never summed — a phantom must not cancel a real gap.
        try:
            from rebalance.ingest.github_coverage import check_coverage, coverage_health

            repos = _resolve_repos_for_refresh(database_path, None)
            report = check_coverage(database_path, repos)
            drift["commit_coverage"] = {
                "checked_at": report.checked_at,
                "repos_checked": len(report.repos),
                "collection_gap": sum(r.collection_gap for r in report.repos),
                "projection_gap": sum(r.projection_gap for r in report.repos),
                "orphan_count": sum(r.orphan_count for r in report.repos),
                "incomplete": sum(r.incomplete for r in report.repos),
                "uncoverable": [
                    r.repo for r in report.repos if r.state == "uncoverable"
                ],
                "stale": [r.repo for r in report.repos if r.state == "stale"],
                "health": coverage_health(report),
            }
        except Exception as exc:  # never let a coverage probe break status
            drift["commit_coverage"] = {"error": str(exc)}

        payload["freshness"] = {**drift, "signal_health": _derive_signal_health(payload["sources"])}

    return payload


def _refresh_vault(
    database_path: Path,
    vault_path: Path,
    *,
    dry_run: bool,
) -> dict[str, Any]:
    plan = {
        "steps": [
            f"ingest_vault(vault={vault_path})",
            "embed_chunks()",
        ]
    }
    if dry_run:
        return {"scope": "vault", "dry_run": True, **plan}

    from rebalance.ingest.note_ingester import ingest_vault
    from rebalance.ingest.embedder import embed_chunks

    ingest_result = ingest_vault(
        vault_path=vault_path,
        database_path=database_path,
        exclude_patterns=[".obsidian/*", ".trash/*", "node_modules/*", ".git/*", ".venv/*", "*/.venv/*"],
        dry_run=False,
    )
    embed_result = embed_chunks(database_path=database_path)

    return {
        "scope": "vault",
        "dry_run": False,
        "ingest": {
            "total_files": ingest_result.total_files,
            "new_files": ingest_result.new_files,
            "updated_files": ingest_result.updated_files,
            "touched_files": ingest_result.touched_files,
            "deleted_files": ingest_result.deleted_files,
            "total_chunks": ingest_result.total_chunks,
            "elapsed_seconds": ingest_result.elapsed_seconds,
        },
        "embed_chunks": {
            "total_chunks": embed_result.total_chunks,
            "embedded": embed_result.embedded_chunks,
            "skipped_unchanged": embed_result.skipped_unchanged,
            "elapsed_seconds": embed_result.elapsed_seconds,
        },
    }


def _project_repos(database_path: Path) -> list[str]:
    """Repos drawn from the active project registry (operator-curated)."""
    repos: list[str] = []
    try:
        for project in get_projects(database_path, status="active"):
            for repo in project.get("repos") or []:
                r = repo.strip()
                if r and r not in repos:
                    repos.append(r)
    except Exception:
        pass
    return repos


def _activity_repos(database_path: Path, *, since_days: int = 14) -> list[str]:
    """Repos with recent activity according to ``github_activity``.

    These are repos the user has *actually worked in* on GitHub in the last
    *since_days*, regardless of whether they appear in the project registry.
    Passive events such as starring/watching a repo may create GitHub Events
    API entries, but they must not auto-monitor a repo.
    """
    from rebalance.ingest.github_watch import WATCHED_LOGIN

    repos: list[str] = []
    try:
        with db_connection(database_path) as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT repo_full_name
                FROM github_activity
                WHERE scan_date >= date('now', ?)
                  AND login != ?
                  AND (
                    commits + pushes + prs_opened + prs_merged
                    + issues_opened + issue_comments + reviews
                  ) > 0
                ORDER BY repo_full_name
                """,
                (f"-{int(since_days)} days", WATCHED_LOGIN),
            ).fetchall()
            for r in rows:
                repo = (r["repo_full_name"] or "").strip()
                if repo and repo not in repos:
                    repos.append(repo)
    except Exception:
        pass
    return repos


def _pushed_repos(database_path: Path, *, since_days: int = 14) -> list[str]:
    """Repos discovered via /user/repos?sort=pushed with a recent pushed_at.

    Read from the github_pushed_repos table populated by sync_pushed_repos().
    Catches activity that the events feed misses — pushes by collaborators
    on private org repos, pushes dropped by the events API's 300-event
    pagination cap, eventual-consistency gaps, and non-default-branch /
    force-push edge cases. The events feed and this signal are
    complementary; the union goes into the watched set.
    """
    from datetime import datetime, timedelta, timezone

    repos: list[str] = []
    try:
        cutoff = (
            datetime.now(timezone.utc) - timedelta(days=int(since_days))
        ).isoformat()
        with db_connection(database_path) as conn:
            rows = conn.execute(
                """
                SELECT repo_full_name FROM github_pushed_repos
                WHERE pushed_at >= ?
                  AND archived = 0 AND disabled = 0
                ORDER BY pushed_at DESC
                """,
                (cutoff,),
            ).fetchall()
            for r in rows:
                repo = (r["repo_full_name"] or "").strip()
                if repo and repo not in repos:
                    repos.append(repo)
    except Exception:
        pass
    return repos


def _external_repos(database_path: Path) -> list[str]:
    """External/watched repos drawn from the project registry (external: true).

    Always-on (not windowed), like ``_project_repos`` — a watched external repo
    should be synced every refresh regardless of recent activity, since the point
    is to catch other people's activity the operator's events feed never sees.
    """
    try:
        from rebalance.ingest.registry import get_external_repos

        return get_external_repos(database_path)
    except Exception:  # noqa: BLE001
        return []


def get_watched_repos(
    database_path: Path,
    *,
    since_days: int = 14,
) -> dict[str, list[str]]:
    """Return the canonical view of which repos are monitored.

    The merged ``watched`` list = (project_repos ∪ activity_repos ∪
    pushed_repos ∪ external_repos) − ignored. Callers (``refresh_index``,
    ``list_watched_repos`` MCP tool, the ``raw`` diagnostic) consume the
    same source of truth so the user can never wonder "what's actually
    being synced?". ``external_repos`` are third-party repos monitored for
    everyone's activity (see ``rebalance.ingest.github_watch``).
    """
    from rebalance.ingest.config import get_github_ignored_repos

    project = _project_repos(database_path)
    activity = _activity_repos(database_path, since_days=since_days)
    pushed = _pushed_repos(database_path, since_days=since_days)
    external = _external_repos(database_path)
    ignored = sorted(get_github_ignored_repos())
    # Ignored entries are stored lowercased (CLI normalizes on add);
    # watched-set sources keep GitHub's original casing. Compare on lowercase
    # so e.g. an "xpressbase/athenacomply" entry blocks "xpressbase/athenaComply".
    ignored_lower = {r.lower() for r in ignored}

    project_set = set(project)
    activity_set = set(activity)
    pushed_set = set(pushed)

    watched: list[str] = []
    for repo in project + external + activity + pushed:
        if repo.lower() in ignored_lower:
            continue
        if repo not in watched:
            watched.append(repo)

    auto_discovered = sorted(
        repo for repo in (activity_set | pushed_set) - project_set
        if repo.lower() not in ignored_lower
    )

    return {
        "watched": watched,
        "project_repos": project,
        "activity_repos": activity,
        "pushed_repos": pushed,
        "external_repos": external,
        "auto_discovered": auto_discovered,
        "ignored": ignored,
        "since_days": since_days,
    }


def _resolve_repos_for_refresh(database_path: Path, repos: list[str]) -> list[str]:
    if repos:
        return [r.strip() for r in repos if r.strip()]
    return get_watched_repos(database_path)["watched"]


def _refresh_github(
    database_path: Path,
    *,
    token: str,
    since_days: int,
    repos: list[str],
    dry_run: bool,
    backfill_since: str | None = None,
) -> dict[str, Any]:
    initial_target_repos = _resolve_repos_for_refresh(database_path, repos)
    external_count = len(
        [r for r in initial_target_repos if r.lower() in {e.lower() for e in _external_repos(database_path)}]
    )
    plan_steps = [
        "sync_pushed_repos()",
        f"github_scan(days={since_days})",
        "capture_direct_commits(events, watched_repos, cap=5/20)",
        "backfill_repos(local git walk, 0 API calls)",
        f"sync_github_repo() x ~{len(initial_target_repos)} repos (after auto-discovery)",
        f"reconcile_watched_repo() x {external_count} external repos (rollup or purge)",
        "embed_github_documents()",
    ]
    if dry_run:
        return {
            "scope": "github",
            "dry_run": True,
            "target_repos": initial_target_repos,
            "steps": plan_steps,
        }

    from rebalance.ingest.github_scan import (
        filter_ignored_repo_activity,
        scan_github,
        sync_pushed_repos,
        upsert_github_activity,
    )
    from rebalance.ingest.config import get_github_ignored_repos
    from rebalance.ingest.github_knowledge import sync_github_repo
    from rebalance.ingest.github_direct_commits import (
        capture_direct_commits,
        sync_direct_commit_documents,
    )
    from rebalance.ingest.github_commit_backfill import backfill_repos

    # Auto-discovery: fetch /user/repos?sort=pushed and upsert into
    # github_pushed_repos BEFORE resolving target repos, so newly-pushed
    # repos enter the watched set on this refresh rather than the next one.
    pushed_result = sync_pushed_repos(database_path, token=token)
    target_repos = _resolve_repos_for_refresh(database_path, repos)

    scan_result = scan_github(token=token, days=since_days)
    skipped = filter_ignored_repo_activity(scan_result, get_github_ignored_repos())
    upsert_github_activity(database_path, scan_result)
    direct_commits = capture_direct_commits(
        database_path,
        token=token,
        events=scan_result.events,
        watched_repos=target_repos,
    )
    # GH-169: the Events API can only see ~300 events / ~90 days of one actor's
    # feed, so it is an accelerator, not a completeness guarantee. The local-git
    # walk is the correctness backstop and runs after it — the ratchet in
    # upsert_direct_commit() means neither path can undo the other's work.
    # Zero API calls, so it adds no rate-limit pressure to the refresh.
    backfill_results = backfill_repos(database_path, target_repos, since=backfill_since)

    repo_results: list[dict[str, Any]] = []
    for repo in target_repos:
        try:
            r = sync_github_repo(
                database_path=database_path,
                repo_full_name=repo,
                token=token,
                since_days=since_days,
            )
            repo_results.append({
                "repo": repo,
                "branches": r.branches_synced,
                "issues": r.issues_synced,
                "prs": r.prs_synced,
                "comments": r.comments_synced,
                "commits": r.commits_synced,
                "checks": r.checks_synced,
                "docs_built": r.docs_built,
                "elapsed_seconds": r.elapsed_seconds,
            })
        except Exception as e:
            repo_results.append({"repo": repo, "error": str(e)})

    # External/watched repos: after their artifacts are synced above, reconcile a
    # whole-repo github_activity rollup so everyone's activity surfaces in the
    # org-activity dashboards/reports. Idempotent + bidirectional — a watched repo
    # that's become active local/cloud work has its sentinel rollup purged instead
    # (see github_watch.reconcile_watched_repo) so it never double-counts.
    from rebalance.ingest.github_watch import reconcile_watched_repo

    external_set = {r.lower() for r in _external_repos(database_path)}
    watched_activity: list[dict[str, Any]] = []
    for repo in target_repos:
        if repo.lower() not in external_set:
            continue
        try:
            watched_activity.append(
                reconcile_watched_repo(
                    database_path, repo, token, since_days=since_days
                )
            )
        except Exception as e:  # noqa: BLE001 — one repo must not abort the run
            watched_activity.append({"repo": repo, "error": str(e)})

    direct_documents = sync_direct_commit_documents(database_path)
    # The GitHub raw source emits github_documents; semantic_index remains the
    # sole writer of semantic_documents. Re-project each refreshed repo so a
    # direct commit is queryable in the same run.
    from rebalance.ingest.db import db_connection, ensure_github_schema
    from rebalance.ingest.semantic_index import sync_github_documents

    direct_semantic: dict[str, dict[str, int]] = {}
    with db_connection(database_path, ensure_github_schema) as conn:
        for repo in target_repos:
            direct_semantic[repo] = sync_github_documents(conn, repo_full_name=repo)
        conn.commit()

    from rebalance.ingest.github_knowledge import embed_github_documents

    gh_embed = embed_github_documents(database_path=database_path)

    # Coverage guard: snapshot the resolved watched set and alarm on a silent
    # reduction. Runs LAST, only on a clean sync (an earlier raise never reaches
    # here), so a truncated mid-failure set can't record a false reduction. Never
    # let the guard break a sync — observability must not reduce reliability.
    try:
        from rebalance.ingest.watchlist_guard import snapshot_and_detect

        watchlist_guard = snapshot_and_detect(database_path)
    except Exception as e:  # noqa: BLE001
        watchlist_guard = {"error": str(e)}

    # GH-124: commit-threshold auto-promotion. Immediately after the coverage
    # guard (same "clean sync only, never break a sync" posture) so a repo that
    # just crossed the operator-commit threshold graduates into project_registry
    # on this same refresh rather than waiting for a future one.
    try:
        from rebalance.ingest.project_inference import sync_commit_threshold_promotions

        auto_promote_summary = sync_commit_threshold_promotions(database_path)
        auto_promote_result: dict[str, Any] = {
            "enabled": auto_promote_summary.enabled,
            "threshold": auto_promote_summary.threshold,
            "candidates_evaluated": auto_promote_summary.candidates_evaluated,
            "promoted_count": auto_promote_summary.promoted_count,
            "promoted_repos": [
                row["custom_fields"]["inference"]["repo_full_name"]
                for row in auto_promote_summary.promoted
            ],
        }
    except Exception as e:  # noqa: BLE001
        auto_promote_result = {"error": str(e)}

    return {
        "scope": "github",
        "dry_run": False,
        "watchlist_guard": watchlist_guard,
        "auto_promote": auto_promote_result,
        "pushed_repos_sync": {
            "fetched": pushed_result.fetched,
            "inserted": pushed_result.inserted,
            "updated": pushed_result.updated,
            "unchanged": pushed_result.unchanged,
            "skipped_archived": pushed_result.skipped_archived,
            "error": pushed_result.error,
        },
        "github_scan": {
            "login": scan_result.login,
            "events": scan_result.total_events,
            "repos": len(scan_result.repo_activity),
            "skipped_ignored": len(skipped),
        },
        "direct_commit_capture": {
            **direct_commits.as_dict(),
            "documents_built": direct_documents,
            "semantic_projection": direct_semantic,
        },
        "commit_backfill": {
            "repos": len(backfill_results),
            "inserted": sum(r.commits_inserted for r in backfill_results),
            "updated": sum(r.commits_updated for r in backfill_results),
            "merge_commits": sum(r.merge_commits for r in backfill_results),
            "uncoverable": [
                {"repo": r.repo, "reason": r.reason}
                for r in backfill_results if r.state == "uncoverable"
            ],
            "warnings": [
                {"repo": r.repo, "warning": w}
                for r in backfill_results for w in r.warnings
            ],
        },
        "artifact_sync": repo_results,
        "watched_activity": watched_activity,
        "github_embed": {
            "total": gh_embed.total_docs,
            "embedded": gh_embed.embedded_docs,
            "skipped_unchanged": gh_embed.skipped_unchanged,
            "elapsed_seconds": gh_embed.elapsed_seconds,
        },
    }


def _refresh_calendar(database_path: Path, *, since_days: int, dry_run: bool) -> dict[str, Any]:
    from rebalance.ingest.calendar import sync_calendar
    from rebalance.ingest.calendar_config import CalendarConfig, OPERATOR_CALENDAR_ID

    config = CalendarConfig.load()

    if dry_run:
        steps = [f"sync_calendar(calendar_id={OPERATOR_CALENDAR_ID!r}, days_back={since_days}) [operator]"]
        for tc in config.team_calendars:
            steps.append(
                f"sync_calendar(calendar_id={tc.calendar_id!r},"
                f" person={tc.person!r}, days_back={since_days})"
            )
        return {"scope": "calendar", "dry_run": True, "steps": steps}

    # Operator's own calendar: always stored under OPERATOR_CALENDAR_ID (canonical)
    # so that the calendar_id filters everywhere cover the operator's data.
    # NOTE (0.40.1, F1): unified from a hardcoded 'primary' literal to the constant
    # (single source of truth). REVERT PATH: inline "primary" here and at the read
    # sites (sync_snapshot.py, pulse.py, querier.py).
    logger.info("calendar sync: operator calendar_id=%s days_back=%d", OPERATOR_CALENDAR_ID, since_days)
    result = sync_calendar(
        database_path=database_path,
        calendar_id=OPERATOR_CALENDAR_ID,
        person=None,  # operator rows: person IS NULL by convention
        days_back=since_days,
        days_forward=7,
    )
    logger.info(
        "calendar sync done: operator fetched=%d stored=%d",
        result.events_fetched, result.events_stored,
    )

    team_results: list[dict[str, Any]] = []
    for tc in config.team_calendars:
        logger.info(
            "calendar sync: person=%s calendar_id=%s days_back=%d",
            tc.person, tc.calendar_id, since_days,
        )
        try:
            tr = sync_calendar(
                database_path=database_path,
                calendar_id=tc.calendar_id,
                person=tc.person,
                days_back=since_days,
                days_forward=7,
            )
        except Exception as e:  # noqa: BLE001 — one teammate calendar must not abort the run
            # A revoked share / 404 / transient 5xx on one teammate calendar
            # (the most failure-prone input — third-party shares change outside
            # the operator's control) must not discard the operator's own
            # already-committed sync result or suppress the dashboard note.
            # Mirror _refresh_github's per-repo isolation.
            logger.warning(
                "calendar sync failed: person=%s calendar_id=%s error=%s",
                tc.person, tc.calendar_id, e,
            )
            team_results.append({
                "person": tc.person,
                "calendar_id": tc.calendar_id,
                "error": str(e),
            })
            continue
        logger.info(
            "calendar sync done: person=%s fetched=%d stored=%d",
            tc.person, tr.events_fetched, tr.events_stored,
        )
        team_results.append({
            "person": tc.person,
            "calendar_id": tc.calendar_id,
            "events_fetched": tr.events_fetched,
            "events_stored": tr.events_stored,
        })

    return {
        "scope": "calendar",
        "dry_run": False,
        "calendar_id": OPERATOR_CALENDAR_ID,
        "events_fetched": result.events_fetched,
        "events_stored": result.events_stored,
        "window_start": result.window_start,
        "window_end": result.window_end,
        "elapsed_seconds": result.elapsed_seconds,
        "team_calendars": team_results,
    }


def _refresh_sleuth(database_path: Path, *, dry_run: bool) -> dict[str, Any]:
    if dry_run:
        return {"scope": "sleuth", "dry_run": True, "steps": ["sync_sleuth_reminders()"]}

    from rebalance.ingest.sleuth_reminders import sync_sleuth

    # Single source-owned path (CLI / MCP / collector all call sync_sleuth). For a
    # file source it refreshes the export clone itself (best-effort, non-destructive)
    # and reports it as `source_refresh`. No more ingest->cli back-import.
    result = sync_sleuth(database_path, active_only=False)
    return {"scope": "sleuth", "dry_run": False, **result.as_dict()}


def _refresh_apple_reminders(database_path: Path, *, dry_run: bool) -> dict[str, Any]:
    if dry_run:
        return {
            "scope": "apple_reminders",
            "dry_run": True,
            "steps": ["sync_apple_reminders() [read-only snapshot of local store]"],
        }

    # Local read-only macOS source — requires Full Disk Access for the host
    # process. Surface the typed access/schema errors as a structured result
    # rather than crashing the whole refresh run.
    from rebalance.ingest.apple_reminders import AppleRemindersError, sync_apple_reminders

    try:
        result = sync_apple_reminders(database_path)
    except AppleRemindersError as exc:
        return {"scope": "apple_reminders", "dry_run": False, "error": str(exc)}
    return {"scope": "apple_reminders", "dry_run": False, **result.as_dict()}


def _refresh_code(database_path: Path, *, dry_run: bool) -> dict[str, Any]:
    """Code projection into semantic_documents is owned by the semantic stage (Phase 3).

    Running scope=['code'] alone is a no-op. The default recipe and
    scope=['semantic'] both include code via _refresh_semantic_only.
    """
    if dry_run:
        return {
            "scope": "code",
            "dry_run": True,
            "steps": ["(code projection deferred to semantic stage)"],
        }
    return {
        "scope": "code",
        "dry_run": False,
        "note": "code projection runs in the semantic stage; use scope=['semantic'] to index code",
    }


def _refresh_email(database_path: Path, *, dry_run: bool) -> dict[str, Any]:
    from rebalance.ingest.config import get_gmail_ingest_method

    if get_gmail_ingest_method() == "mcp":
        # MCP mode: email_messages is populated by an agent via the Gmail MCP
        # connector. A scheduled (launchd) job cannot reach an MCP connector,
        # so this step is a deliberate no-op — reported honestly, neither as a
        # success nor as an error.
        return {
            "scope": "email",
            "dry_run": dry_run,
            "method": "mcp",
            "skipped": True,
            "note": (
                "Gmail is in MCP mode — email_messages is ingested by an agent "
                "via the Gmail MCP connector, not by this job."
            ),
        }

    if dry_run:
        return {
            "scope": "email",
            "dry_run": True,
            "steps": ["sync_gmail()"],
        }

    from rebalance.ingest.gmail import GmailAuthError, sync_gmail

    try:
        sync_result = sync_gmail(database_path=database_path)
    except GmailAuthError as exc:
        return {"scope": "email", "dry_run": False, "error": str(exc)}

    return {
        "scope": "email",
        "dry_run": False,
        "messages_listed": sync_result.messages_listed,
        "messages_stored": sync_result.messages_stored,
        "messages_inserted": sync_result.messages_inserted,
        "messages_updated": sync_result.messages_updated,
        "query_filter": sync_result.query_filter,
        "elapsed_seconds": sync_result.elapsed_seconds,
    }


def _refresh_figma(database_path: Path, *, dry_run: bool) -> dict[str, Any]:
    """Refresh Figma comments (source_type='figma') — the first SourceModule.

    Modeled on :func:`_refresh_email`: sync upstream, then run the unified
    semantic backfill (via the registry-driven provider path) and embed. The
    token is read from keyring/rbos.config; both a missing token and a missing
    file-key allow-list surface as honest structured envelopes, never as silent
    success.
    """
    file_keys = get_figma_file_keys()
    if dry_run:
        return {
            "scope": "figma",
            "dry_run": True,
            "file_keys": file_keys,
            "steps": [
                f"sync_figma_comments(files={len(file_keys)})",
            ],
        }

    token = (get_figma_token() or "").strip()
    if not token:
        return {
            "scope": "figma",
            "dry_run": False,
            "error": (
                "Figma token not configured. Store a Figma personal access "
                "token in the `figma_token` secret (keyring + secret store)."
            ),
        }
    if not file_keys:
        return {
            "scope": "figma",
            "dry_run": False,
            "skipped": True,
            "reason": "No Figma file keys configured. Set figma_file_keys in temp/rbos.config.",
        }

    from rebalance.ingest.figma import sync_figma_comments

    sync_result = sync_figma_comments(
        database_path=database_path,
        file_keys=file_keys,
        token=token,
    )

    return {
        "scope": "figma",
        "dry_run": False,
        "files_requested": sync_result.files_requested,
        "files_synced": sync_result.files_synced,
        "comments_fetched": sync_result.comments_fetched,
        "comments_inserted": sync_result.comments_inserted,
        "comments_updated": sync_result.comments_updated,
        "comments_unchanged": sync_result.comments_unchanged,
        "errors": sync_result.errors,
        "elapsed_seconds": sync_result.elapsed_seconds,
    }


def _all_semantic_sources() -> list[str]:
    """All sources that project into the unified semantic index.

    Derived from the registry so new sources with a ``semantic_docs`` provider
    are automatically included without a second manual edit. The legacy
    if-ladder sources (vault / github / email / code) project via the
    if-ladder in ``backfill_semantic_documents`` without needing a
    ``semantic_docs`` provider; registry-driven sources (figma, …) use the
    provider path. Add a new source to either the ladder or the registry —
    it will appear here automatically.
    """
    _LADDER = ["vault", "github", "email", "code"]
    registry_extra = [n for n in _semantic_source_names() if n not in _LADDER]
    return _LADDER + registry_extra


def _refresh_semantic_only(database_path: Path, *, dry_run: bool) -> dict[str, Any]:
    sources = _all_semantic_sources()
    if dry_run:
        return {
            "scope": "semantic",
            "dry_run": True,
            "steps": [
                f"semantic_backfill(sources={sources}, use_registry_providers=True)",
                f"semantic_embed(sources={sources})",
            ],
        }
    from rebalance.ingest.semantic_index import (
        backfill_semantic_documents,
        embed_pending,
    )
    backfill = backfill_semantic_documents(
        database_path,
        source_types=sources,
        use_registry_providers=True,
    )
    sem_embed = embed_pending(database_path, source_types=sources)
    return {
        "scope": "semantic",
        "dry_run": False,
        "sources": sources,
        "semantic_backfill": {
            "total": backfill.total_documents,
            "inserted": backfill.inserted_count,
            "updated": backfill.updated_count,
            "deleted": backfill.deleted_count,
            "elapsed_seconds": backfill.elapsed_seconds,
        },
        "semantic_embed": {
            "total": sem_embed.total_docs,
            "embedded": sem_embed.embedded_docs,
            "skipped_unchanged": sem_embed.skipped_unchanged,
            "elapsed_seconds": sem_embed.elapsed_seconds,
        },
    }


def _refresh_dashboard_note(
    database_path: Path,
    *,
    vault_path: Path,
    since_days: int,
    dry_run: bool,
    note_path: str = "Dashboards/rebalanceOS Dashboard.md",
) -> dict[str, Any]:
    output_path = (vault_path / note_path).resolve()
    plan = {
        "scope": "dashboard",
        "dry_run": dry_run,
        "output_path": str(output_path),
        "steps": [
            "build_dashboard_note_content()",
            "write_dashboard_note()",
            "ingest_vault()",
            "embed_chunks()",
            "semantic_backfill(source=['vault'])",
            "semantic_embed(source=['vault'])",
        ],
    }
    if dry_run:
        return plan

    from rebalance.ingest.calendar_config import CalendarConfig
    from rebalance.ingest.note_builder import build_dashboard_note_content, write_dashboard_note
    from rebalance.ingest.embedder import embed_chunks
    from rebalance.ingest.note_ingester import ingest_vault

    markdown = build_dashboard_note_content(
        database_path,
        target_date=date.today(),
        since_days=since_days,
        config=CalendarConfig.load(),
    )
    note_file = write_dashboard_note(output_path, markdown)
    ingest_result = ingest_vault(vault_path=vault_path, database_path=database_path)
    embed_result = embed_chunks(database_path=database_path)

    return {
        "scope": "dashboard",
        "dry_run": False,
        "output_path": str(note_file),
        "ingest": {
            "total_files": ingest_result.total_files,
            "new_files": ingest_result.new_files,
            "updated_files": ingest_result.updated_files,
            "touched_files": ingest_result.touched_files,
            "deleted_files": ingest_result.deleted_files,
            "total_chunks": ingest_result.total_chunks,
            "elapsed_seconds": ingest_result.elapsed_seconds,
        },
        "embed_chunks": {
            "total_chunks": embed_result.total_chunks,
            "embedded": embed_result.embedded_chunks,
            "skipped_unchanged": embed_result.skipped_unchanged,
            "elapsed_seconds": embed_result.elapsed_seconds,
        },
    }


def refresh_index(
    database_path: Path,
    *,
    scope: Iterable[str] | str | None = None,
    vault_path: str = "",
    since_days: int = 30,
    repos: list[str] | None = None,
    dry_run: bool = False,
    update_dashboard_note: bool = True,
    precompute_next_actions: bool = True,
) -> dict[str, Any]:
    """Run the configured ingest pipelines for ``scope`` and return a summary.

    ``scope`` accepts any combination of ``vault``, ``github``, ``calendar``,
    ``sleuth``, ``email``, ``semantic``, or ``all``. ``dry_run=True`` returns
    the planned steps without touching the DB or network.

    ``update_dashboard_note`` triggers an optional Obsidian write-back: a
    markdown dashboard note is written to the vault after a full refresh.
    It is a documented side-output, not a core contract — callers that run
    without a vault (CI, portable installs) set this to ``False``.

    ``precompute_next_actions`` (P2 v0.5) runs the live Gemini synthesis of the
    "what should we work on next" ranked list AFTER the data collectors have
    refreshed, and persists it to the local ``ranked_next_actions`` cache the
    dashboard route + static pulse panel read. This is the NETWORK-ALLOWED side
    of the precompute->SQLite decision: it is gated to the full/network refresh
    (``full_refresh_requested``) and skipped on dry runs and read-only/named-scope
    runs. A synthesis/network failure NEVER breaks refresh_index — it is logged
    and the refresh continues.
    """
    db_path = Path(database_path).expanduser().resolve()
    requested_scopes = _normalize_scope(scope)
    full_refresh_requested = scope is None or "all" in (scope or [])
    started = time.monotonic()
    results: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    resolved_vault: Path | None = None
    if "vault" in requested_scopes:
        candidate = (vault_path or "").strip() or get_vault_path() or ""
        if candidate:
            resolved_vault = Path(candidate).expanduser().resolve()
        if resolved_vault is None or not resolved_vault.exists():
            errors.append({
                "scope": "vault",
                "error": (
                    "vault path not configured or missing. Pass vault_path or run "
                    "`rebalance config set-vault-path`."
                ),
            })
            requested_scopes = [s for s in requested_scopes if s != "vault"]

    resolved_token = ""
    if "github" in requested_scopes:
        resolved_token = (get_github_token() or "").strip()
        if not resolved_token:
            errors.append({
                "scope": "github",
                "error": (
                    "GitHub token not configured. Use setup_github_token MCP tool "
                    "or `rebalance config set-github-token`."
                ),
            })
            requested_scopes = [s for s in requested_scopes if s != "github"]
        elif not dry_run:
            # If the stored PAT is deauthorized (401), fall back to the gh CLI
            # token and persist it so this and the launchd jobs recover. No-op
            # when the PAT is valid or gh is unavailable (e.g. under launchd).
            from rebalance.ingest.github_scan import resolve_working_token
            resolved_token = resolve_working_token(resolved_token)

    repos_list = list(repos or [])

    # Figma PAT (keyring → rbos.config). Resolved so a missing token surfaces as
    # the structured "missing required options" envelope below rather than an
    # exception inside the collector. Only resolved when figma is in scope.
    resolved_figma_token = ""
    if "figma" in requested_scopes:
        resolved_figma_token = (get_figma_token() or "").strip()

    # Per-collector kwargs bundle. Each collector ignores keys it doesn't need.
    collector_opts: dict[str, Any] = {
        "vault_path": resolved_vault,
        "token": resolved_token,
        "figma_token": resolved_figma_token,
        "since_days": since_days,
        "repos": repos_list,
        "dry_run": dry_run,
    }

    # Bring the database schema to the latest version before any collector
    # writes to it. Skipped on dry runs, which must not touch the DB.
    migrations_ok = True
    if not dry_run:
        try:
            with db_connection(db_path) as conn:
                run_migrations(conn)
        except Exception as e:  # noqa: BLE001 — error envelope mirrors collector contract
            errors.append({"scope": "migrations", "error": str(e)})
            migrations_ok = False

    for s in requested_scopes:
        # If schema migration failed the DB is in an unknown/incomplete shape;
        # running a collector would only produce confusing secondary errors
        # (e.g. writing a column the migration was meant to add) and waste API
        # calls. Record each scope as skipped behind the single migrations error
        # rather than letting collectors write to a half-migrated schema.
        if not migrations_ok:
            results.append({
                "scope": s,
                "dry_run": False,
                "skipped": True,
                "reason": "schema migration failed",
            })
            continue
        collector = COLLECTORS.get(s)
        if collector is None:
            errors.append({"scope": s, "error": f"no collector registered for scope {s!r}"})
            continue
        # Enforce declared preconditions.
        missing_reqs: list[str] = []
        if "vault_path" in collector.requires and not collector_opts.get("vault_path"):
            missing_reqs.append("vault_path")
        if "github_token" in collector.requires and not collector_opts.get("token"):
            missing_reqs.append("github_token")
        # Skip the figma_token precondition on dry runs so the planned-steps
        # preview (which needs no PAT) still renders; live runs require it.
        if (
            "figma_token" in collector.requires
            and not dry_run
            and not collector_opts.get("figma_token")
        ):
            missing_reqs.append("figma_token")
        if missing_reqs:
            errors.append({"scope": s, "error": f"missing required options: {missing_reqs}"})
            continue
        try:
            results.append(collector.refresh(db_path, **collector_opts))
        except Exception as e:  # noqa: BLE001 — error envelope mirrors legacy contract
            errors.append({"scope": s, "error": str(e)})

    # Precompute the P2 v0.5 "what should we work on next" ranked list now that
    # the collectors above have refreshed the signal. This is the NETWORK-ALLOWED
    # side of the precompute->SQLite decision (live Gemini synthesis), so it is
    # gated to the full/network refresh ONLY — never a dry run, a read-only/named
    # scope, or a half-migrated schema. run_migrations already ran at the
    # chokepoint above, so the ranked_next_actions table (migration 0006) exists
    # before persist. A synthesis/network failure NEVER breaks refresh_index.
    if (
        precompute_next_actions
        and full_refresh_requested
        and not dry_run
        and migrations_ok
    ):
        try:
            from rebalance.ingest import next_actions

            ranked = next_actions.rank_next_actions(
                db_path, blend_team=True, synthesize=True
            )
            next_actions.persist_ranked_next_actions(db_path, ranked)
            # Render the SAME ranked output to the fixed vault file so the vault
            # is the calm daily surface (P1-SIGNAL). Gated like the dashboard-note
            # write-back below (update_dashboard_note + a resolved vault), reusing
            # the already-resolved path. A vault-write failure is non-fatal — log
            # it and keep the (already persisted) precompute.
            vault_file = None
            if update_dashboard_note and resolved_vault is not None:
                try:
                    written = next_actions.write_next_actions_to_vault(
                        ranked, vault_path=resolved_vault
                    )
                    vault_file = str(written) if written else None
                except Exception as ve:  # noqa: BLE001 — vault write must never break refresh
                    logger.warning("next_actions vault write failed: %s", ve)
            logger.info(
                "next_actions precompute: model_used=%s blended=%s count=%d vault=%s",
                ranked.model_used or "(none)", ranked.blended, len(ranked.ranked),
                vault_file or "(skipped)",
            )
            results.append({
                "scope": "next_actions",
                "dry_run": False,
                "model_used": ranked.model_used,
                "blended": ranked.blended,
                "count": len(ranked.ranked),
                "vault_file": vault_file,
            })
        except Exception as e:  # noqa: BLE001 — precompute must never break refresh
            logger.warning("next_actions precompute failed: %s", e)
            # Deliberately NOT appended to `errors`: a non-essential precompute
            # failure must not cascade into skipping the dashboard-note write-back
            # below (which gates on `errors`). Recorded as a non-fatal result note.
            results.append({
                "scope": "next_actions",
                "dry_run": False,
                "skipped": True,
                "error": str(e),
            })

    if update_dashboard_note and full_refresh_requested and resolved_vault is not None:
        if errors and not dry_run:
            results.append({
                "scope": "dashboard",
                "dry_run": False,
                "skipped": True,
                "reason": "upstream refresh errors",
            })
        else:
            try:
                results.append(_refresh_dashboard_note(
                    db_path,
                    vault_path=resolved_vault,
                    since_days=since_days,
                    dry_run=dry_run,
                ))
            except Exception as e:
                errors.append({"scope": "dashboard", "error": str(e)})

    return {
        "database_path": str(db_path),
        "requested_scopes": requested_scopes,
        "dry_run": dry_run,
        "results": results,
        "errors": errors,
        "elapsed_seconds": round(time.monotonic() - started, 2),
    }


# ---------------------------------------------------------------------------
# Built-in collectors
# ---------------------------------------------------------------------------
#
# Adapter functions normalize each per-source refresh function to the Collector
# signature (db_path, **opts). Unknown keys are ignored; required keys are
# extracted by name. The legacy ``_refresh_*`` private functions remain the
# single source of truth for the ingest pipelines — these adapters are 3-line
# shims.

def _dry_run_adapter(refresh_fn: Callable[..., dict[str, Any]]) -> Callable[..., dict[str, Any]]:
    """Adapter for a refresh fn whose only option is ``dry_run``.

    Most stage/source refreshes take no per-source options beyond ``dry_run``;
    this replaces a separate near-identical two-line adapter for each of them.
    Sources with bespoke option mapping (vault, github, calendar) keep their own.
    """
    def adapter(db_path: Path, **opts: Any) -> dict[str, Any]:
        return refresh_fn(db_path, dry_run=opts["dry_run"])
    return adapter


def _vault_adapter(db_path: Path, **opts: Any) -> dict[str, Any]:
    vault_path = opts.get("vault_path")
    assert vault_path is not None, "vault collector requires vault_path"
    # GH-131 (extended 2026-07-27): same transient "database is locked" collision the
    # github scope already retries through. On 2026-07-27 the hourly vault-sync failed
    # 3 of 15 runs on exactly this, in the `vault` and `semantic` scopes — the only two
    # write-heavy scopes that had NOT been given the retry.
    #
    # Safe to retry: ingest_vault deletes then re-inserts per file (CASCADE covers
    # chunks/keywords/links), so a rerun replaces rather than duplicates, and
    # embed_chunks only embeds rows with no existing embedding.
    return _retry_on_db_locked(lambda: _refresh_vault(
        db_path, vault_path, dry_run=opts["dry_run"]
    ))


def _retry_on_db_locked(
    fn: Callable[[], Any],
    *,
    attempts: int = 3,
    base_delay_seconds: float = 5.0,
    sleep_fn: Callable[[float], None] | None = None,
) -> Any:
    """Retry ``fn()`` on a SQLite "database is locked" error, with linear
    backoff (``base_delay_seconds``, 2x, 3x, ...), bounded to ``attempts``
    tries (GH-131). Any other exception, or a lock still present after the
    final attempt, propagates immediately — a persistent lock is never
    silently swallowed, it surfaces as a real scope error.
    """
    sleep = sleep_fn if sleep_fn is not None else time.sleep
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except sqlite3.OperationalError as exc:
            if "database is locked" not in str(exc).lower() or attempt == attempts:
                raise
            sleep(base_delay_seconds * attempt)


def _github_adapter(db_path: Path, **opts: Any) -> dict[str, Any]:
    # GH-131: db_connection() already sets a 30s busy_timeout, but the hourly
    # github-sync launchd job (fires :45 past the hour) can hold rebalance.db's
    # github-table write lock longer than that when it collides with
    # daily-sync's ~30min 06:30 window — busy_timeout alone then still raises
    # "database is locked". _refresh_github is idempotent (upserts), so
    # retrying the whole scope survives the transient collision instead of
    # failing the run and cascading into a skipped dashboard note.
    return _retry_on_db_locked(lambda: _refresh_github(
        db_path,
        token=opts["token"],
        since_days=opts["since_days"],
        repos=opts.get("repos") or [],
        dry_run=opts["dry_run"],
    ))


def _calendar_adapter(db_path: Path, **opts: Any) -> dict[str, Any]:
    return _refresh_calendar(db_path, since_days=opts["since_days"], dry_run=opts["dry_run"])


_sleuth_adapter = _dry_run_adapter(_refresh_sleuth)
_apple_reminders_adapter = _dry_run_adapter(_refresh_apple_reminders)
_email_adapter = _dry_run_adapter(_refresh_email)
_code_adapter = _dry_run_adapter(_refresh_code)
_figma_adapter = _dry_run_adapter(_refresh_figma)
def _semantic_adapter(db_path: Path, **opts: Any) -> dict[str, Any]:
    # GH-131 (extended 2026-07-27) — see _vault_adapter. Safe to retry: the semantic
    # embed is content-hash keyed, so a rerun re-skips unchanged rows rather than
    # re-embedding them (2026-07-27 run: 29,099 of 29,956 skipped unchanged).
    return _retry_on_db_locked(lambda: _refresh_semantic_only(
        db_path, dry_run=opts["dry_run"]
    ))


def _refresh_sync(database_path: Path, *, dry_run: bool) -> dict[str, Any]:
    """Export calendar + email snapshots to the sync subfolder in the pulse repo."""
    from rebalance.ingest.config import get_pulse_config, get_sync_subdir
    from rebalance.ingest.sync_snapshot import (
        commit_and_push_sync,
        export_calendar_snapshot,
        export_email_snapshot,
        get_device_id,
    )

    cfg = get_pulse_config()
    pulse_target = cfg.get("pulse_target_path", "")
    if not pulse_target:
        return {
            "scope": "sync",
            "dry_run": dry_run,
            "error": "pulse_target_path not configured — run: rebalance config set-pulse-config pulse_target_path=<path>",
        }

    target_repo = Path(pulse_target).expanduser().resolve()
    sync_subdir = get_sync_subdir()
    sync_dir = target_repo / sync_subdir
    device_id = get_device_id()

    if dry_run:
        return {
            "scope": "sync",
            "dry_run": True,
            "steps": [
                f"export_calendar_snapshot(window_days=90) → {sync_dir}/calendar/{device_id}.json",
                f"export_email_snapshot(limit=1000) → {sync_dir}/email/{device_id}.json",
                f"git add {sync_subdir}/ && git commit && git push → {target_repo}",
            ],
        }

    import time
    started = time.monotonic()
    cal_path = export_calendar_snapshot(database_path, sync_dir, device_id=device_id)
    email_path = export_email_snapshot(database_path, sync_dir, device_id=device_id)

    import json as _json
    generated_at = _json.loads(cal_path.read_text(encoding="utf-8"))["generated_at"]
    git_result = commit_and_push_sync(
        target_repo, sync_subdir, device_id=device_id, generated_at=generated_at
    )

    return {
        "scope": "sync",
        "dry_run": False,
        "device_id": device_id,
        "calendar_snapshot": str(cal_path.relative_to(target_repo)),
        "email_snapshot": str(email_path.relative_to(target_repo)),
        "git": git_result,
        "elapsed_seconds": round(time.monotonic() - started, 2),
    }


_sync_adapter = _dry_run_adapter(_refresh_sync)


def _refresh_ask_self(database_path: Path, *, dry_run: bool) -> dict[str, Any]:
    """Walk this device for ask_self-enabled repos and record their indexes.

    Discovery-only: reads each repo's ask_self harness + index metadata
    (read-only) and upserts one row per repo into ``ask_self_indexes``. Does not
    build or refresh any RAG index itself. Opt-in (``included_in_all=False``)
    because it walks the filesystem; run explicitly via
    ``refresh_index(scope=["ask_self"])``.
    """
    from rebalance.ingest.config import get_repo_scan_roots

    roots = get_repo_scan_roots()
    if dry_run:
        return {
            "scope": "ask_self",
            "dry_run": True,
            "scan_roots": roots,
            "steps": [
                f"scan_ask_self_repos(roots={roots})",
                "read each ask_self index repo_metadata (read-only)",
                "upsert ask_self_indexes (keyed by device_id, local_path)",
            ],
        }

    from rebalance.ingest.ask_self_scan import sync_ask_self_indexes

    result = sync_ask_self_indexes(database_path, roots=roots)
    return {"scope": "ask_self", "dry_run": False, **result.as_dict()}


_ask_self_adapter = _dry_run_adapter(_refresh_ask_self)


def _refresh_focus5(database_path: Path, *, dry_run: bool) -> dict[str, Any]:
    """Scan device-local git repos and rebuild the Focus 5 roster.

    Discovers active local repos (bounded zero-config walk), probes per-repo
    git signals, and persists both the full signal cache and the ranked top-5
    roster. Local-git-first: the GitHub corpus is enrichment only. Opt-in
    (``included_in_all=False``) because it walks the filesystem and shells git;
    run explicitly via ``refresh_index(scope=["focus5"])`` or lazily from the
    web view when the roster TTL has expired.
    """
    from rebalance.ingest.config import get_focus5_ranking_mode, get_focus5_scan_roots

    roots = get_focus5_scan_roots()
    mode = get_focus5_ranking_mode()
    if dry_run:
        return {
            "scope": "focus5",
            "dry_run": True,
            "scan_roots": roots,
            "ranking_mode": mode,
            "steps": [
                f"iter_git_repos(roots={roots})",
                "probe per-repo signals (read-only git status/log + .git stats)",
                "replace focus5_repo_signals for this device (off-roster cache)",
                f"rank via {mode!r} strategy and replace focus5_roster (top 5)",
            ],
        }

    from rebalance.ingest.focus5_scan import sync_focus5

    result = sync_focus5(database_path, roots=roots, mode=mode)
    return {"scope": "focus5", "dry_run": False, **result.as_dict()}


_focus5_adapter = _dry_run_adapter(_refresh_focus5)


def _refresh_claude_cloud(database_path: Path, *, dry_run: bool) -> dict[str, Any]:
    """Observation-phase refresh for the Claude Code Cloud signal (GH-128).

    DORMANT source: it does not persist a raw table yet — first-class promotion
    adds one (see PROJECT/1-INBOX/GH-128-CC-CLOUD-JOBS-INGEST.md). A live run
    fetches today's cloud sessions and returns their data-quality grade, so
    ``refresh_index(scope=["claude_cloud"])`` doubles as a health probe for the
    signal while it is being watched.
    """
    if dry_run:
        return {"scope": "claude_cloud", "dry_run": True,
                "note": "would fetch today's Claude Code Cloud sessions"}
    from rebalance.ingest.claude_cloud import grade, sessions_for_day

    g = grade(sessions_for_day())
    return {"scope": "claude_cloud", "dry_run": False, "sessions": g["n"],
            "grade": g["letter"], "overall": g["overall"], "counts": g.get("counts", {})}


_claude_cloud_adapter = _dry_run_adapter(_refresh_claude_cloud)


# Next-action candidate providers — the SECOND use of the registry seam
# (mirroring semantic_docs). Each source owns its candidate shape here, so
# next_actions._operator_candidates is a registry walk, not a dispatch chain.
# Imported at registration time (not module top): next_actions does not import
# index_ops at its top, so this one-directional import is cycle-free.
from rebalance.ingest.next_actions import (  # noqa: E402
    calendar_candidates,
    email_candidates,
    figma_candidates,
    github_candidates,
    sleuth_candidates,
    vault_candidates,
)

register_collector(Collector(
    "vault", _vault_adapter, requires=("vault_path",), candidates=vault_candidates,
))
register_collector(Collector(
    "github", _github_adapter, requires=("github_token",), candidates=github_candidates,
))
register_collector(Collector("calendar", _calendar_adapter, candidates=calendar_candidates))
register_collector(Collector("sleuth", _sleuth_adapter, candidates=sleuth_candidates))
# Apple Reminders — local macOS read-only source. Opt-in (included_in_all=False):
# it requires Full Disk Access for the host process and is macOS-only, so it must
# never be part of a default/launchd `all` run on machines that can't read it.
register_collector(Collector("apple_reminders", _apple_reminders_adapter, included_in_all=False))
register_collector(Collector("email", _email_adapter, candidates=email_candidates))
register_collector(Collector("code", _code_adapter, kind="derived_scan"))
register_collector(Collector("semantic", _semantic_adapter, kind="projection"))
register_collector(Collector("sync", _sync_adapter, kind="export"))
register_collector(Collector("focus5", _focus5_adapter, included_in_all=False, kind="derived_scan"))
register_collector(Collector("ask_self", _ask_self_adapter, included_in_all=False, kind="derived_scan"))

# Figma — the first registry-driven SourceModule. Imported here (not at module
# top) so figma.py — and its later, optional dependencies — only load when the
# registry is constructed; figma.py's own top imports stay limited to
# rebalance.ingest.db, so no mlx/embedder is pulled in. included_in_all=False
# keeps it opt-in (requires a PAT + an explicit file-key allow-list). The figma
# arm ships DORMANT — figma_candidates yields nothing until a figma_file_keys
# allow-list turns the collector on.
from rebalance.ingest.figma import figma_semantic_docs  # noqa: E402

register_collector(
    Collector(
        "figma",
        _figma_adapter,
        requires=("figma_token",),
        semantic_docs=figma_semantic_docs,
        candidates=figma_candidates,
        included_in_all=False,
    )
)

# Claude Code Cloud (web) sessions — GH-128. Opt-in derived scan; imported here (not
# at module top) so its stdlib-only fetch loads only when the registry is built. The
# arm ships DORMANT: claude_cloud_candidates yields nothing until the config flag
# `claude_cloud_signal_enabled` is set true — the signal is wired into the ranker's
# candidates= seam but is watched via the Obsidian daily-note grade before it is
# promoted to influence the live verdict.
from rebalance.ingest.claude_cloud import claude_cloud_candidates  # noqa: E402

register_collector(
    Collector(
        "claude_cloud",
        _claude_cloud_adapter,
        candidates=claude_cloud_candidates,
        included_in_all=False,
        kind="derived_scan",
    )
)
