"""Unit tests for utils/obsidian_daily_sync.py (GH-112).

Covers the four contract-critical behaviors: idempotent block upsert, exact
sentinel matching that preserves surrounding human notes, Gemini-failure abort
(no vault write), and the post-midnight late-run skip.
"""

import sys
from datetime import datetime
from pathlib import Path

import pytest

# utils/ is not a package; the module lives there and reuses obsidian_daily_rollover.
UTILS = Path(__file__).resolve().parent.parent / "utils"
sys.path.insert(0, str(UTILS))
import obsidian_daily_sync as ods  # noqa: E402

# Fixed run-time for byte-stable block assertions (18:00 -> "6:00 PM").
GEN_AT = datetime(2026, 7, 4, 18, 0)


# --- upsert / idempotency ----------------------------------------------------
def test_upsert_appends_when_no_block():
    content = "# 0. Today's Notes\n\nSome manual notes.\n"
    out = ods.upsert_block(content, "Summary A", GEN_AT)
    assert out.startswith(content)  # manual notes preserved verbatim at the top
    assert out.count(ods.MARKER_START) == 1
    assert out.count(ods.MARKER_END) == 1
    assert "Summary A" in out


def test_upsert_replaces_in_place_and_is_idempotent():
    content = "# 0. Today's Notes\n\nManual note above.\n"
    once = ods.upsert_block(content, "First summary", GEN_AT)
    twice = ods.upsert_block(once, "Second summary", GEN_AT)
    # Exactly one block after replacement — never a second appended.
    assert twice.count(ods.MARKER_START) == 1
    assert twice.count(ods.MARKER_END) == 1
    assert "Second summary" in twice
    assert "First summary" not in twice
    # Re-running with the SAME summary is a fixed point (byte-stable).
    assert ods.upsert_block(twice, "Second summary", GEN_AT) == twice


def test_upsert_preserves_manual_notes_above():
    manual = "# 0. Today's Notes\n\n- bought milk\n- called Jose\n"
    out = ods.upsert_block(manual, "AI text", GEN_AT)
    # Everything the user typed stays byte-identical as the prefix.
    assert out[: len(manual)] == manual


def test_upsert_collapses_accidental_duplicate_blocks():
    dup = (
        "notes\n"
        f"{ods.MARKER_START}\nold one\n{ods.MARKER_END}\n"
        f"{ods.MARKER_START}\nold two\n{ods.MARKER_END}\n"
    )
    out = ods.upsert_block(dup, "fresh", GEN_AT)
    assert out.count(ods.MARKER_START) == 1
    assert out.count(ods.MARKER_END) == 1
    assert "fresh" in out and "old one" not in out and "old two" not in out


# --- auto-generated reminder line --------------------------------------------
@pytest.mark.parametrize("hour,minute,expected", [
    (18, 0, "6:00 PM"), (6, 5, "6:05 AM"), (0, 0, "12:00 AM"),
    (12, 0, "12:00 PM"), (23, 55, "11:55 PM"),
])
def test_format_time(hour, minute, expected):
    assert ods._format_time(datetime(2026, 7, 4, hour, minute)) == expected


def test_block_carries_auto_generated_reminder():
    block = ods.build_block("body text", datetime(2026, 7, 4, 18, 0))
    assert "*Auto-generated at 6:00 PM.*" in block
    # Reminder sits under the heading, above the summary body.
    assert block.index(ods.BLOCK_HEADING) < block.index("Auto-generated") < block.index("body text")


# --- late-run guard ----------------------------------------------------------
@pytest.mark.parametrize("hour,expected", [(0, True), (2, True), (11, True), (17, True),
                                           (18, False), (19, False), (23, False)])
def test_is_late_run(hour, expected):
    assert ods.is_late_run(datetime(2026, 7, 4, hour, 30)) is expected


def test_run_skips_late_catch_up(tmp_path, monkeypatch):
    target = tmp_path / "0. Today's Notes.md"
    target.write_text("manual\n", encoding="utf-8")
    monkeypatch.setattr(ods, "TODAY_FILE", target)
    monkeypatch.setattr(ods, "vault_ready", lambda: True)
    # Guard must fire BEFORE any signal collection / synthesis.
    monkeypatch.setattr(ods, "collect_today_activity", lambda: pytest.fail("collected on late run"))
    monkeypatch.setattr(ods, "synthesize", lambda a: pytest.fail("synthesized on late run"))

    rc = ods.run(now=datetime(2026, 7, 5, 2, 5))  # 02:05 next morning
    assert rc == 0
    assert target.read_text(encoding="utf-8") == "manual\n"  # untouched


# --- Gemini-failure abort ----------------------------------------------------
def test_run_aborts_without_write_when_gemini_fails(tmp_path, monkeypatch):
    target = tmp_path / "0. Today's Notes.md"
    original = "# 0. Today's Notes\n\nmanual\n"
    target.write_text(original, encoding="utf-8")
    monkeypatch.setattr(ods, "TODAY_FILE", target)
    monkeypatch.setattr(ods, "vault_ready", lambda: True)
    monkeypatch.setattr(ods, "collect_today_activity", lambda: {"gh_commits": []})
    monkeypatch.setattr(ods, "synthesize", lambda a: None)  # Gemini unavailable/failed

    rc = ods.run(now=datetime(2026, 7, 4, 18, 30))
    assert rc == 0
    assert target.read_text(encoding="utf-8") == original  # nothing written


# --- happy path --------------------------------------------------------------
def test_run_writes_block_and_preserves_notes(tmp_path, monkeypatch):
    target = tmp_path / "0. Today's Notes.md"
    manual = "# 0. Today's Notes\n\n- manual note\n"
    target.write_text(manual, encoding="utf-8")
    monkeypatch.setattr(ods, "TODAY_FILE", target)
    monkeypatch.setattr(ods, "vault_ready", lambda: True)
    monkeypatch.setattr(ods, "collect_today_activity", lambda: {"gh_items": ["x"]})
    monkeypatch.setattr(ods, "synthesize", lambda a: "Shipped GH-112 today.")

    rc = ods.run(now=datetime(2026, 7, 4, 19, 0))
    assert rc == 0
    out = target.read_text(encoding="utf-8")
    assert out.startswith(manual)  # human notes intact at the top
    assert out.count(ods.MARKER_START) == 1
    assert "Shipped GH-112 today." in out


def test_run_dry_run_does_not_write(tmp_path, monkeypatch, capsys):
    target = tmp_path / "0. Today's Notes.md"
    original = "manual\n"
    target.write_text(original, encoding="utf-8")
    monkeypatch.setattr(ods, "TODAY_FILE", target)
    monkeypatch.setattr(ods, "vault_ready", lambda: True)
    monkeypatch.setattr(ods, "collect_today_activity", lambda: {})
    monkeypatch.setattr(ods, "synthesize", lambda a: "preview text")

    rc = ods.run(dry_run=True, now=datetime(2026, 7, 4, 20, 0))
    assert rc == 0
    assert target.read_text(encoding="utf-8") == original  # unchanged
    assert "preview text" in capsys.readouterr().out  # but shown
