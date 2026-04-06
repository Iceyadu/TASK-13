from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import ORDER_TRANSITIONS, Order, OrderMilestone


def validate_transition(current_status: str, to_status: str) -> bool:
    """Return ``True`` if *to_status* is a valid next state for *current_status*.

    The set of allowed transitions is defined in
    ``app.models.order.ORDER_TRANSITIONS``.
    """
    allowed = ORDER_TRANSITIONS.get(current_status, set())
    return to_status in allowed


async def transition_order(
    db: AsyncSession,
    order: Order,
    to_status: str,
    user_id: UUID,
    notes: Optional[str] = None,
) -> Order:
    """Move *order* to *to_status*, recording a milestone.

    Parameters
    ----------
    db:
        Active async session (caller is responsible for commit).
    order:
        The ``Order`` instance to update.
    to_status:
        The desired new status string.
    user_id:
        UUID of the user performing the transition.
    notes:
        Optional free-text note attached to the milestone.

    Returns
    -------
    Order
        The updated order instance.

    Raises
    ------
    ValueError
        If the transition is not permitted by the state machine.
    """
    current_status: str = order.status

    if not validate_transition(current_status, to_status):
        raise ValueError(
            f"Cannot transition order from '{current_status}' to '{to_status}'"
        )

    # Record the milestone
    milestone = OrderMilestone(
        order_id=order.id,
        from_status=current_status,
        to_status=to_status,
        changed_by=user_id,
        notes=notes,
    )
    db.add(milestone)

    # Update the order itself
    order.status = to_status
    order.version = (order.version or 0) + 1
    order.updated_at = datetime.now(timezone.utc)

    await db.flush()
    return order
