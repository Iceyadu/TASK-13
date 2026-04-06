import uuid as uuid_mod
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_roles
from app.models.billing import Bill, Payment
from app.models.media import Media
from app.models.user import User
from app.schemas.payment import (
    PaymentListResponse,
    PaymentResponse,
    PaymentVerifyRequest,
)
from app.middleware.idempotency import check_idempotency, store_idempotency
from app.services.storage_service import save_file
from app.utils.ownership import enforce_bill_access, enforce_payment_access, get_resident_id_for_user, require_financial_access

router = APIRouter(prefix="/payments", tags=["payments"])

ALLOWED_MIME_TYPES = {"image/jpeg", "image/png"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
VALID_PAYMENT_METHODS = {"check", "money_order"}


@router.get("/", response_model=PaymentListResponse)
async def list_payments(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    resident_id: UUID | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_financial_access(current_user)
    offset = (page - 1) * page_size
    query = select(Payment)

    # If current user is a resident, restrict to their own payments
    if current_user.role == "resident":
        own_resident_id = await get_resident_id_for_user(db, current_user)
        if own_resident_id:
            query = query.where(Payment.resident_id == own_resident_id)
        else:
            # Resident with no profile sees nothing
            return PaymentListResponse(items=[], total=0, page=page, page_size=page_size)
    elif resident_id:
        query = query.where(Payment.resident_id == resident_id)

    if status_filter:
        query = query.where(Payment.status == status_filter)

    total_result = await db.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = total_result.scalar() or 0

    result = await db.execute(
        query.order_by(Payment.created_at.desc()).offset(offset).limit(page_size)
    )
    payments = result.scalars().all()

    return PaymentListResponse(
        items=[PaymentResponse.model_validate(p) for p in payments],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def create_payment(
    request: Request,
    bill_id: UUID = Form(...),
    amount: float = Form(...),
    payment_method: str = Form(...),
    evidence_file: UploadFile | None = File(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Use client-provided idempotency key or generate one
    idempotency_key = getattr(request.state, "idempotency_key", None) or uuid_mod.uuid4()

    # Check if a payment with this idempotency key already exists
    existing_result = await db.execute(
        select(Payment).where(Payment.idempotency_key == idempotency_key)
    )
    existing_payment = existing_result.scalars().first()
    if existing_payment:
        return PaymentResponse.model_validate(existing_payment)

    # Validate payment method
    if payment_method not in VALID_PAYMENT_METHODS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="payment_method must be 'check' or 'money_order'",
        )

    # Evidence is required for check and money_order payments
    if payment_method in VALID_PAYMENT_METHODS and (not evidence_file or not evidence_file.filename):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment evidence (scanned image) is required for check and money order payments",
        )

    # Look up the bill to get resident_id
    bill_result = await db.execute(select(Bill).where(Bill.id == bill_id))
    bill = bill_result.scalars().first()
    if not bill:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Bill not found"
        )

    # Verify the caller owns this bill or is authorized staff
    await enforce_bill_access(db, current_user, bill.resident_id)

    evidence_media_id = None
    if evidence_file and evidence_file.filename:
        # Validate file type
        content_type = evidence_file.content_type or ""
        if content_type not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only JPG and PNG files are allowed",
            )

        # Read file content and validate size
        file_content = await evidence_file.read()
        if len(file_content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File size must not exceed 10MB",
            )

        # Generate a unique filename and save
        ext = evidence_file.filename.rsplit(".", 1)[-1] if "." in evidence_file.filename else "bin"
        unique_filename = f"{uuid_mod.uuid4()}.{ext}"
        relative_path = f"payments/{unique_filename}"
        await save_file(file_content, relative_path)

        # Create Media record
        media = Media(
            uploaded_by=current_user.id,
            filename=unique_filename,
            original_name=evidence_file.filename,
            mime_type=content_type,
            file_size=len(file_content),
            storage_path=relative_path,
            created_at=datetime.now(timezone.utc),
        )
        db.add(media)
        await db.flush()
        evidence_media_id = media.id

    payment = Payment(
        bill_id=bill_id,
        resident_id=bill.resident_id,
        amount=amount,
        payment_method=payment_method,
        evidence_media_id=evidence_media_id,
        status="pending",
        idempotency_key=idempotency_key,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        version=1,
    )
    db.add(payment)
    await db.commit()
    await db.refresh(payment)
    return PaymentResponse.model_validate(payment)


@router.get("/{payment_id}", response_model=PaymentResponse)
async def get_payment(
    payment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Payment).where(Payment.id == payment_id))
    payment = result.scalars().first()
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found"
        )
    await enforce_payment_access(db, current_user, payment.resident_id)
    return PaymentResponse.model_validate(payment)


@router.put("/{payment_id}/verify", response_model=PaymentResponse)
async def verify_payment(
    payment_id: UUID,
    body: PaymentVerifyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "property_manager", "accounting_clerk")),
):
    result = await db.execute(select(Payment).where(Payment.id == payment_id))
    payment = result.scalars().first()
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found"
        )

    if payment.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Payment is already {payment.status}",
        )

    payment.status = "verified" if body.action == "verify" else "rejected"
    payment.reviewed_by = current_user.id
    payment.reviewed_at = datetime.now(timezone.utc)
    payment.rejection_reason = body.rejection_reason if body.action == "reject" else None
    payment.updated_at = datetime.now(timezone.utc)
    payment.version += 1

    # When payment is verified, update the bill's balance_due and status
    if body.action == "verify":
        bill_result = await db.execute(select(Bill).where(Bill.id == payment.bill_id))
        bill = bill_result.scalars().first()
        if bill:
            # Sum all verified payments for this bill (including this one being verified)
            verified_sum_result = await db.execute(
                select(func.coalesce(func.sum(Payment.amount), Decimal("0.00")))
                .where(
                    Payment.bill_id == bill.id,
                    Payment.status == "verified",
                    Payment.id != payment.id,
                )
            )
            previously_verified = verified_sum_result.scalar() or Decimal("0.00")
            total_verified = previously_verified + Decimal(str(payment.amount))

            bill.balance_due = bill.total - total_verified
            if bill.balance_due <= Decimal("0.00"):
                bill.balance_due = Decimal("0.00")
                bill.status = "paid"
            elif total_verified > Decimal("0.00"):
                bill.status = "partially_paid"
            bill.updated_at = datetime.now(timezone.utc)
            bill.version += 1

    await db.commit()
    await db.refresh(payment)
    return PaymentResponse.model_validate(payment)
