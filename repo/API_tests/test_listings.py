"""API tests for the /listings endpoints."""

import httpx


def test_get_listings_with_admin_token_returns_200(auth_client: httpx.Client):
    response = auth_client.get("/listings/")
    print(f"[GET /listings/ admin] status={response.status_code}")

    assert response.status_code == 200


def test_post_listings_without_auth_returns_401(client: httpx.Client):
    response = client.post(
        "/listings/",
        json={
            "title": "2BR Apartment - Harbor View",
            "description": "Beautiful waterfront unit",
            "price": 2500.00,
        },
    )
    print(f"[POST /listings/ no auth] status={response.status_code}")

    assert response.status_code == 401
