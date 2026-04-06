from __future__ import annotations
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.billing import Bill, BillLineItem, FeeItem, Payment
from app.models.property import Property, Unit
from app.models.resident import Resident

async def generate_bills(db: AsyncSession, property_id: UUID, billing_period: str) -> int:
    # Check for existing bills for this period to prevent duplicates
    existing = await db.execute(
        select(func.count()).select_from(Bill).where(
            Bill.property_id == property_id, Bill.billing_period == billing_period
        )
    )
    if existing.scalar_one() > 0:
        return 0  # Already generated

    prop_result = await db.execute(select(Property).where(Property.id == property_id))
    prop = prop_result.scalar_one_or_none()
    if prop is None:
        raise ValueError(f"Property {property_id} not found")

    tax_rate = Decimal(str(prop.tax_rate))

    fee_result = await db.execute(
        select(FeeItem).where(FeeItem.property_id == property_id, FeeItem.is_active == True)
    )
    fee_items = list(fee_result.scalars().all())
    if not fee_items:
        return 0

    unit_ids_q = select(Unit.id).where(Unit.property_id == property_id, Unit.status == "active")
    resident_result = await db.execute(
        select(Resident).where(Resident.unit_id.in_(unit_ids_q))
    )
    residents = list(resident_result.scalars().all())
    if not residents:
        return 0

    # Calculate due_date from billing_period (YYYY-MM) + billing_day
    try:
        year, month = billing_period.split("-")
        period_start = date(int(year), int(month), prop.billing_day)
    except (ValueError, IndexError):
        period_start = date.today()
    due_date = period_start
    bills_created = 0

    for resident in residents:
        subtotal = Decimal("0.00")
        tax_total = Decimal("0.00")
        line_items = []

        for fee in fee_items:
            amount = Decimal(str(fee.amount))
            tax_amount = (amount * tax_rate).quantize(Decimal("0.01")) if fee.is_taxable else Decimal("0.00")
            subtotal += amount
            tax_total += tax_amount
            line_items.append(BillLineItem(
                fee_item_id=fee.id,
                description=fee.name,
                amount=amount,
                tax_amount=tax_amount,
            ))

        total = subtotal + tax_total
        bill = Bill(
            property_id=property_id,
            resident_id=resident.id,
            billing_period=billing_period,
            due_date=due_date,
            subtotal=subtotal,
            tax_total=tax_total,
            total=total,
            balance_due=total,
            status="generated",
        )
        db.add(bill)
        await db.flush()

        for li in line_items:
            li.bill_id = bill.id
            db.add(li)

        bills_created += 1

    await db.flush()
    return bills_created


async def get_reconciliation_report(db: AsyncSession, property_id: UUID | None, billing_period: str | None) -> dict:
    query = select(Bill)
    if property_id:
        query = query.where(Bill.property_id == property_id)
    if billing_period:
        query = query.where(Bill.billing_period == billing_period)

    result = await db.execute(query)
    bills = list(result.scalars().all())

    total_billed = sum(b.total for b in bills)
    total_late_fees = sum(b.late_fee for b in bills)

    # Sum verified payments
    bill_ids = [b.id for b in bills]
    total_received = Decimal("0.00")
    if bill_ids:
        pay_result = await db.execute(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.bill_id.in_(bill_ids), Payment.status == "verified"
            )
        )
        total_received = Decimal(str(pay_result.scalar_one()))

    total_outstanding = total_billed - total_received

    return {
        "property_id": str(property_id) if property_id else None,
        "billing_period": billing_period,
        "summary": {
            "total_billed": total_billed,
            "total_received": total_received,
            "total_outstanding": total_outstanding,
            "total_credits": Decimal("0.00"),
            "total_late_fees": total_late_fees,
        },
        "residents": [],
    }


async def apply_late_fees(db: AsyncSession) -> int:
    """Apply late fees to overdue bills. Returns count updated."""
    today = date.today()

    # Find all unpaid bills that haven't had a late fee applied yet
    result = await db.execute(
        select(Bill).where(
            Bill.status.in_(["generated", "partially_paid"]),
            Bill.late_fee == Decimal("0.00"),
        )
    )
    bills = list(result.scalars().all())

    count = 0
    for bill in bills:
        # Look up property to get late_fee_amount and grace period
        prop_result = await db.execute(
            select(Property).where(Property.id == bill.property_id)
        )
        prop = prop_result.scalars().first()
        if not prop:
            continue

        # Late after due_date + grace period
        grace_deadline = bill.due_date + timedelta(days=prop.late_fee_days)
        if today <= grace_deadline:
            continue  # Not late yet

        late_fee_amount = Decimal(str(prop.late_fee_amount))
        bill.late_fee = late_fee_amount
        bill.total = bill.subtotal + bill.tax_total + bill.late_fee

        # Calculate verified payments sum for this bill
        pay_result = await db.execute(
            select(func.coalesce(func.sum(Payment.amount), Decimal("0.00")))
            .where(Payment.bill_id == bill.id, Payment.status == "verified")
        )
        verified_sum = pay_result.scalar() or Decimal("0.00")

        bill.balance_due = bill.total - verified_sum

        # If bill was 'generated', move to 'overdue'
        if bill.status == "generated":
            bill.status = "overdue"

        count += 1

    await db.flush()
    return count
