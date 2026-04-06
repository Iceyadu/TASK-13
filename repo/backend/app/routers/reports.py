import csv
import io
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_roles
from app.models.billing import Bill, BillLineItem, Payment
from app.models.order import Order
from app.models.property import Property, Unit
from app.models.resident import Resident
from app.models.user import User
from app.utils.ownership import enforce_bill_access, enforce_payment_access

router = APIRouter(tags=["reports"])


def _rows_to_csv(header: list[str], rows: list[list]) -> io.StringIO:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(header)
    for row in rows:
        writer.writerow(row)
    output.seek(0)
    return output


# -- CSV Reports ---------------------------------------------------------------

@router.get("/reports/billing/csv")
async def billing_csv(
    billing_period: str | None = Query(None),
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _staff: User = Depends(require_roles("admin", "property_manager", "accounting_clerk")),
):
    query = select(Bill)
    if billing_period:
        query = query.where(Bill.billing_period == billing_period)
    if from_date:
        query = query.where(Bill.due_date >= from_date)
    if to_date:
        query = query.where(Bill.due_date <= to_date)
    query = query.order_by(Bill.created_at.desc())

    result = await db.execute(query)
    bills = result.scalars().all()

    header = ["id", "resident_id", "billing_period", "total", "status", "created_at"]
    rows = [
        [str(b.id), str(b.resident_id), b.billing_period, str(b.total), b.status, str(b.created_at)]
        for b in bills
    ]

    output = _rows_to_csv(header, rows)
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=billing_report.csv"},
    )


@router.get("/reports/payments/csv")
async def payments_csv(
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _staff: User = Depends(require_roles("admin", "property_manager", "accounting_clerk")),
):
    query = select(Payment)
    if from_date:
        query = query.where(Payment.created_at >= from_date)
    if to_date:
        query = query.where(Payment.created_at <= to_date)
    query = query.order_by(Payment.created_at.desc())

    result = await db.execute(query)
    payments = result.scalars().all()

    header = ["id", "bill_id", "amount", "payment_method", "status", "created_at"]
    rows = [
        [str(p.id), str(p.bill_id), str(p.amount), p.payment_method, p.status, str(p.created_at)]
        for p in payments
    ]

    output = _rows_to_csv(header, rows)
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=payments_report.csv"},
    )


@router.get("/reports/orders/csv")
async def orders_csv(
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _staff: User = Depends(require_roles("admin", "property_manager", "maintenance_dispatcher")),
):
    query = select(Order)
    if from_date:
        query = query.where(Order.created_at >= from_date)
    if to_date:
        query = query.where(Order.created_at <= to_date)
    query = query.order_by(Order.created_at.desc())

    result = await db.execute(query)
    orders = result.scalars().all()

    header = ["id", "resident_id", "title", "category", "status", "created_at"]
    rows = [
        [str(o.id), str(o.resident_id), o.title, o.category or "", o.status, str(o.created_at)]
        for o in orders
    ]

    output = _rows_to_csv(header, rows)
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=orders_report.csv"},
    )


# -- PDF Downloads -------------------------------------------------------------

async def _lookup_bill_context(db: AsyncSession, bill: Bill) -> dict:
    """Look up Property name, Resident name, and Unit number for a bill."""
    property_name = ""
    resident_name = ""
    unit_number = ""

    prop_result = await db.execute(select(Property).where(Property.id == bill.property_id))
    prop = prop_result.scalars().first()
    if prop:
        property_name = prop.name

    res_result = await db.execute(select(Resident).where(Resident.id == bill.resident_id))
    resident = res_result.scalars().first()
    if resident:
        resident_name = f"{resident.first_name} {resident.last_name}"
        unit_result = await db.execute(select(Unit).where(Unit.id == resident.unit_id))
        unit = unit_result.scalars().first()
        if unit:
            unit_number = unit.unit_number

    return {
        "property_name": property_name,
        "resident_name": resident_name,
        "unit_number": unit_number,
    }


@router.get("/billing/statements/{bill_id}/pdf")
async def download_statement_pdf(
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

    context = await _lookup_bill_context(db, bill)

    # Load line items
    li_result = await db.execute(select(BillLineItem).where(BillLineItem.bill_id == bill.id))
    line_items = li_result.scalars().all()

    line_item_dicts = [
        {
            "description": li.description,
            "amount": float(li.amount),
            "tax_amount": float(li.tax_amount),
            "total": float(li.amount + li.tax_amount),
        }
        for li in line_items
    ]

    from app.services.pdf_service import generate_statement_pdf

    pdf_bytes = generate_statement_pdf({
        "property_name": context["property_name"],
        "resident_name": context["resident_name"],
        "unit_number": context["unit_number"],
        "billing_period": bill.billing_period,
        "bill_date": str(bill.created_at),
        "due_date": str(bill.due_date),
        "line_items": line_item_dicts,
        "total_amount": float(bill.total),
    })

    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=statement_{bill_id}.pdf"
        },
    )


@router.get("/payments/{payment_id}/receipt/pdf")
async def download_receipt_pdf(
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

    # Look up the bill to get property context
    bill_result = await db.execute(select(Bill).where(Bill.id == payment.bill_id))
    bill = bill_result.scalars().first()

    property_name = ""
    resident_name = ""
    unit_number = ""

    if bill:
        context = await _lookup_bill_context(db, bill)
        property_name = context["property_name"]
        resident_name = context["resident_name"]
        unit_number = context["unit_number"]

    from app.services.pdf_service import generate_receipt_pdf

    pdf_bytes = generate_receipt_pdf({
        "receipt_number": str(payment.id),
        "resident_name": resident_name,
        "unit_number": unit_number,
        "payment_date": str(payment.created_at),
        "payment_method": payment.payment_method,
        "amount": float(payment.amount),
        "bill_reference": str(payment.bill_id),
        "property_name": property_name,
    })

    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=receipt_{payment_id}.pdf"
        },
    )
