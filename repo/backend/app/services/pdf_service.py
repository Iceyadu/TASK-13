"""PDF generation helpers using ReportLab.

Each public function accepts a plain ``dict`` of data, renders a PDF
using ReportLab's platypus, and returns the resulting PDF as ``bytes``.
"""
from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer


_STYLES = getSampleStyleSheet()
_TITLE_STYLE = ParagraphStyle(
    "CustomTitle",
    parent=_STYLES["Title"],
    textColor=colors.HexColor("#1a3c5e"),
    spaceAfter=12,
)
_NORMAL = _STYLES["Normal"]
_FOOTER_STYLE = ParagraphStyle(
    "Footer",
    parent=_STYLES["Normal"],
    fontSize=8,
    textColor=colors.grey,
    alignment=1,  # center
)


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _build_pdf(elements: list) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, topMargin=0.5 * inch, bottomMargin=0.5 * inch)
    doc.build(elements)
    return buf.getvalue()


def generate_statement_pdf(bill_data: dict[str, Any]) -> bytes:
    elements = []

    elements.append(Paragraph("Billing Statement", _TITLE_STYLE))
    elements.append(Spacer(1, 6))

    meta_lines = [
        f"<b>Property:</b> {bill_data.get('property_name', 'N/A')}",
        f"<b>Resident:</b> {bill_data.get('resident_name', 'N/A')}",
        f"<b>Unit:</b> {bill_data.get('unit_number', 'N/A')}",
        f"<b>Period:</b> {bill_data.get('billing_period', '')} &nbsp;&nbsp; "
        f"<b>Bill Date:</b> {bill_data.get('bill_date', '')} &nbsp;&nbsp; "
        f"<b>Due Date:</b> {bill_data.get('due_date', '')}",
    ]
    for line in meta_lines:
        elements.append(Paragraph(line, _NORMAL))
    elements.append(Spacer(1, 12))

    # Line items table
    table_data = [["Description", "Amount", "Tax", "Total"]]
    for item in bill_data.get("line_items", []):
        table_data.append([
            str(item.get("description", "")),
            f"${item.get('amount', 0):.2f}",
            f"${item.get('tax_amount', 0):.2f}",
            f"${item.get('total', 0):.2f}",
        ])
    table_data.append(["Total Due", "", "", f"${bill_data.get('total_amount', 0):.2f}"])

    t = Table(table_data, colWidths=[3 * inch, 1.2 * inch, 1.2 * inch, 1.2 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f4f8")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f9f9f9")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(t)

    elements.append(Spacer(1, 24))
    elements.append(Paragraph(f"HarborView Property Operations Portal — Generated {_timestamp()}", _FOOTER_STYLE))

    return _build_pdf(elements)


def generate_receipt_pdf(payment_data: dict[str, Any]) -> bytes:
    elements = []

    elements.append(Paragraph("Payment Receipt", _TITLE_STYLE))
    elements.append(Spacer(1, 6))

    meta_lines = [
        f"<b>Receipt #:</b> {payment_data.get('receipt_number', '')}",
        f"<b>Date:</b> {payment_data.get('payment_date', '')}",
        f"<b>Property:</b> {payment_data.get('property_name', 'N/A')}",
        f"<b>Resident:</b> {payment_data.get('resident_name', 'N/A')}",
        f"<b>Unit:</b> {payment_data.get('unit_number', 'N/A')}",
    ]
    for line in meta_lines:
        elements.append(Paragraph(line, _NORMAL))
    elements.append(Spacer(1, 12))

    table_data = [
        ["Bill Reference", str(payment_data.get("bill_reference", "N/A"))],
        ["Payment Method", str(payment_data.get("payment_method", ""))],
        ["Amount Paid", f"${payment_data.get('amount', 0):.2f}"],
    ]
    t = Table(table_data, colWidths=[2.5 * inch, 3 * inch])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f9f9f9")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(t)

    elements.append(Spacer(1, 24))
    elements.append(Paragraph(f"HarborView Property Operations Portal — Generated {_timestamp()}", _FOOTER_STYLE))

    return _build_pdf(elements)


def generate_credit_memo_pdf(credit_data: dict[str, Any]) -> bytes:
    elements = []

    elements.append(Paragraph("Credit Memo", _TITLE_STYLE))
    elements.append(Spacer(1, 6))

    meta_lines = [
        f"<b>Memo #:</b> {credit_data.get('memo_number', '')}",
        f"<b>Date:</b> {credit_data.get('issue_date', '')}",
        f"<b>Property:</b> {credit_data.get('property_name', 'N/A')}",
        f"<b>Resident:</b> {credit_data.get('resident_name', 'N/A')}",
        f"<b>Unit:</b> {credit_data.get('unit_number', 'N/A')}",
    ]
    for line in meta_lines:
        elements.append(Paragraph(line, _NORMAL))
    elements.append(Spacer(1, 12))

    table_data = [
        ["Original Bill", str(credit_data.get("original_bill_reference", "N/A"))],
        ["Reason", str(credit_data.get("reason", ""))],
        ["Credit Amount", f"${credit_data.get('amount', 0):.2f}"],
    ]
    t = Table(table_data, colWidths=[2.5 * inch, 3 * inch])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f9f9f9")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(t)

    elements.append(Spacer(1, 24))
    elements.append(Paragraph(f"HarborView Property Operations Portal — Generated {_timestamp()}", _FOOTER_STYLE))

    return _build_pdf(elements)
