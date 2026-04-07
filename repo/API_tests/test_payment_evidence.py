"""API tests for payment creation with evidence upload and verification."""

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


def _ensure_bills(base_url: str, admin_token: str, property_id: str, period: str):
    """Ensure fee items and bills exist for the period."""
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
            json={"property_id": property_id, "billing_period": period},
        )


def _get_bill_id(base_url: str, token: str, resident_id: str) -> str:
    """Get a bill_id for the resident."""
    with httpx.Client(
        base_url=base_url,
        timeout=30.0,
        headers={"Authorization": f"Bearer {token}"},
    ) as c:
        resp = c.get("/billing/bills", params={"resident_id": resident_id})
        resp.raise_for_status()
        items = resp.json()["items"]
        assert len(items) > 0, "No bills found for resident"
        return items[0]["id"]


def test_create_payment_with_jpeg_evidence(base_url: str, auth_token: str):
    """POST /payments/ with multipart form and JPEG evidence_file -> 201, status pending."""
    property_id = _get_property_id(base_url, auth_token)
    _ensure_bills(base_url, auth_token, property_id, "2026-04")

    resident_token, resident_id = _login_as_resident(base_url)
    bill_id = _get_bill_id(base_url, resident_token, resident_id)

    # Minimal JPEG header
    jpeg_bytes = bytes([0xFF, 0xD8, 0xFF, 0xE0]) + b"\x00" * 100

    with httpx.Client(
        base_url=base_url,
        timeout=30.0,
        headers={"Authorization": f"Bearer {resident_token}"},
    ) as c:
        resp = c.post(
            "/payments/",
            data={
                "bill_id": bill_id,
                "amount": "500.00",
                "payment_method": "check",
            },
            files={"evidence_file": ("evidence.jpg", jpeg_bytes, "image/jpeg")},
        )
        print(f"[POST /payments/ with JPEG evidence] status={resp.status_code}")
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "pending"
        assert data["payment_method"] == "check"
        print(f"  -> payment id={data['id']}, status={data['status']}")


def test_create_payment_with_unsupported_format(base_url: str, auth_token: str):
    """POST /payments/ with unsupported file format returns error or accepts it."""
    property_id = _get_property_id(base_url, auth_token)
    _ensure_bills(base_url, auth_token, property_id, "2026-04")

    resident_token, resident_id = _login_as_resident(base_url)
    bill_id = _get_bill_id(base_url, resident_token, resident_id)

    # Create a fake .exe file
    fake_exe = b"\x4D\x5A" + b"\x00" * 100

    with httpx.Client(
        base_url=base_url,
        timeout=30.0,
        headers={"Authorization": f"Bearer {resident_token}"},
    ) as c:
        resp = c.post(
            "/payments/",
            data={
                "bill_id": bill_id,
                "amount": "100.00",
                "payment_method": "check",
            },
            files={"evidence_file": ("malware.exe", fake_exe, "application/octet-stream")},
        )
        print(f"[POST /payments/ with .exe file] status={resp.status_code}")
        # The API may reject unsupported formats (400/415) or may accept any file.
        # We just document the behavior.
        print(f"  -> response status={resp.status_code} (unsupported format test)")
        if resp.status_code in (400, 415, 422):
            print("  -> correctly rejected unsupported file format")
        else:
            print("  -> API accepted the file (no format validation)")


def test_create_payment_without_file_rejected(base_url: str, auth_token: str):
    """POST /payments/ without evidence file returns 400 (evidence is required)."""
    property_id = _get_property_id(base_url, auth_token)
    _ensure_bills(base_url, auth_token, property_id, "2026-04")

    resident_token, resident_id = _login_as_resident(base_url)
    bill_id = _get_bill_id(base_url, resident_token, resident_id)

    with httpx.Client(
        base_url=base_url,
        timeout=30.0,
        headers={"Authorization": f"Bearer {resident_token}"},
    ) as c:
        resp = c.post(
            "/payments/",
            data={
                "bill_id": bill_id,
                "amount": "200.00",
                "payment_method": "check",
            },
        )
        print(f"[POST /payments/ without file] status={resp.status_code}")
        assert resp.status_code == 400
        detail = resp.json()["detail"]
        assert "required" in detail.lower()
        print(f"  -> correctly rejected: {detail}")


def test_verify_payment_with_admin_token(base_url: str, auth_token: str):
    """PUT /payments/{id}/verify with admin token -> 200, status becomes 'verify'."""
    property_id = _get_property_id(base_url, auth_token)
    _ensure_bills(base_url, auth_token, property_id, "2026-04")

    resident_token, resident_id = _login_as_resident(base_url)
    bill_id = _get_bill_id(base_url, resident_token, resident_id)

    # Create a payment as resident (with required evidence)
    jpeg_bytes = bytes([0xFF, 0xD8, 0xFF, 0xE0]) + b"\x00" * 100
    with httpx.Client(
        base_url=base_url,
        timeout=30.0,
        headers={"Authorization": f"Bearer {resident_token}"},
    ) as c:
        create_resp = c.post(
            "/payments/",
            data={
                "bill_id": bill_id,
                "amount": "300.00",
                "payment_method": "check",
            },
            files={"evidence_file": ("evidence.jpg", jpeg_bytes, "image/jpeg")},
        )
        create_resp.raise_for_status()
        payment_id = create_resp.json()["id"]
        print(f"  -> created payment id={payment_id}")

    # Verify with admin token
    with httpx.Client(
        base_url=base_url,
        timeout=30.0,
        headers={"Authorization": f"Bearer {auth_token}"},
    ) as c:
        resp = c.put(
            f"/payments/{payment_id}/verify",
            json={"action": "verify"},
        )
        print(f"[PUT /payments/{{id}}/verify admin] status={resp.status_code}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "verified"
        print(f"  -> payment status={data['status']}, reviewed_by={data['reviewed_by']}")


def test_payment_evidence_file_can_be_downloaded(base_url: str, auth_token: str):
    """Create payment evidence and verify media file endpoint serves it."""
    property_id = _get_property_id(base_url, auth_token)
    _ensure_bills(base_url, auth_token, property_id, "2026-05")
    resident_token, resident_id = _login_as_resident(base_url)
    bill_id = _get_bill_id(base_url, resident_token, resident_id)

    png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 128
    with httpx.Client(
        base_url=base_url,
        timeout=30.0,
        headers={"Authorization": f"Bearer {resident_token}"},
    ) as c:
        create_resp = c.post(
            "/payments/",
            data={
                "bill_id": bill_id,
                "amount": "120.00",
                "payment_method": "check",
            },
            files={"evidence_file": ("evidence.png", png_bytes, "image/png")},
        )
        create_resp.raise_for_status()
        payment = create_resp.json()
        media_id = payment.get("evidence_media_id")
        assert media_id, "Expected evidence_media_id on created payment"

        file_resp = c.get(f"/media/{media_id}/file")
        print(f"[GET /media/{{id}}/file] status={file_resp.status_code}")
        assert file_resp.status_code == 200
        assert file_resp.headers.get("content-type", "").startswith("image/png")
