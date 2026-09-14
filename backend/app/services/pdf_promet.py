from __future__ import annotations

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
    KeepTogether,
    LongTable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.schemas.promet import PrometRow
from app.services import pdf_invoice


def _amount(value: Decimal) -> str:
    return f"{Decimal(str(value)):.2f}"


def render_promet_pdf(
    *,
    tenant_code: str,
    rows: Iterable[PrometRow],
    filter_label: str,
) -> bytes:
    """Renderuje informativni canonical izvještaj Knjige prometa."""

    pdf_invoice._register_fonts()
    regular = pdf_invoice.REGULAR_FONT_NAME
    bold = pdf_invoice.BOLD_FONT_NAME
    glyphs = pdfmetrics.getFont(regular).face.charToGlyph

    def paragraph(value: object, style: ParagraphStyle) -> Paragraph:
        text = "" if value is None else str(value)

        for char in text:
            if not char.isspace() and ord(char) not in glyphs:
                raise pdf_invoice.UnsupportedPdfGlyphError(
                    f"Promet PDF font ne podržava U+{ord(char):04X}."
                )

        safe = escape(
            text.replace("\r\n", "\n").replace("\r", "\n")
        )
        return Paragraph(
            safe.replace("\n", "<br/>"),
            style,
        )

    body = ParagraphStyle(
        "PrometBody",
        fontName=regular,
        fontSize=7.5,
        leading=9.5,
        alignment=TA_LEFT,
        splitLongWords=1,
    )
    heading = ParagraphStyle(
        "PrometHeading",
        parent=body,
        fontName=bold,
        alignment=TA_CENTER,
    )
    right = ParagraphStyle(
        "PrometRight",
        parent=body,
        alignment=TA_RIGHT,
    )
    meta = ParagraphStyle(
        "PrometMeta",
        parent=body,
        fontSize=9,
        leading=12,
    )
    summary_style = ParagraphStyle(
        "PrometSummary",
        parent=meta,
        fontName=bold,
    )

    page_width, page_height = landscape(A4)
    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=(page_width, page_height),
        leftMargin=32,
        rightMargin=32,
        topMargin=65,
        bottomMargin=36,
        title="Knjiga prometa",
    )

    def page_decoration(canvas, document):
        canvas.saveState()

        canvas.setFont(bold, 12)
        canvas.drawString(
            32,
            page_height - 25,
            "Knjiga prometa",
        )

        canvas.setFont(regular, 8)
        canvas.drawString(
            32,
            page_height - 39,
            f"Filteri: {filter_label}",
        )

        canvas.setStrokeColor(colors.HexColor("#D1D5DB"))
        canvas.line(
            32,
            page_height - 46,
            page_width - 32,
            page_height - 46,
        )

        canvas.setFont(regular, 7.5)
        canvas.drawString(
            32,
            20,
            "Informativni izvještaj - nije službeni obrazac",
        )
        canvas.drawRightString(
            page_width - 32,
            20,
            f"Stranica {document.page}",
        )

        canvas.restoreState()

    rows_list = list(rows)

    total_amount = sum(
        (Decimal(str(row.amount)) for row in rows_list),
        Decimal("0.00"),
    )

    story = [
        paragraph(f"Tenant: {tenant_code}", meta),
        paragraph(f"Filteri: {filter_label}", meta),
        Spacer(1, 8),
    ]

    headers = [
        "#",
        "Datum",
        "Broj dokumenta",
        "Partner",
        "Iznos (BAM)",
        "Napomena",
    ]

    data = [
        [paragraph(label, heading) for label in headers]
    ]

    for number, row in enumerate(rows_list, 1):
        values = [
            number,
            row.date.isoformat(),
            row.document_number or "",
            row.partner_name or "",
            _amount(row.amount),
            row.note or "",
        ]

        data.append(
            [
                paragraph(
                    value,
                    right if index in (0, 4) else body,
                )
                for index, value in enumerate(values)
            ]
        )

    if not rows_list:
        data.append(
            [
                paragraph(
                    "Nema evidentiranih stavki za odabrani period.",
                    body,
                ),
                "",
                "",
                "",
                "",
                "",
            ]
        )

    table_style = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        (
            "BACKGROUND",
            (0, 0),
            (-1, 0),
            colors.HexColor("#E5E7EB"),
        ),
        (
            "LINEBELOW",
            (0, 0),
            (-1, 0),
            0.6,
            colors.HexColor("#9CA3AF"),
        ),
        (
            "LINEBELOW",
            (0, 1),
            (-1, -1),
            0.3,
            colors.HexColor("#E5E7EB"),
        ),
    ]

    if not rows_list:
        table_style.append(
            ("SPAN", (0, 1), (-1, 1))
        )

    table = LongTable(
        data,
        colWidths=[24, 60, 110, 180, 75, 320],
        repeatRows=1,
        splitByRow=1,
        splitInRow=1,
        hAlign="LEFT",
    )
    table.setStyle(TableStyle(table_style))

    story.extend(
        [
            table,
            Spacer(1, 12),
        ]
    )

    summary = Table(
        [
            [
                paragraph("Ukupan promet", summary_style),
                paragraph(
                    f"{_amount(total_amount)} BAM",
                    right,
                ),
            ]
        ],
        colWidths=[180, 100],
        hAlign="RIGHT",
    )
    summary.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                (
                    "LINEABOVE",
                    (0, 0),
                    (-1, 0),
                    0.6,
                    colors.HexColor("#9CA3AF"),
                ),
            ]
        )
    )

    story.append(
        KeepTogether(
            [
                summary,
                Spacer(1, 5),
                paragraph(
                    "Ukupan promet je zbir prikazanih stavki.",
                    meta,
                ),
            ]
        )
    )

    doc.build(
        story,
        onFirstPage=page_decoration,
        onLaterPages=page_decoration,
    )

    return buffer.getvalue()
