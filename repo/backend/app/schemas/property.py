import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class PropertyCreate(BaseModel):
    name: str
    address: Optional[str] = None
    billing_day: int = 1
    late_fee_days: int = 10
    late_fee_amount: Decimal = Decimal("25.00")
    tax_rate: Decimal = Decimal("0.0600")


class PropertyUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    billing_day: Optional[int] = None
    late_fee_days: Optional[int] = None
    late_fee_amount: Optional[Decimal] = None
    tax_rate: Optional[Decimal] = None


class PropertyResponse(BaseModel):
    id: uuid.UUID
    name: str
    address: Optional[str]
    billing_day: int
    late_fee_days: int
    late_fee_amount: Decimal
    tax_rate: Decimal
    created_at: datetime
    updated_at: datetime
    version: int

    model_config = {"from_attributes": True}


class PropertyListResponse(BaseModel):
    items: list[PropertyResponse]
    total: int
    page: int
    page_size: int


class UnitCreate(BaseModel):
    unit_number: str
    status: str = "active"


class UnitUpdate(BaseModel):
    unit_number: Optional[str] = None
    status: Optional[str] = None


class UnitResponse(BaseModel):
    id: uuid.UUID
    property_id: uuid.UUID
    unit_number: str
    status: str
    created_at: datetime
    updated_at: datetime
    version: int

    model_config = {"from_attributes": True}
