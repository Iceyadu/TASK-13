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
