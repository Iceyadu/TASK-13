from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Header, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_roles
from app.utils.conflict import raise_conflict, detect_changed_fields
from app.models.billing import Bill, CreditMemo
from app.models.resident import Resident
from app.models.user import User
from app.utils.ownership import enforce_credit_access, get_resident_id_for_user, require_financial_access
from app.schemas.credit import (
    CreditApproveRequest,
    CreditCreate,
    CreditListResponse,
    CreditResponse,
)

router = APIRouter(prefix="/credits", tags=["credits"])


@router.get("/", response_model=CreditListResponse)
async def list_credits(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    resident_id: UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_financial_access(current_user)
    offset = (page - 1) * page_size
    query = select(CreditMemo)

    # If current user is a resident, restrict to their own credits
    if current_user.role == "resident":
        own_resident_id = await get_resident_id_for_user(db, current_user)
        if own_resident_id:
            query = query.where(CreditMemo.resident_id == own_resident_id)
        else:
            return CreditListResponse(items=[], total=0, page=page, page_size=page_size)
    elif resident_id:
        query = query.where(CreditMemo.resident_id == resident_id)

    total_result = await db.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = total_result.scalar() or 0

    result = await db.execute(
        query.order_by(CreditMemo.created_at.desc()).offset(offset).limit(page_size)
    )
    credits = result.scalars().all()

    return CreditListResponse(
        items=[CreditResponse.model_validate(c) for c in credits],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/", response_model=CreditResponse, status_code=status.HTTP_201_CREATED)
async def create_credit(
    body: CreditCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Allow staff roles and residents
    staff_roles = {"admin", "property_manager", "accounting_clerk"}

    if current_user.role == "resident":
        # Resident can only create credits for themselves
        res_result = await db.execute(
            select(Resident).where(Resident.user_id == current_user.id)
        )
        resident = res_result.scalars().first()
        if not resident:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resident profile not found",
            )
        # Override resident_id with the caller's own resident id
        resident_id = resident.id
    elif current_user.role in staff_roles:
        # Staff uses the resident_id from the body
        resident_id = body.resident_id
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )

    credit = CreditMemo(
        resident_id=resident_id,
        bill_id=body.bill_id,
        order_id=body.order_id,
        amount=body.amount,
        reason=body.reason,
        status="pending",
        created_by=current_user.id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        version=1,
    )
    db.add(credit)
    await db.commit()
    await db.refresh(credit)
    return CreditResponse.model_validate(credit)


@router.get("/{credit_id}", response_model=CreditResponse)
async def get_credit(
    credit_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(CreditMemo).where(CreditMemo.id == credit_id))
    credit = result.scalars().first()
    if not credit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Credit not found"
        )
    await enforce_credit_access(db, current_user, credit.resident_id)
    return CreditResponse.model_validate(credit)


@router.put("/{credit_id}/approve", response_model=CreditResponse)
async def approve_credit(
    credit_id: UUID,
    body: CreditApproveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
    if_match: str | None = Header(None, alias="If-Match"),
):
    result = await db.execute(select(CreditMemo).where(CreditMemo.id == credit_id))
    credit = result.scalars().first()
    if not credit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Credit not found"
        )

    if if_match is not None and str(credit.version) != if_match:
        client_version = int(if_match)
        update_data = body.model_dump(exclude_unset=True)
        server_data_dict = {field: getattr(credit, field) for field in update_data.keys() if hasattr(credit, field)}
        for k, v in server_data_dict.items():
            if hasattr(v, 'isoformat'):
                server_data_dict[k] = v.isoformat()
            elif hasattr(v, 'hex'):
                server_data_dict[k] = str(v)
        changed = detect_changed_fields(update_data, server_data_dict)
        raise_conflict(
            your_version=client_version,
            server_version=credit.version,
            your_data=update_data,
            server_data=server_data_dict,
            changed_fields=changed,
        )

    if credit.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Credit is already {credit.status}",
        )

    credit.status = "approved"
    credit.approved_by = current_user.id
    if body.applied_to_bill_id:
        credit.applied_to_bill_id = body.applied_to_bill_id

        # Reduce the bill's balance_due when credit is applied
        bill_result = await db.execute(
            select(Bill).where(Bill.id == body.applied_to_bill_id)
        )
        bill = bill_result.scalars().first()
        if bill:
            bill.balance_due = bill.balance_due - credit.amount
            if bill.balance_due <= Decimal("0.00"):
                bill.balance_due = Decimal("0.00")
                bill.status = "paid"
            bill.updated_at = datetime.now(timezone.utc)
            bill.version += 1

    credit.version += 1
    credit.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(credit)
    return CreditResponse.model_validate(credit)


@router.get("/{credit_id}/pdf")
async def download_credit_pdf(
    credit_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(CreditMemo).where(CreditMemo.id == credit_id))
    credit = result.scalars().first()
    if not credit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Credit not found"
        )
    await enforce_credit_access(db, current_user, credit.resident_id)

    from app.services.pdf_service import generate_credit_memo_pdf

    pdf_bytes = generate_credit_memo_pdf({
        "memo_number": str(credit.id),
        "resident_name": "",
        "unit_number": "",
        "issue_date": str(credit.created_at),
        "reason": credit.reason,
        "amount": float(credit.amount),
        "property_name": "",
    })

    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=credit_memo_{credit_id}.pdf"
        },
    )
