from datetime import datetime
from unittest.mock import patch

import sys
from pathlib import Path

# Add repo root to path to allow imports from utils
repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root))

from utils.git_pulse_daily_synthesis import (
    build_block,
    upsert_block,
    upsert_clio_block,
    sync_to_clio,
    is_late_run,
    MARKER_START,
    MARKER_END,
    BLOCK_HEADING,
    FALLBACK_SUMMARY,
    synthesize,
    run,
    _extract_block_text,
    _would_clobber_real_summary,
    _clio_markers,
)


def test_build_block():
    dt = datetime(2026, 7, 5, 18, 30)
    summary = "Mock summary"
    block = build_block(summary, dt)

    assert MARKER_START in block
    assert MARKER_END in block
    assert BLOCK_HEADING in block
    assert "6:30 PM" in block
    assert summary in block


def test_upsert_block_appends_to_empty():
    dt = datetime(2026, 7, 5, 18, 30)
    content = ""
    summary = "New summary"
    new_content = upsert_block(content, summary, dt)

    assert MARKER_START in new_content
    assert MARKER_END in new_content
    assert summary in new_content


def test_upsert_block_appends_to_existing_text():
    dt = datetime(2026, 7, 5, 18, 30)
    content = "Some existing text.\n"
    summary = "New summary"
    new_content = upsert_block(content, summary, dt)

    assert new_content.startswith("Some existing text.\n\n")
    assert MARKER_START in new_content
    assert summary in new_content


def test_upsert_block_replaces_existing_block():
    dt2 = datetime(2026, 7, 5, 19, 00)
    content = f"Prefix\n\n{MARKER_START}\nOld summary\n{MARKER_END}\n\nSuffix"
    summary = "New summary"

    new_content = upsert_block(content, summary, dt2)

    assert "Prefix" in new_content
    assert "Suffix" in new_content
    assert "Old summary" not in new_content
    assert "New summary" in new_content
    assert new_content.count(MARKER_START) == 1


def test_is_late_run():
    # RUN_HOUR_FLOOR is 18
    assert is_late_run(datetime(2026, 7, 5, 1, 0)) is True
    assert is_late_run(datetime(2026, 7, 5, 17, 59)) is True
    assert is_late_run(datetime(2026, 7, 5, 18, 0)) is False
    assert is_late_run(datetime(2026, 7, 5, 23, 59)) is False


def test_synthesize_zero_rows():
    # Only header
    tsv_content = "local_day\tlocal_time\tutc_time\tdevice_id\tdevice_name\trepo\tbranch\tshort_sha\tsubject"
    result = synthesize(tsv_content)
    assert result == "No git activity found today."

    # Empty string
    result_empty = synthesize("")
    assert result_empty == "No git activity found today."


@patch("rebalance.ingest.config.get_gemini_api_key")
@patch("rebalance.ingest.querier._synthesize_gemini")
def test_synthesize_with_rows(mock_synthesize, mock_get_key):
    mock_get_key.return_value = "fake_key"
    mock_synthesize.return_value = "Mocked LLM summary"

    tsv_content = (
        "local_day\tlocal_time\tutc_time\tdevice_id\tdevice_name\trepo\tbranch\tshort_sha\tsubject\n"
        "2026-07-05\t10:00 UTC\t2026-07-05T10:00:00Z\tmac-mini\tMac Mini\trebalance-OS\tmain\ta1b2c3d\tfix: handle zero rows in view.sh\n"
    )
    result = synthesize(tsv_content)

    assert result == "Mocked LLM summary"
    mock_synthesize.assert_called_once()
    args, kwargs = mock_synthesize.call_args
    assert tsv_content in args[0]


# --- CLIO block logic ----------------------------------------------------

def test_upsert_clio_block_new_file():
    dt = datetime(2026, 7, 9, 18, 30)
    new_content = upsert_clio_block("", "Did some work", dt)

    assert "<!-- Git Pulse Daily Summary 2026-07-09 Start -->" in new_content
    assert "<!-- Git Pulse Daily Summary 2026-07-09 End -->" in new_content
    assert "2026-07-09" in new_content
    assert "Did some work" in new_content


def test_upsert_clio_block_new_day_preserves_prior_days():
    content = upsert_clio_block("", "Yesterday's summary", datetime(2026, 7, 8, 18, 30))
    new_content = upsert_clio_block(content, "Today's summary", datetime(2026, 7, 9, 18, 30))

    assert "Yesterday's summary" in new_content
    assert "Today's summary" in new_content
    assert "<!-- Git Pulse Daily Summary 2026-07-08 Start -->" in new_content
    assert "<!-- Git Pulse Daily Summary 2026-07-09 Start -->" in new_content


def test_upsert_clio_block_rerun_same_day_replaces_only_that_day():
    content = upsert_clio_block("", "Prior day summary", datetime(2026, 7, 8, 18, 0))
    content = upsert_clio_block(content, "First run summary", datetime(2026, 7, 9, 18, 0))

    new_content = upsert_clio_block(content, "Rerun summary", datetime(2026, 7, 9, 19, 0))

    assert "Prior day summary" in new_content
    assert "First run summary" not in new_content
    assert "Rerun summary" in new_content
    assert new_content.count("<!-- Git Pulse Daily Summary 2026-07-09 Start -->") == 1


# --- sync_to_clio ----------------------------------------------------------

@patch("rebalance.ingest.config.get_pulse_config")
def test_sync_to_clio_disabled_is_noop(mock_get_cfg):
    mock_get_cfg.return_value = {"git_pulse_clio_enabled": False}
    result = sync_to_clio("summary", datetime(2026, 7, 9, 18, 0))
    assert result == {"enabled": False}


@patch("rebalance.ingest.config.get_pulse_config")
def test_sync_to_clio_missing_target_path(mock_get_cfg):
    mock_get_cfg.return_value = {"git_pulse_clio_enabled": True, "pulse_target_path": None}
    result = sync_to_clio("summary", datetime(2026, 7, 9, 18, 0))
    assert result["enabled"] is True
    assert result["ok"] is False


@patch("rebalance.ingest.pulse._commit_and_push_if_changed")
@patch("rebalance.ingest.config.get_pulse_config")
def test_sync_to_clio_writes_and_commits(mock_get_cfg, mock_commit, tmp_path):
    (tmp_path / ".git").mkdir()
    mock_get_cfg.return_value = {
        "git_pulse_clio_enabled": True,
        "pulse_target_path": str(tmp_path),
        "git_pulse_clio_subdir": "CLIO",
        "git_pulse_clio_filename": "git-pulse-daily-log.md",
    }
    mock_commit.return_value = {"wrote_file": True, "committed": True, "pushed": True}

    result = sync_to_clio("Today's summary", datetime(2026, 7, 9, 18, 0))

    assert result["ok"] is True
    assert result["file_rel"] == "CLIO/git-pulse-daily-log.md"
    mock_commit.assert_called_once()
    _, kwargs = mock_commit.call_args
    assert kwargs["file_rel"] == "CLIO/git-pulse-daily-log.md"
    assert "Today's summary" in kwargs["new_content"]
    assert kwargs["push"] is True


@patch("rebalance.ingest.config.get_pulse_config")
def test_sync_to_clio_dry_run_writes_nothing(mock_get_cfg, tmp_path):
    (tmp_path / ".git").mkdir()
    mock_get_cfg.return_value = {
        "git_pulse_clio_enabled": True,
        "pulse_target_path": str(tmp_path),
        "git_pulse_clio_subdir": "CLIO",
        "git_pulse_clio_filename": "git-pulse-daily-log.md",
    }

    result = sync_to_clio("Summary", datetime(2026, 7, 9, 18, 0), dry_run=True)

    assert result["dry_run"] is True
    assert not (tmp_path / "CLIO" / "git-pulse-daily-log.md").exists()


# --- run() decoupling -------------------------------------------------------

@patch("utils.git_pulse_daily_synthesis.sync_to_clio")
@patch("utils.git_pulse_daily_synthesis.synthesize")
@patch("utils.git_pulse_daily_synthesis.collect_today_activity")
@patch("rebalance.ingest.config.get_pulse_config")
@patch("utils.git_pulse_daily_synthesis.vault_ready")
def test_run_writes_to_clio_when_vault_not_ready(
    mock_vault_ready, mock_get_cfg, mock_collect, mock_synthesize, mock_sync_clio
):
    mock_vault_ready.return_value = False
    mock_get_cfg.return_value = {"git_pulse_clio_enabled": True}
    mock_collect.return_value = ("tsv data", 0)
    mock_synthesize.return_value = "A summary"

    now = datetime(2026, 7, 9, 18, 30)
    code = run(now=now)

    assert code == 0
    mock_synthesize.assert_called_once()
    mock_sync_clio.assert_called_once_with("A summary", now, dry_run=False)


@patch("utils.git_pulse_daily_synthesis.synthesize")
@patch("utils.git_pulse_daily_synthesis.collect_today_activity")
@patch("rebalance.ingest.config.get_pulse_config")
@patch("utils.git_pulse_daily_synthesis.vault_ready")
def test_run_skips_entirely_with_no_destination(
    mock_vault_ready, mock_get_cfg, mock_collect, mock_synthesize
):
    mock_vault_ready.return_value = False
    mock_get_cfg.return_value = {"git_pulse_clio_enabled": False}

    code = run(now=datetime(2026, 7, 9, 18, 30))

    assert code == 0
    mock_collect.assert_not_called()
    mock_synthesize.assert_not_called()


# --- no-clobber guard (GH-129 follow-up #3) ----------------------------------
# A later, transient zero-row rerun on the same day must not overwrite an
# earlier successful run's real summary with the empty-activity fallback.

def test_extract_block_text_present():
    content = f"Prefix\n{MARKER_START}\nBlock body\n{MARKER_END}\nSuffix"
    assert _extract_block_text(content, MARKER_START, MARKER_END) == "\nBlock body\n"


def test_extract_block_text_absent():
    assert _extract_block_text("No markers here", MARKER_START, MARKER_END) is None


def test_extract_block_text_with_clio_date_scoped_markers():
    start, end = _clio_markers("2026-07-16")
    content = f"{start}\nBody\n{end}\n"
    assert _extract_block_text(content, start, end) == "\nBody\n"


def test_would_clobber_real_summary_true_for_real_block_and_fallback_new():
    existing = "\n## Heading\n*stamp*\n\nDid real work today.\n"
    assert _would_clobber_real_summary(existing, FALLBACK_SUMMARY) is True


def test_would_clobber_real_summary_false_when_no_existing_block():
    assert _would_clobber_real_summary(None, FALLBACK_SUMMARY) is False


def test_would_clobber_real_summary_false_when_existing_block_is_fallback():
    existing = f"\n## Heading\n*stamp*\n\n{FALLBACK_SUMMARY}\n"
    assert _would_clobber_real_summary(existing, FALLBACK_SUMMARY) is False


def test_would_clobber_real_summary_false_when_existing_block_empty():
    assert _would_clobber_real_summary("   \n", FALLBACK_SUMMARY) is False


def test_would_clobber_real_summary_false_when_new_summary_is_real():
    existing = "\n## Heading\n*stamp*\n\nDid real work today.\n"
    assert _would_clobber_real_summary(existing, "Fresh new content") is False


# --- run(): vault-write no-clobber guard -------------------------------------

@patch("utils.git_pulse_daily_synthesis.synthesize")
@patch("utils.git_pulse_daily_synthesis.collect_today_activity")
@patch("rebalance.ingest.config.get_pulse_config")
@patch("utils.git_pulse_daily_synthesis.vault_ready")
def test_run_zero_row_rerun_does_not_clobber_existing_real_summary(
    mock_vault_ready, mock_get_cfg, mock_collect, mock_synthesize, tmp_path, capsys
):
    today_file = tmp_path / "0. Today's Notes.md"
    real_block = build_block("Shipped GH-129 follow-up.", datetime(2026, 7, 16, 10, 0))
    original_content = f"Prefix text\n\n{real_block}"
    today_file.write_text(original_content, encoding="utf-8")

    mock_vault_ready.return_value = True
    mock_get_cfg.return_value = {"git_pulse_clio_enabled": False}
    mock_collect.return_value = ("header only", 0)
    mock_synthesize.return_value = FALLBACK_SUMMARY

    with patch("utils.git_pulse_daily_synthesis.TODAY_FILE", today_file):
        code = run(now=datetime(2026, 7, 16, 20, 0))

    assert code == 0
    assert today_file.read_text(encoding="utf-8") == original_content
    out = capsys.readouterr().out
    assert "SKIP: zero-row rerun would clobber an existing non-empty summary" in out


@patch("utils.git_pulse_daily_synthesis.synthesize")
@patch("utils.git_pulse_daily_synthesis.collect_today_activity")
@patch("rebalance.ingest.config.get_pulse_config")
@patch("utils.git_pulse_daily_synthesis.vault_ready")
def test_run_first_zero_row_write_of_day_still_writes_fallback(
    mock_vault_ready, mock_get_cfg, mock_collect, mock_synthesize, tmp_path
):
    """No existing block yet — the documented first-write-of-the-day behavior
    must be completely unaffected by the new guard."""
    today_file = tmp_path / "0. Today's Notes.md"
    today_file.write_text("Just some prefix text.\n", encoding="utf-8")

    mock_vault_ready.return_value = True
    mock_get_cfg.return_value = {"git_pulse_clio_enabled": False}
    mock_collect.return_value = ("header only", 0)
    mock_synthesize.return_value = FALLBACK_SUMMARY

    with patch("utils.git_pulse_daily_synthesis.TODAY_FILE", today_file):
        code = run(now=datetime(2026, 7, 16, 20, 0))

    assert code == 0
    new_content = today_file.read_text(encoding="utf-8")
    assert MARKER_START in new_content
    assert FALLBACK_SUMMARY in new_content


@patch("utils.git_pulse_daily_synthesis.synthesize")
@patch("utils.git_pulse_daily_synthesis.collect_today_activity")
@patch("rebalance.ingest.config.get_pulse_config")
@patch("utils.git_pulse_daily_synthesis.vault_ready")
def test_run_rerun_over_existing_fallback_block_still_writes(
    mock_vault_ready, mock_get_cfg, mock_collect, mock_synthesize, tmp_path
):
    """An existing block that is ALREADY the fallback is not 'real content' —
    a fresh zero-row rerun must still be free to rewrite it (e.g. refresh the
    timestamp); the guard must not treat this as a clobber."""
    today_file = tmp_path / "0. Today's Notes.md"
    old_block = build_block(FALLBACK_SUMMARY, datetime(2026, 7, 16, 9, 0))
    today_file.write_text(f"Prefix\n\n{old_block}", encoding="utf-8")

    mock_vault_ready.return_value = True
    mock_get_cfg.return_value = {"git_pulse_clio_enabled": False}
    mock_collect.return_value = ("header only", 0)
    mock_synthesize.return_value = FALLBACK_SUMMARY

    with patch("utils.git_pulse_daily_synthesis.TODAY_FILE", today_file):
        code = run(now=datetime(2026, 7, 16, 20, 0))

    assert code == 0
    new_content = today_file.read_text(encoding="utf-8")
    assert MARKER_START in new_content
    assert FALLBACK_SUMMARY in new_content


# --- sync_to_clio(): CLIO-write no-clobber guard -----------------------------

@patch("rebalance.ingest.pulse._commit_and_push_if_changed")
@patch("rebalance.ingest.config.get_pulse_config")
def test_sync_to_clio_zero_row_rerun_does_not_clobber_existing_real_summary(
    mock_get_cfg, mock_commit, tmp_path, capsys
):
    (tmp_path / ".git").mkdir()
    now = datetime(2026, 7, 16, 20, 0)
    existing_content = upsert_clio_block("", "Real work landed today.", now)
    clio_file = tmp_path / "CLIO" / "git-pulse-daily-log.md"
    clio_file.parent.mkdir(parents=True)
    clio_file.write_text(existing_content, encoding="utf-8")

    mock_get_cfg.return_value = {
        "git_pulse_clio_enabled": True,
        "pulse_target_path": str(tmp_path),
        "git_pulse_clio_subdir": "CLIO",
        "git_pulse_clio_filename": "git-pulse-daily-log.md",
    }

    result = sync_to_clio(FALLBACK_SUMMARY, now)

    assert result["ok"] is True
    assert result.get("skipped") == "would_clobber"
    mock_commit.assert_not_called()
    assert clio_file.read_text(encoding="utf-8") == existing_content
    out = capsys.readouterr().out
    assert "SKIP: zero-row rerun would clobber an existing non-empty summary" in out
