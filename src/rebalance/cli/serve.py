"""`rebalance serve` — start the local web dashboard (auth log, future pages).

Extracted from the cli monolith (Phase 5). Registers on the shared Typer `app`.
"""

from __future__ import annotations

import typer

from rebalance.cli._core import app


@app.command("serve")
def serve_cmd(
    port: int = typer.Option(8787, "--port", "-p", help="Port to listen on"),
    host: str = typer.Option("127.0.0.1", "--host", help="Bind address"),
) -> None:
    """Start the local web dashboard (auth log, future dashboards).

    Opens http://localhost:<port>/auth-log in your browser automatically.
    Requires: pip install 'rebalance-os[server]'
    """
    try:
        import uvicorn
    except ImportError:
        typer.echo("uvicorn not installed. Run: pip install 'rebalance-os[server]'")
        raise typer.Exit(1)

    import webbrowser
    import threading

    url = f"http://{host}:{port}"
    typer.echo(f"Starting rebalance web server at {url}")
    typer.echo(f"  Auth log: {url}/auth-log")
    threading.Timer(0.8, lambda: webbrowser.open(f"{url}/auth-log")).start()

    from rebalance.web import app as web_app
    uvicorn.run(web_app, host=host, port=port, log_level="warning")
