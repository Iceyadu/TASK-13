import csv
import io
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Header, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_roles
from app.utils.conflict import raise_conflict, detect_changed_fields
from app.utils.ownership import enforce_bill_access, require_financial_access
from app.models.billing import Bill, CreditMemo, FeeItem, Payment
from app.models.resident import Resident
from app.models.user import User
from app.services.audit_service import log_audit
from app.schemas.billing import (
    BillGenerateRequest,
    BillListResponse,
    BillResponse,
    FeeItemCreate,
    FeeItemListResponse,
    FeeItemResponse,
    FeeItemUpdate,
    ReconciliationResponse,
)

router = APIRouter(tags=["billing"])


# -- Fee Items -----------------------------------------------------------------

@router.get("/billing/fee-items", response_model=FeeItemListResponse)
async def list_fee_items(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _staff: User = Depends(require_roles("admin", "property_manager", "accounting_clerk")),
):
    offset = (page - 1) * page_size

    total_result = await db.execute(select(func.count()).select_from(FeeItem))
    total = total_result.scalar() or 0

    result = await db.execute(
        select(FeeItem).order_by(FeeItem.name).offset(offset).limit(page_size)
    )
    items = result.scalars().all()

    return FeeItemListResponse(
        items=[FeeItemResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/billing/fee-items",
    response_model=FeeItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_fee_item(
    body: FeeItemCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_roles("admin")),
):
    fee_item = FeeItem(
        **body.model_dump(),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        version=1,
    )
    db.add(fee_item)
    await db.commit()
    await db.refresh(fee_item)
    return FeeItemResponse.model_validate(fee_item)


@router.put("/billing/fee-items/{fee_item_id}", response_model=FeeItemResponse)
async def update_fee_item(
    fee_item_id: UUID,
    body: FeeItemUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_roles("admin")),
    if_match: str | None = Header(None, alias="If-Match"),
):
    if if_match is None:
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail="If-Match header is required for updates",
        )

    result = await db.execute(select(FeeItem).where(FeeItem.id == fee_item_id))
    fee_item = result.scalars().first()
    if not fee_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Fee item not found"
        )

    update_data = body.model_dump(exclude_unset=True)

    if str(fee_item.version) != if_match:
        client_version = int(if_match)
        server_data_dict = {field: getattr(fee_item, field) for field in update_data.keys()}
        for k, v in server_data_dict.items():
            if hasattr(v, 'isoformat'):
                server_data_dict[k] = v.isoformat()
            elif hasattr(v, 'hex'):
                server_data_dict[k] = str(v)
        changed = detect_changed_fields(update_data, server_data_dict)
        raise_conflict(
            your_version=client_version,
            server_version=fee_item.version,
            your_data=update_data,
            server_data=server_data_dict,
            changed_fields=changed,
        )

    for field, value in update_data.items():
        setattr(fee_item, field, value)

    fee_item.version += 1
    fee_item.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(fee_item)
    return FeeItemResponse.model_validate(fee_item)


# -- Bills ---------------------------------------------------------------------

@router.get("/billing/bills/overdue", response_model=BillListResponse)
async def list_overdue_bills(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _staff: User = Depends(require_roles("admin", "property_manager", "accounting_clerk")),
):
    offset = (page - 1) * page_size
    today = date.today()

    query = select(Bill).where(
        Bill.due_date < today,
        Bill.status != "paid",
    )

    total_result = await db.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = total_result.scalar() or 0

    result = await db.execute(
        query.order_by(Bill.due_date.asc()).offset(offset).limit(page_size)
    )
    bills = result.scalars().all()

    return BillListResponse(
        items=[BillResponse.model_validate(b) for b in bills],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/billing/bills", response_model=BillListResponse)
async def list_bills(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    resident_id: UUID | None = Query(None),
    billing_period: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_financial_access(current_user)
    offset = (page - 1) * page_size
    query = select(Bill)

    # If current user is a resident, restrict to their own bills
    if current_user.role == "resident":
        res_result = await db.execute(
            select(Resident).where(Resident.user_id == current_user.id)
        )
        resident = res_result.scalars().first()
        if not resident:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resident profile not found",
            )
        query = query.where(Bill.resident_id == resident.id)
    elif resident_id:
        query = query.where(Bill.resident_id == resident_id)

    if billing_period:
        query = query.where(Bill.billing_period == billing_period)

    total_result = await db.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = total_result.scalar() or 0

    result = await db.execute(
        query.order_by(Bill.created_at.desc()).offset(offset).limit(page_size)
    )
    bills = result.scalars().all()

    return BillListResponse(
        items=[BillResponse.model_validate(b) for b in bills],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/billing/bills/{bill_id}", response_model=BillResponse)
async def get_bill(
    bill_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Bill).where(Bill.id == bill_id))
    bill = result.scalars().first()
    if not bill:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Bill not found"
        )
    await enforce_bill_access(db, current_user, bill.resident_id)
    return BillResponse.model_validate(bill)


# -- Bill Generation -----------------------------------------------------------

@router.post("/billing/generate", status_code=status.HTTP_202_ACCEPTED)
async def generate_bills(
    body: BillGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "accounting_clerk")),
):
    from app.services.billing_service import generate_bills as billing_generate

    count = await billing_generate(
        db=db,
        property_id=body.property_id,
        billing_period=body.billing_period,
    )
    await log_audit(db, user_id=current_user.id, action="GENERATE_BILLS", resource_type="billing", resource_id=body.property_id, new_value={"billing_period": body.billing_period, "bills_created": count})
    return {"detail": "Bill generation started", "bills_created": count}


# -- Apply Late Fees -----------------------------------------------------------

@router.post("/billing/apply-late-fees", status_code=status.HTTP_200_OK)
async def apply_late_fees_endpoint(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "property_manager", "accounting_clerk")),
):
    from app.services.billing_service import apply_late_fees

    count = await apply_late_fees(db)
    await log_audit(db, user_id=current_user.id, action="APPLY_LATE_FEES", resource_type="billing", resource_id=current_user.id, new_value={"bills_updated": count})
    await db.commit()
    return {"detail": "Late fees applied", "bills_updated": count}


# -- Reconciliation -----------------------------------------------------------

@router.get("/billing/reconciliation", response_model=ReconciliationResponse)
async def get_reconciliation(
    property_id: UUID | None = Query(None),
    billing_period: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _staff: User = Depends(require_roles("admin", "property_manager", "accounting_clerk")),
):
    query = select(Bill)
    if property_id:
        query = query.where(Bill.property_id == property_id)
    if billing_period:
        query = query.where(Bill.billing_period == billing_period)

    result = await db.execute(query)
    bills = result.scalars().all()

    if not bills:
        return ReconciliationResponse(
            property_id=property_id or "00000000-0000-0000-0000-000000000000",
            billing_period=billing_period or "",
            summary={
                "total_billed": Decimal("0.00"),
                "total_received": Decimal("0.00"),
                "total_outstanding": Decimal("0.00"),
                "total_credits": Decimal("0.00"),
                "total_late_fees": Decimal("0.00"),
            },
            residents=[],
        )

    total_billed = Decimal("0.00")
    total_received = Decimal("0.00")
    total_credits = Decimal("0.00")
    total_late_fees = Decimal("0.00")
    residents_data = []

    for bill in bills:
        total_billed += bill.total
        total_late_fees += bill.late_fee

        pay_result = await db.execute(
            select(func.coalesce(func.sum(Payment.amount), Decimal("0.00")))
            .where(Payment.bill_id == bill.id, Payment.status == "verified")
        )
        paid = pay_result.scalar() or Decimal("0.00")
        total_received += paid

        credit_result = await db.execute(
            select(func.coalesce(func.sum(CreditMemo.amount), Decimal("0.00")))
            .where(CreditMemo.applied_to_bill_id == bill.id, CreditMemo.status == "approved")
        )
        credits_amt = credit_result.scalar() or Decimal("0.00")
        total_credits += credits_amt

        balance = bill.total - paid - credits_amt

        res_result = await db.execute(select(Resident).where(Resident.id == bill.resident_id))
        res = res_result.scalars().first()
        name = f"{res.first_name} {res.last_name}" if res else "Unknown"

        residents_data.append({
            "resident_id": bill.resident_id,
            "name": name,
            "billed": bill.total,
            "paid": paid,
            "credits": credits_amt,
            "balance": balance,
            "status": "paid" if balance <= 0 else "outstanding",
        })

    return ReconciliationResponse(
        property_id=property_id or bills[0].property_id,
        billing_period=billing_period or bills[0].billing_period,
        summary={
            "total_billed": total_billed,
            "total_received": total_received,
            "total_outstanding": total_billed - total_received - total_credits,
            "total_credits": total_credits,
            "total_late_fees": total_late_fees,
        },
        residents=residents_data,
    )


@router.get("/billing/reconciliation/csv")
async def get_reconciliation_csv(
    property_id: UUID | None = Query(None),
    billing_period: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _staff: User = Depends(require_roles("admin", "property_manager", "accounting_clerk")),
):
    report = await get_reconciliation(
        property_id=property_id,
        billing_period=billing_period,
        db=db,
        _staff=_staff,
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["resident_id", "name", "billed", "paid", "credits", "balance", "status"])
    for row in report.residents:
        writer.writerow([
            str(row.resident_id), row.name, str(row.billed),
            str(row.paid), str(row.credits), str(row.balance), row.status,
        ])

    output.seek(0)
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=reconciliation.csv"},
    )
