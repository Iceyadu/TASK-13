from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Header, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_roles
from app.utils.conflict import raise_conflict, detect_changed_fields
from app.models.user import User
from app.schemas.user import (
    UserCreate,
    UserResponse,
    UserListResponse,
    UserUpdate,
    ResetPasswordRequest,
)
from app.services.auth_service import hash_password
from app.services.audit_service import log_audit

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/", response_model=UserListResponse)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_roles("admin")),
):
    offset = (page - 1) * page_size

    total_result = await db.execute(
        select(func.count()).select_from(User).where(User.is_active == True)
    )
    total = total_result.scalar() or 0

    result = await db.execute(
        select(User)
        .where(User.is_active == True)
        .order_by(User.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    users = result.scalars().all()

    return UserListResponse(
        items=[UserResponse.model_validate(u) for u in users],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    existing = await db.execute(select(User).where(User.username == body.username))
    if existing.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Username already exists"
        )

    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        role=body.role,
        is_active=body.is_active,
        canary_enabled=body.canary_enabled,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        version=1,
    )
    db.add(user)
    await db.flush()
    await log_audit(db, user_id=current_user.id, action="CREATE", resource_type="user", resource_id=user.id, new_value={"username": user.username, "role": user.role})
    await db.commit()
    await db.refresh(user)
    return UserResponse.model_validate(user)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_roles("admin")),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserResponse.model_validate(user)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    body: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
    if_match: str | None = Header(None, alias="If-Match"),
):
    if if_match is None:
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail="If-Match header is required for updates",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    update_data = body.model_dump(exclude_unset=True)

    if str(user.version) != if_match:
        client_version = int(if_match)
        server_data_dict = {field: getattr(user, field) for field in update_data.keys()}
        for k, v in server_data_dict.items():
            if hasattr(v, 'isoformat'):
                server_data_dict[k] = v.isoformat()
            elif hasattr(v, 'hex'):
                server_data_dict[k] = str(v)
        changed = detect_changed_fields(update_data, server_data_dict)
        raise_conflict(
            your_version=client_version,
            server_version=user.version,
            your_data=update_data,
            server_data=server_data_dict,
            changed_fields=changed,
        )

    old_values = {field: getattr(user, field) for field in update_data.keys()}
    for field, value in update_data.items():
        setattr(user, field, value)

    user.version += 1
    user.updated_at = datetime.now(timezone.utc)
    await log_audit(db, user_id=current_user.id, action="UPDATE", resource_type="user", resource_id=user.id, old_value={k: str(v) for k, v in old_values.items()}, new_value={k: str(v) for k, v in update_data.items()})
    await db.commit()
    await db.refresh(user)
    return UserResponse.model_validate(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.is_active = False
    user.updated_at = datetime.now(timezone.utc)
    await log_audit(db, user_id=current_user.id, action="DELETE", resource_type="user", resource_id=user.id, old_value={"username": user.username, "is_active": True})
    await db.commit()
    return None


@router.put("/{user_id}/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(
    user_id: UUID,
    body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.password_hash = hash_password(body.new_password)
    user.updated_at = datetime.now(timezone.utc)
    await log_audit(db, user_id=current_user.id, action="RESET_PASSWORD", resource_type="user", resource_id=user.id)
    await db.commit()
    return {"detail": "Password reset successfully"}
