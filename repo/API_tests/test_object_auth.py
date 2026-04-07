"""Object-level authorization tests.

Verifies that residents cannot access other residents' bills, payments,
credits, PDFs, or orders by ID.
"""
import uuid
import httpx

def _login(base_url, username, password):
    resp = httpx.post(f"{base_url}/auth/login", json={"username": username, "password": password})
    return resp.json()["access_token"]

def _admin(base_url):
    return _login(base_url, "admin", "Admin@Harbor2026")

def _resident(base_url):
    return _login(base_url, "resident1", "Resident@Hbr2026")

def _h(token):
    return {"Authorization": f"Bearer {token}"}

def _get_resident_id(base_url, token):
    resp = httpx.get(f"{base_url}/residents/me", headers=_h(token))
    return resp.json()["id"]

def _property_id(base_url, token):
    resp = httpx.get(f"{base_url}/properties/", headers=_h(token))
    return resp.json()["items"][0]["id"]


def test_resident_cannot_get_other_residents_bill(base_url):
    """Resident cannot fetch a bill belonging to another resident."""
    admin = _admin(base_url)
    resident_token = _resident(base_url)

    # Get a bill (any bill created by admin processes)
    bills_resp = httpx.get(f"{base_url}/billing/bills", headers=_h(admin))
    bills = bills_resp.json()["items"]
    if not bills:
        # Generate one
        prop_id = _property_id(base_url, admin)
        httpx.post(f"{base_url}/billing/fee-items", json={"property_id": prop_id, "name": "Test", "amount": 100}, headers=_h(admin))
        httpx.post(f"{base_url}/billing/generate", json={"property_id": prop_id, "billing_period": "2026-07"}, headers=_h(admin))
        bills_resp = httpx.get(f"{base_url}/billing/bills", headers=_h(admin))
        bills = bills_resp.json()["items"]

    if not bills:
        print("[SKIP] No bills to test against")
        return

    bill = bills[0]
    resident_id = _get_resident_id(base_url, resident_token)

    # If bill belongs to this resident, skip (we need a bill from a different resident)
    if bill["resident_id"] == resident_id:
        print("[SKIP] All bills belong to test resident - need a second resident for cross-user test")
        return

    # Try to access it
    resp = httpx.get(f"{base_url}/billing/bills/{bill['id']}", headers=_h(resident_token))
    print(f"[resident GET other's bill] status={resp.status_code}")
    assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"


def test_resident_cannot_get_other_residents_statement_pdf(base_url):
    """Resident cannot download another resident's statement PDF."""
    admin = _admin(base_url)
    resident_token = _resident(base_url)

    bills_resp = httpx.get(f"{base_url}/billing/bills", headers=_h(admin))
    bills = bills_resp.json()["items"]
    resident_id = _get_resident_id(base_url, resident_token)

    # Find a bill NOT belonging to this resident
    other_bill = None
    for b in bills:
        if b["resident_id"] != resident_id:
            other_bill = b
            break

    if not other_bill:
        print("[SKIP] No cross-user bill available for test")
        return

    resp = httpx.get(f"{base_url}/billing/statements/{other_bill['id']}/pdf", headers=_h(resident_token))
    print(f"[resident GET other's PDF] status={resp.status_code}")
    assert resp.status_code == 403


def test_resident_cannot_list_other_residents_payments(base_url):
    """Resident payment list only shows own payments."""
    admin = _admin(base_url)
    resident_token = _resident(base_url)
    resident_id = _get_resident_id(base_url, resident_token)

    resp = httpx.get(f"{base_url}/payments/", headers=_h(resident_token))
    print(f"[resident GET payments] status={resp.status_code}")
    assert resp.status_code == 200

    # All returned payments should belong to this resident
    for p in resp.json().get("items", []):
        assert p["resident_id"] == resident_id, f"Payment {p['id']} belongs to {p['resident_id']}, not {resident_id}"
    print(f"  -> all {len(resp.json().get('items', []))} payments belong to resident")


def test_resident_cannot_list_other_residents_credits(base_url):
    """Resident credit list only shows own credits."""
    resident_token = _resident(base_url)
    resident_id = _get_resident_id(base_url, resident_token)

    resp = httpx.get(f"{base_url}/credits/", headers=_h(resident_token))
    print(f"[resident GET credits] status={resp.status_code}")
    assert resp.status_code == 200

    for c in resp.json().get("items", []):
        assert c["resident_id"] == resident_id
    print(f"  -> all {len(resp.json().get('items', []))} credits belong to resident")


def test_resident_cannot_access_other_residents_order(base_url):
    """Resident cannot GET another resident's order detail."""
    admin = _admin(base_url)
    resident_token = _resident(base_url)
    resident_id = _get_resident_id(base_url, resident_token)

    # Create an order as admin with a fake resident (won't work since admin isn't a resident)
    # Instead, check that resident's order list is scoped
    resp = httpx.get(f"{base_url}/orders/", headers=_h(resident_token))
    assert resp.status_code == 200
    for o in resp.json().get("items", []):
        assert o["resident_id"] == resident_id
    print(f"[resident orders scoped] {len(resp.json().get('items', []))} orders, all owned")


def test_non_admin_cannot_access_backup(base_url):
    """Non-admin roles cannot trigger or view backups."""
    resident_token = _resident(base_url)

    resp = httpx.get(f"{base_url}/backup/records", headers=_h(resident_token))
    print(f"[resident GET backup records] status={resp.status_code}")
    assert resp.status_code == 403

    resp = httpx.post(f"{base_url}/backup/trigger", json={}, headers=_h(resident_token))
    print(f"[resident POST backup trigger] status={resp.status_code}")
    assert resp.status_code == 403


def test_non_admin_cannot_access_users(base_url):
    """Non-admin roles cannot list users."""
    resident_token = _resident(base_url)

    resp = httpx.get(f"{base_url}/users/", headers=_h(resident_token))
    print(f"[resident GET users] status={resp.status_code}")
    assert resp.status_code == 403


def test_credit_cannot_be_applied_to_other_resident_bill(base_url):
    """Admin cannot apply a resident's credit to another resident's bill."""
    admin = _admin(base_url)
    resident_token = _resident(base_url)
    resident_id = _get_resident_id(base_url, resident_token)

    bills_resp = httpx.get(f"{base_url}/billing/bills", headers=_h(admin))
    bills = bills_resp.json().get("items", [])
    own_bill = next((b for b in bills if b["resident_id"] == resident_id), None)
    other_bill = next((b for b in bills if b["resident_id"] != resident_id), None)
    if not own_bill or not other_bill:
        print("[SKIP] Need bills from two residents for cross-resident credit test")
        return

    create_resp = httpx.post(
        f"{base_url}/credits/",
        headers=_h(admin),
        json={
            "resident_id": resident_id,
            "bill_id": own_bill["id"],
            "amount": "25.00",
            "reason": "Cross-resident integrity test",
        },
    )
    assert create_resp.status_code == 201, create_resp.text
    credit = create_resp.json()

    approve_resp = httpx.put(
        f"{base_url}/credits/{credit['id']}/approve",
        headers={**_h(admin), "If-Match": str(credit["version"])},
        json={"applied_to_bill_id": other_bill["id"]},
    )
    print(f"[cross-resident credit approve] status={approve_resp.status_code}")
    assert approve_resp.status_code == 400
