"""API tests for resident address CRUD endpoints."""

import httpx


def _login_as_resident(base_url: str) -> str:
    """Log in as resident1 and return the access token."""
    with httpx.Client(base_url=base_url, timeout=30.0) as c:
        resp = c.post(
            "/auth/login",
            json={"username": "resident1", "password": "Resident@Hbr2026"},
        )
        resp.raise_for_status()
        return resp.json()["access_token"]


def _get_resident_id(base_url: str, token: str) -> str:
    """Fetch the resident profile and return the resident id."""
    with httpx.Client(
        base_url=base_url,
        timeout=30.0,
        headers={"Authorization": f"Bearer {token}"},
    ) as c:
        resp = c.get("/residents/me")
        resp.raise_for_status()
        return resp.json()["id"]


def test_create_shipping_address_returns_201(base_url: str):
    """POST /residents/me/addresses with resident token creates shipping address -> 201."""
    token = _login_as_resident(base_url)
    with httpx.Client(
        base_url=base_url,
        timeout=30.0,
        headers={"Authorization": f"Bearer {token}"},
    ) as c:
        resp = c.post(
            "/residents/me/addresses",
            json={
                "address_type": "shipping",
                "line1": "123 Harbor Lane",
                "line2": "Apt 4B",
                "city": "Bayville",
                "state": "CA",
                "zip_code": "90210",
                "is_primary": True,
            },
        )
        print(f"[POST /residents/me/addresses shipping] status={resp.status_code}")
        assert resp.status_code == 201
        data = resp.json()
        assert data["address_type"] == "shipping"
        assert data["line1"] == "123 Harbor Lane"
        print(f"  -> address id={data['id']}")


def test_create_mailing_address_returns_201(base_url: str):
    """POST /residents/me/addresses with resident token creates mailing address -> 201."""
    token = _login_as_resident(base_url)
    with httpx.Client(
        base_url=base_url,
        timeout=30.0,
        headers={"Authorization": f"Bearer {token}"},
    ) as c:
        resp = c.post(
            "/residents/me/addresses",
            json={
                "address_type": "mailing",
                "line1": "456 Seaside Blvd",
                "city": "Bayville",
                "state": "CA",
                "zip_code": "90211",
                "is_primary": False,
            },
        )
        print(f"[POST /residents/me/addresses mailing] status={resp.status_code}")
        assert resp.status_code == 201
        data = resp.json()
        assert data["address_type"] == "mailing"
        print(f"  -> address id={data['id']}")


def test_list_my_addresses_returns_both(base_url: str):
    """GET /residents/me/addresses returns addresses -> 200."""
    token = _login_as_resident(base_url)
    with httpx.Client(
        base_url=base_url,
        timeout=30.0,
        headers={"Authorization": f"Bearer {token}"},
    ) as c:
        # Create two addresses so we know there are at least two
        for addr_type in ("shipping", "mailing"):
            c.post(
                "/residents/me/addresses",
                json={
                    "address_type": addr_type,
                    "line1": f"999 Test St ({addr_type})",
                    "city": "Testville",
                    "state": "TX",
                    "zip_code": "73301",
                },
            )

        resp = c.get("/residents/me/addresses")
        print(f"[GET /residents/me/addresses] status={resp.status_code}")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 2
        types_found = {a["address_type"] for a in data}
        print(f"  -> {len(data)} addresses, types={types_found}")
        assert "shipping" in types_found
        assert "mailing" in types_found


def test_admin_updates_address_returns_200(base_url: str, auth_token: str):
    """PUT /residents/{resident_id}/addresses/{id} with admin token updates address -> 200."""
    resident_token = _login_as_resident(base_url)
    resident_id = _get_resident_id(base_url, resident_token)

    # Create an address as the resident first
    with httpx.Client(
        base_url=base_url,
        timeout=30.0,
        headers={"Authorization": f"Bearer {resident_token}"},
    ) as c:
        create_resp = c.post(
            "/residents/me/addresses",
            json={
                "address_type": "shipping",
                "line1": "100 Old Street",
                "city": "Oldtown",
                "state": "NY",
                "zip_code": "10001",
            },
        )
        create_resp.raise_for_status()
        address_id = create_resp.json()["id"]

    # Update with admin token
    with httpx.Client(
        base_url=base_url,
        timeout=30.0,
        headers={"Authorization": f"Bearer {auth_token}"},
    ) as c:
        # GET the address to obtain the current version for If-Match
        addr_list_resp = c.get(f"/residents/{resident_id}/addresses")
        addr_list_resp.raise_for_status()
        address_version = next(
            a["version"] for a in addr_list_resp.json() if a["id"] == address_id
        )

        resp = c.put(
            f"/residents/{resident_id}/addresses/{address_id}",
            json={
                "line1": "200 New Avenue",
                "city": "Newtown",
            },
            headers={"If-Match": str(address_version)},
        )
        print(f"[PUT /residents/{{id}}/addresses/{{id}} admin] status={resp.status_code}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["line1"] == "200 New Avenue"
        assert data["city"] == "Newtown"
        print(f"  -> updated address id={data['id']}")


def test_admin_deletes_address_returns_204(base_url: str, auth_token: str):
    """DELETE /residents/{resident_id}/addresses/{id} with admin token -> 204."""
    resident_token = _login_as_resident(base_url)
    resident_id = _get_resident_id(base_url, resident_token)

    # Create an address to delete
    with httpx.Client(
        base_url=base_url,
        timeout=30.0,
        headers={"Authorization": f"Bearer {resident_token}"},
    ) as c:
        create_resp = c.post(
            "/residents/me/addresses",
            json={
                "address_type": "mailing",
                "line1": "999 Disposable Rd",
                "city": "Deleteville",
                "state": "FL",
                "zip_code": "33101",
            },
        )
        create_resp.raise_for_status()
        address_id = create_resp.json()["id"]

    # Delete with admin token
    with httpx.Client(
        base_url=base_url,
        timeout=30.0,
        headers={"Authorization": f"Bearer {auth_token}"},
    ) as c:
        resp = c.delete(f"/residents/{resident_id}/addresses/{address_id}")
        print(f"[DELETE /residents/{{id}}/addresses/{{id}} admin] status={resp.status_code}")
        assert resp.status_code == 204


def test_create_address_with_invalid_type_returns_400(base_url: str):
    """POST with invalid address_type returns 422 or 400."""
    token = _login_as_resident(base_url)
    with httpx.Client(
        base_url=base_url,
        timeout=30.0,
        headers={"Authorization": f"Bearer {token}"},
    ) as c:
        resp = c.post(
            "/residents/me/addresses",
            json={
                "address_type": "invalid_type",
                "line1": "123 Bad Type St",
                "city": "Errorville",
                "state": "CA",
                "zip_code": "90000",
            },
        )
        print(f"[POST /residents/me/addresses invalid type] status={resp.status_code}")
        assert resp.status_code in (400, 422)
        print(f"  -> correctly rejected invalid address_type")
