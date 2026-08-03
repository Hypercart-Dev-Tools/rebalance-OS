"""Obsidian vault source plugin for HiQS."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
import hashlib
import os
from pathlib import Path
import re
from typing import Any

from hiqs.plugins import Doc, Source, SyncReport

# Exclusion patterns for generated/system files and directories (L5)
EXCLUDED_DIR_NAMES = {
    ".git",
    ".obsidian",
    ".trash",
    ".venv",
    "__pycache__",
    "node_modules",
    "build",
    "dist",
    "target",
}

EXCLUDED_FILE_EXTENSIONS = {
    ".tmp",
    ".bak",
    ".swp",
    ".DS_Store",
}


def is_generated_file(path: Path | str, base_path: Path | str | None = None) -> bool:
    """Return True if path represents a generated, temporary, or hidden system file.

    v1 writes nothing to the vault; this exclusion helper guarantees generated
    files are excluded from ingest by construction (L5).
    """
    path_obj = Path(path)
    if base_path is not None:
        try:
            path_obj = path_obj.relative_to(base_path)
        except ValueError:
            pass

    for part in path_obj.parts[:-1]:
        if part in EXCLUDED_DIR_NAMES or (part.startswith(".") and len(part) > 1):
            return True

    name = path_obj.name
    if name in EXCLUDED_DIR_NAMES or (name.startswith(".") and len(name) > 1):
        return True

    if path_obj.suffix in EXCLUDED_FILE_EXTENSIONS:
        return True

    if ".gen." in name or ".tmp." in name:
        return True

    return False


def _resolve_vault_path(config: Mapping[str, Any] | Any) -> Path | None:
    """Resolve vault path from config without hardcoded assumptions (L11)."""
    if isinstance(config, Mapping):
        if "vault_path" in config and config["vault_path"]:
            return Path(config["vault_path"])
        vault_conf = config.get("vault")
        if isinstance(vault_conf, (str, Path)):
            return Path(vault_conf)
        if isinstance(vault_conf, Mapping) and "path" in vault_conf:
            return Path(vault_conf["path"])
    return None


def _ensure_schema(connection: Any) -> None:
    """Ensure vault_files raw table exists with required columns."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS vault_files(
          path TEXT PRIMARY KEY,
          content_hash TEXT NOT NULL,
          mtime TEXT NOT NULL,
          content TEXT
        )
        """
    )
    try:
        connection.execute("ALTER TABLE vault_files ADD COLUMN content TEXT")
    except Exception:
        pass


def fetch(connection: Any, config: Mapping[str, Any]) -> SyncReport:
    """Walk .md files in the vault, hash delta into vault_files table.

    Idempotent and incremental (§5 rule 2, pattern 1).
    """
    _ensure_schema(connection)

    counts = {
        "inserted": 0,
        "updated": 0,
        "unchanged": 0,
        "skipped": 0,
        "rejected": 0,
        "pruned": 0,
    }
    errors: list[str] = []

    vault_path = _resolve_vault_path(config)
    if vault_path is None or not vault_path.exists() or not vault_path.is_dir():
        errors.append(f"Vault path does not exist or is not a directory: {vault_path}")
        return SyncReport(counts=counts, errors=errors)

    existing = {
        row[0]: (row[1], row[2])
        for row in connection.execute("SELECT path, content_hash, mtime FROM vault_files").fetchall()
    }

    seen_paths: set[str] = set()

    for root, dirs, files in os.walk(vault_path):
        root_path = Path(root)
        dirs[:] = [d for d in dirs if not is_generated_file(root_path / d, base_path=vault_path)]

        for filename in files:
            file_path = root_path / filename
            rel_path = file_path.relative_to(vault_path).as_posix()

            if is_generated_file(file_path, base_path=vault_path) or file_path.suffix.lower() != ".md":
                counts["skipped"] += 1
                continue

            try:
                st = file_path.stat()
                content_bytes = file_path.read_bytes()
            except Exception as err:
                errors.append(f"Failed to read {rel_path}: {err}")
                counts["rejected"] += 1
                # L19: Watermark/mtime state does NOT advance for a file whose read failed.
                # Existing row in vault_files remains untouched!
                continue

            seen_paths.add(rel_path)

            mtime_str = str(st.st_mtime)
            content_hash = hashlib.sha256(content_bytes).hexdigest()
            content_str = content_bytes.decode("utf-8", errors="replace")

            if rel_path in existing:
                old_hash, _old_mtime = existing[rel_path]
                if old_hash == content_hash:
                    counts["unchanged"] += 1
                else:
                    with connection:
                        connection.execute(
                            "UPDATE vault_files SET content_hash = ?, mtime = ?, content = ? WHERE path = ?",
                            (content_hash, mtime_str, content_str, rel_path),
                        )
                    counts["updated"] += 1
            else:
                with connection:
                    connection.execute(
                        "INSERT INTO vault_files (path, content_hash, mtime, content) VALUES (?, ?, ?, ?)",
                        (rel_path, content_hash, mtime_str, content_str),
                    )
                counts["inserted"] += 1

    # Reconcile vanished files ONLY after a complete walk with zero errors (rule 5 / L15).
    if not errors:
        vanished = set(existing.keys()) - seen_paths
        for rel_path in sorted(vanished):
            with connection:
                connection.execute("DELETE FROM vault_files WHERE path = ?", (rel_path,))
            counts["pruned"] += 1

    return SyncReport(counts=counts, errors=errors)


def _chunk_markdown_content(content: str, rel_path: str) -> list[Doc]:
    """Chunk markdown content by heading, emitting Doc objects with file-scoped chunk ids."""
    file_title = Path(rel_path).stem

    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            for line in parts[1].splitlines():
                if line.startswith("title:"):
                    raw_title = line.split("title:", 1)[1].strip().strip("\"'")
                    if raw_title:
                        file_title = raw_title
                    break

    heading_re = re.compile(r"^(#{1,6})\s+(.*)$")
    lines = content.splitlines()

    chunks: list[tuple[str | None, list[str]]] = []
    current_heading: str | None = None
    current_lines: list[str] = []

    for line in lines:
        match = heading_re.match(line)
        if match:
            if current_lines or current_heading is not None:
                chunks.append((current_heading, current_lines))
            current_heading = match.group(2).strip()
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_lines or current_heading is not None:
        chunks.append((current_heading, current_lines))

    result: list[Doc] = []
    seen_heading_hashes: dict[str, int] = {}

    for heading, chunk_lines in chunks:
        body = "\n".join(chunk_lines).strip()
        if not body:
            continue

        if heading is None:
            clean_body = body
            if clean_body.startswith("---"):
                fm_parts = clean_body.split("---", 2)
                if len(fm_parts) >= 3:
                    clean_body = fm_parts[2].strip()
            if not clean_body:
                continue

            base_hash = hashlib.sha256(b"preamble").hexdigest()[:12]
            seen_heading_hashes[base_hash] = seen_heading_hashes.get(base_hash, 0) + 1
            if seen_heading_hashes[base_hash] > 1:
                heading_hash = hashlib.sha256(f"preamble:{seen_heading_hashes[base_hash]}".encode()).hexdigest()[:12]
            else:
                heading_hash = base_hash

            chunk_id = f"vault:{rel_path}:{heading_hash}"
            doc_title = file_title
            result.append(
                Doc(
                    source="vault",
                    id=chunk_id,
                    title=doc_title,
                    body=body,
                    url="",
                    ts="",
                    project="",
                    author="",
                )
            )
        else:
            raw_hash = hashlib.sha256(heading.encode("utf-8")).hexdigest()[:12]
            seen_heading_hashes[raw_hash] = seen_heading_hashes.get(raw_hash, 0) + 1
            if seen_heading_hashes[raw_hash] > 1:
                heading_hash = hashlib.sha256(f"{heading}:{seen_heading_hashes[raw_hash]}".encode("utf-8")).hexdigest()[:12]
            else:
                heading_hash = raw_hash

            chunk_id = f"vault:{rel_path}:{heading_hash}"
            doc_title = f"{file_title} - {heading}" if heading != file_title else file_title
            result.append(
                Doc(
                    source="vault",
                    id=chunk_id,
                    title=doc_title,
                    body=body,
                    url="",
                    ts="",
                    project="",
                    author="",
                )
            )

    return result


def docs(connection: Any) -> Iterable[Doc]:
    """Expose vault note chunks through the public document-provider contract.

    Chunk ids are file-scoped: vault:<rel_path>:<heading-hash> (§6.1).
    Doc.author is "" for vault notes (they are the operator's own).
    """
    _ensure_schema(connection)
    rows = connection.execute("SELECT path, content FROM vault_files ORDER BY path").fetchall()
    documents: list[Doc] = []
    for rel_path, content in rows:
        if content:
            documents.extend(_chunk_markdown_content(content, rel_path))
    return documents


SOURCE = Source(
    name="vault",
    fetch=fetch,
    docs=docs,
)
