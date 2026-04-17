"""Shared fixtures for API tests.

By default (API_INPROCESS=1) requests go through the FastAPI app via httpx.ASGITransport — no
running Uvicorn or host port required; only PostgreSQL must be reachable (DATABASE_URL).
Use ./run_tests.sh api to run these tests in Docker with backend dependencies.

Set API_INPROCESS=0 to use a live HTTP server at API_BASE_URL (legacy integration style).
"""

from __future__ import annotations

import asyncio
import functools
import os
import sys
from pathlib import Path
from typing import Optional

import httpx
import pytest

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")
# Default off: local `pytest API_tests` expects a live server unless API_INPROCESS=1.
# run_tests.sh sets API_INPROCESS=1 (ASGI in-process; only Postgres required).
USE_INPROCESS = os.environ.get("API_INPROCESS", "0").lower() in ("1", "true", "yes")


def pytest_configure(config: pytest.Config) -> None:
    if not USE_INPROCESS:
        return
    try:
        import asyncpg  # noqa: F401
    except ImportError:
        pytest.exit(
            "API in-process tests require backend dependencies (asyncpg). "
            "Run them via Docker: ./run_tests.sh api",
            returncode=1,
        )


_ASGI_TRANSPORT: Optional["_SyncASGIBridgeTransport"] = None
_ORIG_CLIENT_INIT = httpx.Client.__init__


class _SyncASGIBridgeTransport(httpx.BaseTransport):
    """Drive FastAPI via httpx's async-only ASGITransport using a sync httpx.Client.

    httpx.ASGITransport only implements ``handle_async_request``; synchronous ``Client``
    calls ``handle_request``. Subclassing ``BaseTransport`` and bridging with
    ``asyncio.run`` works across httpx versions (including conda builds that lack
    ``transport.__enter__`` on async transports).
    """

    __slots__ = ("_inner",)

    def __init__(self, inner: httpx.ASGITransport) -> None:
        self._inner = inner

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        request.read()
        async_req = httpx.Request(
            method=request.method,
            url=request.url,
            headers=request.headers,
            content=request.content,
            extensions=request.extensions,
        )

        async def _call() -> httpx.Response:
            resp = await self._inner.handle_async_request(async_req)
            body = await resp.aread()
            return httpx.Response(
                status_code=resp.status_code,
                headers=resp.headers,
                content=body,
                request=request,
            )

        return asyncio.run(_call())


def _install_inprocess_mode() -> None:
    """Wire httpx → ASGI so all API_tests (including ad-hoc httpx.Client / httpx.get) hit the app."""
    global _ASGI_TRANSPORT
    if not USE_INPROCESS:
        return
    repo_root = Path(__file__).resolve().parent.parent
    backend_root = repo_root / "backend"
    sys.path.insert(0, str(backend_root))
    from app.main import app  # noqa: E402

    # httpx >= 0.28 supports lifespan= on ASGITransport; older conda builds do not.
    try:
        raw = httpx.ASGITransport(app=app, lifespan="on")
    except TypeError:
        raw = httpx.ASGITransport(app=app)
    _ASGI_TRANSPORT = _SyncASGIBridgeTransport(raw)

    @functools.wraps(_ORIG_CLIENT_INIT)
    def _wrapped_init(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        if _ASGI_TRANSPORT is not None:
            kwargs.setdefault("transport", _ASGI_TRANSPORT)
        return _ORIG_CLIENT_INIT(self, *args, **kwargs)

    httpx.Client.__init__ = _wrapped_init  # type: ignore[method-assign]


_install_inprocess_mode()


@pytest.fixture(scope="session")
def base_url() -> str:
    """Return the versioned API base URL (e.g. http://test/api/v1)."""
    return f"{API_BASE_URL}/api/v1"


@pytest.fixture(scope="session")
def client(base_url: str) -> httpx.Client:
    """Unauthenticated client (in-process ASGI or live HTTP per API_INPROCESS)."""
    with httpx.Client(base_url=base_url, timeout=30.0) as c:
        yield c


@pytest.fixture(scope="session")
def auth_token(client: httpx.Client) -> str:
    """Log in as the default admin user and return the access_token string."""
    response = client.post(
        "/auth/login",
        json={"username": "admin", "password": "Admin@Harbor2026"},
    )
    response.raise_for_status()
    data = response.json()
    token = data["access_token"]
    print(f"[auth_token] Logged in as admin, token starts with: {token[:12]}...")
    return token


@pytest.fixture(scope="session")
def auth_client(base_url: str, auth_token: str) -> httpx.Client:
    """Client with admin Authorization header."""
    with httpx.Client(
        base_url=base_url,
        timeout=30.0,
        headers={"Authorization": f"Bearer {auth_token}"},
    ) as c:
        yield c
