import uuid
from datetime import datetime

from pydantic import BaseModel


class MediaResponse(BaseModel):
    id: uuid.UUID
    filename: str
    original_name: str
    mime_type: str
    file_size: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ListingMediaAttach(BaseModel):
    media_id: uuid.UUID
    sort_order: int = 0
