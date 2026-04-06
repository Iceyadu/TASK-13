import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, field_validator, model_validator


class ListingCreate(BaseModel):
    property_id: uuid.UUID
    title: str
    description: Optional[str] = None
    category: str
    price: Optional[Decimal] = None

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        valid = {"garage_sale", "parking_sublet", "amenity_addon"}
        if v not in valid:
            raise ValueError(f"Category must be one of: {', '.join(sorted(valid))}")
        return v


class ListingUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    price: Optional[Decimal] = None


class ListingStatusUpdate(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        valid = {"published", "unpublished", "archived"}
        if v not in valid:
            raise ValueError(f"Status must be one of: {', '.join(sorted(valid))}")
        return v


class BulkStatusRequest(BaseModel):
    listing_ids: list[uuid.UUID]
    status: str


class BulkStatusResult(BaseModel):
    id: uuid.UUID
    status: str
    success: bool


class BulkStatusResponse(BaseModel):
    updated: int
    failed: int
    results: list[BulkStatusResult]


class ListingListResponse(BaseModel):
    items: list["ListingResponse"]
    total: int
    page: int
    page_size: int


class ListingMediaRef(BaseModel):
    media_id: uuid.UUID
    sort_order: int
    model_config = {"from_attributes": True}


class ListingResponse(BaseModel):
    id: uuid.UUID
    property_id: uuid.UUID
    created_by: uuid.UUID
    title: str
    description: Optional[str]
    category: str
    price: Optional[Decimal]
    status: str
    published_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    version: int
    media: list[ListingMediaRef] = []

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def map_media_links(cls, data):
        if hasattr(data, "media_links"):
            data_dict = {k: getattr(data, k) for k in cls.model_fields if hasattr(data, k)}
            data_dict["media"] = [
                {"media_id": link.media_id, "sort_order": link.sort_order}
                for link in data.media_links
            ]
            return data_dict
        return data
