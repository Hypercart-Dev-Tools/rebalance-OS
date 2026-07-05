import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock

import sys
from pathlib import Path

# Add repo root to path to allow imports from utils
repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root))

from utils.git_pulse_daily_synthesis import (
    build_block,
    upsert_block,
    is_late_run,
    MARKER_START,
    MARKER_END,
    BLOCK_HEADING,
    synthesize,
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
    dt1 = datetime(2026, 7, 5, 18, 30)
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
