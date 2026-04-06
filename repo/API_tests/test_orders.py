"""API tests for the /orders endpoints."""

import httpx


def test_get_orders_with_admin_token_returns_200(auth_client: httpx.Client):
    response = auth_client.get("/orders/")
    print(f"[GET /orders/ admin] status={response.status_code}")

    assert response.status_code == 200


def test_post_orders_without_auth_returns_401(client: httpx.Client):
    response = client.post(
        "/orders/",
        json={
            "title": "Fix leaky faucet",
            "description": "Kitchen sink is dripping",
            "category": "plumbing",
            "priority": "normal",
        },
    )
    print(f"[POST /orders/ no auth] status={response.status_code}")

    assert response.status_code == 401
