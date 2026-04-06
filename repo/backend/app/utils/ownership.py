"""Ownership/object-level authorization helpers."""
from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.resident import Resident
from app.models.user import User


async def get_resident_id_for_user(db: AsyncSession, user: User) -> UUID | None:
    """Return the resident_id for a user, or None if not a resident."""
    if user.role != "resident":
        return None
    result = await db.execute(select(Resident).where(Resident.user_id == user.id))
    res = result.scalars().first()
    return res.id if res else None


def is_staff(user: User) -> bool:
    return user.role in ("admin", "property_manager", "accounting_clerk")


def require_financial_access(user: User) -> None:
    """Raise 403 if user has no financial data access."""
    if user.role not in ("admin", "property_manager", "accounting_clerk", "resident"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions for financial data",
        )


async def enforce_bill_access(db: AsyncSession, user: User, bill_resident_id: UUID) -> None:
    """Raise 403 if user is a resident and doesn't own this bill."""
    if is_staff(user):
        return
    resident_id = await get_resident_id_for_user(db, user)
    if resident_id != bill_resident_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")


async def enforce_payment_access(db: AsyncSession, user: User, payment_resident_id: UUID) -> None:
    if is_staff(user):
        return
    resident_id = await get_resident_id_for_user(db, user)
    if resident_id != payment_resident_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")


async def enforce_credit_access(db: AsyncSession, user: User, credit_resident_id: UUID) -> None:
    if is_staff(user):
        return
    resident_id = await get_resident_id_for_user(db, user)
    if resident_id != credit_resident_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")


async def enforce_order_access(db: AsyncSession, user: User, order_resident_id: UUID) -> None:
    if is_staff(user):
        return
    resident_id = await get_resident_id_for_user(db, user)
    if resident_id != order_resident_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
