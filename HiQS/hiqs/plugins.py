"""Plugin contract and discovery for HiQS sources."""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib import metadata
from typing import Any, Callable, Iterable


Conn = Any
Config = Any


@dataclass(frozen=True)
class Source:
    name: str
    fetch: Callable[[Conn, Config], SyncReport]
    docs: Callable[[Conn], Iterable[Doc]] | None = None
    candidates: Callable[[Conn, Config], Iterable[Candidate]] | None = None


@dataclass(frozen=True)
class SyncReport:
    """Result of a source sync; counts keys are inserted, updated, unchanged, skipped, rejected, pruned."""

    counts: dict[str, int]
    errors: list[str] = field(default_factory=list)
    meta: dict = field(default_factory=dict)
    units_ok: tuple[str, ...] = ()


@dataclass(frozen=True)
class Doc:
    source: str
    id: str
    title: str
    body: str
    url: str = ""
    ts: str = ""
    project: str = ""
    author: str = ""
    unit: str = ""


@dataclass(frozen=True)
class Candidate:
    title: str
    source: str
    evidence: str
    why: str
    ts: str
    url: str = ""
    author: str = ""
    owed_by: str = ""
    due: str = ""


def discover_sources() -> list[Source]:
    """Load source objects advertised through the ``hiqs.sources`` entry-point group."""
    return [entry_point.load() for entry_point in metadata.entry_points(group="hiqs.sources")]
