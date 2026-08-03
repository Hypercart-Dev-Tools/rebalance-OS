"""Pin clean-room imports as the extraction precondition, not a style check."""

from __future__ import annotations

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
HIQS_ROOT = REPO_ROOT / "HiQS"
INCUMBENT_ROOT = REPO_ROOT / "src" / "rebalance"


def _forbidden_imports(root: Path, forbidden_top_level: str) -> list[tuple[Path, int, str]]:
    """Return AST-detected imports of one top-level package below ``root``."""
    violations = []
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            else:
                continue
            for name in names:
                if name.split(".", 1)[0] == forbidden_top_level:
                    violations.append((path, node.lineno, name))
    return violations


def test_hiqs_and_the_incumbent_are_mutually_clean_rooms():
    assert _forbidden_imports(HIQS_ROOT, "rebalance") == []
    assert _forbidden_imports(INCUMBENT_ROOT, "hiqs") == []


def test_ast_detector_rejects_a_deliberate_import_in_either_direction(tmp_path):
    hiqs_module = tmp_path / "HiQS" / "module.py"
    incumbent_module = tmp_path / "incumbent" / "module.py"
    hiqs_module.parent.mkdir()
    incumbent_module.parent.mkdir()
    hiqs_module.write_text("import rebalance\n", encoding="utf-8")
    incumbent_module.write_text("from hiqs import plugins\n", encoding="utf-8")

    assert _forbidden_imports(hiqs_module.parent, "rebalance") == [
        (hiqs_module, 1, "rebalance")
    ]
    assert _forbidden_imports(incumbent_module.parent, "hiqs") == [
        (incumbent_module, 1, "hiqs")
    ]
