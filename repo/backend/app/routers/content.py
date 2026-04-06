from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Header, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_roles
from app.utils.conflict import raise_conflict, detect_changed_fields
from app.models.content import ContentConfig, ContentSection
from app.models.user import User
from app.schemas.content import (
    ContentConfigCreate,
    ContentConfigListResponse,
    ContentConfigResponse,
    ContentConfigStatusUpdate,
    ContentConfigUpdate,
    ContentSectionCreate,
    ContentSectionResponse,
    ContentSectionUpdate,
)

router = APIRouter(prefix="/content", tags=["content"])


# -- Content Configs -----------------------------------------------------------

@router.get("/configs", response_model=ContentConfigListResponse)
async def list_configs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _staff: User = Depends(require_roles("admin", "property_manager")),
):
    offset = (page - 1) * page_size

    total_result = await db.execute(
        select(func.count()).select_from(ContentConfig)
    )
    total = total_result.scalar() or 0

    result = await db.execute(
        select(ContentConfig)
        .order_by(ContentConfig.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    configs = result.scalars().all()

    return ContentConfigListResponse(
        items=[ContentConfigResponse.model_validate(c) for c in configs],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/configs",
    response_model=ContentConfigResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_config(
    body: ContentConfigCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    config = ContentConfig(
        **body.model_dump(),
        status="draft",
        created_by=current_user.id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        version=1,
    )
    db.add(config)
    await db.commit()
    await db.refresh(config)
    return ContentConfigResponse.model_validate(config)


@router.get("/configs/active", response_model=ContentConfigResponse)
async def get_active_config(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the active content config. If the user has canary enabled, return
    the canary config (status='canary'); otherwise return the published config."""
    is_canary = current_user.canary_enabled

    if is_canary:
        result = await db.execute(
            select(ContentConfig).where(ContentConfig.status == "canary").limit(1)
        )
        config = result.scalars().first()
        if config:
            return ContentConfigResponse.model_validate(config)

    # Fall back to the published config.
    result = await db.execute(
        select(ContentConfig).where(ContentConfig.status == "published").limit(1)
    )
    config = result.scalars().first()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active content config found",
        )
    return ContentConfigResponse.model_validate(config)


@router.get("/configs/{config_id}", response_model=ContentConfigResponse)
async def get_config(
    config_id: UUID,
    db: AsyncSession = Depends(get_db),
    _staff: User = Depends(require_roles("admin", "property_manager")),
):
    result = await db.execute(
        select(ContentConfig).where(ContentConfig.id == config_id)
    )
    config = result.scalars().first()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content config not found",
        )
    return ContentConfigResponse.model_validate(config)


@router.put("/configs/{config_id}", response_model=ContentConfigResponse)
async def update_config(
    config_id: UUID,
    body: ContentConfigUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_roles("admin")),
    if_match: str | None = Header(None, alias="If-Match"),
):
    if if_match is None:
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail="If-Match header is required for updates",
        )

    result = await db.execute(
        select(ContentConfig).where(ContentConfig.id == config_id)
    )
    config = result.scalars().first()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content config not found",
        )

    update_data = body.model_dump(exclude_unset=True)

    if str(config.version) != if_match:
        client_version = int(if_match)
        server_data_dict = {field: getattr(config, field) for field in update_data.keys()}
        for k, v in server_data_dict.items():
            if hasattr(v, 'isoformat'):
                server_data_dict[k] = v.isoformat()
            elif hasattr(v, 'hex'):
                server_data_dict[k] = str(v)
        changed = detect_changed_fields(update_data, server_data_dict)
        raise_conflict(
            your_version=client_version,
            server_version=config.version,
            your_data=update_data,
            server_data=server_data_dict,
            changed_fields=changed,
        )

    for field, value in update_data.items():
        setattr(config, field, value)

    config.version += 1
    config.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(config)
    return ContentConfigResponse.model_validate(config)


@router.put("/configs/{config_id}/status", response_model=ContentConfigResponse)
async def update_config_status(
    config_id: UUID,
    body: ContentConfigStatusUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_roles("admin")),
    if_match: str | None = Header(None, alias="If-Match"),
):
    if if_match is None:
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail="If-Match header is required for updates",
        )

    result = await db.execute(
        select(ContentConfig).where(ContentConfig.id == config_id)
    )
    config = result.scalars().first()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content config not found",
        )

    if str(config.version) != if_match:
        client_version = int(if_match)
        update_data = body.model_dump(exclude_unset=True)
        server_data_dict = {field: getattr(config, field) for field in update_data.keys()}
        for k, v in server_data_dict.items():
            if hasattr(v, 'isoformat'):
                server_data_dict[k] = v.isoformat()
            elif hasattr(v, 'hex'):
                server_data_dict[k] = str(v)
        changed = detect_changed_fields(update_data, server_data_dict)
        raise_conflict(
            your_version=client_version,
            server_version=config.version,
            your_data=update_data,
            server_data=server_data_dict,
            changed_fields=changed,
        )

    now = datetime.now(timezone.utc)
    new_status = body.status

    # -- Business rules for status transitions ---------------------------------

    if new_status == "published":
        # Archive any existing published config so only one is published at a time.
        await db.execute(
            update(ContentConfig)
            .where(
                ContentConfig.status == "published",
                ContentConfig.id != config_id,
            )
            .values(status="archived", published_at=None, updated_at=now)
        )
        config.published_at = now

    elif new_status == "canary":
        # Archive any existing canary config so only one is canary at a time.
        await db.execute(
            update(ContentConfig)
            .where(
                ContentConfig.status == "canary",
                ContentConfig.id != config_id,
            )
            .values(status="archived", updated_at=now)
        )

    elif new_status == "archived":
        # Clear published_at when archiving.
        config.published_at = None

    # --------------------------------------------------------------------------

    config.status = new_status
    config.version += 1
    config.updated_at = now
    await db.commit()
    await db.refresh(config)
    return ContentConfigResponse.model_validate(config)


@router.get("/configs/{config_id}/preview", response_model=ContentConfigResponse)
async def preview_config(
    config_id: UUID,
    db: AsyncSession = Depends(get_db),
    _staff: User = Depends(require_roles("admin", "property_manager")),
):
    result = await db.execute(
        select(ContentConfig).where(ContentConfig.id == config_id)
    )
    config = result.scalars().first()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content config not found",
        )
    return ContentConfigResponse.model_validate(config)


# -- Content Sections ----------------------------------------------------------

@router.post(
    "/configs/{config_id}/sections",
    response_model=ContentSectionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_section(
    config_id: UUID,
    body: ContentSectionCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_roles("admin")),
):
    config_result = await db.execute(
        select(ContentConfig).where(ContentConfig.id == config_id)
    )
    if not config_result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content config not found",
        )

    section = ContentSection(
        **body.model_dump(),
        config_id=config_id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        version=1,
    )
    db.add(section)
    await db.commit()
    await db.refresh(section)
    return ContentSectionResponse.model_validate(section)


@router.put(
    "/configs/{config_id}/sections/{section_id}",
    response_model=ContentSectionResponse,
)
async def update_section(
    config_id: UUID,
    section_id: UUID,
    body: ContentSectionUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_roles("admin")),
    if_match: str | None = Header(None, alias="If-Match"),
):
    if if_match is None:
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail="If-Match header is required for updates",
        )

    result = await db.execute(
        select(ContentSection).where(
            ContentSection.id == section_id,
            ContentSection.config_id == config_id,
        )
    )
    section = result.scalars().first()
    if not section:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content section not found",
        )

    update_data = body.model_dump(exclude_unset=True)

    if str(section.version) != if_match:
        client_version = int(if_match)
        server_data_dict = {field: getattr(section, field) for field in update_data.keys()}
        for k, v in server_data_dict.items():
            if hasattr(v, 'isoformat'):
                server_data_dict[k] = v.isoformat()
            elif hasattr(v, 'hex'):
                server_data_dict[k] = str(v)
        changed = detect_changed_fields(update_data, server_data_dict)
        raise_conflict(
            your_version=client_version,
            server_version=section.version,
            your_data=update_data,
            server_data=server_data_dict,
            changed_fields=changed,
        )

    for field, value in update_data.items():
        setattr(section, field, value)

    section.version += 1
    section.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(section)
    return ContentSectionResponse.model_validate(section)


@router.delete(
    "/configs/{config_id}/sections/{section_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_section(
    config_id: UUID,
    section_id: UUID,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_roles("admin")),
):
    result = await db.execute(
        select(ContentSection).where(
            ContentSection.id == section_id,
            ContentSection.config_id == config_id,
        )
    )
    section = result.scalars().first()
    if not section:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content section not found",
        )

    await db.delete(section)
    await db.commit()
    return None
