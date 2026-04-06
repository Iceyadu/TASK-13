"""API tests for CSV export endpoints."""

import csv
import io

import httpx


def test_billing_csv_export(base_url: str, auth_token: str):
    """GET /reports/billing/csv with admin token -> 200, Content-Type text/csv."""
    with httpx.Client(
        base_url=base_url,
        timeout=30.0,
        headers={"Authorization": f"Bearer {auth_token}"},
    ) as c:
        resp = c.get("/reports/billing/csv")
        print(f"[GET /reports/billing/csv] status={resp.status_code}")
        assert resp.status_code == 200

        content_type = resp.headers.get("content-type", "")
        assert "text/csv" in content_type, f"Expected text/csv, got {content_type}"
        print(f"  -> content-type={content_type}")

        # Parse CSV and verify headers
        reader = csv.reader(io.StringIO(resp.text))
        rows = list(reader)
        assert len(rows) >= 1, "CSV should have at least a header row"
        headers = rows[0]
        print(f"  -> CSV headers: {headers}")
        expected_headers = ["id", "resident_id", "billing_period", "total", "status", "created_at"]
        assert headers == expected_headers, f"Expected headers {expected_headers}, got {headers}"
        print(f"  -> data rows: {len(rows) - 1}")


def test_payments_csv_export(base_url: str, auth_token: str):
    """GET /reports/payments/csv with admin token -> 200, Content-Type text/csv."""
    with httpx.Client(
        base_url=base_url,
        timeout=30.0,
        headers={"Authorization": f"Bearer {auth_token}"},
    ) as c:
        resp = c.get("/reports/payments/csv")
        print(f"[GET /reports/payments/csv] status={resp.status_code}")
        assert resp.status_code == 200

        content_type = resp.headers.get("content-type", "")
        assert "text/csv" in content_type, f"Expected text/csv, got {content_type}"
        print(f"  -> content-type={content_type}")

        reader = csv.reader(io.StringIO(resp.text))
        rows = list(reader)
        assert len(rows) >= 1, "CSV should have at least a header row"
        headers = rows[0]
        print(f"  -> CSV headers: {headers}")
        expected_headers = ["id", "bill_id", "amount", "payment_method", "status", "created_at"]
        assert headers == expected_headers, f"Expected headers {expected_headers}, got {headers}"
        print(f"  -> data rows: {len(rows) - 1}")


def test_orders_csv_export(base_url: str, auth_token: str):
    """GET /reports/orders/csv with admin token -> 200, Content-Type text/csv."""
    with httpx.Client(
        base_url=base_url,
        timeout=30.0,
        headers={"Authorization": f"Bearer {auth_token}"},
    ) as c:
        resp = c.get("/reports/orders/csv")
        print(f"[GET /reports/orders/csv] status={resp.status_code}")
        assert resp.status_code == 200

        content_type = resp.headers.get("content-type", "")
        assert "text/csv" in content_type, f"Expected text/csv, got {content_type}"
        print(f"  -> content-type={content_type}")

        reader = csv.reader(io.StringIO(resp.text))
        rows = list(reader)
        assert len(rows) >= 1, "CSV should have at least a header row"
        headers = rows[0]
        print(f"  -> CSV headers: {headers}")
        expected_headers = ["id", "resident_id", "title", "category", "status", "created_at"]
        assert headers == expected_headers, f"Expected headers {expected_headers}, got {headers}"
        print(f"  -> data rows: {len(rows) - 1}")
