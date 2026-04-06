import uuid
from datetime import datetime, timedelta, timezone

from fastapi import Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.base import BaseHTTPMiddleware

from app.models.audit import IdempotencyRecord


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """Check Idempotency-Key header on POST/PUT/PATCH to prevent duplicate writes."""

    async def dispatch(self, request: Request, call_next):
        if request.method not in ("POST", "PUT", "PATCH"):
            return await call_next(request)

        idem_key = request.headers.get("Idempotency-Key")
        if not idem_key:
            return await call_next(request)

        try:
            idem_uuid = uuid.UUID(idem_key)
        except ValueError:
            return await call_next(request)

        # Store the key for downstream handlers to use
        request.state.idempotency_key = idem_uuid
        return await call_next(request)


async def check_idempotency(db: AsyncSession, key: uuid.UUID) -> IdempotencyRecord | None:
    result = await db.execute(
        select(IdempotencyRecord).where(IdempotencyRecord.key == key)
    )
    return result.scalar_one_or_none()


async def store_idempotency(
    db: AsyncSession,
    key: uuid.UUID,
    user_id: uuid.UUID,
    endpoint: str,
    response_code: int,
    response_body: dict,
) -> None:
    record = IdempotencyRecord(
        key=key,
        user_id=user_id,
        endpoint=endpoint,
        response_code=response_code,
        response_body=response_body,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    db.add(record)
    await db.flush()
