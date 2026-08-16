"""Tests for src/rebalance/ingest/sleuth_grouping.py."""

from __future__ import annotations

import sqlite3


from rebalance.ingest.sleuth_grouping import (
    ReminderGroup,
    _does_reminder_match_client,
    _github_label_from_url,
    extract_task_text,
    find_connections,
    group_reminders,
    load_active_reminders,
    load_client_mapping,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _reminder(
    rid: str = "r1",
    channel: str = "general",
    channel_id: str | None = None,
    text: str = "follow up",
    urls: list[str] | None = None,
    state: str = "scheduled",
) -> dict:
    return {
        "reminder_id":          rid,
        "original_channel_name": channel,
        "original_channel_id":  channel_id,
        "reminder_message_text": text,
        "github_urls":          urls or [],
        "state":                state,
        "should_post_on":       None,
        "created_on":           None,
        "task_text":            text,
    }


BINOID_CLIENT = {
    "ClientName":        "Binoid",
    "Aliases":           ["binoid"],
    "ChannelIDs":        [],
    "ChannelNamePatterns": ["binoid"],
    "GitHubRepoPatterns": ["binoid"],
}


# ---------------------------------------------------------------------------
# extract_task_text
# ---------------------------------------------------------------------------

class TestExtractTaskText:
    def test_key_task_block(self):
        text = "please follow up:\n\nKey task(s):\n• Fix the login bug\nExtra stuff"
        assert extract_task_text(text) == "Fix the login bug"

    def test_key_task_block_no_bullet(self):
        text = "Key task(s):\n  Do the thing"
        assert extract_task_text(text) == "Do the thing"

    def test_strips_follow_up_prefix(self):
        text = "<@U032TCHJ8> - please follow up on <https://slack.com/p123>:\n> Build the widget"
        result = extract_task_text(text)
        assert "Build the widget" in result
        assert "please follow up" not in result

    def test_strips_slack_user_mentions(self):
        text = "<@U032TCHJ8>, <@U050SAU372L> - please follow up on <https://slack.com/p>:\nDo the thing"
        result = extract_task_text(text)
        assert "<@" not in result

    def test_strips_slack_link_tokens_keeps_label(self):
        text = "Key task(s):\n• See <https://example.com|this PR>"
        result = extract_task_text(text)
        assert "this PR" in result
        assert "https://" not in result

    def test_strips_mrkdwn(self):
        text = "Key task(s):\n• *Bold task* and _italic_ and `code`"
        result = extract_task_text(text)
        assert "*" not in result
        assert "_" not in result
        assert "`" not in result

    def test_truncates_at_140(self):
        long_text = "Key task(s):\n• " + "x" * 200
        result = extract_task_text(long_text)
        assert len(result) <= 141  # 140 + ellipsis char

    def test_empty_string(self):
        assert extract_task_text("") == ""

    def test_non_string_returns_empty(self):
        assert extract_task_text(None) == ""  # type: ignore[arg-type]

    def test_plain_message(self):
        result = extract_task_text("Just do this thing")
        assert result == "Just do this thing"


# ---------------------------------------------------------------------------
# _github_label_from_url
# ---------------------------------------------------------------------------

class TestGithubLabelFromUrl:
    def test_pull_request(self):
        assert _github_label_from_url("https://github.com/owner/repo/pull/42") == "PR #42"

    def test_issue(self):
        assert _github_label_from_url("https://github.com/owner/repo/issues/7") == "#7"

    def test_no_match_returns_url(self):
        url = "https://github.com/owner/repo"
        assert _github_label_from_url(url) == url

    def test_empty_string(self):
        assert _github_label_from_url("") == ""

    def test_case_insensitive(self):
        assert _github_label_from_url("https://github.com/X/Y/PULL/99") == "PR #99"


# ---------------------------------------------------------------------------
# _does_reminder_match_client
# ---------------------------------------------------------------------------

class TestDoesReminderMatchClient:
    def test_channel_name_pattern_match(self):
        r = _reminder(channel="clients-1-binoid-devops")
        assert _does_reminder_match_client(r, BINOID_CLIENT)

    def test_channel_name_no_match(self):
        r = _reminder(channel="1-neochrome-team-tech")
        assert not _does_reminder_match_client(r, BINOID_CLIENT)

    def test_channel_id_match(self):
        client = {**BINOID_CLIENT, "ChannelIDs": ["C123ABC"]}
        r = _reminder(channel_id="C123ABC")
        assert _does_reminder_match_client(r, client)

    def test_github_repo_pattern_match(self):
        r = _reminder(urls=["https://github.com/BinoidCBD/some-repo/issues/5"])
        assert _does_reminder_match_client(r, BINOID_CLIENT)

    def test_github_repo_no_match(self):
        r = _reminder(urls=["https://github.com/OtherOrg/some-repo/issues/5"])
        assert not _does_reminder_match_client(r, BINOID_CLIENT)

    def test_empty_client(self):
        r = _reminder(channel="binoid-something")
        assert not _does_reminder_match_client(r, {"ClientName": "X"})


# ---------------------------------------------------------------------------
# group_reminders
# ---------------------------------------------------------------------------

class TestGroupReminders:
    def test_empty_input(self):
        assert group_reminders([]) == []

    def test_single_reminder_becomes_other(self):
        groups = group_reminders([_reminder()])
        assert len(groups) == 1
        assert groups[0].kind == "other"

    def test_github_grouping_by_shared_url(self):
        url = "https://github.com/org/repo/issues/1"
        r1 = _reminder("r1", urls=[url])
        r2 = _reminder("r2", urls=[url])
        r3 = _reminder("r3")
        groups = group_reminders([r1, r2, r3], clients=[])
        gh = next((g for g in groups if g.kind == "github"), None)
        assert gh is not None
        assert len(gh.reminders) == 2
        assert gh.label == "#1"

    def test_github_transitive_union(self):
        r1 = _reminder("r1", urls=["https://github.com/o/r/issues/1"])
        r2 = _reminder("r2", urls=["https://github.com/o/r/issues/1",
                                    "https://github.com/o/r/issues/2"])
        r3 = _reminder("r3", urls=["https://github.com/o/r/issues/2"])
        groups = group_reminders([r1, r2, r3], clients=[])
        gh = next(g for g in groups if g.kind == "github")
        assert len(gh.reminders) == 3

    def test_client_grouping(self):
        r1 = _reminder("r1", channel="clients-1-binoid-devops")
        r2 = _reminder("r2", channel="binoid-ltvera")
        r3 = _reminder("r3", channel="1-neochrome-team-tech")
        groups = group_reminders([r1, r2, r3], clients=[BINOID_CLIENT])
        client_grp = next((g for g in groups if g.kind == "client"), None)
        assert client_grp is not None
        assert client_grp.label == "Binoid"
        assert len(client_grp.reminders) == 2
        # neochrome reminder is not in the client group
        assert all(r["reminder_id"] != "r3" for r in client_grp.reminders)

    def test_channel_grouping(self):
        r1 = _reminder("r1", channel="general")
        r2 = _reminder("r2", channel="general")
        r3 = _reminder("r3", channel="random")
        groups = group_reminders([r1, r2, r3], clients=[])
        channel_grp = next((g for g in groups if g.kind == "channel"), None)
        assert channel_grp is not None
        assert channel_grp.label == "#general"
        assert len(channel_grp.reminders) == 2

    def test_lone_channel_dissolves_to_other(self):
        r1 = _reminder("r1", channel="only-me")
        groups = group_reminders([r1], clients=[])
        assert groups[0].kind == "other"

    def test_github_takes_priority_over_client(self):
        url = "https://github.com/BinoidCBD/repo/issues/5"
        r1 = _reminder("r1", channel="clients-1-binoid-devops", urls=[url])
        r2 = _reminder("r2", channel="clients-1-binoid-devops")
        groups = group_reminders([r1, r2], clients=[BINOID_CLIENT])
        # r1 should be in github group, r2 in client group
        gh_grp = next((g for g in groups if g.kind == "github"), None)
        client_grp = next((g for g in groups if g.kind == "client"), None)
        assert gh_grp is not None and client_grp is not None
        assert any(r["reminder_id"] == "r1" for r in gh_grp.reminders)
        assert any(r["reminder_id"] == "r2" for r in client_grp.reminders)

    def test_groups_sorted_by_size(self):
        # 3 reminders in channel-a, 1 in client → client group smaller → sorted last
        reminders = [
            _reminder("a1", channel="big-chan"),
            _reminder("a2", channel="big-chan"),
            _reminder("a3", channel="big-chan"),
            _reminder("b1", channel="clients-1-binoid-devops"),
        ]
        groups = group_reminders(reminders, clients=[BINOID_CLIENT])
        non_other = [g for g in groups if g.kind != "other"]
        sizes = [len(g.reminders) for g in non_other]
        assert sizes == sorted(sizes, reverse=True)

    def test_other_always_last(self):
        r_lone = _reminder("lone", channel="unique-chan")
        r_grp1 = _reminder("g1", channel="shared")
        r_grp2 = _reminder("g2", channel="shared")
        groups = group_reminders([r_lone, r_grp1, r_grp2], clients=[])
        assert groups[-1].kind == "other"
        assert groups[-1].reminders[0]["reminder_id"] == "lone"

    def test_returns_reminder_group_instances(self):
        groups = group_reminders([_reminder()], clients=[])
        assert all(isinstance(g, ReminderGroup) for g in groups)

    def test_no_double_placement(self):
        url = "https://github.com/o/r/issues/1"
        r = _reminder("r1", channel="clients-1-binoid-devops", urls=[url])
        groups = group_reminders([r], clients=[BINOID_CLIENT])
        total = sum(len(g.reminders) for g in groups)
        assert total == 1


# ---------------------------------------------------------------------------
# find_connections
# ---------------------------------------------------------------------------

class TestFindConnections:
    def test_shared_github_url(self):
        url = "https://github.com/o/r/issues/1"
        target = _reminder("t", channel="chan-a", urls=[url])
        other  = _reminder("o", channel="chan-b", urls=[url])
        unrelated = _reminder("u", channel="chan-c")
        result = find_connections(target, [target, other, unrelated], clients=[])
        ids = [r["reminder_id"] for r in result]
        assert "o" in ids
        assert "u" not in ids
        assert "t" not in ids

    def test_same_client(self):
        target = _reminder("t", channel="clients-1-binoid-devops")
        other  = _reminder("o", channel="binoid-ltvera")
        unrelated = _reminder("u", channel="1-neochrome-team-tech")
        result = find_connections(target, [target, other, unrelated], clients=[BINOID_CLIENT])
        ids = [r["reminder_id"] for r in result]
        assert "o" in ids
        assert "u" not in ids

    def test_same_channel(self):
        target = _reminder("t", channel="general")
        other  = _reminder("o", channel="general")
        unrelated = _reminder("u", channel="random")
        result = find_connections(target, [target, other, unrelated], clients=[])
        ids = [r["reminder_id"] for r in result]
        assert "o" in ids
        assert "u" not in ids

    def test_never_returns_self(self):
        target = _reminder("t", channel="general")
        result = find_connections(target, [target], clients=[])
        assert result == []

    def test_empty_list(self):
        target = _reminder("t")
        assert find_connections(target, [], clients=[]) == []


# ---------------------------------------------------------------------------
# load_active_reminders (in-memory SQLite)
# ---------------------------------------------------------------------------

class TestLoadActiveReminders:
    def _make_db(self) -> sqlite3.Connection:
        conn = sqlite3.connect(":memory:")
        conn.execute(
            """
            CREATE TABLE sleuth_reminders (
                reminder_id TEXT PRIMARY KEY,
                workspace_name TEXT, state TEXT, is_active INTEGER,
                created_on TEXT, should_post_on TEXT, reminder_message_text TEXT,
                ignore_snooze INTEGER, assignee_id TEXT, original_sender_id TEXT,
                target_channel_id TEXT, original_channel_id TEXT,
                original_channel_name TEXT, original_message_id TEXT,
                original_thread_ts TEXT, github_urls_json TEXT,
                first_seen_at TEXT, last_seen_at TEXT, last_synced_at TEXT
            )
            """
        )
        return conn

    def _insert(self, conn, rid, channel="general", text="do the thing", active=1, urls="[]"):
        conn.execute(
            "INSERT INTO sleuth_reminders VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (rid, "ws", "scheduled", active, None, None, text, 0,
             None, None, None, None, channel, None, None, urls,
             "2026-01-01", "2026-01-01", "2026-01-01"),
        )
        conn.commit()

    def test_returns_only_active(self):
        conn = self._make_db()
        self._insert(conn, "a1", active=1)
        self._insert(conn, "a2", active=0)
        rows = load_active_reminders(conn)
        assert len(rows) == 1
        assert rows[0]["reminder_id"] == "a1"

    def test_github_urls_parsed(self):
        conn = self._make_db()
        self._insert(conn, "r1", urls='["https://github.com/o/r/issues/1"]')
        rows = load_active_reminders(conn)
        assert rows[0]["github_urls"] == ["https://github.com/o/r/issues/1"]

    def test_invalid_json_urls_defaults_to_empty(self):
        conn = self._make_db()
        self._insert(conn, "r1", urls="not-json")
        rows = load_active_reminders(conn)
        assert rows[0]["github_urls"] == []

    def test_task_text_populated(self):
        conn = self._make_db()
        self._insert(conn, "r1", text="Key task(s):\n• Ship the feature")
        rows = load_active_reminders(conn)
        assert rows[0]["task_text"] == "Ship the feature"

    def test_empty_table(self):
        conn = self._make_db()
        assert load_active_reminders(conn) == []


# ---------------------------------------------------------------------------
# load_client_mapping
# ---------------------------------------------------------------------------

class TestLoadClientMapping:
    def test_returns_list(self):
        mapping = load_client_mapping()
        assert isinstance(mapping, list)

    def test_missing_path_returns_empty(self, tmp_path):
        result = load_client_mapping(tmp_path / "nonexistent.json")
        assert result == []

    def test_invalid_json_returns_empty(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("not-json", encoding="utf-8")
        assert load_client_mapping(bad) == []

    def test_valid_file_parsed(self, tmp_path):
        mapping_file = tmp_path / "mapping.json"
        mapping_file.write_text(
            '{"clients": [{"ClientName": "Acme", "ChannelNamePatterns": ["acme"]}]}',
            encoding="utf-8",
        )
        result = load_client_mapping(mapping_file)
        assert len(result) == 1
        assert result[0]["ClientName"] == "Acme"
