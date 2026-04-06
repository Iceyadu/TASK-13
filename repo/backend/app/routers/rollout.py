from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_roles
from app.models.user import User
from app.schemas.rollout import CanaryUserListResponse, CanaryUserResponse, CanaryBatchUpdate

router = APIRouter(prefix="/rollout", tags=["rollout"])


@router.get("/canary-users", response_model=CanaryUserListResponse)
async def list_canary_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_roles("admin")),
):
    offset = (page - 1) * page_size

    total_result = await db.execute(
        select(func.count()).select_from(User).where(
            User.role.in_(["admin", "property_manager", "accounting_clerk", "maintenance_dispatcher"])
        )
    )
    total = total_result.scalar() or 0

    result = await db.execute(
        select(User)
        .where(User.role.in_(["admin", "property_manager", "accounting_clerk", "maintenance_dispatcher"]))
        .order_by(User.username)
        .offset(offset)
        .limit(page_size)
    )
    users = result.scalars().all()

    items = [
        CanaryUserResponse(
            id=u.id,
            username=u.username,
            role=u.role,
            canary_enabled=u.canary_enabled,
        )
        for u in users
    ]
    return CanaryUserListResponse(items=items, total=total, page=page, page_size=page_size)


@router.put("/canary-users", status_code=status.HTTP_200_OK)
async def batch_update_canary(
    body: CanaryBatchUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_roles("admin")),
):
    updated = []
    errors = []

    for entry in body.updates:
        result = await db.execute(select(User).where(User.id == entry.user_id))
        user = result.scalars().first()
        if not user:
            errors.append({"user_id": str(entry.user_id), "error": "Not found"})
            continue

        user.canary_enabled = entry.canary_enabled
        user.updated_at = datetime.now(timezone.utc)
        updated.append(str(entry.user_id))

    await db.commit()
    return {"updated": updated, "errors": errors}


@router.get("/stats")
async def get_rollout_stats(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_roles("admin")),
):
    """Return canary rollout statistics across all staff users."""
    staff_roles = ["admin", "property_manager", "accounting_clerk", "maintenance_dispatcher"]

    total_result = await db.execute(
        select(func.count()).select_from(User).where(
            User.role.in_(staff_roles),
            User.is_active == True,
        )
    )
    t = total_result.scalar() or 0

    canary_result = await db.execute(
        select(func.count()).select_from(User).where(
            User.canary_enabled == True,
            User.role.in_(staff_roles),
            User.is_active == True,
        )
    )
    c = canary_result.scalar() or 0

    return {
        "total_staff": t,
        "canary_count": c,
        "canary_percentage": round(c / t * 100, 1) if t > 0 else 0,
    }
