import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class CreditCreate(BaseModel):
    resident_id: uuid.UUID
    bill_id: uuid.UUID | None = None
    order_id: uuid.UUID | None = None
    amount: Decimal
    reason: str


class CreditResponse(BaseModel):
    id: uuid.UUID
    resident_id: uuid.UUID
    bill_id: uuid.UUID | None
    order_id: uuid.UUID | None
    amount: Decimal
    reason: str
    status: str
    applied_to_bill_id: uuid.UUID | None
    created_by: uuid.UUID
    approved_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    version: int

    model_config = {"from_attributes": True}


class CreditListResponse(BaseModel):
    items: list[CreditResponse]
    total: int
    page: int
    page_size: int


class CreditApproveRequest(BaseModel):
    applied_to_bill_id: uuid.UUID | None = None
