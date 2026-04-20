"""Unit tests for order_service.transition_order behavior."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services.order_service import transition_order


@pytest.fixture
def anyio_backend() -> str:
    """Run anyio tests on asyncio only (local trio versions may be incompatible)."""
    return "asyncio"


class _FakeAsyncSession:
    def __init__(self) -> None:
        self.added = []
        self.flush_called = 0

    def add(self, obj) -> None:  # noqa: ANN001
        self.added.append(obj)

    async def flush(self) -> None:
        self.flush_called += 1


@pytest.mark.anyio
async def test_transition_order_updates_status_version_and_adds_milestone():
    db = _FakeAsyncSession()
    order = SimpleNamespace(id=uuid4(), status="created", version=2, updated_at=None)

    updated = await transition_order(
        db=db,
        order=order,
        to_status="payment_recorded",
        user_id=uuid4(),
        notes="Paid online",
    )

    assert updated is order
    assert order.status == "payment_recorded"
    assert order.version == 3
    assert order.updated_at is not None
    assert db.flush_called == 1
    assert len(db.added) == 1
    milestone = db.added[0]
    assert milestone.from_status == "created"
    assert milestone.to_status == "payment_recorded"
    assert milestone.notes == "Paid online"


@pytest.mark.anyio
async def test_transition_order_rejects_invalid_transition_without_flushing():
    db = _FakeAsyncSession()
    order = SimpleNamespace(id=uuid4(), status="created", version=1, updated_at=None)

    with pytest.raises(ValueError):
        await transition_order(
            db=db,
            order=order,
            to_status="completed",
            user_id=uuid4(),
        )

    assert db.flush_called == 0
    assert db.added == []
    assert order.status == "created"
    assert order.version == 1
