import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, field_validator


class ContentConfigCreate(BaseModel):
    name: str


class ContentConfigUpdate(BaseModel):
    name: Optional[str] = None


class ContentStatusUpdate(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        valid = {"canary", "published", "archived"}
        if v not in valid:
            raise ValueError(f"Status must be one of: {', '.join(sorted(valid))}")
        return v


class ContentSectionCreate(BaseModel):
    section_type: str
    title: Optional[str] = None
    content_json: dict[str, Any]
    sort_order: int = 0
    is_active: bool = True

    @field_validator("section_type")
    @classmethod
    def validate_section_type(cls, v: str) -> str:
        valid = {"carousel", "recommended_tiles", "announcement_banner"}
        if v not in valid:
            raise ValueError(f"Section type must be one of: {', '.join(sorted(valid))}")
        return v


class ContentSectionUpdate(BaseModel):
    title: Optional[str] = None
    content_json: Optional[dict[str, Any]] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class ContentSectionResponse(BaseModel):
    id: uuid.UUID
    config_id: uuid.UUID
    section_type: str
    title: Optional[str]
    content_json: dict[str, Any]
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    version: int

    model_config = {"from_attributes": True}


ContentConfigStatusUpdate = ContentStatusUpdate


class ContentConfigResponse(BaseModel):
    id: uuid.UUID
    name: str
    status: str
    created_by: uuid.UUID
    published_at: Optional[datetime]
    sections: list[ContentSectionResponse] = []
    created_at: datetime
    updated_at: datetime
    version: int

    model_config = {"from_attributes": True}


class ContentConfigListResponse(BaseModel):
    items: list[ContentConfigResponse]
    total: int
    page: int
    page_size: int
