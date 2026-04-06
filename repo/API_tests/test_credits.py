"""API tests for credit memo (refund request) endpoints."""

import httpx


def _login_as_resident(base_url: str) -> tuple[str, str]:
    """Log in as resident1, return (token, resident_id)."""
    with httpx.Client(base_url=base_url, timeout=30.0) as c:
        resp = c.post(
            "/auth/login",
            json={"username": "resident1", "password": "Resident@Hbr2026"},
        )
        resp.raise_for_status()
        token = resp.json()["access_token"]

    with httpx.Client(
        base_url=base_url,
        timeout=30.0,
        headers={"Authorization": f"Bearer {token}"},
    ) as c:
        me_resp = c.get("/residents/me")
        me_resp.raise_for_status()
        resident_id = me_resp.json()["id"]

    return token, resident_id


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


def _ensure_bills_and_get_bill_id(
    base_url: str, admin_token: str, resident_token: str, resident_id: str
) -> str:
    """Make sure bills exist and return a bill_id."""
    property_id = _get_property_id(base_url, admin_token)

    with httpx.Client(
        base_url=base_url,
        timeout=30.0,
        headers={"Authorization": f"Bearer {admin_token}"},
    ) as c:
        fee_resp = c.get("/billing/fee-items")
        fee_resp.raise_for_status()
        if fee_resp.json()["total"] == 0:
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
            json={"property_id": property_id, "billing_period": "2026-04"},
        )

    with httpx.Client(
        base_url=base_url,
        timeout=30.0,
        headers={"Authorization": f"Bearer {resident_token}"},
    ) as c:
        resp = c.get("/billing/bills", params={"resident_id": resident_id})
        resp.raise_for_status()
        items = resp.json()["items"]
        assert len(items) > 0, "No bills found for resident"
        return items[0]["id"]


def test_create_credit_memo(base_url: str, auth_token: str):
    """POST /credits/ with admin token creates a credit memo -> 201."""
    resident_token, resident_id = _login_as_resident(base_url)
    bill_id = _ensure_bills_and_get_bill_id(
        base_url, auth_token, resident_token, resident_id
    )

    # Credits require staff role (admin/property_manager/accounting_clerk)
    with httpx.Client(
        base_url=base_url,
        timeout=30.0,
        headers={"Authorization": f"Bearer {auth_token}"},
    ) as c:
        resp = c.post(
            "/credits/",
            json={
                "resident_id": resident_id,
                "bill_id": bill_id,
                "amount": 50.00,
                "reason": "Overcharge on parking fee",
            },
        )
        print(f"[POST /credits/] status={resp.status_code}")
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "pending"
        assert float(data["amount"]) == 50.00
        assert data["reason"] == "Overcharge on parking fee"
        print(f"  -> credit id={data['id']}, status={data['status']}, amount={data['amount']}")


def test_list_credits(base_url: str, auth_token: str):
    """GET /credits/ with admin token returns at least 1 item -> 200."""
    # Make sure there is at least one credit
    resident_token, resident_id = _login_as_resident(base_url)
    bill_id = _ensure_bills_and_get_bill_id(
        base_url, auth_token, resident_token, resident_id
    )

    with httpx.Client(
        base_url=base_url,
        timeout=30.0,
        headers={"Authorization": f"Bearer {auth_token}"},
    ) as c:
        # Create one credit to be sure
        c.post(
            "/credits/",
            json={
                "resident_id": resident_id,
                "bill_id": bill_id,
                "amount": 25.00,
                "reason": "Test credit for listing",
            },
        )

        resp = c.get("/credits/")
        print(f"[GET /credits/] status={resp.status_code}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        print(f"  -> {data['total']} credit memos found")


def test_approve_credit_with_admin_token(base_url: str, auth_token: str):
    """PUT /credits/{id}/approve with admin token -> 200, status approved."""
    resident_token, resident_id = _login_as_resident(base_url)
    bill_id = _ensure_bills_and_get_bill_id(
        base_url, auth_token, resident_token, resident_id
    )

    with httpx.Client(
        base_url=base_url,
        timeout=30.0,
        headers={"Authorization": f"Bearer {auth_token}"},
    ) as c:
        # Create a fresh credit to approve
        create_resp = c.post(
            "/credits/",
            json={
                "resident_id": resident_id,
                "bill_id": bill_id,
                "amount": 30.00,
                "reason": "Approve test credit",
            },
        )
        create_resp.raise_for_status()
        credit_id = create_resp.json()["id"]
        print(f"  -> created credit id={credit_id}")

        # Approve
        resp = c.put(
            f"/credits/{credit_id}/approve",
            json={"applied_to_bill_id": bill_id},
        )
        print(f"[PUT /credits/{{id}}/approve admin] status={resp.status_code}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"
        print(f"  -> credit status={data['status']}, approved_by={data['approved_by']}")


def test_download_credit_pdf(base_url: str, auth_token: str):
    """GET /credits/{id}/pdf -> 200, Content-Type application/pdf."""
    resident_token, resident_id = _login_as_resident(base_url)
    bill_id = _ensure_bills_and_get_bill_id(
        base_url, auth_token, resident_token, resident_id
    )

    with httpx.Client(
        base_url=base_url,
        timeout=30.0,
        headers={"Authorization": f"Bearer {auth_token}"},
    ) as c:
        # Create a credit
        create_resp = c.post(
            "/credits/",
            json={
                "resident_id": resident_id,
                "bill_id": bill_id,
                "amount": 15.00,
                "reason": "PDF download test credit",
            },
        )
        create_resp.raise_for_status()
        credit_id = create_resp.json()["id"]

        resp = c.get(f"/credits/{credit_id}/pdf")
        print(f"[GET /credits/{{id}}/pdf] status={resp.status_code}")
        assert resp.status_code == 200
        assert "application/pdf" in resp.headers.get("content-type", "")
        assert len(resp.content) > 0
        print(f"  -> PDF size={len(resp.content)} bytes")
