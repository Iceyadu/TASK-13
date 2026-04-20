"""API tests for the /health endpoints."""

import httpx


def test_health_returns_200_with_status_ok(client: httpx.Client):
    response = client.get("/health")
    print(f"[GET /health] status={response.status_code} body={response.json()}")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_health_ready_returns_200_with_database_connected(client: httpx.Client):
    response = client.get("/health/ready")
    print(f"[GET /health/ready] status={response.status_code} body={response.json()}")

    assert response.status_code == 200
    data = response.json()
    assert data["database"] == "connected"


def test_health_echoes_request_id_header(client: httpx.Client):
    response = client.get("/health", headers={"X-Request-ID": "test-health-req-id"})
    print(f"[GET /health request-id] status={response.status_code}")

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == "test-health-req-id"
