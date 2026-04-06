import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, field_validator


class PaymentResponse(BaseModel):
    id: uuid.UUID
    bill_id: uuid.UUID
    resident_id: uuid.UUID
    amount: Decimal
    payment_method: str
    evidence_media_id: Optional[uuid.UUID]
    status: str
    reviewed_by: Optional[uuid.UUID]
    reviewed_at: Optional[datetime]
    rejection_reason: Optional[str]
    created_at: datetime
    updated_at: datetime
    version: int

    model_config = {"from_attributes": True}


class PaymentListResponse(BaseModel):
    items: list[PaymentResponse]
    total: int
    page: int
    page_size: int


class PaymentVerifyRequest(BaseModel):
    action: str
    rejection_reason: Optional[str] = None

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        if v not in {"verify", "reject"}:
            raise ValueError("Action must be 'verify' or 'reject'")
        return v


class CreditMemoCreate(BaseModel):
    resident_id: uuid.UUID
    bill_id: Optional[uuid.UUID] = None
    order_id: Optional[uuid.UUID] = None
    amount: Decimal
    reason: str


class CreditMemoApproveRequest(BaseModel):
    applied_to_bill_id: Optional[uuid.UUID] = None


class CreditMemoResponse(BaseModel):
    id: uuid.UUID
    resident_id: uuid.UUID
    bill_id: Optional[uuid.UUID]
    order_id: Optional[uuid.UUID]
    amount: Decimal
    reason: str
    status: str
    applied_to_bill_id: Optional[uuid.UUID]
    created_by: uuid.UUID
    approved_by: Optional[uuid.UUID]
    created_at: datetime
    updated_at: datetime
    version: int

    model_config = {"from_attributes": True}
