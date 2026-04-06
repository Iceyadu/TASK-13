"""API tests for the /residents endpoints."""

import httpx


def test_get_residents_with_admin_token_returns_200(auth_client: httpx.Client):
    response = auth_client.get("/residents/")
    print(f"[GET /residents/ admin] status={response.status_code}")

    assert response.status_code == 200


def test_get_residents_without_auth_returns_401(client: httpx.Client):
    response = client.get("/residents/")
    print(f"[GET /residents/ no auth] status={response.status_code}")

    assert response.status_code == 401


def test_get_residents_me_with_resident_token_returns_200(base_url: str):
    # Log in as resident1
    with httpx.Client(base_url=base_url, timeout=30.0) as c:
        login_resp = c.post(
            "/auth/login",
            json={"username": "resident1", "password": "Resident@Hbr2026"},
        )
        login_resp.raise_for_status()
        token = login_resp.json()["access_token"]

    with httpx.Client(
        base_url=base_url,
        timeout=30.0,
        headers={"Authorization": f"Bearer {token}"},
    ) as c:
        response = c.get("/residents/me")
        print(f"[GET /residents/me resident1] status={response.status_code}")

        assert response.status_code == 200
        data = response.json()
        assert data["first_name"] == "Jane"
