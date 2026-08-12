import os
import re
from pathlib import Path

INGEST_DIR = Path("src/rebalance/ingest")

def replace_in_file(path):
    with open(path, "r") as f:
        content = f.read()

    original_content = content

    # Regex to match function definitions and their bodies
    # Matches 'def _funcname(...):\n(?:    .*\n)*'
    patterns = {
        'time_ops': [
            r'def _parse_iso\(.*?\)(?:\s*->.*?)?:\n(?:(?:    .*?\n)|(?:[ \t]*\n))*',
            r'def _now_iso\(.*?\)(?:\s*->.*?)?:\n(?:(?:    .*?\n)|(?:[ \t]*\n))*',
            r'def _now\(.*?\)(?:\s*->.*?)?:\n(?:(?:    .*?\n)|(?:[ \t]*\n))*',
            r'def _now_utc\(.*?\)(?:\s*->.*?)?:\n(?:(?:    .*?\n)|(?:[ \t]*\n))*',
        ],
        'json_ops': [
            r'def _json_dumps\(.*?\)(?:\s*->.*?)?:\n(?:(?:    .*?\n)|(?:[ \t]*\n))*',
        ],
        'git_ops': [
            # Be careful not to remove the _git in github_commit_backfill.py as it has different semantics, 
            # we'll handle git_ops separately or rely on manual replacement for git.
            r'def _git\(.*?\)(?:\s*->.*?)?:\n(?:(?:    .*?\n)|(?:[ \t]*\n))*',
        ]
    }

    imports_to_add = []

    for lib, funcs in patterns.items():
        if lib == 'git_ops' and 'github_commit_backfill.py' in str(path):
            continue # skip this one for git
        
        imported_funcs = []
        
        if lib == 'time_ops':
            if '_parse_iso' in content: imported_funcs.append('_parse_iso')
            if '_now_iso' in content: imported_funcs.append('_now_iso')
            if '_now' in content and 'def _now' in content: imported_funcs.append('_now')
            if '_now_utc' in content: imported_funcs.append('_now_utc')
        elif lib == 'json_ops':
            if '_json_dumps' in content: imported_funcs.append('_json_dumps')
        elif lib == 'git_ops':
            # local_repos.py, focus5_scan.py etc.
            if 'def _git(' in content: imported_funcs.append('_git')

        if imported_funcs:
            imports_to_add.append(f"from rebalance.lib.{lib} import {', '.join(imported_funcs)}")
            for pattern in funcs:
                content = re.sub(pattern, '', content, flags=re.MULTILINE)

    if content != original_content:
        # Add imports after the last import statement or at the top
        # We can just put them near the top after imports.
        # Let's insert them before the first class or def, or just at the top.
        lines = content.split('\n')
        insert_idx = 0
        for i, line in enumerate(lines):
            if line.startswith('import ') or line.startswith('from '):
                insert_idx = i + 1
        
        lines = lines[:insert_idx] + imports_to_add + lines[insert_idx:]
        
        with open(path, "w") as f:
            f.write('\n'.join(lines))
        print(f"Refactored {path}")


def main():
    for root, _, files in os.walk(INGEST_DIR):
        for file in files:
            if file.endswith('.py'):
                replace_in_file(Path(root) / file)

if __name__ == "__main__":
    main()
