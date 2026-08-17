"""Obsidian vault source plugin for HiQS."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import re
from typing import Any

from hiqs.chunking import split_oversized
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


def _resolve_vault_path(config: Any = None) -> Path | None:
    """Resolve vault path from config without hardcoded assumptions (L11)."""
    if config is None:
        try:
            from hiqs.config import load_config

            config = load_config()
        except Exception:
            return None

    if isinstance(config, (str, Path)):
        return Path(config)

    if isinstance(config, Mapping):
        if "vault_path" in config and config["vault_path"]:
            return Path(config["vault_path"])
        vault_conf = config.get("vault")
        if isinstance(vault_conf, (str, Path)):
            return Path(vault_conf)
        if isinstance(vault_conf, Mapping) and "path" in vault_conf:
            return Path(vault_conf["path"])
    elif config is not None:
        vault_path = getattr(config, "vault_path", None)
        if vault_path:
            return Path(vault_path)
        vault_conf = getattr(config, "vault", None)
        if isinstance(vault_conf, (str, Path)):
            return Path(vault_conf)
        if isinstance(vault_conf, Mapping) and "path" in vault_conf:
            return Path(vault_conf["path"])
        if hasattr(vault_conf, "path"):
            return Path(getattr(vault_conf, "path"))
    return None


def _ensure_schema(connection: Any) -> None:
    """Ensure vault_files raw table exists with canonical schema (path, content_hash, mtime)."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS vault_files(
          path TEXT PRIMARY KEY,
          content_hash TEXT NOT NULL,
          mtime TEXT NOT NULL
        )
        """
    )


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

    def _on_walk_error(os_err: OSError) -> None:
        errors.append(f"Directory walk error: {os_err}")

    walked_paths: set[str] = set()
    units_ok: list[str] = []

    for root, dirs, files in os.walk(vault_path, onerror=_on_walk_error):
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

            walked_paths.add(rel_path)
            units_ok.append(rel_path)

            mtime_dt = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc)
            mtime_str = mtime_dt.isoformat().replace("+00:00", "Z")
            content_hash = hashlib.sha256(content_bytes).hexdigest()

            if rel_path in existing:
                old_hash, _old_mtime = existing[rel_path]
                if old_hash == content_hash:
                    counts["unchanged"] += 1
                else:
                    with connection:
                        connection.execute(
                            "UPDATE vault_files SET content_hash = ?, mtime = ? WHERE path = ?",
                            (content_hash, mtime_str, rel_path),
                        )
                    counts["updated"] += 1
            else:
                with connection:
                    connection.execute(
                        "INSERT INTO vault_files (path, content_hash, mtime) VALUES (?, ?, ?)",
                        (rel_path, content_hash, mtime_str),
                    )
                counts["inserted"] += 1

    if len(errors) == 0:
        vanished = set(existing.keys()) - walked_paths
        for rel_path in sorted(vanished):
            with connection:
                connection.execute("DELETE FROM vault_files WHERE path = ?", (rel_path,))
            units_ok.append(rel_path)

    return SyncReport(counts=counts, errors=errors, units_ok=tuple(units_ok))


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

    raw_chunks: list[tuple[str | None, list[str]]] = []
    current_heading: str | None = None
    current_lines: list[str] = []

    for line in lines:
        match = heading_re.match(line)
        if match:
            if current_lines or current_heading is not None:
                raw_chunks.append((current_heading, current_lines))
            current_heading = match.group(2).strip()
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_lines or current_heading is not None:
        raw_chunks.append((current_heading, current_lines))

    # Pre-pass: clean and gather (heading, body) tuples
    processed_chunks: list[tuple[str | None, str]] = []
    heading_counts: Counter[str | None] = Counter()

    for heading, chunk_lines in raw_chunks:
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

        # A heading section is not bounded by anything — the largest one in this vault ran to
        # 6893 word-pieces against MiniLM's 256-token window, so 36% of the corpus was being
        # embedded from its opening lines only. Cap it here; ids stay content-derived because
        # the hash below is taken over the part, so parts get distinct ids for free and the
        # existing duplicate counter still resolves genuine collisions.
        for part in split_oversized(body):
            processed_chunks.append((heading, part))
            heading_counts[heading] += 1

    result: list[Doc] = []
    duplicate_occurrences: dict[tuple[str | None, str], int] = {}

    for heading, body in processed_chunks:
        key_str = f"{heading or 'preamble'}:{body}"
        dup_idx = duplicate_occurrences.get((heading, body), 0) + 1
        duplicate_occurrences[(heading, body)] = dup_idx
        if dup_idx > 1:
            key_str = f"{key_str}:{dup_idx}"
        heading_hash = hashlib.sha256(key_str.encode("utf-8")).hexdigest()[:12]

        chunk_id = f"vault:{rel_path}:{heading_hash}"
        doc_title = (
            file_title
            if (heading is None or heading == file_title)
            else f"{file_title} - {heading}"
        )

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
                unit=rel_path,
            )
        )

    return result


def docs(connection: Any, config: Any = None) -> Iterable[Doc]:
    """Expose vault note chunks through the public document-provider contract.

    Chunk ids are file-scoped: vault:<rel_path>:<heading-hash> (§6.1).
    Doc.author is "" for vault notes (they are the operator's own).
    """
    _ensure_schema(connection)
    vault_path = _resolve_vault_path(config)
    if vault_path is None or not vault_path.exists():
        rows = connection.execute("SELECT path FROM vault_files").fetchall()
        if rows:
            raise RuntimeError(f"Vault path does not exist or is unavailable: {vault_path}")
        return []

    rows = connection.execute("SELECT path, content_hash FROM vault_files ORDER BY path").fetchall()
    documents: list[Doc] = []

    for rel_path, stored_hash in rows:
        file_path = vault_path / rel_path
        if not file_path.exists():
            continue
        if is_generated_file(file_path, base_path=vault_path):
            continue

        try:
            content_bytes = file_path.read_bytes()
        except Exception as err:
            raise RuntimeError(f"Failed to read tracked file {rel_path}: {err}") from err

        current_hash = hashlib.sha256(content_bytes).hexdigest()
        if current_hash != stored_hash:
            raise RuntimeError(f"Tracked file content drifted without fetch: {rel_path}")

        content = content_bytes.decode("utf-8", errors="replace")
        documents.extend(_chunk_markdown_content(content, rel_path))

    return documents


SOURCE = Source(
    name="vault",
    fetch=fetch,
    docs=docs,
)

