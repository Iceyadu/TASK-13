"""API tests for the /billing endpoints."""

import httpx


def test_get_fee_items_with_admin_token_returns_200(auth_client: httpx.Client):
    response = auth_client.get("/billing/fee-items")
    print(f"[GET /billing/fee-items] status={response.status_code}")

    assert response.status_code == 200


def test_get_bills_with_admin_token_returns_200(auth_client: httpx.Client):
    response = auth_client.get("/billing/bills")
    print(f"[GET /billing/bills] status={response.status_code}")

    assert response.status_code == 200


def test_get_fee_items_with_resident_token_returns_403(base_url: str):
    with httpx.Client(base_url=base_url, timeout=30.0) as c:
        login = c.post(
            "/auth/login",
            json={"username": "resident1", "password": "Resident@Hbr2026"},
        )
        login.raise_for_status()
        token = login.json()["access_token"]

    with httpx.Client(
        base_url=base_url,
        timeout=30.0,
        headers={"Authorization": f"Bearer {token}"},
    ) as c:
        response = c.get("/billing/fee-items")
        print(f"[GET /billing/fee-items resident] status={response.status_code}")
        assert response.status_code == 403


def test_generate_bills_without_auth_returns_401(client: httpx.Client):
    response = client.post(
        "/billing/generate",
        json={"property_id": "00000000-0000-0000-0000-000000000000", "billing_period": "2039-01"},
    )
    print(f"[POST /billing/generate no auth] status={response.status_code}")
    assert response.status_code == 401
