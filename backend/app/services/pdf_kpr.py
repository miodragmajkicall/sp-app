from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from io import BytesIO
from typing import Iterable
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.platypus import (
    KeepTogether, LongTable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from . import pdf_invoice
from app.schemas.kpr import KprRowItem


@dataclass
class KprPeriod:
    year: int
    month: int | None = None


def _amount(value: Decimal) -> str:
    return f"{Decimal(str(value)):.2f}"


def _tax_label(row: KprRowItem) -> str:
    if row.kind == "income":
        return "—"
    labels = {
        "deductible": "Odbitno",
        "nondeductible": "Neodbitno",
        "unresolved": "Nerazriješeno",
    }
    if row.tax_treatment is not None:
        return labels.get(row.tax_treatment, str(row.tax_treatment))
    if row.tax_deductible is True:
        return "Odbitno"
    if row.tax_deductible is False:
        return "Neodbitno"
    return "Nema tretmana"


def render_kpr_pdf(
    tenant_code: str,
    period: KprPeriod,
    rows: Iterable[KprRowItem],
) -> bytes:
    """Informativni, višestranični KPR izvještaj; bez promjene evidencije."""
    pdf_invoice._register_fonts()
    regular = pdf_invoice.REGULAR_FONT_NAME
    bold = pdf_invoice.BOLD_FONT_NAME
    glyphs = pdfmetrics.getFont(regular).face.charToGlyph

    def paragraph(value: object, style: ParagraphStyle) -> Paragraph:
        text = "" if value is None else str(value)
        for char in text:
            if not char.isspace() and ord(char) not in glyphs:
                raise pdf_invoice.UnsupportedPdfGlyphError(
                    f"KPR PDF font ne podržava U+{ord(char):04X}."
                )
        safe = escape(text.replace("\r\n", "\n").replace("\r", "\n"))
        return Paragraph(safe.replace("\n", "<br/>"), style)

    body = ParagraphStyle(
        "KprBody", fontName=regular, fontSize=7.2, leading=9.4,
        alignment=TA_LEFT, splitLongWords=1,
    )
    heading = ParagraphStyle(
        "KprHeading", parent=body, fontName=bold, fontSize=7.2,
        leading=9.4, alignment=TA_CENTER,
    )
    right = ParagraphStyle("KprRight", parent=body, alignment=TA_RIGHT)
    meta = ParagraphStyle("KprMeta", parent=body, fontSize=9, leading=12)
    summary_style = ParagraphStyle("KprSummary", parent=meta, fontName=bold)

    page_width, page_height = landscape(A4)
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=(page_width, page_height),
        leftMargin=32, rightMargin=32, topMargin=65, bottomMargin=36,
        title="Knjiga prihoda i rashoda (KPR)",
    )
    period_label = (
        f"{period.year:04d}-{period.month:02d}"
        if period.month is not None else f"{period.year:04d} (cijela godina)"
    )

    def page_decoration(canvas, document):
        canvas.saveState()
        canvas.setFont(bold, 12)
        canvas.drawString(32, page_height - 25, "Knjiga prihoda i rashoda")
        canvas.setFont(regular, 8)
        canvas.drawString(32, page_height - 39, f"Period: {period_label}")
        canvas.setStrokeColor(colors.HexColor("#D1D5DB"))
        canvas.line(32, page_height - 46, page_width - 32, page_height - 46)
        canvas.setFont(regular, 7.5)
        canvas.drawString(32, 20, "Informativni izvještaj - nije službeni obrazac")
        canvas.drawRightString(page_width - 32, 20, f"Stranica {document.page}")
        canvas.restoreState()

    rows_list = list(rows)
    income = sum((Decimal(str(r.amount)) for r in rows_list if r.kind == "income"), Decimal("0.00"))
    expense = sum((Decimal(str(r.amount)) for r in rows_list if r.kind == "expense"), Decimal("0.00"))

    story = [
        paragraph(f"Tenant: {tenant_code}", meta),
        paragraph(f"Period: {period_label}", meta),
        Spacer(1, 8),
    ]
    headers = [
        "#", "Datum", "Vrsta", "Kategorija", "Kupac / dobavljač",
        "Dokument", "Opis", "Iznos (BAM)", "Poreski tretman", "Izvor / ID",
    ]
    data = [[paragraph(label, heading) for label in headers]]
    for number, row in enumerate(rows_list, 1):
        values = [
            number, row.entry_date.isoformat(),
            "Prihod" if row.kind == "income" else "Rashod",
            row.category, row.counterparty, row.document_number,
            row.description, _amount(row.amount), _tax_label(row),
            f"{row.source} / {row.source_id}",
        ]
        data.append([
            paragraph(value, right if index in (0, 7) else body)
            for index, value in enumerate(values)
        ])
    if not rows_list:
        data.append([paragraph("Nema evidentiranih stavki za odabrani period.", body)] + [""] * 9)

    table_style = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E5E7EB")),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.HexColor("#9CA3AF")),
        ("LINEBELOW", (0, 1), (-1, -1), 0.3, colors.HexColor("#E5E7EB")),
    ]
    if not rows_list:
        table_style.append(("SPAN", (0, 1), (-1, 1)))
    table = LongTable(
        data,
        colWidths=[24, 55, 43, 53, 95, 72, 158, 64, 83, 118],
        repeatRows=1, splitByRow=1, splitInRow=1, hAlign="LEFT",
    )
    table.setStyle(TableStyle(table_style))
    story.extend([table, Spacer(1, 12)])

    totals = [
        ("Ukupni prihodi", income),
        ("Ukupni rashodi", expense),
        ("Neto rezultat", income - expense),
    ]
    summary = Table(
        [[paragraph(label, summary_style), paragraph(_amount(amount) + " BAM", right)]
         for label, amount in totals],
        colWidths=[180, 100], hAlign="RIGHT",
    )
    summary.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEABOVE", (0, 0), (-1, 0), 0.6, colors.HexColor("#9CA3AF")),
    ]))
    story.append(KeepTogether([
        summary, Spacer(1, 5),
        paragraph("Neto rezultat je informativan i nije poreska osnovica.", meta),
    ]))
    doc.build(story, onFirstPage=page_decoration, onLaterPages=page_decoration)
    return buffer.getvalue()
