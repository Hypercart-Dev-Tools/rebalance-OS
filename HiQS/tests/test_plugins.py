from dataclasses import FrozenInstanceError, fields

import pytest

from hiqs.plugins import Candidate, Doc, Source, SyncReport, discover_sources


def _fetch(_conn, _config):
    return SyncReport(counts={})


@pytest.mark.parametrize(
    ("record", "field_names"),
    [
        (Source(name="test", fetch=_fetch), ["name", "fetch", "docs", "candidates"]),
        (SyncReport(counts={}), ["counts", "errors", "meta", "units_ok"]),
        (Doc(source="test", id="1", title="title", body="body"), ["source", "id", "title", "body", "url", "ts", "project", "author", "unit"]),
        (Candidate(title="title", source="test", evidence="evidence", why="why", ts="2026-08-03"), ["title", "source", "evidence", "why", "ts", "url", "author", "owed_by", "due"]),
    ],
)
def test_plugin_records_are_frozen_with_contract_fields(record, field_names):
    assert [item.name for item in fields(record)] == field_names
    with pytest.raises(FrozenInstanceError):
        record.source = "changed"


def test_optional_contract_defaults():
    assert SyncReport(counts={}).errors == []
    assert SyncReport(counts={}).meta == {}
    assert SyncReport(counts={}).units_ok == ()
    assert Doc(source="test", id="1", title="title", body="body").author == ""
    assert Doc(source="test", id="1", title="title", body="body").unit == ""
    candidate = Candidate(title="title", source="test", evidence="evidence", why="why", ts="2026-08-03")
    assert (candidate.url, candidate.author, candidate.owed_by, candidate.due) == ("", "", "", "")


def test_sync_report_counts_document_reconciliation_key():
    assert "pruned" in SyncReport.__doc__


def test_discover_sources_is_empty_without_registered_plugins(monkeypatch):
    monkeypatch.setattr("hiqs.plugins.metadata.entry_points", lambda *, group: ())
    assert discover_sources() == []
