from __future__ import annotations

import json

from scripts.pulse_warning_watch import PulseSnapshot, append_log, extract_banner_text


def test_extract_banner_text_with_warning_banner() -> None:
    html = """
    <html><body>
      <span class="synced synced-warn"><span class="ok-dot"></span>Collector warnings · 38m ago</span>
      <section class="health-banner health-banner-warn" aria-live="polite">
        <div class="health-banner-lead">
          <button class="health-banner-copy-btn"
            data-copy-text="Collector attention needed&#10;Status: 2 warnings&#10;Last collector activity: 38m ago&#10;gmail: token missing&#10;Hint: rerun auth">
          </button>
        </div>
      </section>
    </body></html>
    """

    page_state, sync_text, banner_text, sync_tone = extract_banner_text(html)

    assert page_state == "warning"
    assert sync_tone == "warn"
    assert sync_text == "Collector warnings · 38m ago"
    assert "Status: 2 warnings" in banner_text
    assert "gmail: token missing" in banner_text


def test_extract_banner_text_when_healthy() -> None:
    html = """
    <html><body>
      <span class="synced synced-ok"><span class="ok-dot"></span>Collector active 4m ago</span>
    </body></html>
    """

    page_state, sync_text, banner_text, sync_tone = extract_banner_text(html)

    assert page_state == "healthy"
    assert sync_tone == "ok"
    assert sync_text == "Collector active 4m ago"
    assert banner_text == ""


def test_append_log_writes_jsonl(tmp_path) -> None:
    log_path = tmp_path / "watch.jsonl"
    snapshot = PulseSnapshot(
        fetched_at="2026-06-03T00:00:00+00:00",
        url="http://127.0.0.1:8767/",
        fetch_ok=True,
        page_state="warning",
        sync_tone="warn",
        sync_text="Collector warnings · 12m ago",
        banner_text="Collector attention needed",
        fingerprint="abc123",
        changed=True,
    )

    append_log(log_path, snapshot)

    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["fingerprint"] == "abc123"
    assert payload["page_state"] == "warning"
