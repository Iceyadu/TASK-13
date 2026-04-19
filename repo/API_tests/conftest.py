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
import threading
import time
from pathlib import Path
from typing import Any, Optional

import httpx
import pytest

# Single event loop for all in-process ASGI requests. asyncio.run() per request creates a new
# loop each time; SQLAlchemy async + asyncpg bind connections to one loop, causing
# "another operation is in progress" across requests.
_bridge_loop: Optional[asyncio.AbstractEventLoop] = None
_bridge_thread: Optional[threading.Thread] = None
_bridge_ready = threading.Event()
_bridge_start_lock = threading.Lock()


def _ensure_asyncio_bridge_loop() -> asyncio.AbstractEventLoop:
    global _bridge_loop, _bridge_thread
    if _bridge_loop is not None:
        return _bridge_loop
    with _bridge_start_lock:
        if _bridge_loop is not None:
            return _bridge_loop
        _bridge_ready.clear()

        def _runner() -> None:
            global _bridge_loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            _bridge_loop = loop
            _bridge_ready.set()
            try:
                loop.run_forever()
            finally:
                loop.close()

        _bridge_thread = threading.Thread(
            target=_runner, daemon=True, name="api-tests-asgi-bridge"
        )
        _bridge_thread.start()
        if not _bridge_ready.wait(timeout=60.0):
            raise RuntimeError("ASGI test bridge event loop did not start")
        assert _bridge_loop is not None
        return _bridge_loop


def _run_coro_on_bridge_loop(coro: Any) -> Any:
    loop = _ensure_asyncio_bridge_loop()
    fut = asyncio.run_coroutine_threadsafe(coro, loop)
    return fut.result(timeout=120.0)


# FastAPI lifespan (migrations + seed) must run on the same loop as ASGI requests. httpx.ASGITransport
# often does not run Starlette lifespan, so we hold router.lifespan_context for the pytest session.
_inprocess_app: Any = None
_lifespan_startup_done = threading.Event()
_lifespan_future: Optional["asyncio.Future[Any]"] = None
_bridge_shutdown_event: Optional[asyncio.Event] = None


async def _lifespan_worker(app: Any) -> None:
    global _bridge_shutdown_event
    _bridge_shutdown_event = asyncio.Event()
    async with app.router.lifespan_context(app):
        _lifespan_startup_done.set()
        await _bridge_shutdown_event.wait()


def _start_api_lifespan_on_bridge(app: Any) -> None:
    """Run FastAPI startup (create tables, seed admin) on the bridge loop before any HTTP request."""
    global _lifespan_future
    loop = _ensure_asyncio_bridge_loop()
    _lifespan_future = asyncio.run_coroutine_threadsafe(_lifespan_worker(app), loop)
    deadline = time.monotonic() + 120.0
    while time.monotonic() < deadline:
        if _lifespan_startup_done.is_set():
            return
        if _lifespan_future.done():
            _lifespan_future.result()
            raise RuntimeError("FastAPI lifespan exited before startup completed")
        time.sleep(0.05)
    if _lifespan_future.done():
        _lifespan_future.result()
    raise RuntimeError(
        "FastAPI lifespan startup timed out (check DATABASE_URL and PostgreSQL for API tests)"
    )


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
    calls ``handle_request``. All async work runs on one dedicated event loop (background
    thread) so the DB engine and asyncpg stay on a single loop — unlike ``asyncio.run`` per
    request, which breaks SQLAlchemy async sessions.
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

        return _run_coro_on_bridge_loop(_call())


def _install_inprocess_mode() -> None:
    """Wire httpx → ASGI so all API_tests (including ad-hoc httpx.Client / httpx.get) hit the app."""
    global _ASGI_TRANSPORT, _inprocess_app
    if not USE_INPROCESS:
        return
    repo_root = Path(__file__).resolve().parent.parent
    backend_root = repo_root / "backend"
    sys.path.insert(0, str(backend_root))
    from app.main import app  # noqa: E402

    _inprocess_app = app
    # Lifespan is driven by _lifespan_worker (same loop as requests); do not use transport lifespan.
    raw = httpx.ASGITransport(app=app)
    _ASGI_TRANSPORT = _SyncASGIBridgeTransport(raw)
    _start_api_lifespan_on_bridge(app)

    @functools.wraps(_ORIG_CLIENT_INIT)
    def _wrapped_init(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        if _ASGI_TRANSPORT is not None:
            kwargs.setdefault("transport", _ASGI_TRANSPORT)
        return _ORIG_CLIENT_INIT(self, *args, **kwargs)

    httpx.Client.__init__ = _wrapped_init  # type: ignore[method-assign]


_install_inprocess_mode()


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Signal lifespan shutdown, wait for cleanup, then stop the bridge loop."""
    global _bridge_loop, _bridge_shutdown_event, _lifespan_future
    if not USE_INPROCESS:
        return
    loop = _bridge_loop
    if loop is None or loop.is_closed():
        return
    try:
        if _bridge_shutdown_event is not None:

            def _release_lifespan() -> None:
                _bridge_shutdown_event.set()

            loop.call_soon_threadsafe(_release_lifespan)
        if _lifespan_future is not None:
            try:
                _lifespan_future.result(timeout=120.0)
            except Exception:
                pass
        if not loop.is_closed():

            def _stop() -> None:
                loop.stop()

            loop.call_soon_threadsafe(_stop)
    except RuntimeError:
        pass


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
