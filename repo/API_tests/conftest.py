"""Shared fixtures for API integration tests.

All tests in this package call real HTTP endpoints via httpx (sync client).
"""

import os

import httpx
import pytest

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")


@pytest.fixture(scope="session")
def base_url() -> str:
    """Return the versioned API base URL (e.g. http://localhost:8000/api/v1)."""
    return f"{API_BASE_URL}/api/v1"


@pytest.fixture(scope="session")
def client(base_url: str) -> httpx.Client:
    """Return a plain (unauthenticated) httpx client pointed at the API."""
    with httpx.Client(base_url=base_url, timeout=30.0) as c:
        yield c


@pytest.fixture(scope="session")
def auth_token(base_url: str) -> str:
    """Log in as the default admin user and return the access_token string."""
    with httpx.Client(base_url=base_url, timeout=30.0) as c:
        response = c.post(
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
    """Return an httpx client with the admin Authorization header already set."""
    with httpx.Client(
        base_url=base_url,
        timeout=30.0,
        headers={"Authorization": f"Bearer {auth_token}"},
    ) as c:
        yield c
