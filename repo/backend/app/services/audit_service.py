from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog


async def log_audit(
    db: AsyncSession,
    user_id: UUID,
    action: str,
    resource_type: str,
    resource_id: UUID,
    old_value: Optional[dict[str, Any]] = None,
    new_value: Optional[dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    idempotency_key: Optional[str] = None,
) -> AuditLog:
    """Persist an audit-log entry and return the created record.

    Parameters
    ----------
    db:
        An active SQLAlchemy ``AsyncSession``.
    user_id:
        The UUID of the user who performed the action.
    action:
        A short verb describing the action (e.g. ``"create"``, ``"update"``).
    resource_type:
        The type of resource affected (e.g. ``"order"``, ``"bill"``).
    resource_id:
        Primary key of the affected resource.
    old_value / new_value:
        Optional JSON-serialisable dicts capturing state before/after.
    ip_address:
        Optional client IP address.
    idempotency_key:
        Optional key to prevent duplicate audit entries for retried requests.
    """
    entry = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        old_value=old_value,
        new_value=new_value,
        ip_address=ip_address,
        idempotency_key=idempotency_key,
    )
    db.add(entry)
    await db.flush()
    return entry
