import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ResidentCreate(BaseModel):
    user_id: uuid.UUID
    unit_id: uuid.UUID
    first_name: str
    last_name: str
    email: Optional[str] = None
    phone: Optional[str] = None


class ResidentUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None


class ResidentResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    unit_id: uuid.UUID
    first_name: str
    last_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    version: int

    model_config = {"from_attributes": True}


class ResidentListResponse(BaseModel):
    items: list[ResidentResponse]
    total: int
    page: int
    page_size: int


class AddressCreate(BaseModel):
    address_type: str
    line1: str
    line2: Optional[str] = None
    city: str
    state: str
    zip_code: str
    is_primary: bool = False


class AddressUpdate(BaseModel):
    address_type: Optional[str] = None
    line1: Optional[str] = None
    line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    is_primary: Optional[bool] = None


class AddressResponse(BaseModel):
    id: uuid.UUID
    resident_id: uuid.UUID
    address_type: str
    line1: str
    line2: Optional[str]
    city: str
    state: str
    zip_code: str
    is_primary: bool
    created_at: datetime
    updated_at: datetime
    version: int

    model_config = {"from_attributes": True}
