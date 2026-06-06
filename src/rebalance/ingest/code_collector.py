"""Native code-corpus collector for the unified semantic index.

Phase 2 of PROJECT/2-WORKING/CHAT-WITH-DATA.md. Walks the repo source tree and
AST-chunks Python modules by top-level function and class (plus a module header
chunk), yielding records that ``semantic_index.sync_code_documents`` upserts as
``source_type="code"``. This gives the Phase 1 hybrid FTS real code to surface
(``auth_log.py``, ``web.py``, …) that the work corpus never contained.

Pure stdlib (``ast``) — no third-party parser. Non-Python files and files that
fail to parse are skipped (they simply don't contribute chunks).
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator

DEFAULT_INCLUDE_DIRS = ("src", "scripts")
SKIP_DIR_NAMES = frozenset({
    ".venv", "venv", "node_modules", ".git", "__pycache__", "temp",
    "build", "dist", ".mypy_cache", ".pytest_cache", ".ruff_cache",
})


@dataclass(frozen=True)
class CodeChunk:
    path: str          # repo-relative POSIX path
    symbol: str        # function/class name, or "<module>"
    parent_symbol: str
    doc_kind: str      # function | class | module
    language: str      # always "python" for now
    body: str          # source segment
    start_line: int
    mtime_iso: str     # source file mtime (stable change key)


def iter_python_files(
    repo_root: Path, include_dirs: Iterable[str] = DEFAULT_INCLUDE_DIRS
) -> Iterator[Path]:
    for d in include_dirs:
        base = repo_root / d
        if not base.is_dir():
            continue
        for p in base.rglob("*.py"):
            if any(part in SKIP_DIR_NAMES for part in p.parts):
                continue
            yield p


def chunk_python_source(rel_path: str, source: str, mtime_iso: str) -> list[CodeChunk]:
    """Chunk one module's source into function/class/module records."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    chunks: list[CodeChunk] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            segment = ast.get_source_segment(source, node) or ""
            if not segment.strip():
                continue
            kind = "class" if isinstance(node, ast.ClassDef) else "function"
            chunks.append(CodeChunk(
                path=rel_path, symbol=node.name, parent_symbol="", doc_kind=kind,
                language="python", body=segment, start_line=node.lineno, mtime_iso=mtime_iso,
            ))

    # Module header chunk: docstring + import lines — captures "what this file is".
    doc = ast.get_docstring(tree) or ""
    import_lines = [
        ln for ln in source.splitlines()[:60]
        if ln.startswith(("import ", "from "))
    ]
    header = "\n".join(filter(None, [doc, "\n".join(import_lines)])).strip()
    if header:
        chunks.append(CodeChunk(
            path=rel_path, symbol="<module>", parent_symbol="", doc_kind="module",
            language="python", body=header, start_line=1, mtime_iso=mtime_iso,
        ))
    return chunks


def collect_code_chunks(
    repo_root: Path, include_dirs: Iterable[str] = DEFAULT_INCLUDE_DIRS
) -> list[CodeChunk]:
    """Walk *repo_root* and return all code chunks under *include_dirs*."""
    out: list[CodeChunk] = []
    for p in iter_python_files(repo_root, include_dirs):
        try:
            source = p.read_text(encoding="utf-8")
            mtime_iso = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc).isoformat()
        except (OSError, UnicodeDecodeError):
            continue
        rel = p.relative_to(repo_root).as_posix()
        out.extend(chunk_python_source(rel, source, mtime_iso))
    return out
