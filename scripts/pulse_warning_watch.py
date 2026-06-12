#!/usr/bin/env python3
"""Watch the local pulse page health banner and log findings.

Fetches ``http://127.0.0.1:8767/`` with ``curl``, extracts the top collector
warning banner from the rendered HTML, and appends one JSONL record per check.

Optional: send the extracted banner text to any OpenAI-compatible local model
endpoint (including Ollama's ``/v1`` surface) for a short triage note.

Examples
--------
One shot:
    .venv/bin/python scripts/pulse_warning_watch.py --print

15-minute loop:
    .venv/bin/python scripts/pulse_warning_watch.py --watch --interval-seconds 900

With Ollama/Gemma via OpenAI-compatible API:
    .venv/bin/python scripts/pulse_warning_watch.py \
      --ollama-model gemma3:12b \
      --ollama-base-url http://127.0.0.1:11434/v1
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_URL = "http://127.0.0.1:8767/"
DEFAULT_INTERVAL_SECONDS = 900
DEFAULT_LOG_PATH = PROJECT_ROOT / "temp" / "pulse-warning-watch.jsonl"
DEFAULT_STATE_PATH = PROJECT_ROOT / "temp" / "pulse-warning-watch.state.json"

_BANNER_RE = re.compile(
    r'<section class="health-banner[^"]*"[^>]*>(?P<body>.*?)</section>',
    re.IGNORECASE | re.DOTALL,
)
_COPY_TEXT_RE = re.compile(
    r'data-copy-text="(?P<text>.*?)"',
    re.IGNORECASE | re.DOTALL,
)
_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")

_LLM_SYSTEM = """\
You are monitoring rebalance-OS collector health.

Given the current pulse-page health banner text, return EXACTLY one JSON object:
{
  "severity": "ok" | "warn" | "fail",
  "summary": "<one sentence, <= 20 words>",
  "next_action": "<one sentence, <= 20 words>"
}

Use:
- "ok" when there is no warning banner and collection appears healthy.
- "warn" for degraded or stale but non-failing states.
- "fail" for broken, unreachable, or clearly failing collectors.
"""


@dataclass
class PulseSnapshot:
    fetched_at: str
    url: str
    fetch_ok: bool
    page_state: str
    sync_tone: str
    sync_text: str
    banner_text: str
    fingerprint: str
    changed: bool
    llm_used: bool = False
    llm_model: str = ""
    llm_summary: str = ""
    llm_next_action: str = ""
    llm_severity: str = ""
    fetch_error: str = ""


class _PulseHTMLParser(HTMLParser):
    """Extract the sync chip and banner copy text from pulse HTML."""

    def __init__(self) -> None:
        super().__init__()
        self.sync_tone = ""
        self.sync_text = ""
        self.banner_text = ""
        self._sync_depth = 0
        self._sync_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_map = {k: v or "" for k, v in attrs}
        classes = set(attrs_map.get("class", "").split())
        if tag == "span" and "synced" in classes:
            for tone in ("ok", "warn", "danger"):
                if f"synced-{tone}" in classes:
                    self.sync_tone = tone
                    self._sync_depth += 1
                    break
        elif self._sync_depth > 0:
            self._sync_depth += 1

        copy_text = attrs_map.get("data-copy-text", "")
        if copy_text and not self.banner_text:
            self.banner_text = html.unescape(copy_text).strip()

    def handle_endtag(self, tag: str) -> None:
        if self._sync_depth > 0:
            self._sync_depth -= 1
            if self._sync_depth == 0:
                self.sync_text = _compact("".join(self._sync_parts))
                self._sync_parts = []

    def handle_data(self, data: str) -> None:
        if self._sync_depth > 0 and data.strip():
            self._sync_parts.append(data)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_now() -> str:
    return _utc_now().isoformat()


def _compact(text: str) -> str:
    return _SPACE_RE.sub(" ", text).strip()


def _strip_tags(fragment: str) -> str:
    text = _TAG_RE.sub(" ", fragment)
    return _compact(html.unescape(text))


def fetch_html_with_curl(url: str, timeout_seconds: int) -> str:
    proc = subprocess.run(
        ["curl", "-fsS", "--max-time", str(timeout_seconds), url],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        stderr = proc.stderr.strip() or f"curl exit {proc.returncode}"
        raise RuntimeError(stderr)
    return proc.stdout


def extract_banner_text(page_html: str) -> tuple[str, str, str, str]:
    """Return (page_state, sync_text, banner_text, sync_tone) from rendered pulse HTML."""
    parser = _PulseHTMLParser()
    parser.feed(page_html)
    sync_text = parser.sync_text
    sync_tone = parser.sync_tone

    banner_match = _BANNER_RE.search(page_html)
    if not banner_match and not parser.banner_text:
        page_state = "healthy" if sync_tone == "ok" else "unknown"
        return page_state, sync_text, "", sync_tone

    banner_html = banner_match.group("body") if banner_match else ""
    if parser.banner_text:
        banner_text = parser.banner_text
    elif copy_match := _COPY_TEXT_RE.search(banner_html):
        banner_text = html.unescape(copy_match.group("text")).strip()
    else:
        banner_text = _strip_tags(banner_html)
    page_state = "warning" if sync_tone in {"warn", "danger"} else "unknown"
    return page_state, sync_text, banner_text, sync_tone


def compute_fingerprint(sync_text: str, banner_text: str) -> str:
    payload = f"{sync_text}\n---\n{banner_text}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def call_openai_compatible(
    *,
    base_url: str,
    model: str,
    prompt: str,
    api_key: str = "local",
    timeout_seconds: int = 30,
) -> dict[str, Any]:
    base = base_url.rstrip("/")
    if not base.endswith("/v1"):
        base = f"{base}/v1"
    url = f"{base}/chat/completions"
    payload = json.dumps(
        {
            "model": model,
            "temperature": 0.1,
            "max_tokens": 180,
            "messages": [
                {"role": "system", "content": _LLM_SYSTEM},
                {"role": "user", "content": prompt},
            ],
        }
    )
    proc = subprocess.run(
        [
            "curl",
            "-fsS",
            "--max-time",
            str(timeout_seconds),
            "-H",
            "Content-Type: application/json",
            "-H",
            f"Authorization: Bearer {api_key or 'local'}",
            "-X",
            "POST",
            url,
            "-d",
            payload,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        stderr = proc.stderr.strip() or f"curl exit {proc.returncode}"
        raise RuntimeError(stderr)
    response = json.loads(proc.stdout)
    content = (
        ((((response.get("choices") or [])[0] or {}).get("message") or {}).get("content"))
        or ""
    ).strip()
    return json.loads(content)


def maybe_llm_triage(
    *,
    snapshot: PulseSnapshot,
    previous_state: dict[str, Any],
    base_url: str,
    model: str,
    api_key: str,
    timeout_seconds: int,
) -> PulseSnapshot:
    if not model or not base_url:
        return snapshot

    previous_fingerprint = str(previous_state.get("fingerprint") or "")
    previous_triage = previous_state.get("llm") or {}
    if (
        snapshot.fingerprint == previous_fingerprint
        and isinstance(previous_triage, dict)
        and previous_triage.get("summary")
    ):
        snapshot.llm_used = False
        snapshot.llm_model = str(previous_triage.get("model") or model)
        snapshot.llm_summary = str(previous_triage.get("summary") or "")
        snapshot.llm_next_action = str(previous_triage.get("next_action") or "")
        snapshot.llm_severity = str(previous_triage.get("severity") or "")
        return snapshot

    prompt = (
        f"Sync chip: {snapshot.sync_text or 'missing'}\n"
        f"Banner text:\n{snapshot.banner_text or 'No warning banner; page appears healthy.'}"
    )
    result = call_openai_compatible(
        base_url=base_url,
        model=model,
        prompt=prompt,
        api_key=api_key,
        timeout_seconds=timeout_seconds,
    )
    snapshot.llm_used = True
    snapshot.llm_model = model
    snapshot.llm_summary = str(result.get("summary") or "").strip()
    snapshot.llm_next_action = str(result.get("next_action") or "").strip()
    snapshot.llm_severity = str(result.get("severity") or "").strip()
    return snapshot


def append_log(path: Path, snapshot: PulseSnapshot) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(asdict(snapshot), ensure_ascii=True) + "\n")


def collect_snapshot(
    *,
    url: str,
    timeout_seconds: int,
    state_path: Path,
    llm_base_url: str,
    llm_model: str,
    llm_api_key: str,
) -> PulseSnapshot:
    previous_state = load_state(state_path)
    try:
        page_html = fetch_html_with_curl(url, timeout_seconds)
        page_state, sync_text, banner_text, sync_tone = extract_banner_text(page_html)
        fingerprint = compute_fingerprint(sync_text, banner_text)
        snapshot = PulseSnapshot(
            fetched_at=_iso_now(),
            url=url,
            fetch_ok=True,
            page_state=page_state,
            sync_tone=sync_tone,
            sync_text=sync_text,
            banner_text=banner_text,
            fingerprint=fingerprint,
            changed=fingerprint != str(previous_state.get("fingerprint") or ""),
        )
        snapshot = maybe_llm_triage(
            snapshot=snapshot,
            previous_state=previous_state,
            base_url=llm_base_url,
            model=llm_model,
            api_key=llm_api_key,
            timeout_seconds=timeout_seconds,
        )
    except Exception as exc:  # noqa: BLE001
        fingerprint = compute_fingerprint("fetch-failed", str(exc))
        snapshot = PulseSnapshot(
            fetched_at=_iso_now(),
            url=url,
            fetch_ok=False,
            page_state="unreachable",
            sync_tone="",
            sync_text="",
            banner_text="",
            fingerprint=fingerprint,
            changed=fingerprint != str(previous_state.get("fingerprint") or ""),
            fetch_error=str(exc),
        )

    state_payload = {
        "fingerprint": snapshot.fingerprint,
        "fetched_at": snapshot.fetched_at,
        "page_state": snapshot.page_state,
        "sync_text": snapshot.sync_text,
        "banner_text": snapshot.banner_text,
        "llm": {
            "model": snapshot.llm_model,
            "summary": snapshot.llm_summary,
            "next_action": snapshot.llm_next_action,
            "severity": snapshot.llm_severity,
        },
    }
    save_state(state_path, state_payload)
    return snapshot


def print_snapshot(snapshot: PulseSnapshot) -> None:
    print(f"[{snapshot.fetched_at}] {snapshot.page_state} {snapshot.url}")
    if snapshot.sync_text:
        print(f"sync: {snapshot.sync_text}")
    if snapshot.banner_text:
        print(snapshot.banner_text)
    if snapshot.fetch_error:
        print(f"error: {snapshot.fetch_error}")
    if snapshot.llm_summary:
        print(f"llm: {snapshot.llm_severity or 'n/a'} | {snapshot.llm_summary}")
        if snapshot.llm_next_action:
            print(f"next: {snapshot.llm_next_action}")


def run_once(args: argparse.Namespace) -> int:
    snapshot = collect_snapshot(
        url=args.url,
        timeout_seconds=args.timeout_seconds,
        state_path=args.state,
        llm_base_url=args.ollama_base_url,
        llm_model=args.ollama_model,
        llm_api_key=args.ollama_api_key,
    )
    append_log(args.log, snapshot)
    if args.print:
        print_snapshot(snapshot)
    return 0 if snapshot.fetch_ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL, help="Pulse page URL to fetch")
    parser.add_argument(
        "--log",
        type=Path,
        default=DEFAULT_LOG_PATH,
        help="JSONL log file path",
    )
    parser.add_argument(
        "--state",
        type=Path,
        default=DEFAULT_STATE_PATH,
        help="State file used to detect changes and cache the last LLM note",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=15,
        help="curl and LLM request timeout",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Run continuously instead of one shot",
    )
    parser.add_argument(
        "--interval-seconds",
        type=int,
        default=DEFAULT_INTERVAL_SECONDS,
        help="Loop interval when --watch is enabled",
    )
    parser.add_argument(
        "--print",
        action="store_true",
        help="Print the extracted banner and any LLM note to stdout",
    )
    parser.add_argument(
        "--ollama-model",
        default="",
        help="Optional OpenAI-compatible/Ollama model name for short triage notes",
    )
    parser.add_argument(
        "--ollama-base-url",
        default="",
        help="OpenAI-compatible base URL, e.g. http://127.0.0.1:11434/v1",
    )
    parser.add_argument(
        "--ollama-api-key",
        default="local",
        help="API key for OpenAI-compatible local endpoints",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.watch:
        return run_once(args)

    while True:
        exit_code = run_once(args)
        time.sleep(max(1, int(args.interval_seconds)))


if __name__ == "__main__":
    raise SystemExit(main())
