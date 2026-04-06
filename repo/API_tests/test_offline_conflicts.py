"""Offline fault tolerance and conflict resolution tests.

Covers:
  1. Version conflict detected (409 with structured body)
  2. Keep-theirs resolution (re-submit with server version)
  3. Keep-mine resolution (re-submit with server version, your data)
  4. Merge-fields resolution (mixed data)
  5. Duplicate write prevented by idempotency
  6. Conflict body contains changed_fields
  7. Version check on multiple domains (listings, orders, billing)
"""
import uuid

import httpx
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _login(base_url: str, username: str, password: str) -> str:
    resp = httpx.post(f"{base_url}/auth/login", json={"username": username, "password": password})
    return resp.json()["access_token"]


def _admin(base_url: str) -> str:
    return _login(base_url, "admin", "Admin@Harbor2026")


def _property_id(base_url: str, token: str) -> str:
    resp = httpx.get(f"{base_url}/properties/", headers={"Authorization": f"Bearer {token}"})
    return resp.json()["items"][0]["id"]


def _h(token: str, version: int | None = None) -> dict:
    h = {"Authorization": f"Bearer {token}"}
    if version is not None:
        h["If-Match"] = str(version)
    return h


# ---------------------------------------------------------------------------
# Test 1: Version conflict detected (409)
# ---------------------------------------------------------------------------

def test_version_conflict_returns_409(base_url: str):
    """PUT with stale If-Match returns 409 with structured conflict body."""
    token = _admin(base_url)
    prop_id = _property_id(base_url, token)

    # Create a listing
    resp = httpx.post(f"{base_url}/listings/", json={
        "property_id": prop_id, "title": "Conflict Test Item", "category": "garage_sale",
    }, headers=_h(token))
    listing = resp.json()
    listing_id = listing["id"]
    current_version = listing["version"]
    print(f"[created listing] id={listing_id}, version={current_version}")

    # Update it once (version goes from 1 to 2)
    resp = httpx.put(f"{base_url}/listings/{listing_id}", json={
        "title": "Updated Title"
    }, headers=_h(token, current_version))
    assert resp.status_code == 200
    new_version = resp.json()["version"]
    print(f"[updated] version={new_version}")

    # Now try to update with the STALE version (1)
    resp = httpx.put(f"{base_url}/listings/{listing_id}", json={
        "title": "Stale Update"
    }, headers=_h(token, current_version))  # sending version 1, server is at 2
    print(f"[stale update] status={resp.status_code}")
    assert resp.status_code == 409

    body = resp.json()["detail"]
    assert body["error"] == "conflict"
    assert body["your_version"] == current_version
    assert body["server_version"] == new_version
    assert "your_data" in body
    assert "server_data" in body
    assert "changed_fields" in body
    assert "title" in body["changed_fields"]
    print(f"  -> conflict: your_v={body['your_version']}, server_v={body['server_version']}")
    print(f"  -> your_data={body['your_data']}")
    print(f"  -> server_data={body['server_data']}")
    print(f"  -> changed_fields={body['changed_fields']}")


# ---------------------------------------------------------------------------
# Test 2: Keep-theirs resolution
# ---------------------------------------------------------------------------

def test_keep_theirs_resolution(base_url: str):
    """After a 409, re-submit with server's version and server's data."""
    token = _admin(base_url)
    prop_id = _property_id(base_url, token)

    resp = httpx.post(f"{base_url}/listings/", json={
        "property_id": prop_id, "title": "Keep Theirs Test", "category": "parking_sublet",
    }, headers=_h(token))
    listing_id = resp.json()["id"]
    v1 = resp.json()["version"]

    # User A updates
    httpx.put(f"{base_url}/listings/{listing_id}", json={
        "title": "User A Title"
    }, headers=_h(token, v1))

    # User B tries with stale version
    conflict_resp = httpx.put(f"{base_url}/listings/{listing_id}", json={
        "title": "User B Title"
    }, headers=_h(token, v1))
    assert conflict_resp.status_code == 409
    conflict = conflict_resp.json()["detail"]

    # Keep theirs: re-submit with server's data and server's version
    server_v = conflict["server_version"]
    resp = httpx.put(f"{base_url}/listings/{listing_id}", json={
        "title": conflict["server_data"]["title"]  # "User A Title"
    }, headers=_h(token, server_v))
    print(f"[keep theirs] status={resp.status_code}")
    assert resp.status_code == 200
    assert resp.json()["title"] == "User A Title"
    print(f"  -> title={resp.json()['title']} (kept theirs)")


# ---------------------------------------------------------------------------
# Test 3: Keep-mine resolution
# ---------------------------------------------------------------------------

def test_keep_mine_resolution(base_url: str):
    """After a 409, re-submit with server's version but your original data."""
    token = _admin(base_url)
    prop_id = _property_id(base_url, token)

    resp = httpx.post(f"{base_url}/listings/", json={
        "property_id": prop_id, "title": "Keep Mine Test", "category": "amenity_addon", "price": 10.00,
    }, headers=_h(token))
    listing_id = resp.json()["id"]
    v1 = resp.json()["version"]

    # User A updates
    httpx.put(f"{base_url}/listings/{listing_id}", json={
        "title": "User A Changed This"
    }, headers=_h(token, v1))

    # User B tries with stale version
    conflict_resp = httpx.put(f"{base_url}/listings/{listing_id}", json={
        "title": "User B Wants This"
    }, headers=_h(token, v1))
    assert conflict_resp.status_code == 409
    conflict = conflict_resp.json()["detail"]

    # Keep mine: re-submit with MY data but server's version
    server_v = conflict["server_version"]
    resp = httpx.put(f"{base_url}/listings/{listing_id}", json={
        "title": conflict["your_data"]["title"]  # "User B Wants This"
    }, headers=_h(token, server_v))
    print(f"[keep mine] status={resp.status_code}")
    assert resp.status_code == 200
    assert resp.json()["title"] == "User B Wants This"
    print(f"  -> title={resp.json()['title']} (kept mine)")


# ---------------------------------------------------------------------------
# Test 4: Merge-fields resolution
# ---------------------------------------------------------------------------

def test_merge_fields_resolution(base_url: str):
    """After a 409, merge different fields from both versions."""
    token = _admin(base_url)
    prop_id = _property_id(base_url, token)

    resp = httpx.post(f"{base_url}/listings/", json={
        "property_id": prop_id, "title": "Merge Test", "description": "Original desc",
        "category": "garage_sale", "price": 50.00,
    }, headers=_h(token))
    listing_id = resp.json()["id"]
    v1 = resp.json()["version"]

    # User A updates title
    httpx.put(f"{base_url}/listings/{listing_id}", json={
        "title": "A's Title", "description": "A's Desc"
    }, headers=_h(token, v1))

    # User B tries updating title + description with stale version
    conflict_resp = httpx.put(f"{base_url}/listings/{listing_id}", json={
        "title": "B's Title", "description": "B's Desc"
    }, headers=_h(token, v1))
    assert conflict_resp.status_code == 409
    conflict = conflict_resp.json()["detail"]

    # Merge: take title from A (theirs) and description from B (mine)
    server_v = conflict["server_version"]
    resp = httpx.put(f"{base_url}/listings/{listing_id}", json={
        "title": conflict["server_data"]["title"],       # "A's Title" (theirs)
        "description": conflict["your_data"]["description"],  # "B's Desc" (mine)
    }, headers=_h(token, server_v))
    print(f"[merge fields] status={resp.status_code}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "A's Title"
    assert data["description"] == "B's Desc"
    print(f"  -> title={data['title']} (theirs), description={data['description']} (mine)")


# ---------------------------------------------------------------------------
# Test 5: Duplicate write prevented by idempotency
# ---------------------------------------------------------------------------

def test_duplicate_write_prevented_by_idempotency(base_url: str):
    """Creating an order twice with the same idempotency key returns same order."""
    token = _login(base_url, "resident1", "Resident@Hbr2026")
    admin_token = _admin(base_url)
    prop_id = _property_id(base_url, admin_token)

    idem_key = str(uuid.uuid4())

    resp1 = httpx.post(f"{base_url}/orders/", json={
        "property_id": prop_id, "title": "Idempotent Order",
        "idempotency_key": idem_key,
    }, headers={"Authorization": f"Bearer {token}"})
    assert resp1.status_code == 201
    order_id_1 = resp1.json()["id"]

    resp2 = httpx.post(f"{base_url}/orders/", json={
        "property_id": prop_id, "title": "Different Title Same Key",
        "idempotency_key": idem_key,
    }, headers={"Authorization": f"Bearer {token}"})
    # Returns the existing order, not a new one
    assert resp2.status_code in (200, 201)
    order_id_2 = resp2.json()["id"]

    print(f"[idempotency] order1={order_id_1[:8]}, order2={order_id_2[:8]}")
    assert order_id_1 == order_id_2
    assert resp2.json()["title"] == "Idempotent Order"  # original title kept
    print(f"  -> same order returned, duplicate prevented")


# ---------------------------------------------------------------------------
# Test 6: Conflict body contains correct changed_fields
# ---------------------------------------------------------------------------

def test_conflict_body_contains_changed_fields(base_url: str):
    """The 409 body correctly identifies which fields differ."""
    token = _admin(base_url)

    # Use fee items to test another domain
    prop_id = _property_id(base_url, token)
    resp = httpx.post(f"{base_url}/billing/fee-items", json={
        "property_id": prop_id, "name": "Test Fee", "amount": 100.00, "is_taxable": False,
    }, headers=_h(token))
    fee_id = resp.json()["id"]
    v1 = resp.json()["version"]

    # Update name
    httpx.put(f"{base_url}/billing/fee-items/{fee_id}", json={
        "name": "Updated Fee Name"
    }, headers=_h(token, v1))

    # Stale update of name
    conflict_resp = httpx.put(f"{base_url}/billing/fee-items/{fee_id}", json={
        "name": "Stale Fee Name"
    }, headers=_h(token, v1))
    assert conflict_resp.status_code == 409
    body = conflict_resp.json()["detail"]
    print(f"[changed_fields] fields={body['changed_fields']}")
    assert "name" in body["changed_fields"]
    assert body["your_data"]["name"] == "Stale Fee Name"
    assert body["server_data"]["name"] == "Updated Fee Name"
    print(f"  -> your={body['your_data']['name']}, server={body['server_data']['name']}")


# ---------------------------------------------------------------------------
# Test 7: Version check across multiple domains
# ---------------------------------------------------------------------------

def test_version_conflict_on_orders(base_url: str):
    """Verify 409 conflict works on order updates too."""
    admin_token = _admin(base_url)
    resident_token = _login(base_url, "resident1", "Resident@Hbr2026")
    prop_id = _property_id(base_url, admin_token)

    # Create order
    resp = httpx.post(f"{base_url}/orders/", json={
        "property_id": prop_id, "title": "Order Conflict Test",
        "idempotency_key": str(uuid.uuid4()),
    }, headers={"Authorization": f"Bearer {resident_token}"})
    order_id = resp.json()["id"]
    v1 = resp.json()["version"]

    # Admin updates priority
    httpx.put(f"{base_url}/orders/{order_id}", json={
        "priority": "urgent"
    }, headers=_h(admin_token, v1))

    # Stale update
    conflict_resp = httpx.put(f"{base_url}/orders/{order_id}", json={
        "priority": "low"
    }, headers=_h(admin_token, v1))
    print(f"[order conflict] status={conflict_resp.status_code}")
    assert conflict_resp.status_code == 409
    body = conflict_resp.json()["detail"]
    assert body["error"] == "conflict"
    assert "priority" in body["changed_fields"]
    print(f"  -> conflict detected on order, changed_fields={body['changed_fields']}")
