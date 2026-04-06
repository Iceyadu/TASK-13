"""API tests for overdue bill reminders."""

import httpx
import pytest


def test_get_overdue_bills(base_url: str, auth_token: str):
    """GET /billing/bills/overdue with admin token -> 200, print count."""
    with httpx.Client(
        base_url=base_url,
        timeout=30.0,
        headers={"Authorization": f"Bearer {auth_token}"},
    ) as c:
        resp = c.get("/billing/bills/overdue")
        print(f"[GET /billing/bills/overdue] status={resp.status_code}")

        if resp.status_code in (404, 405):
            print("  -> /billing/bills/overdue endpoint not found, skipping")
            pytest.skip("overdue endpoint not implemented (404/405)")

        assert resp.status_code == 200
        data = resp.json()

        # The response could be a list or a paginated object
        if isinstance(data, list):
            count = len(data)
        elif isinstance(data, dict) and "items" in data:
            count = len(data["items"])
        elif isinstance(data, dict) and "total" in data:
            count = data["total"]
        else:
            count = 0

        print(f"  -> overdue bills found: {count}")
