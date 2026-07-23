"""The classifier boundary for 3-Eyes (GH-195).

This is the ONLY module allowed to reach the local LLM (Ollama ``gemma4:12b-mlx``).
The egress static-guard test enforces that — no other 3-Eyes file may contain an
ollama/http call. Centralising it here means "does 3-Eyes talk to a model?" has
one answer in one place, gated once.

Inert by default. ``classify`` refuses unless EITHER 3-Eyes is active OR the
classifier is explicitly stubbed for tests/dry-runs (``THREE_EYES_CLASSIFY_STUB``).
With neither, it returns a refusal dict and makes zero network calls.
"""

from __future__ import annotations

import json
import urllib.request

from . import config

MODEL = "gemma4:12b-mlx"
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"


def _stub_classify(text: str) -> dict:
    """Deterministic offline classification for tests and dry-runs.

    Keyword-based, no network. Good enough to exercise the routing/draft path
    without a live model, and stable so tests never flake.
    """
    lowered = text.lower()
    if any(k in lowered for k in ("panic", "kernel", "oom", "corrupt", "fatal")):
        severity = "critical"
    elif any(k in lowered for k in ("error", "fail", "exception", "traceback")):
        severity = "error"
    elif any(k in lowered for k in ("warn", "deprecat", "retry")):
        severity = "warn"
    else:
        severity = "info"
    return {
        "severity": severity,
        "summary": text.strip().splitlines()[0][:200] if text.strip() else "(empty)",
        "stub": True,
    }


def available() -> bool:
    """True when classification may proceed (active or stubbed)."""
    return config.three_eyes_active() or config.classify_stubbed()


def classify(text: str, model: str | None = None, timeout: float = 30.0) -> dict:
    """Classify a finding's text into a severity + summary.

    Returns ``{"severity": ..., "summary": ..., ...}`` or, when 3-Eyes is inert
    and unstubbed, ``{"refused": True, "reason": ...}`` after making NO network
    call. The stub path also makes no network call.
    """
    if config.classify_stubbed():
        return _stub_classify(text)
    if not config.three_eyes_active():
        return {"refused": True, "reason": "3-Eyes inert (no runtime.env / disabled)"}

    payload = json.dumps(
        {
            "model": model or MODEL,
            "prompt": (
                "Classify this log/finding. Reply with a single JSON object: "
                '{"severity": one of critical|error|warn|info, "summary": short}. '
                f"Finding:\n{text[:4000]}"
            ),
            "stream": False,
            "format": "json",
        }
    ).encode()
    req = urllib.request.Request(OLLAMA_URL, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - localhost only
            body = json.loads(resp.read().decode())
    except (OSError, ValueError) as exc:
        return {"refused": True, "reason": f"ollama unreachable: {exc}"}

    inner = body.get("response", "")
    try:
        parsed = json.loads(inner)
    except (ValueError, TypeError):
        return {"severity": "info", "summary": str(inner)[:200], "raw": True}
    parsed.setdefault("severity", "info")
    parsed.setdefault("summary", str(inner)[:200])
    return parsed
