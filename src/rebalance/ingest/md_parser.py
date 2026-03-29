"""
Markdown parser for Obsidian vault notes.

Pure functions — no I/O side effects, no DB access.
Handles: YAML frontmatter, wikilinks, embeds, #tags, heading-based chunking.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class ParsedChunk:
    chunk_index: int
    heading: str | None          # "Architecture" (text only, no ## prefix)
    heading_level: int | None    # 1-6, None for preamble
    body: str                    # raw markdown text of this chunk
    char_count: int = 0

    def __post_init__(self) -> None:
        self.char_count = len(self.body)


@dataclass
class ParsedNote:
    rel_path: str                            # relative to vault root
    title: str                               # from first H1 or filename
    frontmatter: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    wikilinks: list[tuple[str, str]] = field(default_factory=list)  # (target, 'wikilink'|'embed')
    chunks: list[ParsedChunk] = field(default_factory=list)
    content_hash: str = ""                   # SHA-256 of raw file bytes


# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?\n)---\s*\n", re.DOTALL)
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
_TAG_RE = re.compile(r"(?<!\w)#([a-zA-Z][a-zA-Z0-9_/-]*)")
_WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
_EMBED_RE = re.compile(r"!\[\[([^\]]+)\]\]")
_CODE_BLOCK_RE = re.compile(r"```.*?```", re.DOTALL)


# ---------------------------------------------------------------------------
# Parsing functions
# ---------------------------------------------------------------------------


def extract_frontmatter(raw_text: str) -> tuple[dict[str, Any], str]:
    """Split YAML frontmatter from body. Returns (frontmatter_dict, body_text)."""
    match = _FRONTMATTER_RE.match(raw_text)
    if not match:
        return {}, raw_text
    fm_text = match.group(1)
    body = raw_text[match.end():]
    try:
        parsed = yaml.safe_load(fm_text)
        if not isinstance(parsed, dict):
            parsed = {}
    except yaml.YAMLError:
        parsed = {}
    return parsed, body


def extract_tags(text: str) -> list[str]:
    """Find all #tag patterns, excluding those inside code blocks and headings."""
    # Strip code blocks to avoid false positives
    stripped = _CODE_BLOCK_RE.sub("", text)
    # Strip heading lines (# chars at start would match tag regex)
    lines = []
    for line in stripped.split("\n"):
        if not line.lstrip().startswith("#") or not re.match(r"^#{1,6}\s", line.lstrip()):
            lines.append(line)
    cleaned = "\n".join(lines)
    return list(dict.fromkeys(_TAG_RE.findall(cleaned)))  # deduplicate, preserve order


def extract_wikilinks(text: str) -> list[tuple[str, str]]:
    """Find [[Target]] and ![[Embed]] patterns. Returns (target, type) tuples."""
    results: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    # Embeds first (so ![[x]] isn't also matched as [[x]])
    for match in _EMBED_RE.finditer(text):
        raw = match.group(1).split("|")[0].strip()  # handle [[Target|Alias]]
        key = (raw, "embed")
        if key not in seen:
            results.append(key)
            seen.add(key)

    # Then standard wikilinks (skip positions already matched as embeds)
    embed_positions = {m.start() for m in _EMBED_RE.finditer(text)}
    for match in _WIKILINK_RE.finditer(text):
        # Skip if this [[ is part of a ![[ embed
        if (match.start() - 1) in embed_positions:
            continue
        raw = match.group(1).split("|")[0].strip()
        key = (raw, "wikilink")
        if key not in seen:
            results.append(key)
            seen.add(key)

    return results


def chunk_by_headings(body_text: str) -> list[ParsedChunk]:
    """Split markdown body into chunks at heading boundaries.

    Content before the first heading becomes chunk_index=0 with heading=None.
    Each chunk includes all content until the next heading of equal or higher level.
    Chunks with empty body (after stripping) are still included for structure.
    """
    chunks: list[ParsedChunk] = []
    heading_matches = list(_HEADING_RE.finditer(body_text))

    if not heading_matches:
        # No headings — entire body is one chunk
        return [ParsedChunk(chunk_index=0, heading=None, heading_level=None, body=body_text.strip())]

    # Preamble: content before first heading
    first_start = heading_matches[0].start()
    preamble = body_text[:first_start].strip()
    if preamble:
        chunks.append(ParsedChunk(chunk_index=0, heading=None, heading_level=None, body=preamble))

    # Each heading starts a chunk that ends at the next heading
    for i, match in enumerate(heading_matches):
        level = len(match.group(1))
        heading_text = match.group(2).strip()
        start = match.start()
        end = heading_matches[i + 1].start() if i + 1 < len(heading_matches) else len(body_text)
        body = body_text[start:end].strip()

        chunks.append(ParsedChunk(
            chunk_index=len(chunks),
            heading=heading_text,
            heading_level=level,
            body=body,
        ))

    return chunks


def _title_from_body(body: str, file_path: Path) -> str:
    """Extract title from first H1, falling back to filename."""
    match = re.match(r"^#\s+(.+)$", body, re.MULTILINE)
    if match:
        return match.group(1).strip()
    stem = file_path.stem.replace("_", " ").replace("-", " ").strip()
    return " ".join(word.capitalize() for word in stem.split()) if stem else "Untitled"


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def parse_note(file_path: Path, vault_path: Path) -> ParsedNote:
    """Parse a single .md file into structured data."""
    raw_bytes = file_path.read_bytes()
    content_hash = hashlib.sha256(raw_bytes).hexdigest()
    raw_text = raw_bytes.decode("utf-8", errors="replace")

    frontmatter, body = extract_frontmatter(raw_text)
    tags = extract_tags(raw_text)
    wikilinks = extract_wikilinks(body)
    chunks = chunk_by_headings(body)
    title = _title_from_body(body, file_path)

    # Also collect tags from frontmatter 'tags' field
    fm_tags = frontmatter.get("tags", [])
    if isinstance(fm_tags, list):
        for t in fm_tags:
            tag_str = str(t).lstrip("#")
            if tag_str and tag_str not in tags:
                tags.append(tag_str)

    rel_path = str(file_path.relative_to(vault_path))

    return ParsedNote(
        rel_path=rel_path,
        title=title,
        frontmatter=frontmatter,
        tags=tags,
        wikilinks=wikilinks,
        chunks=chunks,
        content_hash=content_hash,
    )
