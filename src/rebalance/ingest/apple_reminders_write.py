"""Apple Reminders write-back orchestrator (Phase 5.1).

This module is the product-facing **mutation** path for Apple Reminders. It is
deliberately separate from the read collector (`apple_reminders.py`) and from
`refresh_index()` — writing has its own contract, audit trail, confirmation flow,
and failure handling, per APPLE-REMINDERS-UNIFIED-PLAN Phase 5.1.

Runtime contract (proven in Phase 5.0):
    EventKit writes succeed ONLY from a signed, LaunchServices-launched macOS app
    bundle holding a Reminders TCC grant — never from this Python process (it runs
    under the agent/VS Code responsible tree, where TCC suppresses the grant). So
    this orchestrator does NOT call EventKit. It builds a typed JSON request,
    delegates the mutation to the out-of-process signed helper bundle (the single
    writer to Apple Reminders), records an audit trail, then reconciles the local
    `apple_reminders` table from Apple (the source of truth) via
    `sync_apple_reminders`.

Design decisions (cross-model consult, 2026-06-27):
    * IPC = on-demand `open` of the signed helper bundle per request.
    * Audit = a dedicated `apple_reminders_write_audit` SQLite table (immutable
      request/response blobs + per-op reminder_id for joins).
    * Write scope = restricted to the single configured ingest list — writing to a
      list the read path never ingests would break the post-apply reconcile
      invariant.
    * Idempotency keyed by `request_id`; helper-side write serialization;
      helper-identity verification on launch; explicit lifecycle states
      (accepted -> applied_in_eventkit -> reconciled_locally); atomic file IPC.

Testing seams: `apply_reminder_writes` accepts an `invoker` (helper call) and a
`reconcile_fn` (local re-sync) so the full orchestrator — scope, confirmation,
audit lifecycle, idempotency — runs headlessly without macOS/EventKit.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import sqlite3
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from rebalance.ingest.apple_reminders import AppleRemindersError
from rebalance.lib.time_ops import _now_iso

logger = logging.getLogger(__name__)

# Contract version embedded in every request/response so the helper and
# orchestrator can fail loud on a mismatch instead of silently mis-parsing.
WRITE_SCHEMA_VERSION = 1

# The signed helper bundle this orchestrator trusts. Identity is verified
# (bundle id + valid signature) before any response is trusted — confused-deputy
# guard. The build harness assembles this bundle under temp/ (gitignored).
HELPER_BUNDLE_ID = "com.rebalanceos.apple-reminders-helper"
_HELPER_BUNDLE_RELPATH = "temp/apple-reminders/build/AppleRemindersHelper.app"

# Ops that destroy or overwrite state — gated behind confirm_destructive on apply.
_DESTRUCTIVE_OPS = frozenset({"delete"})
_VALID_OPS = frozenset({"create", "update", "complete", "delete"})

# Lifecycle states recorded per request in the audit table.
STATE_ACCEPTED = "accepted"
STATE_APPLIED = "applied_in_eventkit"
STATE_RECONCILED = "reconciled_locally"
STATE_FAILED = "failed"
STATE_SKIPPED = "skipped"
_DONE_STATES = frozenset({STATE_APPLIED, STATE_RECONCILED})

# ponytail: the audit table + 3-state lifecycle, helper-side flock serialization,
# and codesign identity verification below are heavier than a single-user personal
# tool needs (they came from a cross-model consult's enterprise-hardening pass).
# They're built, tested, and cheap to keep, so left in — but don't grow them.
# If this ever gets trimmed: keep request_id idempotency (guards a real
# duplicate-create-on-timeout bug); the rest (audit 3-state, flock, codesign
# verify) can collapse to a 1-line log + plain create for one user on one Mac.


class AppleRemindersWriteError(AppleRemindersError):
    """Base for write-path failures (distinct from read/extract errors)."""


class AppleRemindersWriteScopeError(AppleRemindersWriteError):
    """An op targets a list outside the configured ingest scope."""


class AppleRemindersConfirmationError(AppleRemindersWriteError):
    """A destructive op was requested under apply without confirm_destructive."""


class AppleRemindersHelperError(AppleRemindersWriteError):
    """The signed helper failed to launch, verify, or respond in time."""


@dataclass
class WriteOp:
    """One requested mutation. ``create`` uses ``client_token`` for correlation
    (no id exists yet); the others address an existing reminder by ``reminder_id``
    (== EventKit calendarItemIdentifier == ZCKIDENTIFIER, a 1:1 mapping)."""

    op: str
    client_token: str | None = None
    reminder_id: str | None = None
    list_name: str | None = None
    fields: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"op": self.op}
        if self.client_token is not None:
            d["client_token"] = self.client_token
        if self.reminder_id is not None:
            d["reminder_id"] = self.reminder_id
        if self.list_name is not None:
            d["list_name"] = self.list_name
        if self.fields:
            d["fields"] = self.fields
        return d


@dataclass
class WriteOpResult:
    op: str
    status: str  # ok | skipped | error
    client_token: str | None = None
    reminder_id: str | None = None
    readback_ok: bool = False
    detail: str = ""

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "WriteOpResult":
        return cls(
            op=d.get("op", ""),
            status=d.get("status", "error"),
            client_token=d.get("client_token"),
            reminder_id=d.get("reminder_id"),
            readback_ok=bool(d.get("readback_ok", False)),
            detail=str(d.get("detail", "")),
        )


@dataclass
class WriteResult:
    request_id: str
    mode: str
    state: str
    host_runtime: str
    authorization_status: str
    results: list[WriteOpResult]
    started_at: str
    finished_at: str
    reconciled: bool = False

    @property
    def ok(self) -> bool:
        """True when no op errored (skips are allowed, e.g. plan / unconfirmed)."""
        return all(r.status != "error" for r in self.results)

    def as_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "mode": self.mode,
            "state": self.state,
            "host_runtime": self.host_runtime,
            "authorization_status": self.authorization_status,
            "reconciled": self.reconciled,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "results": [
                {
                    "op": r.op,
                    "status": r.status,
                    "client_token": r.client_token,
                    "reminder_id": r.reminder_id,
                    "readback_ok": r.readback_ok,
                    "detail": r.detail,
                }
                for r in self.results
            ],
        }


# Type of the helper-invocation seam: takes a request dict, returns a response
# dict (or raises AppleRemindersHelperError). The default impl `open`s the signed
# bundle; tests inject a fake.
Invoker = Callable[[dict[str, Any]], dict[str, Any]]


def _new_request_id() -> str:
    return uuid.uuid4().hex


def ensure_apple_reminders_write_schema(conn: sqlite3.Connection) -> None:
    """Create the write-audit table if absent. One row per (request, op_index):
    per-op ``reminder_id`` joins to ``apple_reminders``; the immutable
    ``request_json`` / ``response_json`` blobs give full forensic replay."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS apple_reminders_write_audit (
            request_id          TEXT NOT NULL,
            op_index            INTEGER NOT NULL,
            op                  TEXT NOT NULL,
            client_token        TEXT,
            reminder_id         TEXT,
            mode                TEXT NOT NULL,
            state               TEXT NOT NULL,
            op_status           TEXT,
            readback_ok         INTEGER,
            helper_identity     TEXT,
            request_json        TEXT NOT NULL,
            response_json       TEXT,
            detail              TEXT,
            created_at          TEXT NOT NULL,
            updated_at          TEXT NOT NULL,
            PRIMARY KEY (request_id, op_index)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_arw_audit_reminder "
        "ON apple_reminders_write_audit(reminder_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_arw_audit_state "
        "ON apple_reminders_write_audit(state)"
    )
    conn.commit()


def build_request(
    operations: list[WriteOp],
    *,
    mode: str = "plan",
    confirm_destructive: bool = False,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Assemble a wire request dict from typed ops. ``mode`` is ``plan`` (resolve
    + validate, no mutation) or ``apply`` (execute)."""
    if mode not in ("plan", "apply"):
        raise AppleRemindersWriteError(f"invalid mode: {mode!r} (expected plan|apply)")
    for op in operations:
        if op.op not in _VALID_OPS:
            raise AppleRemindersWriteError(
                f"invalid op: {op.op!r} (expected one of {sorted(_VALID_OPS)})"
            )
    return {
        "schema_version": WRITE_SCHEMA_VERSION,
        "request_id": request_id or _new_request_id(),
        "mode": mode,
        "confirm_destructive": bool(confirm_destructive),
        "operations": [op.as_dict() for op in operations],
    }


def _validate_scope(request: dict[str, Any], allowed_list: str) -> None:
    """Reject any create/update whose target list != the configured ingest list.
    Writing to a list the read path never ingests breaks the reconcile invariant
    (consult graded this a Blocker). complete/delete address an existing reminder
    by id and carry no list, so they are not scope-checked here."""
    for i, op in enumerate(request["operations"]):
        if op["op"] not in ("create", "update"):
            continue
        target = op.get("list_name")
        if target is not None and target != allowed_list:
            raise AppleRemindersWriteScopeError(
                f"op[{i}] {op['op']} targets list {target!r}, but writes are "
                f"restricted to the configured ingest list {allowed_list!r} in v1"
            )


def _check_confirmation(request: dict[str, Any]) -> None:
    """On apply, destructive ops require confirm_destructive=True."""
    if request["mode"] != "apply":
        return
    if request.get("confirm_destructive"):
        return
    destructive = [
        op["op"] for op in request["operations"] if op["op"] in _DESTRUCTIVE_OPS
    ]
    if destructive:
        raise AppleRemindersConfirmationError(
            f"apply contains destructive op(s) {destructive} but "
            f"confirm_destructive is not set"
        )


def _prior_result(
    conn: sqlite3.Connection, request_id: str
) -> WriteResult | None:
    """Idempotency: if this request_id already reached applied/reconciled, return
    the recorded result instead of re-invoking the helper. Guards the
    'Python timed out after a successful apply, then retried' duplicate path."""
    rows = conn.execute(
        "SELECT state, response_json FROM apple_reminders_write_audit "
        "WHERE request_id = ? ORDER BY op_index",
        (request_id,),
    ).fetchall()
    if not rows:
        return None
    states = {r[0] for r in rows}
    if not (states & _DONE_STATES):
        return None
    response_json = rows[0][1]
    if not response_json:
        return None
    return _parse_response(json.loads(response_json), request_id)


def _record_audit(
    conn: sqlite3.Connection,
    request: dict[str, Any],
    *,
    state: str,
    response: dict[str, Any] | None,
    helper_identity: str | None,
) -> None:
    """Upsert one audit row per op for this request. Blobs are written once and
    not rewritten on a state bump beyond what this call supplies."""
    now = _now_iso()
    request_json = json.dumps(request, sort_keys=True)
    response_json = json.dumps(response, sort_keys=True) if response else None
    results_by_token: dict[str | None, dict[str, Any]] = {}
    results_by_id: dict[str | None, dict[str, Any]] = {}
    if response:
        for r in response.get("results", []):
            results_by_token[r.get("client_token")] = r
            results_by_id[r.get("reminder_id")] = r
    for i, op in enumerate(request["operations"]):
        res = results_by_token.get(op.get("client_token")) or results_by_id.get(
            op.get("reminder_id")
        )
        reminder_id = op.get("reminder_id")
        op_status = None
        readback = None
        detail = None
        if res:
            reminder_id = res.get("reminder_id") or reminder_id
            op_status = res.get("status")
            readback = 1 if res.get("readback_ok") else 0
            detail = res.get("detail")
        conn.execute(
            """
            INSERT INTO apple_reminders_write_audit (
                request_id, op_index, op, client_token, reminder_id, mode, state,
                op_status, readback_ok, helper_identity, request_json,
                response_json, detail, created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(request_id, op_index) DO UPDATE SET
                state=excluded.state,
                op_status=COALESCE(excluded.op_status, apple_reminders_write_audit.op_status),
                reminder_id=COALESCE(excluded.reminder_id, apple_reminders_write_audit.reminder_id),
                readback_ok=COALESCE(excluded.readback_ok, apple_reminders_write_audit.readback_ok),
                helper_identity=COALESCE(excluded.helper_identity, apple_reminders_write_audit.helper_identity),
                response_json=COALESCE(excluded.response_json, apple_reminders_write_audit.response_json),
                detail=COALESCE(excluded.detail, apple_reminders_write_audit.detail),
                updated_at=excluded.updated_at
            """,
            (
                request["request_id"], i, op["op"], op.get("client_token"),
                reminder_id, request["mode"], state, op_status, readback,
                helper_identity, request_json, response_json, detail, now, now,
            ),
        )
    conn.commit()


def _parse_response(response: dict[str, Any], request_id: str) -> WriteResult:
    if response.get("schema_version") != WRITE_SCHEMA_VERSION:
        raise AppleRemindersHelperError(
            f"helper response schema_version "
            f"{response.get('schema_version')!r} != {WRITE_SCHEMA_VERSION}"
        )
    if response.get("request_id") != request_id:
        raise AppleRemindersHelperError(
            f"helper response request_id {response.get('request_id')!r} "
            f"!= sent {request_id!r} (stale or mismatched response)"
        )
    return WriteResult(
        request_id=request_id,
        mode=response.get("mode", ""),
        state=STATE_ACCEPTED,
        host_runtime=response.get("host_runtime", ""),
        authorization_status=response.get("authorization_status", ""),
        results=[WriteOpResult.from_dict(r) for r in response.get("results", [])],
        started_at=response.get("started_at", ""),
        finished_at=response.get("finished_at", ""),
    )


def apply_reminder_writes(
    database_path: Path,
    request: dict[str, Any],
    *,
    list_name: str | None = None,
    invoker: Invoker | None = None,
    reconcile_fn: Callable[[], Any] | None = None,
    reconcile: bool = True,
) -> WriteResult:
    """Run a write request end-to-end: validate scope + confirmation, record the
    audit lifecycle, delegate the mutation to the signed helper, and (on apply)
    reconcile the local table from Apple.

    Args:
        database_path: rebalance DB (holds the audit table + local reminders).
        request: a dict from `build_request`.
        list_name: the configured ingest list; defaults to config.
        invoker: helper-call seam; defaults to the real `open`-the-bundle path.
        reconcile_fn: local re-sync seam; defaults to `sync_apple_reminders`.
        reconcile: whether to re-sync after a successful apply.

    Returns a `WriteResult`. Raises on scope/confirmation/helper failures.
    """
    from rebalance.ingest.db import db_connection

    if request.get("schema_version") != WRITE_SCHEMA_VERSION:
        raise AppleRemindersWriteError(
            f"request schema_version {request.get('schema_version')!r} "
            f"!= {WRITE_SCHEMA_VERSION}"
        )
    if list_name is None:
        from rebalance.ingest.config import get_apple_reminders_list_name
        list_name = get_apple_reminders_list_name()

    _validate_scope(request, list_name)
    _check_confirmation(request)

    request_id = request["request_id"]
    mode = request["mode"]

    with db_connection(database_path, ensure_apple_reminders_write_schema) as conn:
        # Idempotency: a replay of an already-applied request returns the
        # recorded result without touching Apple again.
        prior = _prior_result(conn, request_id)
        if prior is not None:
            logger.info(
                "apple_reminders write: request %s already applied — replay no-op",
                request_id,
            )
            return prior

        _record_audit(conn, request, state=STATE_ACCEPTED, response=None,
                      helper_identity=None)

        call = invoker if invoker is not None else _open_bundle_invoker
        try:
            response = call(request)
        except AppleRemindersHelperError:
            _record_audit(conn, request, state=STATE_FAILED, response=None,
                          helper_identity=None)
            raise

        result = _parse_response(response, request_id)
        helper_identity = result.host_runtime

        # plan never mutates; record and return without reconcile.
        if mode == "plan":
            result.state = STATE_SKIPPED
            _record_audit(conn, request, state=STATE_SKIPPED, response=response,
                          helper_identity=helper_identity)
            result.finished_at = _now_iso()
            return result

        applied_any = any(r.status == "ok" for r in result.results)
        if not applied_any:
            # Nothing applied (e.g. auth denied, all ops errored) — record the
            # honest terminal state, no reconcile.
            result.state = STATE_FAILED
            _record_audit(conn, request, state=STATE_FAILED, response=response,
                          helper_identity=helper_identity)
            result.finished_at = _now_iso()
            return result

        result.state = STATE_APPLIED
        _record_audit(conn, request, state=STATE_APPLIED, response=response,
                      helper_identity=helper_identity)

        if reconcile:
            fn = reconcile_fn
            if fn is None:
                def fn() -> Any:  # type: ignore[misc]
                    from rebalance.ingest.apple_reminders import sync_apple_reminders
                    return sync_apple_reminders(database_path, list_name=list_name)
            try:
                fn()
                result.reconciled = True
                result.state = STATE_RECONCILED
                _record_audit(conn, request, state=STATE_RECONCILED,
                              response=response, helper_identity=helper_identity)
            except Exception as exc:  # reconcile is best-effort; write already done
                logger.warning(
                    "apple_reminders write: apply succeeded but reconcile failed "
                    "for request %s: %s", request_id, exc,
                )

    result.finished_at = _now_iso()
    return result


# ---------------------------------------------------------------------------
# Real helper invocation (macOS only). Atomic file IPC + `open` launch + helper
# identity verification. Not exercised by the headless test suite (which injects
# a fake invoker); guarded so import never requires macOS.
# ---------------------------------------------------------------------------

def _helper_bundle_path(repo_root: Path | None = None) -> Path:
    root = repo_root or _repo_root()
    return root / _HELPER_BUNDLE_RELPATH


def _repo_root() -> Path:
    # apple_reminders_write.py -> ingest -> rebalance -> src -> repo root
    return Path(__file__).resolve().parents[3]


def _verify_helper_identity(bundle: Path, expected_bundle_id: str) -> str:
    """Confused-deputy guard: the bundle must exist, carry a valid code signature,
    and declare the expected bundle id. Returns the verified identity string."""
    if not bundle.exists():
        raise AppleRemindersHelperError(
            f"helper bundle not found at {bundle}. Build it with "
            f"scripts/build_apple_reminders_helper_app.sh"
        )
    if not shutil.which("codesign"):
        raise AppleRemindersHelperError("codesign not available to verify helper")
    verify = subprocess.run(
        ["codesign", "--verify", "--deep", "--strict", str(bundle)],
        capture_output=True, text=True,
    )
    if verify.returncode != 0:
        raise AppleRemindersHelperError(
            f"helper signature failed verification: {verify.stderr.strip()}"
        )
    info = subprocess.run(
        ["codesign", "-d", "--verbose=2", str(bundle)],
        capture_output=True, text=True,
    )
    blob = (info.stderr or "") + (info.stdout or "")
    ident_line = next(
        (ln for ln in blob.splitlines() if ln.startswith("Identifier=")), ""
    )
    identity = ident_line.partition("=")[2].strip()
    if identity != expected_bundle_id:
        raise AppleRemindersHelperError(
            f"helper bundle id {identity!r} != expected {expected_bundle_id!r}"
        )
    return identity


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, sort_keys=True)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def _open_bundle_invoker(
    request: dict[str, Any],
    *,
    repo_root: Path | None = None,
    timeout_seconds: float = 30.0,
    poll_seconds: float = 0.4,
) -> dict[str, Any]:
    """Default invoker: verify the signed helper, write the request atomically,
    `open` the bundle via LaunchServices, and poll for the response file.

    `open` proves only that the helper LAUNCHED — never that the write succeeded;
    only the response file (carrying per-op readback) proves that."""
    root = repo_root or _repo_root()
    bundle = _helper_bundle_path(root)
    identity = _verify_helper_identity(bundle, HELPER_BUNDLE_ID)
    logger.info("apple_reminders write: helper verified (%s)", identity)

    io_dir = root / "temp/apple-reminders/write-io"
    req_path = io_dir / f"{request['request_id']}.req.json"
    resp_path = io_dir / f"{request['request_id']}.resp.json"
    # Clear any stale response so we don't read a previous run's file.
    resp_path.unlink(missing_ok=True)
    _atomic_write_json(req_path, request)

    launch = subprocess.run(
        ["open", "-a", str(bundle), "--args", "--request", str(req_path)],
        capture_output=True, text=True,
    )
    if launch.returncode != 0:
        raise AppleRemindersHelperError(
            f"failed to launch helper via `open`: {launch.stderr.strip()}"
        )

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if resp_path.exists():
            try:
                with open(resp_path, encoding="utf-8") as fh:
                    return json.load(fh)
            except (json.JSONDecodeError, OSError):
                pass  # helper may still be writing; retry
        time.sleep(poll_seconds)
    raise AppleRemindersHelperError(
        f"helper did not produce a response within {timeout_seconds:.0f}s "
        f"(request {request['request_id']}). `open` launched the helper but no "
        f"response file appeared — check Reminders TCC grant on the bundle."
    )
