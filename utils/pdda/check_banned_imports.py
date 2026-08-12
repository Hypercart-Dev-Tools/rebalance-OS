import os
import ast
import sys
from pathlib import Path

def check_file(path: Path) -> list[str]:
    errors = []
    try:
        content = path.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(path))
    except Exception as e:
        return []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in ("subprocess", "datetime") and "src/rebalance/lib" not in str(path):
                    errors.append(f"{path}:{node.lineno}: Banned import '{alias.name}'. Use rebalance.lib instead.")
        elif isinstance(node, ast.ImportFrom):
            if node.module in ("subprocess", "datetime") and "src/rebalance/lib" not in str(path):
                errors.append(f"{path}:{node.lineno}: Banned import from '{node.module}'. Use rebalance.lib instead.")
    return errors

def main():
    root_dir = Path("src/rebalance/ingest")
    for root, _, files in os.walk(root_dir):
        for file in files:
            if file.endswith(".py"):
                path = Path(root) / file
                errors = check_file(path)
                for err in errors:
                    print(err)

if __name__ == "__main__":
    main()
