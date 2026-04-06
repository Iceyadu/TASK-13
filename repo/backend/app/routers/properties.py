from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Header, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_roles
from app.utils.conflict import raise_conflict, detect_changed_fields
from app.models.property import Property, Unit
from app.models.user import User
from app.schemas.property import (
    PropertyCreate,
    PropertyListResponse,
    PropertyResponse,
    PropertyUpdate,
    UnitCreate,
    UnitResponse,
)

router = APIRouter(prefix="/properties", tags=["properties"])


@router.get("/", response_model=PropertyListResponse)
async def list_properties(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    offset = (page - 1) * page_size

    total_result = await db.execute(select(func.count()).select_from(Property))
    total = total_result.scalar() or 0

    result = await db.execute(
        select(Property)
        .order_by(Property.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    properties = result.scalars().all()

    return PropertyListResponse(
        items=[PropertyResponse.model_validate(p) for p in properties],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/", response_model=PropertyResponse, status_code=status.HTTP_201_CREATED)
async def create_property(
    body: PropertyCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_roles("admin")),
):
    prop = Property(
        **body.model_dump(),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        version=1,
    )
    db.add(prop)
    await db.commit()
    await db.refresh(prop)
    return PropertyResponse.model_validate(prop)


@router.get("/{property_id}", response_model=PropertyResponse)
async def get_property(
    property_id: UUID,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Property).where(Property.id == property_id))
    prop = result.scalars().first()
    if not prop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Property not found"
        )
    return PropertyResponse.model_validate(prop)


@router.put("/{property_id}", response_model=PropertyResponse)
async def update_property(
    property_id: UUID,
    body: PropertyUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_roles("admin")),
    if_match: str | None = Header(None, alias="If-Match"),
):
    if if_match is None:
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail="If-Match header is required for updates",
        )

    result = await db.execute(select(Property).where(Property.id == property_id))
    prop = result.scalars().first()
    if not prop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Property not found"
        )

    update_data = body.model_dump(exclude_unset=True)

    if str(prop.version) != if_match:
        client_version = int(if_match)
        server_data_dict = {field: getattr(prop, field) for field in update_data.keys()}
        for k, v in server_data_dict.items():
            if hasattr(v, 'isoformat'):
                server_data_dict[k] = v.isoformat()
            elif hasattr(v, 'hex'):
                server_data_dict[k] = str(v)
        changed = detect_changed_fields(update_data, server_data_dict)
        raise_conflict(
            your_version=client_version,
            server_version=prop.version,
            your_data=update_data,
            server_data=server_data_dict,
            changed_fields=changed,
        )
    for field, value in update_data.items():
        setattr(prop, field, value)

    prop.version += 1
    prop.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(prop)
    return PropertyResponse.model_validate(prop)


@router.get("/{property_id}/units")
async def list_property_units(
    property_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    prop_result = await db.execute(select(Property).where(Property.id == property_id))
    if not prop_result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Property not found"
        )

    offset = (page - 1) * page_size

    total_result = await db.execute(
        select(func.count())
        .select_from(Unit)
        .where(Unit.property_id == property_id)
    )
    total = total_result.scalar() or 0

    result = await db.execute(
        select(Unit)
        .where(Unit.property_id == property_id)
        .order_by(Unit.unit_number)
        .offset(offset)
        .limit(page_size)
    )
    units = result.scalars().all()

    return {
        "items": [UnitResponse.model_validate(u) for u in units],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post(
    "/{property_id}/units",
    response_model=UnitResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_unit(
    property_id: UUID,
    body: UnitCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_roles("admin")),
):
    prop_result = await db.execute(select(Property).where(Property.id == property_id))
    if not prop_result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Property not found"
        )

    unit = Unit(
        **body.model_dump(),
        property_id=property_id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        version=1,
    )
    db.add(unit)
    await db.commit()
    await db.refresh(unit)
    return UnitResponse.model_validate(unit)
