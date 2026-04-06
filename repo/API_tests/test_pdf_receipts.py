"""API tests for PDF generation (statements and payment receipts)."""

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
    """Ensure fee items and bills exist, return a bill_id."""
    property_id = _get_property_id(base_url, admin_token)

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


def test_statement_pdf_download(base_url: str, auth_token: str):
    """GET /billing/statements/{bill_id}/pdf -> 200, application/pdf, size > 0."""
    resident_token, resident_id = _login_as_resident(base_url)
    bill_id = _ensure_bills_and_get_bill_id(
        base_url, auth_token, resident_token, resident_id
    )

    with httpx.Client(
        base_url=base_url,
        timeout=30.0,
        headers={"Authorization": f"Bearer {resident_token}"},
    ) as c:
        resp = c.get(f"/billing/statements/{bill_id}/pdf")
        print(f"[GET /billing/statements/{{bill_id}}/pdf] status={resp.status_code}")
        assert resp.status_code == 200

        content_type = resp.headers.get("content-type", "")
        assert "application/pdf" in content_type, f"Expected application/pdf, got {content_type}"
        assert len(resp.content) > 0, "PDF content should not be empty"
        print(f"  -> content-type={content_type}")
        print(f"  -> PDF size={len(resp.content)} bytes")


def test_payment_receipt_pdf_download(base_url: str, auth_token: str):
    """GET /payments/{payment_id}/receipt/pdf -> 200, application/pdf, size > 0."""
    resident_token, resident_id = _login_as_resident(base_url)
    bill_id = _ensure_bills_and_get_bill_id(
        base_url, auth_token, resident_token, resident_id
    )

    # Create a payment
    with httpx.Client(
        base_url=base_url,
        timeout=30.0,
        headers={"Authorization": f"Bearer {resident_token}"},
    ) as c:
        jpeg_bytes = bytes([0xFF, 0xD8, 0xFF, 0xE0]) + b"\x00" * 100
        pay_resp = c.post(
            "/payments/",
            data={
                "bill_id": bill_id,
                "amount": "750.00",
                "payment_method": "money_order",
            },
            files={"evidence_file": ("receipt.jpg", jpeg_bytes, "image/jpeg")},
        )
        print(f"[POST /payments/ for receipt test] status={pay_resp.status_code}")
        pay_resp.raise_for_status()
        payment_id = pay_resp.json()["id"]
        print(f"  -> payment id={payment_id}")

        # Download receipt PDF
        resp = c.get(f"/payments/{payment_id}/receipt/pdf")
        print(f"[GET /payments/{{payment_id}}/receipt/pdf] status={resp.status_code}")
        assert resp.status_code == 200

        content_type = resp.headers.get("content-type", "")
        assert "application/pdf" in content_type, f"Expected application/pdf, got {content_type}"
        assert len(resp.content) > 0, "PDF content should not be empty"
        print(f"  -> content-type={content_type}")
        print(f"  -> PDF size={len(resp.content)} bytes")
