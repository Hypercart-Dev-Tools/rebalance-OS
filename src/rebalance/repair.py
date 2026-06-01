"""Finite-state-machine repair loop with optional Haiku escalation.

States
------
PENDING   — attempting deterministic repair
REPAIRED  — terminal success
ESCALATED — deterministic repair exhausted; Haiku selected the next action
DEAD      — terminal failure (circuit breaker hit or all attempts exhausted)

Circuit breakers
----------------
1. Unrecoverable error class  → DEAD immediately, no retry
2. max_deterministic_attempts → cap on deterministic retries before escalation
3. max_haiku_attempts         → Haiku is called at most once by default
4. Bounded action menu        → Haiku picks a name from a known list,
                                 never executes free-form commands

Usage
-----
    fsm = RepairFSM(
        actions={"pull_rebase": my_fn, "notify_only": lambda: RepairResult(ok=False)},
        action_descriptions={"pull_rebase": "pull --rebase and retry push", ...},
        preferred_action="pull_rebase",
        error_context="git push to pulse repo failed",
    )
    state = fsm.run(initial_error=captured_stderr)
    if state.status == RepairStatus.REPAIRED:
        ...
"""

from __future__ import annotations

import dataclasses
import json
import urllib.error
import urllib.request
from enum import Enum
from typing import Any, Callable

from rebalance.ingest.config import get_anthropic_api_key


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

class RepairStatus(str, Enum):
    PENDING   = "pending"
    REPAIRED  = "repaired"
    ESCALATED = "escalated"
    DEAD      = "dead"


@dataclasses.dataclass
class RepairResult:
    ok: bool
    output: str = ""
    error: str = ""


@dataclasses.dataclass
class RepairState:
    status: RepairStatus
    attempts: int = 0
    haiku_attempts: int = 0
    log: list[str] = dataclasses.field(default_factory=list)
    final_error: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "attempts": self.attempts,
            "haiku_attempts": self.haiku_attempts,
            "log": self.log,
            "final_error": self.final_error,
        }


# ---------------------------------------------------------------------------
# Unrecoverable error classes (circuit breaker — no retry, no escalation)
# ---------------------------------------------------------------------------

_UNRECOVERABLE = (
    "authentication failed",
    "permission denied",
    "not a git repository",
    "repository not found",
    "fatal: could not read",
    "fatal: unable to access",
    "no such file or directory",
    "invalid credentials",
)

def is_unrecoverable(error: str) -> bool:
    low = error.lower()
    return any(p in low for p in _UNRECOVERABLE)


# ---------------------------------------------------------------------------
# FSM
# ---------------------------------------------------------------------------

_HAIKU_MODEL    = "claude-haiku-4-5-20251001"
_HAIKU_ENDPOINT = "https://api.anthropic.com/v1/messages"


class RepairFSM:
    """Deterministic repair with bounded Haiku escalation."""

    def __init__(
        self,
        *,
        actions: dict[str, Callable[[], RepairResult]],
        action_descriptions: dict[str, str],
        error_context: str = "",
        preferred_action: str | None = None,
        max_deterministic_attempts: int = 2,
        max_haiku_attempts: int = 1,
        haiku_api_key: str | None = None,
    ) -> None:
        if not actions:
            raise ValueError("RepairFSM requires at least one action")
        self.actions = actions
        self.action_descriptions = action_descriptions
        self.error_context = error_context
        self.preferred_action = preferred_action or next(iter(actions))
        self.max_deterministic_attempts = max_deterministic_attempts
        self.max_haiku_attempts = max_haiku_attempts
        self.haiku_api_key = haiku_api_key or get_anthropic_api_key()

    def run(self, initial_error: str) -> RepairState:
        state = RepairState(status=RepairStatus.PENDING, final_error=initial_error)

        # Circuit breaker: unrecoverable error class — skip immediately to DEAD
        if is_unrecoverable(initial_error):
            state.log.append(
                f"circuit-breaker: unrecoverable error class — no repair attempted"
            )
            state.status = RepairStatus.DEAD
            return state

        # ── Deterministic repair loop ────────────────────────────────────────
        action_name = self.preferred_action
        while state.attempts < self.max_deterministic_attempts:
            fn = self.actions.get(action_name)
            if fn is None:
                state.log.append(f"unknown action '{action_name}' — stopping")
                break

            state.log.append(
                f"attempt {state.attempts + 1}/{self.max_deterministic_attempts}: {action_name}"
            )
            result = fn()
            state.attempts += 1

            if result.ok:
                state.log.append(f"repaired via deterministic '{action_name}'")
                state.status = RepairStatus.REPAIRED
                return state

            state.final_error = result.error
            state.log.append(f"failed: {result.error[:120]}")

            # Circuit breaker: unrecoverable error mid-repair
            if is_unrecoverable(result.error):
                state.log.append("circuit-breaker: unrecoverable error — stopping")
                state.status = RepairStatus.DEAD
                return state

        # ── Haiku escalation ─────────────────────────────────────────────────
        if self.haiku_api_key and state.haiku_attempts < self.max_haiku_attempts:
            state.status = RepairStatus.ESCALATED
            state.log.append("escalating to Haiku for action selection")
            chosen = self._haiku_triage(state)
            state.haiku_attempts += 1

            if chosen and chosen in self.actions:
                state.log.append(f"Haiku selected: '{chosen}'")
                result = self.actions[chosen]()
                if result.ok:
                    state.log.append(f"repaired via Haiku-selected '{chosen}'")
                    state.status = RepairStatus.REPAIRED
                    return state
                state.final_error = result.error
                state.log.append(f"Haiku action failed: {result.error[:120]}")
            else:
                state.log.append(f"Haiku returned invalid/no action: {chosen!r}")
        elif not self.haiku_api_key:
            state.log.append("no ANTHROPIC_API_KEY — Haiku escalation skipped")

        state.status = RepairStatus.DEAD
        return state

    def _haiku_triage(self, state: RepairState) -> str | None:
        """Call Haiku with the error context and bounded action menu; return chosen name."""
        menu = "\n".join(
            f"  {name}: {self.action_descriptions.get(name, '(no description)')}"
            for name in self.actions
        )
        prompt = "\n".join([
            "You are a repair assistant. A deterministic fix failed.",
            "Pick the single best next repair action from the menu below.",
            "",
            f"Context: {self.error_context}",
            f"Last error: {state.final_error[:300]}",
            f"Repair log: {'; '.join(state.log[-5:])}",
            "",
            "Available actions:",
            menu,
            "",
            "Reply with ONLY the action name — one word, no punctuation, no explanation.",
        ])
        body = json.dumps({
            "model": _HAIKU_MODEL,
            "max_tokens": 16,
            "messages": [{"role": "user", "content": prompt}],
        }).encode()
        req = urllib.request.Request(
            _HAIKU_ENDPOINT,
            data=body,
            headers={
                "x-api-key": self.haiku_api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                payload = json.loads(resp.read().decode())
            # Take only the first word to guard against verbose responses
            chosen = payload["content"][0]["text"].strip().lower().split()[0]
            return chosen if chosen in self.actions else None
        except Exception as exc:
            state.log.append(f"Haiku call failed: {exc}")
            return None
