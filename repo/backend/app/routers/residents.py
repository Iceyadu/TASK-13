from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Header, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_roles
from app.utils.conflict import raise_conflict, detect_changed_fields
from app.models.resident import Address, Resident
from app.models.user import User
from app.schemas.resident import (
    AddressCreate,
    AddressResponse,
    AddressUpdate,
    ResidentCreate,
    ResidentListResponse,
    ResidentResponse,
    ResidentUpdate,
)
from app.services.encryption_service import encrypt_field, decrypt_field, mask_email, mask_phone
from app.utils.ownership import is_staff

router = APIRouter(prefix="/residents", tags=["residents"])

VALID_ADDRESS_TYPES = {"shipping", "mailing"}


def _resident_response(resident: Resident, caller: User) -> dict:
    """Build a ResidentResponse dict with decryption and role-based masking."""
    data = {
        "id": resident.id,
        "user_id": resident.user_id,
        "unit_id": resident.unit_id,
        "first_name": resident.first_name,
        "last_name": resident.last_name,
        "created_at": resident.created_at,
        "updated_at": resident.updated_at,
        "version": resident.version,
    }
    # Decrypt contact fields
    raw_email = decrypt_field(resident.email_encrypted) if resident.email_encrypted else None
    raw_phone = decrypt_field(resident.phone_encrypted) if resident.phone_encrypted else None

    # Mask based on role
    if caller.role == "admin":
        data["email"] = raw_email
        data["phone"] = raw_phone
    elif caller.role == "resident" and resident.user_id == caller.id:
        # Resident sees their own data unmasked
        data["email"] = raw_email
        data["phone"] = raw_phone
    elif caller.role in ("property_manager", "accounting_clerk"):
        data["email"] = mask_email(raw_email) if raw_email else None
        data["phone"] = mask_phone(raw_phone) if raw_phone else None
    else:
        data["email"] = "****" if raw_email else None
        data["phone"] = "****" if raw_phone else None

    return data


# -- Helper to get resident by user_id ----------------------------------------

async def _get_resident_for_user(db: AsyncSession, user_id: UUID) -> Resident:
    result = await db.execute(
        select(Resident).where(Resident.user_id == user_id)
    )
    resident = result.scalars().first()
    if not resident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resident profile not found"
        )
    return resident


def _encrypt_contact_fields(data: dict, body) -> dict:
    """Remove plain email/phone from data and add encrypted versions."""
    filtered = {k: v for k, v in data.items() if k not in ("email", "phone")}
    if getattr(body, "email", None):
        filtered["email_encrypted"] = encrypt_field(body.email)
    if getattr(body, "phone", None):
        filtered["phone_encrypted"] = encrypt_field(body.phone)
    return filtered


# -- Self-service profile endpoints -------------------------------------------

@router.get("/me", response_model=None)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    resident = await _get_resident_for_user(db, current_user.id)
    return _resident_response(resident, current_user)


@router.put("/me", response_model=None)
async def update_my_profile(
    body: ResidentUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    if_match: str | None = Header(None, alias="If-Match"),
):
    if if_match is None:
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail="If-Match header is required for updates",
        )

    resident = await _get_resident_for_user(db, current_user.id)

    update_data = body.model_dump(exclude_unset=True)

    if str(resident.version) != if_match:
        client_version = int(if_match)
        server_data_dict = {field: getattr(resident, field) for field in update_data.keys() if hasattr(resident, field)}
        for k, v in server_data_dict.items():
            if hasattr(v, 'isoformat'):
                server_data_dict[k] = v.isoformat()
            elif hasattr(v, 'hex'):
                server_data_dict[k] = str(v)
        changed = detect_changed_fields(update_data, server_data_dict)
        raise_conflict(
            your_version=client_version,
            server_version=resident.version,
            your_data=update_data,
            server_data=server_data_dict,
            changed_fields=changed,
        )

    # Handle encryption of contact fields
    if "email" in update_data:
        email_val = update_data.pop("email")
        if email_val:
            resident.email_encrypted = encrypt_field(email_val)
        else:
            resident.email_encrypted = None
    if "phone" in update_data:
        phone_val = update_data.pop("phone")
        if phone_val:
            resident.phone_encrypted = encrypt_field(phone_val)
        else:
            resident.phone_encrypted = None

    for field, value in update_data.items():
        setattr(resident, field, value)

    resident.version += 1
    resident.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(resident)
    return _resident_response(resident, current_user)


# -- Self-service address endpoints (must come before /{resident_id} routes) ---

@router.get("/me/addresses", response_model=list[AddressResponse])
async def list_my_addresses(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    resident = await _get_resident_for_user(db, current_user.id)
    result = await db.execute(
        select(Address).where(Address.resident_id == resident.id)
    )
    addresses = result.scalars().all()
    return [AddressResponse.model_validate(a) for a in addresses]


@router.post("/me/addresses", response_model=AddressResponse, status_code=status.HTTP_201_CREATED)
async def create_my_address(
    body: AddressCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.address_type not in VALID_ADDRESS_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="address_type must be 'shipping' or 'mailing'",
        )

    resident = await _get_resident_for_user(db, current_user.id)
    address = Address(
        resident_id=resident.id,
        **body.model_dump(),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        version=1,
    )
    db.add(address)
    await db.commit()
    await db.refresh(address)
    return AddressResponse.model_validate(address)


@router.put("/me/addresses/{address_id}", response_model=AddressResponse)
async def update_my_address(
    address_id: UUID,
    body: AddressUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    if_match: str | None = Header(None, alias="If-Match"),
):
    if if_match is None:
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail="If-Match header is required for updates",
        )

    resident = await _get_resident_for_user(db, current_user.id)
    result = await db.execute(
        select(Address).where(Address.id == address_id, Address.resident_id == resident.id)
    )
    address = result.scalars().first()
    if not address:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Address not found")

    if str(address.version) != if_match:
        raise HTTPException(status_code=status.HTTP_428_PRECONDITION_REQUIRED, detail="Version mismatch")

    update_data = body.model_dump(exclude_unset=True)
    if "address_type" in update_data and update_data["address_type"] not in VALID_ADDRESS_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="address_type must be 'shipping' or 'mailing'")

    for field, value in update_data.items():
        setattr(address, field, value)
    address.version += 1
    address.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(address)
    return AddressResponse.model_validate(address)


@router.delete("/me/addresses/{address_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_address(
    address_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    resident = await _get_resident_for_user(db, current_user.id)
    result = await db.execute(
        select(Address).where(Address.id == address_id, Address.resident_id == resident.id)
    )
    address = result.scalars().first()
    if not address:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Address not found")
    await db.delete(address)
    await db.commit()
    return None


# -- Staff list / CRUD for residents ------------------------------------------

@router.get("/", response_model=None)
async def list_residents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "property_manager", "accounting_clerk", "maintenance_dispatcher")),
):
    offset = (page - 1) * page_size

    total_result = await db.execute(select(func.count()).select_from(Resident))
    total = total_result.scalar() or 0

    result = await db.execute(
        select(Resident)
        .order_by(Resident.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    residents = result.scalars().all()

    return {
        "items": [_resident_response(r, current_user) for r in residents],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{resident_id}", response_model=None)
async def get_resident(
    resident_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "property_manager", "accounting_clerk", "maintenance_dispatcher")),
):
    result = await db.execute(select(Resident).where(Resident.id == resident_id))
    resident = result.scalars().first()
    if not resident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resident not found"
        )
    return _resident_response(resident, current_user)


@router.post("/", response_model=None, status_code=status.HTTP_201_CREATED)
async def create_resident(
    body: ResidentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "property_manager")),
):
    create_data = body.model_dump(exclude={"email", "phone"})
    if body.email:
        create_data["email_encrypted"] = encrypt_field(body.email)
    if body.phone:
        create_data["phone_encrypted"] = encrypt_field(body.phone)

    resident = Resident(
        **create_data,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        version=1,
    )
    db.add(resident)
    await db.commit()
    await db.refresh(resident)
    return _resident_response(resident, current_user)


@router.put("/{resident_id}", response_model=None)
async def update_resident(
    resident_id: UUID,
    body: ResidentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "property_manager")),
    if_match: str | None = Header(None, alias="If-Match"),
):
    if if_match is None:
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail="If-Match header is required for updates",
        )

    result = await db.execute(select(Resident).where(Resident.id == resident_id))
    resident = result.scalars().first()
    if not resident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resident not found"
        )

    update_data = body.model_dump(exclude_unset=True)

    if str(resident.version) != if_match:
        client_version = int(if_match)
        server_data_dict = {field: getattr(resident, field) for field in update_data.keys() if hasattr(resident, field)}
        for k, v in server_data_dict.items():
            if hasattr(v, 'isoformat'):
                server_data_dict[k] = v.isoformat()
            elif hasattr(v, 'hex'):
                server_data_dict[k] = str(v)
        changed = detect_changed_fields(update_data, server_data_dict)
        raise_conflict(
            your_version=client_version,
            server_version=resident.version,
            your_data=update_data,
            server_data=server_data_dict,
            changed_fields=changed,
        )

    # Handle encryption of contact fields
    if "email" in update_data:
        email_val = update_data.pop("email")
        if email_val:
            resident.email_encrypted = encrypt_field(email_val)
        else:
            resident.email_encrypted = None
    if "phone" in update_data:
        phone_val = update_data.pop("phone")
        if phone_val:
            resident.phone_encrypted = encrypt_field(phone_val)
        else:
            resident.phone_encrypted = None

    for field, value in update_data.items():
        setattr(resident, field, value)

    resident.version += 1
    resident.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(resident)
    return _resident_response(resident, current_user)


# -- Address CRUD for a specific resident (staff or own) ----------------------

async def _authorize_address_access(
    resident_id: UUID, current_user: User, db: AsyncSession
) -> Resident:
    """Staff can access any resident's addresses; residents can only access their own."""
    if current_user.role in ("admin", "property_manager", "accounting_clerk", "maintenance_dispatcher"):
        result = await db.execute(select(Resident).where(Resident.id == resident_id))
        resident = result.scalars().first()
        if not resident:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Resident not found"
            )
        return resident

    # Resident accessing own addresses
    resident = await _get_resident_for_user(db, current_user.id)
    if resident.id != resident_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    return resident


@router.get("/{resident_id}/addresses", response_model=list[AddressResponse])
async def list_addresses(
    resident_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _authorize_address_access(resident_id, current_user, db)
    result = await db.execute(
        select(Address).where(Address.resident_id == resident_id)
    )
    addresses = result.scalars().all()
    return [AddressResponse.model_validate(a) for a in addresses]


@router.post(
    "/{resident_id}/addresses",
    response_model=AddressResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_address(
    resident_id: UUID,
    body: AddressCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.address_type not in VALID_ADDRESS_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="address_type must be 'shipping' or 'mailing'",
        )

    await _authorize_address_access(resident_id, current_user, db)
    address = Address(
        resident_id=resident_id,
        **body.model_dump(),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        version=1,
    )
    db.add(address)
    await db.commit()
    await db.refresh(address)
    return AddressResponse.model_validate(address)


@router.put("/{resident_id}/addresses/{address_id}", response_model=AddressResponse)
async def update_address(
    resident_id: UUID,
    address_id: UUID,
    body: AddressUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    if_match: str | None = Header(None, alias="If-Match"),
):
    if if_match is None:
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail="If-Match header is required for updates",
        )

    await _authorize_address_access(resident_id, current_user, db)

    result = await db.execute(
        select(Address).where(
            Address.id == address_id, Address.resident_id == resident_id
        )
    )
    address = result.scalars().first()
    if not address:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Address not found"
        )

    if str(address.version) != if_match:
        raise HTTPException(status_code=status.HTTP_428_PRECONDITION_REQUIRED, detail="Version mismatch")

    update_data = body.model_dump(exclude_unset=True)
    if "address_type" in update_data and update_data["address_type"] not in VALID_ADDRESS_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="address_type must be 'shipping' or 'mailing'",
        )

    for field, value in update_data.items():
        setattr(address, field, value)

    address.version += 1
    address.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(address)
    return AddressResponse.model_validate(address)


@router.delete("/{resident_id}/addresses/{address_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_address(
    resident_id: UUID,
    address_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _authorize_address_access(resident_id, current_user, db)

    result = await db.execute(
        select(Address).where(
            Address.id == address_id, Address.resident_id == resident_id
        )
    )
    address = result.scalars().first()
    if not address:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Address not found"
        )

    await db.delete(address)
    await db.commit()
