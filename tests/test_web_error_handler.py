"""The shared unhandled-exception handler (rebalance.web.unhandled_exception_handler)
shows tracebacks locally and hides them when bound to a public interface.

This one handler is registered on BOTH local FastAPI servers: the :8787 web app
(rebalance serve) and the :8767 pulse server (scripts/pulse_server.py)."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from rebalance.web import unhandled_exception_handler


def _app() -> FastAPI:
    app = FastAPI()
    app.add_exception_handler(Exception, unhandled_exception_handler)

    @app.get("/boom")
    def boom():
        raise ValueError("kaboom-marker")

    return app


def test_shows_traceback_by_default():
    client = TestClient(_app(), raise_server_exceptions=False)
    resp = client.get("/boom")
    assert resp.status_code == 500
    assert "Traceback" in resp.text
    assert "kaboom-marker" in resp.text  # the real error, not a generic 500


def test_hides_traceback_when_disabled():
    app = _app()
    app.state.show_tracebacks = False  # what serve.py does on a public bind
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/boom")
    assert resp.status_code == 500
    assert resp.text == "Internal Server Error"
    assert "kaboom-marker" not in resp.text
