# Backward-compatibility shim — .vscode/mcp.json uses `-m rebalance.mcp_server`.
# All tool logic lives in src/rebalance/mcp/.
from rebalance.mcp.server import create_server, main  # noqa: F401

if __name__ == "__main__":
    main()
