import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class FeeItemCreate(BaseModel):
    property_id: uuid.UUID
    name: str
    amount: Decimal
    is_taxable: bool = False


class FeeItemUpdate(BaseModel):
    name: Optional[str] = None
    amount: Optional[Decimal] = None
    is_taxable: Optional[bool] = None
    is_active: Optional[bool] = None


class FeeItemResponse(BaseModel):
    id: uuid.UUID
    property_id: uuid.UUID
    name: str
    amount: Decimal
    is_taxable: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime
    version: int

    model_config = {"from_attributes": True}


class BillLineItemResponse(BaseModel):
    id: uuid.UUID
    description: str
    amount: Decimal
    tax_amount: Decimal

    model_config = {"from_attributes": True}


class BillResponse(BaseModel):
    id: uuid.UUID
    resident_id: uuid.UUID
    property_id: uuid.UUID
    billing_period: str
    due_date: date
    subtotal: Decimal
    tax_total: Decimal
    late_fee: Decimal
    total: Decimal
    balance_due: Decimal
    status: str
    line_items: list[BillLineItemResponse] = []
    generated_at: datetime
    created_at: datetime
    updated_at: datetime
    version: int

    model_config = {"from_attributes": True}


class BillGenerateRequest(BaseModel):
    property_id: uuid.UUID
    billing_period: str


class BillGenerateResponse(BaseModel):
    bills_generated: int
    property_id: uuid.UUID
    billing_period: str


class FeeItemListResponse(BaseModel):
    items: list[FeeItemResponse]
    total: int
    page: int
    page_size: int


class BillListResponse(BaseModel):
    items: list[BillResponse]
    total: int
    page: int
    page_size: int


class ReconciliationSummary(BaseModel):
    total_billed: Decimal
    total_received: Decimal
    total_outstanding: Decimal
    total_credits: Decimal
    total_late_fees: Decimal


class ReconciliationResident(BaseModel):
    resident_id: uuid.UUID
    name: str
    billed: Decimal
    paid: Decimal
    credits: Decimal
    balance: Decimal
    status: str


class ReconciliationResponse(BaseModel):
    property_id: uuid.UUID
    billing_period: str
    summary: ReconciliationSummary
    residents: list[ReconciliationResident]
