"""API tests for billing reconciliation endpoints."""

from decimal import Decimal

import httpx


def _get_property_id(base_url: str, admin_token: str) -> str:
    """Fetch the first property id."""
    with httpx.Client(
        base_url=base_url,
        timeout=30.0,
        headers={"Authorization": f"Bearer {admin_token}"},
    ) as c:
        resp = c.get("/properties/")
        resp.raise_for_status()
        return resp.json()["items"][0]["id"]


def _ensure_bills(base_url: str, admin_token: str, property_id: str, period: str):
    """Ensure fee items and bills exist for the period."""
    with httpx.Client(
        base_url=base_url,
        timeout=30.0,
        headers={"Authorization": f"Bearer {admin_token}"},
    ) as c:
        fee_resp = c.get("/billing/fee-items")
        fee_resp.raise_for_status()
        active = [i for i in fee_resp.json()["items"] if i["is_active"]]
        if len(active) == 0:
            c.post(
                "/billing/fee-items",
                json={
                    "property_id": property_id,
                    "name": "Monthly Rent",
                    "amount": 1400.00,
                    "is_taxable": False,
                },
            )
        c.post(
            "/billing/generate",
            json={"property_id": property_id, "billing_period": period},
        )


def test_reconciliation_json(base_url: str, auth_token: str):
    """GET /billing/reconciliation with admin token returns summary with total_billed > 0."""
    property_id = _get_property_id(base_url, auth_token)
    _ensure_bills(base_url, auth_token, property_id, "2026-05")

    with httpx.Client(
        base_url=base_url,
        timeout=30.0,
        headers={"Authorization": f"Bearer {auth_token}"},
    ) as c:
        resp = c.get(
            "/billing/reconciliation",
            params={"property_id": property_id, "billing_period": "2026-05"},
        )
        print(f"[GET /billing/reconciliation] status={resp.status_code}")
        assert resp.status_code == 200

        data = resp.json()
        summary = data["summary"]
        total_billed = Decimal(str(summary["total_billed"]))

        print(f"  -> property_id={data['property_id']}")
        print(f"  -> billing_period={data['billing_period']}")
        print(f"  -> total_billed={summary['total_billed']}")
        print(f"  -> total_received={summary['total_received']}")
        print(f"  -> total_outstanding={summary['total_outstanding']}")
        print(f"  -> total_credits={summary['total_credits']}")
        print(f"  -> total_late_fees={summary['total_late_fees']}")
        print(f"  -> residents count={len(data['residents'])}")

        assert total_billed > 0, f"Expected total_billed > 0, got {total_billed}"


def test_reconciliation_csv(base_url: str, auth_token: str):
    """GET /billing/reconciliation/csv returns text/csv."""
    property_id = _get_property_id(base_url, auth_token)
    _ensure_bills(base_url, auth_token, property_id, "2026-05")

    with httpx.Client(
        base_url=base_url,
        timeout=30.0,
        headers={"Authorization": f"Bearer {auth_token}"},
    ) as c:
        resp = c.get(
            "/billing/reconciliation/csv",
            params={"property_id": property_id, "billing_period": "2026-05"},
        )
        print(f"[GET /billing/reconciliation/csv] status={resp.status_code}")
        assert resp.status_code == 200
        content_type = resp.headers.get("content-type", "")
        assert "text/csv" in content_type, f"Expected text/csv, got {content_type}"
        print(f"  -> content-type={content_type}")
        print(f"  -> CSV content preview: {resp.text[:200]}")
