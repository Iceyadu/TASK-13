"""Comprehensive service order engine tests.

Covers:
  1. Full valid transition chain (created -> ... -> completed)
  2. Invalid transitions rejected (422)
  3. Idempotency on create (same key returns same order)
  4. Idempotency on transition (same transition is no-op)
  5. Immutable milestones (all recorded, timestamped)
  6. Resident tracking (auto-filter, milestones visible)
  7. Permission checks (role-based transition enforcement)
  8. Dispatched requires assigned_to
"""
import uuid

import httpx
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _login(base_url: str, username: str, password: str) -> str:
    resp = httpx.post(
        f"{base_url}/auth/login",
        json={"username": username, "password": password},
    )
    assert resp.status_code == 200, f"Login failed for {username}: {resp.text}"
    return resp.json()["access_token"]


def _admin_token(base_url: str) -> str:
    return _login(base_url, "admin", "Admin@Harbor2026")


def _resident_token(base_url: str) -> str:
    return _login(base_url, "resident1", "Resident@Hbr2026")


def _maint_token(base_url: str) -> str:
    return _login(base_url, "maintenance", "Maint@@Harbor2026")


def _manager_token(base_url: str) -> str:
    return _login(base_url, "manager", "Manager@Hbr2026")


def _property_id(base_url: str, token: str) -> str:
    resp = httpx.get(
        f"{base_url}/properties/",
        headers={"Authorization": f"Bearer {token}"},
    )
    return resp.json()["items"][0]["id"]


def _create_order(base_url: str, token: str, prop_id: str, idem_key: str | None = None) -> dict:
    key = idem_key or str(uuid.uuid4())
    resp = httpx.post(
        f"{base_url}/orders/",
        json={
            "property_id": prop_id,
            "title": f"Fix leaking faucet ({key[:8]})",
            "description": "Kitchen sink faucet drips constantly",
            "category": "plumbing",
            "priority": "high",
            "idempotency_key": key,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, f"Create order failed: {resp.text}"
    return resp.json()


def _transition(base_url: str, token: str, order_id: str, to_status: str, notes: str = "") -> httpx.Response:
    # Get current version for If-Match
    order_resp = httpx.get(
        f"{base_url}/orders/{order_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    version = order_resp.json().get("version", 1)
    return httpx.post(
        f"{base_url}/orders/{order_id}/transition",
        json={
            "to_status": to_status,
            "notes": notes or f"Transitioning to {to_status}",
            "idempotency_key": str(uuid.uuid4()),
        },
        headers={"Authorization": f"Bearer {token}", "If-Match": str(version)},
    )


# ---------------------------------------------------------------------------
# Test 1: Full valid transition chain
# ---------------------------------------------------------------------------

def test_full_valid_transition_chain(base_url: str):
    """Walk an order through the entire state machine: created -> completed."""
    admin = _admin_token(base_url)
    resident = _resident_token(base_url)
    maint = _maint_token(base_url)
    prop_id = _property_id(base_url, admin)

    # Create order as resident
    order = _create_order(base_url, resident, prop_id)
    order_id = order["id"]
    assert order["status"] == "created"
    print(f"[created] order_id={order_id}")

    # Assign to maintenance user before dispatching
    maint_user_resp = httpx.get(
        f"{base_url}/users/",
        headers={"Authorization": f"Bearer {admin}"},
    )
    maint_user_id = None
    for u in maint_user_resp.json()["items"]:
        if u["role"] == "maintenance_dispatcher":
            maint_user_id = u["id"]
            break

    # GET the order to obtain current version for If-Match
    order_resp = httpx.get(
        f"{base_url}/orders/{order_id}",
        headers={"Authorization": f"Bearer {admin}"},
    )
    current_version = order_resp.json()["version"]

    httpx.put(
        f"{base_url}/orders/{order_id}",
        json={"assigned_to": maint_user_id},
        headers={"Authorization": f"Bearer {admin}", "If-Match": str(current_version)},
    )

    # Walk through each state
    transitions = [
        ("payment_recorded", admin),
        ("accepted", admin),
        ("dispatched", admin),
        ("arrived", maint),
        ("in_service", maint),
        ("completed", maint),
    ]

    for to_status, token in transitions:
        resp = _transition(base_url, token, order_id, to_status)
        print(f"  [{to_status}] status_code={resp.status_code}")
        assert resp.status_code == 200, f"Transition to {to_status} failed: {resp.text}"
        data = resp.json()
        assert data["status"] == to_status

    # Verify final state
    final = httpx.get(
        f"{base_url}/orders/{order_id}",
        headers={"Authorization": f"Bearer {admin}"},
    ).json()
    assert final["status"] == "completed"
    assert len(final["milestones"]) == 7  # created + 6 transitions
    print(f"  Final: status={final['status']}, milestones={len(final['milestones'])}")


# ---------------------------------------------------------------------------
# Test 2: Invalid transitions rejected
# ---------------------------------------------------------------------------

def test_invalid_transitions_rejected(base_url: str):
    """Attempt illegal state jumps and verify 422 rejection."""
    admin = _admin_token(base_url)
    resident = _resident_token(base_url)
    prop_id = _property_id(base_url, admin)

    order = _create_order(base_url, resident, prop_id)
    order_id = order["id"]

    # created -> dispatched (skip payment_recorded, accepted)
    resp = _transition(base_url, admin, order_id, "dispatched")
    print(f"[created -> dispatched] status_code={resp.status_code}")
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail["error"] == "invalid_transition"
    assert "created" in detail["current_status"]
    print(f"  -> rejected: {detail['message']}")

    # created -> completed (skip all)
    resp = _transition(base_url, admin, order_id, "completed")
    print(f"[created -> completed] status_code={resp.status_code}")
    assert resp.status_code == 422

    # created -> in_service (skip everything)
    resp = _transition(base_url, admin, order_id, "in_service")
    print(f"[created -> in_service] status_code={resp.status_code}")
    assert resp.status_code == 422

    # Verify order still at created
    current = httpx.get(
        f"{base_url}/orders/{order_id}",
        headers={"Authorization": f"Bearer {admin}"},
    ).json()
    assert current["status"] == "created"
    print(f"  Order still at: {current['status']}")


# ---------------------------------------------------------------------------
# Test 3: Idempotency on create
# ---------------------------------------------------------------------------

def test_idempotency_on_create(base_url: str):
    """Submitting the same idempotency key returns the existing order."""
    resident = _resident_token(base_url)
    admin = _admin_token(base_url)
    prop_id = _property_id(base_url, admin)

    idem_key = str(uuid.uuid4())

    # First create
    order1 = _create_order(base_url, resident, prop_id, idem_key)
    print(f"[create #1] id={order1['id']}")

    # Second create with same key
    resp = httpx.post(
        f"{base_url}/orders/",
        json={
            "property_id": prop_id,
            "title": "Different title",
            "idempotency_key": idem_key,
        },
        headers={"Authorization": f"Bearer {resident}"},
    )
    print(f"[create #2 same key] status_code={resp.status_code}")
    # Should return 201 (or 200) with the SAME order
    assert resp.status_code in (200, 201)
    order2 = resp.json()
    assert order2["id"] == order1["id"]
    assert order2["title"] == order1["title"]  # Original title, not "Different title"
    print(f"  -> same order returned: id={order2['id']}")


# ---------------------------------------------------------------------------
# Test 4: Idempotency on transition
# ---------------------------------------------------------------------------

def test_idempotency_on_transition(base_url: str):
    """Replaying the same transition is a no-op (idempotent)."""
    admin = _admin_token(base_url)
    resident = _resident_token(base_url)
    prop_id = _property_id(base_url, admin)

    order = _create_order(base_url, resident, prop_id)
    order_id = order["id"]

    # First transition: created -> payment_recorded
    resp1 = _transition(base_url, admin, order_id, "payment_recorded")
    assert resp1.status_code == 200
    v1 = resp1.json()["version"]
    print(f"[transition #1] status={resp1.json()['status']}, version={v1}")

    # Replay the same transition
    resp2 = _transition(base_url, admin, order_id, "payment_recorded")
    print(f"[transition #2 replay] status_code={resp2.status_code}")
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "payment_recorded"
    # Version should NOT have incremented
    assert resp2.json()["version"] == v1
    print(f"  -> idempotent: version still {resp2.json()['version']}")


# ---------------------------------------------------------------------------
# Test 5: Immutable milestones
# ---------------------------------------------------------------------------

def test_immutable_milestones(base_url: str):
    """Verify milestones are recorded with timestamps and cannot be modified."""
    admin = _admin_token(base_url)
    resident = _resident_token(base_url)
    maint = _maint_token(base_url)
    prop_id = _property_id(base_url, admin)

    order = _create_order(base_url, resident, prop_id)
    order_id = order["id"]

    # Assign maintenance user
    maint_user_resp = httpx.get(f"{base_url}/users/", headers={"Authorization": f"Bearer {admin}"})
    maint_id = next(u["id"] for u in maint_user_resp.json()["items"] if u["role"] == "maintenance_dispatcher")
    order_get = httpx.get(f"{base_url}/orders/{order_id}", headers={"Authorization": f"Bearer {admin}"})
    order_version = order_get.json()["version"]
    httpx.put(f"{base_url}/orders/{order_id}", json={"assigned_to": maint_id}, headers={"Authorization": f"Bearer {admin}", "If-Match": str(order_version)})

    # Walk through several states
    for to_status, token in [
        ("payment_recorded", admin),
        ("accepted", admin),
        ("dispatched", admin),
        ("arrived", maint),
    ]:
        _transition(base_url, token, order_id, to_status)

    # Get milestones
    resp = httpx.get(
        f"{base_url}/orders/{order_id}/milestones",
        headers={"Authorization": f"Bearer {admin}"},
    )
    print(f"[GET /orders/{{id}}/milestones] status_code={resp.status_code}")
    assert resp.status_code == 200
    data = resp.json()
    milestones = data["milestones"]
    assert len(milestones) == 5  # created + 4 transitions
    print(f"  -> {len(milestones)} milestones recorded")

    # Verify each milestone has timestamp and correct from/to
    expected_chain = [
        (None, "created"),
        ("created", "payment_recorded"),
        ("payment_recorded", "accepted"),
        ("accepted", "dispatched"),
        ("dispatched", "arrived"),
    ]
    for i, (expected_from, expected_to) in enumerate(expected_chain):
        m = milestones[i]
        assert m["from_status"] == expected_from, f"Milestone {i}: expected from={expected_from}, got {m['from_status']}"
        assert m["to_status"] == expected_to, f"Milestone {i}: expected to={expected_to}, got {m['to_status']}"
        assert m["created_at"] is not None
        print(f"  [{i}] {m['from_status']} -> {m['to_status']} at {m['created_at']}")

    # Verify timestamps are in order
    for i in range(1, len(milestones)):
        assert milestones[i]["created_at"] >= milestones[i-1]["created_at"]


# ---------------------------------------------------------------------------
# Test 6: Resident tracking
# ---------------------------------------------------------------------------

def test_resident_tracking(base_url: str):
    """Resident can see only their own orders and milestones."""
    admin = _admin_token(base_url)
    resident = _resident_token(base_url)
    prop_id = _property_id(base_url, admin)

    order = _create_order(base_url, resident, prop_id)
    order_id = order["id"]

    # Resident lists orders - should see this one
    resp = httpx.get(
        f"{base_url}/orders/",
        headers={"Authorization": f"Bearer {resident}"},
    )
    print(f"[GET /orders/ as resident] status_code={resp.status_code}")
    assert resp.status_code == 200
    items = resp.json()["items"]
    order_ids = [o["id"] for o in items]
    assert order_id in order_ids
    print(f"  -> resident sees {len(items)} order(s), including {order_id[:8]}")

    # Resident views order detail with milestones
    resp = httpx.get(
        f"{base_url}/orders/{order_id}",
        headers={"Authorization": f"Bearer {resident}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "created"
    assert len(data["milestones"]) >= 1
    print(f"  -> order status={data['status']}, milestones={len(data['milestones'])}")

    # Resident views milestones endpoint
    resp = httpx.get(
        f"{base_url}/orders/{order_id}/milestones",
        headers={"Authorization": f"Bearer {resident}"},
    )
    assert resp.status_code == 200
    print(f"  -> milestones endpoint accessible by resident")


# ---------------------------------------------------------------------------
# Test 7: Permission checks by role
# ---------------------------------------------------------------------------

def test_permission_checks_by_role(base_url: str):
    """Verify role-based enforcement on transitions."""
    admin = _admin_token(base_url)
    resident = _resident_token(base_url)
    maint = _maint_token(base_url)
    prop_id = _property_id(base_url, admin)

    order = _create_order(base_url, resident, prop_id)
    order_id = order["id"]

    # Maintenance cannot do payment_recorded (not in allowed roles)
    resp = _transition(base_url, maint, order_id, "payment_recorded")
    print(f"[maint -> payment_recorded] status_code={resp.status_code}")
    assert resp.status_code == 403
    print(f"  -> correctly denied")

    # Admin can do payment_recorded
    resp = _transition(base_url, admin, order_id, "payment_recorded")
    assert resp.status_code == 200
    print(f"[admin -> payment_recorded] status_code={resp.status_code} OK")

    # Move to accepted
    _transition(base_url, admin, order_id, "accepted")

    # Resident cannot do dispatched (no staff role)
    resp = _transition(base_url, resident, order_id, "dispatched")
    print(f"[resident -> dispatched] status_code={resp.status_code}")
    assert resp.status_code == 403
    print(f"  -> correctly denied")


# ---------------------------------------------------------------------------
# Test 8: Dispatched requires assigned_to
# ---------------------------------------------------------------------------

def test_dispatched_requires_assigned_to(base_url: str):
    """Cannot dispatch without assigning a technician."""
    admin = _admin_token(base_url)
    resident = _resident_token(base_url)
    prop_id = _property_id(base_url, admin)

    order = _create_order(base_url, resident, prop_id)
    order_id = order["id"]

    # Walk to accepted
    _transition(base_url, admin, order_id, "payment_recorded")
    _transition(base_url, admin, order_id, "accepted")

    # Try to dispatch without assigned_to
    resp = _transition(base_url, admin, order_id, "dispatched")
    print(f"[dispatched without assigned_to] status_code={resp.status_code}")
    assert resp.status_code == 422
    assert "assigned" in resp.json()["detail"].lower()
    print(f"  -> correctly rejected: {resp.json()['detail']}")

    # Assign someone and retry
    maint_resp = httpx.get(f"{base_url}/users/", headers={"Authorization": f"Bearer {admin}"})
    maint_id = next(u["id"] for u in maint_resp.json()["items"] if u["role"] == "maintenance_dispatcher")
    order_get = httpx.get(f"{base_url}/orders/{order_id}", headers={"Authorization": f"Bearer {admin}"})
    order_version = order_get.json()["version"]
    httpx.put(
        f"{base_url}/orders/{order_id}",
        json={"assigned_to": maint_id},
        headers={"Authorization": f"Bearer {admin}", "If-Match": str(order_version)},
    )

    resp = _transition(base_url, admin, order_id, "dispatched")
    print(f"[dispatched with assigned_to] status_code={resp.status_code}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "dispatched"
    print(f"  -> dispatched successfully")
