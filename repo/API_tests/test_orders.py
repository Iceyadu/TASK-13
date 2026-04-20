"""API tests for the /orders endpoints."""

import httpx
import uuid


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


def test_staff_create_order_without_resident_id_returns_422(auth_client: httpx.Client):
    prop_resp = auth_client.get("/properties/")
    prop_resp.raise_for_status()
    property_id = prop_resp.json()["items"][0]["id"]

    response = auth_client.post(
        "/orders/",
        json={
            "property_id": property_id,
            "title": "Missing resident id",
            "description": "Should fail for staff callers",
            "category": "plumbing",
            "priority": "normal",
            "idempotency_key": str(uuid.uuid4()),
        },
    )
    print(f"[POST /orders/ admin missing resident_id] status={response.status_code}")

    assert response.status_code == 422
    assert "resident_id" in str(response.json()).lower()
