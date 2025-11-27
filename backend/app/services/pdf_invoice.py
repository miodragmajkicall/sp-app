from __future__ import annotations

from decimal import Decimal
from io import BytesIO
from typing import Optional

from app.models import Invoice, InvoiceItem, Tenant


def _safe_decimal(value: Decimal | float | int | None) -> float:
    """
    Pomoćna funkcija – sigurno pretvara Decimal u float za PDF engine.
    Ako je None, vraća 0.0.
    """
    if value is None:
        return 0.0
    return float(value)


def render_invoice_pdf(invoice: Invoice, tenant: Optional[Tenant] = None) -> bytes:
    """
    Generiše jednostavan PDF za jednu fakturu.

    Implementacija namjerno koristi lazy import `reportlab` biblioteke da bi
    izbjegla probleme pri startu API-ja ako biblioteka nije instalirana.

    Ako `reportlab` nije instaliran, baca RuntimeError – rutu koja poziva ovu
    funkciju treba da to konvertuje u HTTP 500 sa jasnom porukom.
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
    except ImportError as exc:  # pragma: no cover - zavisi od sistema
        raise RuntimeError(
            "PDF engine 'reportlab' is not installed in the environment."
        ) from exc

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Margine
    left_margin = 40
    right_margin = width - 40
    top = height - 40
    line_height = 14

    # ===============================
    #  HEADER – TENANT + INVOICE INFO
    # ===============================
    c.setFont("Helvetica-Bold", 16)
    tenant_title = "Faktura"
    c.drawString(left_margin, top, tenant_title)

    y = top - 2 * line_height

    c.setFont("Helvetica", 10)
    if tenant is not None:
        tenant_name = tenant.name or tenant.code
        c.drawString(left_margin, y, f"Izdavalac: {tenant_name}")
        y -= line_height
        c.drawString(left_margin, y, f"Tenant code: {tenant.code}")
        y -= line_height
    else:
        c.drawString(left_margin, y, f"Tenant code: {invoice.tenant_code}")
        y -= line_height

    invoice_number = invoice.invoice_number or f"#{invoice.id}"
    c.drawString(left_margin, y, f"Broj fakture: {invoice_number}")
    y -= line_height
    c.drawString(left_margin, y, f"Datum izdavanja: {invoice.issue_date}")
    y -= line_height
    if invoice.due_date:
        c.drawString(left_margin, y, f"Rok plaćanja: {invoice.due_date}")
        y -= line_height

    # Kupac
    y -= line_height
    c.setFont("Helvetica-Bold", 11)
    c.drawString(left_margin, y, "Kupac:")
    y -= line_height
    c.setFont("Helvetica", 10)
    c.drawString(left_margin, y, invoice.buyer_name or "")
    y -= line_height
    if invoice.buyer_address:
        c.drawString(left_margin, y, invoice.buyer_address)
        y -= line_height

    # ===============================
    #  TABLICA STAVKI
    # ===============================
    y -= 2 * line_height
    c.setFont("Helvetica-Bold", 10)
    c.drawString(left_margin, y, "Opis")
    c.drawString(left_margin + 250, y, "Količina")
    c.drawString(left_margin + 320, y, "Cijena")
    c.drawString(left_margin + 390, y, "PDV")
    c.drawString(left_margin + 450, y, "Ukupno")
    y -= line_height
    c.line(left_margin, y, right_margin, y)
    y -= line_height

    c.setFont("Helvetica", 9)

    items: list[InvoiceItem] = list(invoice.items or [])
    for item in items:
        if y < 80:  # nova stranica ako ponestane prostora
            c.showPage()
            y = height - 80
            c.setFont("Helvetica", 9)

        desc = (item.description or "").strip()
        if len(desc) > 40:
            desc = desc[:37] + "..."

        c.drawString(left_margin, y, desc)

        c.drawRightString(
            left_margin + 300,
            y,
            f"{_safe_decimal(item.quantity):.2f}",
        )
        c.drawRightString(
            left_margin + 370,
            y,
            f"{_safe_decimal(item.unit_price):.2f}",
        )
        c.drawRightString(
            left_margin + 430,
            y,
            f"{_safe_decimal(item.vat_amount):.2f}",
        )
        c.drawRightString(
            right_margin,
            y,
            f"{_safe_decimal(item.total_amount):.2f}",
        )
        y -= line_height

    # ===============================
    #  SAŽETAK
    # ===============================
    y -= 2 * line_height
    c.setFont("Helvetica-Bold", 10)
    c.drawRightString(
        left_margin + 370,
        y,
        "Osnovica:",
    )
    c.drawRightString(
        right_margin,
        y,
        f"{_safe_decimal(invoice.total_base):.2f}",
    )
    y -= line_height

    c.drawRightString(
        left_margin + 370,
        y,
        "Ukupan PDV:",
    )
    c.drawRightString(
        right_margin,
        y,
        f"{_safe_decimal(invoice.total_vat):.2f}",
    )
    y -= line_height

    c.drawRightString(
        left_margin + 370,
        y,
        "Ukupno za plaćanje:",
    )
    c.drawRightString(
        right_margin,
        y,
        f"{_safe_decimal(invoice.total_amount):.2f}",
    )
    y -= 2 * line_height

    c.setFont("Helvetica-Oblique", 8)
    c.drawString(
        left_margin,
        y,
        "Napomena: ovaj PDF je generisan iz sp-app sistema (DUMMY layout za razvoj).",
    )

    # Završi PDF
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.getvalue()
