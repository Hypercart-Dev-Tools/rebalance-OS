"""
Desktop extension entry point for rebalance MCP server.

This file is the entry_point referenced in manifest.json. When Claude Desktop
launches the extension, it runs this file directly. The build script
(scripts/build_extension.py) copies src/rebalance/ into a lib/ directory
alongside this file, so we add that to sys.path before importing.
"""

import os
import sys
from pathlib import Path

# Add bundled lib/ to path so imports resolve without pip install
_server_dir = Path(__file__).parent
_lib_dir = _server_dir / "lib"
if _lib_dir.exists():
    sys.path.insert(0, str(_lib_dir))

# Also support running from the source tree (dev mode)
_src_dir = _server_dir.parent / "src"
if _src_dir.exists():
    sys.path.insert(0, str(_src_dir))

from rebalance.mcp_server import main

if __name__ == "__main__":
    main()
