"""Pin clean-room imports as the extraction precondition, not a style check."""

from __future__ import annotations

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
HIQS_ROOT = REPO_ROOT / "HiQS"
INCUMBENT_ROOT = REPO_ROOT / "src" / "rebalance"


def _python_files(root: Path) -> list[Path]:
    """First-party sources below ``root`` — never vendored deps, venvs or caches.

    A bare ``rglob`` also walks ``HiQS/.venv``: today that is 847 of 862 files and
    78% of this suite's runtime, and it grows with every dependency the plan adds.
    Third-party code can never be HiQS code, so scanning it buys no coverage while
    exposing the extraction gate to a false positive from someone else's imports.
    """
    return [
        path
        for path in root.rglob("*.py")
        if not any(part.startswith(".") for part in path.relative_to(root).parts)
    ]


def _forbidden_imports(root: Path, forbidden_top_level: str) -> list[tuple[Path, int, str]]:
    """Return AST-detected imports of one top-level package below ``root``."""
    violations = []
    for path in _python_files(root):
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
    # Scan-nothing is indistinguishable from found-nothing: a missing root makes
    # rglob yield nothing and `== []` pass while checking zero files. That is not
    # hypothetical here — §19 archives rebalance-OS and moves HiQS to its own repo,
    # which deletes INCUMBENT_ROOT out from under the very gate that authorises the
    # extraction. Assert coverage first so the gate fails LOUD instead of green.
    assert _python_files(HIQS_ROOT), f"scanned no HiQS sources under {HIQS_ROOT}"
    assert _python_files(INCUMBENT_ROOT), f"scanned no incumbent sources under {INCUMBENT_ROOT}"

    assert _forbidden_imports(HIQS_ROOT, "rebalance") == []
    assert _forbidden_imports(INCUMBENT_ROOT, "hiqs") == []


def test_scan_skips_vendored_dependencies_but_still_sees_first_party_code(tmp_path):
    (tmp_path / ".venv" / "site-packages").mkdir(parents=True)
    (tmp_path / ".venv" / "site-packages" / "vendored.py").write_text(
        "import rebalance\n", encoding="utf-8"
    )
    (tmp_path / "first_party.py").write_text("x = 1\n", encoding="utf-8")

    assert _python_files(tmp_path) == [tmp_path / "first_party.py"]
    assert _forbidden_imports(tmp_path, "rebalance") == []


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
