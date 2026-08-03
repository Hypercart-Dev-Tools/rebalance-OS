"""A third-party-shaped source used to exercise the public plugin seam only."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from hiqs.plugins import Candidate, Doc, Source, SyncReport


NETWORK_TIMEOUT_SECONDS = 5


def fetch(connection: Any, config: Mapping[str, Any]) -> SyncReport:
    """Fetch one complete unit, reconciling only that unit after success.

    ``fetch_unit`` is injected so the test can prove a timeout is supplied
    without allowing a test plugin to make a real network request.
    """
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS fake_source_records(
          unit TEXT NOT NULL,
          id TEXT NOT NULL,
          title TEXT NOT NULL,
          body TEXT NOT NULL,
          PRIMARY KEY (unit, id))
        """
    )
    fetched = config["fetch_unit"](timeout=NETWORK_TIMEOUT_SECONDS)
    unit = fetched["unit"]
    records = list(fetched["records"])
    existing_ids = {
        row[0]
        for row in connection.execute(
            "SELECT id FROM fake_source_records WHERE unit = ?", (unit,)
        )
    }
    current_ids = {record[0] for record in records}

    with connection:
        connection.executemany(
            """
            INSERT INTO fake_source_records(unit, id, title, body) VALUES (?, ?, ?, ?)
            ON CONFLICT(unit, id) DO UPDATE SET title = excluded.title, body = excluded.body
            """,
            [(unit, record_id, title, body) for record_id, title, body in records],
        )
        if current_ids:
            placeholders = ", ".join("?" for _ in current_ids)
            connection.execute(
                f"DELETE FROM fake_source_records WHERE unit = ? AND id NOT IN ({placeholders})",
                (unit, *sorted(current_ids)),
            )
        else:
            connection.execute("DELETE FROM fake_source_records WHERE unit = ?", (unit,))

    config["watermark"]["last_completed_unit"] = unit
    return SyncReport(
        counts={"inserted": len(current_ids - existing_ids), "pruned": len(existing_ids - current_ids)},
        meta={"timeout_s": NETWORK_TIMEOUT_SECONDS},
    )


def docs(connection: Any) -> Iterable[Doc]:
    """Expose raw records through the public document-provider contract."""
    rows = connection.execute(
        "SELECT unit, id, title, body FROM fake_source_records ORDER BY unit, id"
    ).fetchall()
    return [
        Doc(source="fake", id=f"{unit}:{record_id}", title=title, body=body)
        for unit, record_id, title, body in rows
    ]


def candidates(connection: Any, _config: Mapping[str, Any]) -> Iterable[Candidate]:
    """Return fully attested candidates, never bare ranking input."""
    return [
        Candidate(
            title=document.title,
            source=document.source,
            evidence=f"fake record {document.id}",
            why="The fake source exposes every record as an actionable receipt.",
            ts="2026-08-03T00:00:00Z",
        )
        for document in docs(connection)
    ]


SOURCE = Source(name="fake", fetch=fetch, docs=docs, candidates=candidates)
