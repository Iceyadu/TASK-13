import uuid

from pydantic import BaseModel


class CanaryUserResponse(BaseModel):
    id: uuid.UUID
    username: str
    role: str
    canary_enabled: bool

    model_config = {"from_attributes": True}


class CanaryUserListResponse(BaseModel):
    items: list[CanaryUserResponse]
    total: int
    page: int
    page_size: int


class CanaryBatchUpdateEntry(BaseModel):
    user_id: uuid.UUID
    canary_enabled: bool


class CanaryBatchUpdate(BaseModel):
    updates: list[CanaryBatchUpdateEntry]
