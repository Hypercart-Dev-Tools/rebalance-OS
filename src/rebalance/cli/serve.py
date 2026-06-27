"""`rebalance serve` — start the local web dashboard (auth log, future pages).

Extracted from the cli monolith (Phase 5). Registers on the shared Typer `app`.
"""

from __future__ import annotations

import typer

from rebalance.cli._core import app


# Reserved for the pulse server (scripts/pulse_server.py, launchd job
# com.rebalance-os.pulse-server). The web app must never bind it: when the pulse
# server is briefly down its port is free, and silently squatting it serves the
# wrong dashboard there. See SCHEDULER.md.
PULSE_SERVER_PORT = 8767


@app.command("serve")
def serve_cmd(
    port: int = typer.Option(
        8787, "--port", "-p", help="Port to listen on (8767 is the pulse server's)"
    ),
    host: str = typer.Option("127.0.0.1", "--host", help="Bind address"),
) -> None:
    """Start the local web dashboard (auth log, future dashboards).

    Opens http://localhost:<port>/auth-log in your browser automatically.
    Requires: pip install 'rebalance-os[server]'
    """
    if port == PULSE_SERVER_PORT:
        typer.echo(
            f"Port {PULSE_SERVER_PORT} is reserved for the pulse server "
            f"(launchd: com.rebalance-os.pulse-server). Refusing to start the web "
            f"app here — use the default 8787 or pass a different --port."
        )
        raise typer.Exit(2)

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
    # ponytail: show tracebacks in-browser for local dev; off on a public bind so
    # they never leak off-box.
    web_app.state.show_tracebacks = host in ("127.0.0.1", "localhost", "::1")
    uvicorn.run(web_app, host=host, port=port, log_level="warning")
