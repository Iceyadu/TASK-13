import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


class BackupRecordResponse(BaseModel):
    id: uuid.UUID
    filename: str
    file_size: int | None
    encryption_method: str
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    expires_at: date
    created_at: datetime

    model_config = {"from_attributes": True}


class BackupRecordListResponse(BaseModel):
    items: list[BackupRecordResponse]
    total: int
    page: int
    page_size: int


class BackupTriggerRequest(BaseModel):
    pass  # No fields needed, trigger is a simple POST


class BackupRestoreRequest(BaseModel):
    backup_id: uuid.UUID
    passphrase: str
