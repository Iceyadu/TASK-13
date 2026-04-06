"""API tests for the /auth endpoints."""

import httpx


def test_login_valid_creds_returns_200_with_token_and_user(client: httpx.Client):
    response = client.post(
        "/auth/login",
        json={"username": "admin", "password": "Admin@Harbor2026"},
    )
    print(f"[POST /auth/login valid] status={response.status_code}")

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "user" in data


def test_login_wrong_password_returns_401(client: httpx.Client):
    response = client.post(
        "/auth/login",
        json={"username": "admin", "password": "WrongPassword!"},
    )
    print(f"[POST /auth/login wrong pw] status={response.status_code}")

    assert response.status_code == 401


def test_refresh_with_valid_token_returns_200_with_new_access_token(client: httpx.Client):
    # First obtain a refresh token by logging in
    login_resp = client.post(
        "/auth/login",
        json={"username": "admin", "password": "Admin@Harbor2026"},
    )
    login_data = login_resp.json()
    refresh_token = login_data["refresh_token"]

    # Now call the refresh endpoint
    response = client.post(
        "/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    print(f"[POST /auth/refresh] status={response.status_code}")

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data


def test_me_with_valid_token_returns_user_info(auth_client: httpx.Client):
    response = auth_client.get("/auth/me")
    print(f"[GET /auth/me authed] status={response.status_code}")

    assert response.status_code == 200
    data = response.json()
    assert "username" in data


def test_me_without_token_returns_401(client: httpx.Client):
    response = client.get("/auth/me")
    print(f"[GET /auth/me no auth] status={response.status_code}")

    assert response.status_code == 401
