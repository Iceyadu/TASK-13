from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.utils.conflict import detect_changed_fields
from app.utils.ownership import require_financial_access
from app.utils.pagination import paginate_params, paginated_response


def test_detect_changed_fields_returns_sorted_union_of_diffs():
    your_data = {"title": "A", "priority": "normal", "assigned_to": "u1"}
    server_data = {"title": "A", "priority": "high", "status": "created"}

    changed = detect_changed_fields(your_data, server_data)

    assert changed == ["assigned_to", "priority", "status"]


@pytest.mark.parametrize(
    ("page", "page_size", "expected"),
    [
        (0, 0, (0, 1)),        # clamps both values to minimums
        (2, 500, (100, 100)),  # clamps page_size to max=100
        (3, 25, (50, 25)),
    ],
)
def test_paginate_params_clamps_and_calculates_offset(page: int, page_size: int, expected: tuple[int, int]):
    assert paginate_params(page=page, page_size=page_size) == expected


def test_paginated_response_includes_page_count():
    data = paginated_response(items=[{"id": 1}], total=41, page=2, page_size=20)

    assert data["items"] == [{"id": 1}]
    assert data["total"] == 41
    assert data["page"] == 2
    assert data["page_size"] == 20
    assert data["pages"] == 3


def test_require_financial_access_allows_resident_and_denies_unknown_role():
    require_financial_access(SimpleNamespace(role="resident"))

    with pytest.raises(HTTPException) as exc:
        require_financial_access(SimpleNamespace(role="maintenance_dispatcher"))

    assert exc.value.status_code == 403
