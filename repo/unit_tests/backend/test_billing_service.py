"""Unit tests for billing calculation logic -- pure Python math, no database required.

This mirrors the calculation in app.services.billing_service.generate_bills
but tests the arithmetic in isolation.
"""

from decimal import Decimal


def _calculate_bill(fee_items: list[dict], tax_rate: Decimal) -> dict:
    """Reproduce the per-resident billing loop from generate_bills.

    Each fee_item dict has keys: amount (Decimal), is_taxable (bool).
    tax_rate is a raw decimal multiplier (e.g. Decimal("0.08") for 8%).
    Returns dict with subtotal, tax_total, total.
    """
    subtotal = Decimal("0.00")
    tax_total = Decimal("0.00")

    for fee in fee_items:
        amount = Decimal(str(fee["amount"]))
        tax_amount = (
            (amount * tax_rate).quantize(Decimal("0.01"))
            if fee["is_taxable"]
            else Decimal("0.00")
        )
        subtotal += amount
        tax_total += tax_amount

    total = subtotal + tax_total
    return {"subtotal": subtotal, "tax_total": tax_total, "total": total}


def test_taxable_items_get_tax_applied():
    fee_items = [
        {"amount": Decimal("1000.00"), "is_taxable": True},
        {"amount": Decimal("200.00"), "is_taxable": True},
        {"amount": Decimal("50.00"), "is_taxable": False},
    ]
    tax_rate = Decimal("0.08")

    result = _calculate_bill(fee_items, tax_rate)

    assert result["subtotal"] == Decimal("1250.00")
    # Tax: (1000 * 0.08) + (200 * 0.08) + 0 = 80 + 16 = 96
    assert result["tax_total"] == Decimal("96.00")
    assert result["total"] == Decimal("1346.00")


def test_non_taxable_items_get_no_tax():
    fee_items = [
        {"amount": Decimal("500.00"), "is_taxable": False},
        {"amount": Decimal("300.00"), "is_taxable": False},
    ]
    tax_rate = Decimal("0.10")

    result = _calculate_bill(fee_items, tax_rate)

    assert result["subtotal"] == Decimal("800.00")
    assert result["tax_total"] == Decimal("0.00")
    assert result["total"] == Decimal("800.00")


def test_mixed_taxable_and_non_taxable():
    fee_items = [
        {"amount": Decimal("100.00"), "is_taxable": True},
        {"amount": Decimal("250.00"), "is_taxable": True},
        {"amount": Decimal("75.00"), "is_taxable": False},
    ]
    tax_rate = Decimal("0.05")

    result = _calculate_bill(fee_items, tax_rate)

    assert result["subtotal"] == Decimal("425.00")
    # Tax: (100 * 0.05) + (250 * 0.05) = 5.00 + 12.50 = 17.50
    assert result["tax_total"] == Decimal("17.50")
    assert result["total"] == Decimal("442.50")


def test_tax_rounding():
    """Verify tax amounts are quantized to 2 decimal places."""
    fee_items = [
        {"amount": Decimal("33.33"), "is_taxable": True},
    ]
    tax_rate = Decimal("0.07")

    result = _calculate_bill(fee_items, tax_rate)

    # 33.33 * 0.07 = 2.3331, quantized to 2.33
    assert result["tax_total"] == Decimal("2.33")
    assert result["total"] == Decimal("35.66")
