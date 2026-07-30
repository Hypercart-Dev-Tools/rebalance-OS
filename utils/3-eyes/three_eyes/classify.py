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
from pathlib import Path

from . import config

MODEL = "gemma4:12b-mlx"
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"

#: Default request ceiling, in seconds.
#:
#: Sized for a COLD model, not a warm one. `gemma4:12b-mlx` is ~10 GB and ollama
#: evicts it after roughly 5 minutes idle, while the jobs that call it run every 30
#: minutes and once a day — so in production essentially *every* call pays the cold
#: load. Measured on this machine: 70 s cold, 25-36 s warm.
#:
#: This was 30 s until the first live P7c run, which timed out at exactly 30.1 s and
#: returned a refusal whose `severity` was None. Nothing crashed and nothing logged an
#: error — the classifier simply declined, forever, on every scheduled invocation.
#: A ceiling below the cold-load time is indistinguishable from "the model is broken".
DEFAULT_TIMEOUT_S = 120.0
SYSTEM_INSTRUCTIONS_PATH = Path(__file__).with_name("gemma_system_instructions.md")


def load_system_instructions() -> str:
    """Return the committed, operator-editable instructions for the classifier.

    The prompt belongs beside the runtime package so Codex, Claude Code, and a
    human operator have one obvious edit point. A missing or blank file is a
    configuration error: an active sentinel must fail closed rather than send
    an ungoverned prompt to the local model.
    """
    try:
        instructions = SYSTEM_INSTRUCTIONS_PATH.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise RuntimeError(f"Gemma system instructions unavailable: {exc}") from exc
    if not instructions:
        raise RuntimeError("Gemma system instructions are empty")
    return instructions


def _first_json_object(text: str) -> dict | None:
    """Decode the first balanced ``{...}`` object in ``text``, ignoring any trailing prose.

    Uses ``json.JSONDecoder.raw_decode``, which stops cleanly at the end of the first
    value instead of demanding that the whole string be JSON. Brace-counting by hand
    would mis-handle a ``}`` inside a string literal; the decoder does not.
    """
    start = text.find("{")
    if start < 0:
        return None
    try:
        parsed, _ = json.JSONDecoder().raw_decode(text[start:])
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _parse_model_json(inner: str) -> dict | None:
    """Parse the model's reply as JSON, tolerating a markdown code fence.

    Ollama's ``format: "json"`` is a request, not a guarantee — `gemma4:12b-mlx`
    routinely answers with ```` ```json … ``` ```` anyway. The first live digest run
    hit exactly this: a perfectly good ranked summary was discarded to the `raw`
    branch and the operator's "summary" became the fenced blob verbatim.

    This bug was latent in :func:`classify` since P5 and had never fired, because
    nothing in 3-Eyes had ever called the model. Both callers share this helper so
    it cannot be fixed in one and left broken in the other.

    Returns the parsed object, or ``None`` when the reply genuinely is not JSON.
    """
    text = (inner or "").strip()
    if text.startswith("```"):
        # Drop the opening fence (with optional language tag) and any closing fence.
        text = text.split("\n", 1)[-1] if "\n" in text else ""
        if "```" in text:
            text = text.rsplit("```", 1)[0]
        text = text.strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
    except (ValueError, TypeError):
        # Valid JSON followed by unfenced prose (agy review, P7 QA finding 6):
        # `{"severity": "error"}\nHere is why...` raises "Extra data" and the whole
        # reply was discarded. Retry on just the first balanced {...} object rather
        # than throwing away a good answer because the model kept talking.
        parsed = _first_json_object(text)
        if parsed is None:
            return None
    if not isinstance(parsed, dict):
        return None
    # Drop explicit JSON nulls. `setdefault` only fills a MISSING key, so a reply of
    # {"severity": null} would survive as None and propagate — `str(None)` renders as
    # the literal "None" in an operator-facing summary.
    return {k: v for k, v in parsed.items() if v is not None}


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


def _stub_digest(corpus: str) -> dict:
    """Offline digest summary for tests and dry-runs. No network.

    Mirrors the shape :func:`summarize_digest` returns so the caller's code path is
    identical stubbed or live — the reason the classify path could sit unexercised
    for weeks was that nothing ever ran it, and a stub that diverges from the real
    thing just relocates that problem.
    """
    lines = [l for l in corpus.splitlines() if l.startswith("- ")]
    failing = [l for l in lines if "FAIL" in l]
    severity = "error" if failing else ("warn" if lines else "info")
    head = (failing or lines or ["nothing notable"])[0].lstrip("- ").strip()
    return {
        "severity": severity,
        "summary": f"{len(failing)} failing, {len(lines)} items; first: {head}"[:400],
        "stub": True,
    }


def _stub_explain(evidence: str) -> dict:
    """Offline failure explanation for tests and dry-runs. No network."""
    graded = _stub_classify(evidence)
    return {
        "severity": graded["severity"],
        "headline": "unrecognised failure",
        "summary": graded["summary"],
        "next_step": "inspect the log tail",
        "stub": True,
    }


def explain_failure(evidence: str, model: str | None = None, timeout: float = DEFAULT_TIMEOUT_S) -> dict:
    """Judge a job failure that matched NO known-issue rule (P7b).

    Only reached after deterministic suppression has already failed to match, so the
    model is being asked about genuine novelty — never about the recurring failures,
    which are handled for free upstream in :mod:`explain`.

    The prompt deliberately offers "this looks benign" as an acceptable answer. A
    classifier that can only escalate produces an alert stream the operator stops
    reading, which is the failure mode #139 was closed by deleting an emitter over.
    """
    if config.classify_stubbed():
        return _stub_explain(evidence)
    if not config.three_eyes_active():
        return {"refused": True, "reason": "3-Eyes inert (no runtime.env / disabled)"}

    try:
        system_instructions = load_system_instructions()
    except RuntimeError as exc:
        return {"refused": True, "reason": str(exc)}

    payload = json.dumps(
        {
            "model": model or config.config_value("THREE_EYES_MODEL", MODEL) or MODEL,
            "system": system_instructions,
            "prompt": (
                "A scheduled job on this machine failed three times in a row and has "
                "been quarantined. No known-issue rule matched it. Decide what it is.\n\n"
                "Say plainly if it looks transient or benign — that is a useful answer, "
                "not a failure to find something. If it looks like a real fault, name the "
                "most likely cause from the evidence and one concrete next step. Do not "
                "speculate beyond what the log shows.\n\n"
                'Reply as JSON: {"severity": "info|warn|error|critical", '
                '"headline": "<8 words or fewer>", "summary": "...", "next_step": "..."}.\n\n'
                f"Evidence:\n{evidence[:8000]}"
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

    parsed = _parse_model_json(body.get("response", ""))
    if parsed is None:
        return {"refused": True, "reason": "model reply was not JSON"}
    parsed.setdefault("severity", "error")
    parsed.setdefault("summary", "")
    return parsed


def summarize_digest(corpus: str, model: str | None = None, timeout: float = DEFAULT_TIMEOUT_S) -> dict:
    """Rank a whole day of fleet state into one operator-facing summary (P7a).

    Distinct from :func:`classify`, which grades ONE finding into a severity. This
    asks the model to trade off across everything at once: what broke, what matters,
    what is known-benign. Same egress gate, same inert-by-default refusal, same
    committed system instructions — only the task differs, so there is still exactly
    one file in 3-Eyes that talks to a model.

    The timeout is far longer than ``classify``'s: this prompt carries log tails and
    a 12B local model on first load has to page ~10 GB in from disk. A 30 s ceiling
    would fail every cold morning run and look like the model was broken.
    """
    if config.classify_stubbed():
        return _stub_digest(corpus)
    if not config.three_eyes_active():
        return {"refused": True, "reason": "3-Eyes inert (no runtime.env / disabled)"}

    try:
        system_instructions = load_system_instructions()
    except RuntimeError as exc:
        return {"refused": True, "reason": str(exc)}

    payload = json.dumps(
        {
            "model": model or config.config_value("THREE_EYES_MODEL", MODEL) or MODEL,
            "system": system_instructions,
            "prompt": (
                "You are reviewing one day of scheduled-job state on a single Mac. "
                "Rank what matters. Lead with anything genuinely broken and what it "
                "blocks; then anything degraded; then explicitly say what looks alarming "
                "but is known-benign, so the operator can skip it. Be concise and "
                "concrete — name jobs and exit codes. If nothing is wrong, say so in one "
                "line rather than padding.\n\n"
                'Reply as JSON: {"severity": "info|warn|error|critical", "summary": "..."}.\n\n'
                f"Fleet state:\n{corpus[:12000]}"
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
    parsed = _parse_model_json(inner)
    if parsed is None:
        return {"severity": "info", "summary": str(inner)[:2000], "raw": True}
    parsed.setdefault("severity", "info")
    parsed.setdefault("summary", str(inner)[:2000])
    # gemma volunteers `confidence` / `evidence` / `next_safe_step` beyond the two
    # keys asked for. Keep them — the evidence list is the most operator-useful part
    # of the reply, and discarding it would waste the call that produced it.
    return parsed


def classify(text: str, model: str | None = None, timeout: float = DEFAULT_TIMEOUT_S) -> dict:
    """Classify a finding's text into a severity + summary.

    Returns ``{"severity": ..., "summary": ..., ...}`` or, when 3-Eyes is inert
    and unstubbed, ``{"refused": True, "reason": ...}`` after making NO network
    call. The stub path also makes no network call.
    """
    if config.classify_stubbed():
        return _stub_classify(text)
    if not config.three_eyes_active():
        return {"refused": True, "reason": "3-Eyes inert (no runtime.env / disabled)"}

    try:
        system_instructions = load_system_instructions()
    except RuntimeError as exc:
        return {"refused": True, "reason": str(exc)}

    payload = json.dumps(
        {
            "model": model or config.config_value("THREE_EYES_MODEL", MODEL) or MODEL,
            "system": system_instructions,
            "prompt": (
                "Classify this supplied finding according to the system instructions. "
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
    parsed = _parse_model_json(inner)
    if parsed is None:
        return {"severity": "info", "summary": str(inner)[:200], "raw": True}
    parsed.setdefault("severity", "info")
    parsed.setdefault("summary", str(inner)[:200])
    return parsed
