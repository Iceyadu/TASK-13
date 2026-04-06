"""API tests for statement listing and PDF download."""

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
        items = resp.json()["items"]
        assert len(items) > 0, "No properties found in seed data"
        return items[0]["id"]


def _generate_bills(base_url: str, admin_token: str, property_id: str, period: str):
    """Generate bills for the given period."""
    with httpx.Client(
        base_url=base_url,
        timeout=30.0,
        headers={"Authorization": f"Bearer {admin_token}"},
    ) as c:
        # Ensure fee items exist
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

        resp = c.post(
            "/billing/generate",
            json={"property_id": property_id, "billing_period": period},
        )
        print(f"[POST /billing/generate period={period}] status={resp.status_code}")
        return resp


def test_generate_bills_and_list_with_resident_token(base_url: str, auth_token: str):
    """Generate bills, then GET /billing/bills with resident token returns 200."""
    property_id = _get_property_id(base_url, auth_token)
    gen_resp = _generate_bills(base_url, auth_token, property_id, "2026-04")
    assert gen_resp.status_code == 202
    print(f"  -> bills_created={gen_resp.json().get('bills_created')}")

    resident_token, resident_id = _login_as_resident(base_url)
    with httpx.Client(
        base_url=base_url,
        timeout=30.0,
        headers={"Authorization": f"Bearer {resident_token}"},
    ) as c:
        resp = c.get("/billing/bills", params={"resident_id": resident_id})
        print(f"[GET /billing/bills resident] status={resp.status_code}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        print(f"  -> {data['total']} bills found for resident")


def test_download_statement_pdf(base_url: str, auth_token: str):
    """GET /billing/statements/{bill_id}/pdf returns PDF -> 200."""
    property_id = _get_property_id(base_url, auth_token)
    _generate_bills(base_url, auth_token, property_id, "2026-04")

    resident_token, resident_id = _login_as_resident(base_url)
    with httpx.Client(
        base_url=base_url,
        timeout=30.0,
        headers={"Authorization": f"Bearer {resident_token}"},
    ) as c:
        bills_resp = c.get("/billing/bills", params={"resident_id": resident_id})
        bills_resp.raise_for_status()
        items = bills_resp.json()["items"]
        assert len(items) > 0, "No bills found for resident"
        bill_id = items[0]["id"]

        resp = c.get(f"/billing/statements/{bill_id}/pdf")
        print(f"[GET /billing/statements/{{bill_id}}/pdf] status={resp.status_code}")
        assert resp.status_code == 200
        assert "application/pdf" in resp.headers.get("content-type", "")
        assert len(resp.content) > 0
        print(f"  -> PDF size={len(resp.content)} bytes, content-type={resp.headers['content-type']}")
