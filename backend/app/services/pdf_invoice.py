from __future__ import annotations

from io import BytesIO
from pathlib import Path
import warnings
from typing import TYPE_CHECKING

from PIL import Image, UnidentifiedImageError
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas

if TYPE_CHECKING:
    from app.models import Invoice


PAGE_WIDTH = 595.0
PAGE_HEIGHT = 842.0
LEFT = 40.0
RIGHT = 555.0
TOP = 802.0
BOTTOM = 55.0
LOGO_WIDTH = 150.0
LOGO_HEIGHT = 70.0
MAX_IMAGE_DIMENSION = 4096
LEGACY_ISSUER_MESSAGE = (
    "Istorijski podaci izdavaoca nisu sa\u010duvani za ovu fakturu."
)
TABLE_COLUMNS = (
    ("#", 20.0, "right"),
    ("Opis", 210.0, "left"),
    ("Kol.", 45.0, "right"),
    ("Cijena", 70.0, "right"),
    ("Popust", 50.0, "right"),
    ("PDV", 45.0, "right"),
    ("Ukupno", 75.0, "right"),
)
TABLE_HEADER_HEIGHT = 20.0
TABLE_TEXT_SIZE = 7.5
TABLE_LINE_HEIGHT = 10.0
FONT_DIRECTORY = Path(__file__).resolve().parents[1] / "assets" / "fonts"
REGULAR_FONT_NAME = "NotoSans"
BOLD_FONT_NAME = "NotoSans-Bold"
REGULAR_FONT_PATH = FONT_DIRECTORY / "NotoSans-Regular.ttf"
BOLD_FONT_PATH = FONT_DIRECTORY / "NotoSans-Bold.ttf"


class UnsupportedPdfGlyphError(ValueError):
    """Raised when invoice text contains a glyph unavailable in the PDF font."""


def _register_fonts() -> None:
    registered = set(pdfmetrics.getRegisteredFontNames())
    if REGULAR_FONT_NAME not in registered:
        pdfmetrics.registerFont(TTFont(REGULAR_FONT_NAME, str(REGULAR_FONT_PATH)))
    if BOLD_FONT_NAME not in registered:
        pdfmetrics.registerFont(TTFont(BOLD_FONT_NAME, str(BOLD_FONT_PATH)))


_register_fonts()


def _as_float(value) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _invoice_text_values(invoice: "Invoice") -> list[str]:
    fields = (
        "invoice_number",
        "buyer_name",
        "buyer_address",
        "note",
        "buyer_tax_id",
        "issuer_business_name",
        "issuer_address",
        "issuer_tax_id",
        "issuer_phone",
        "issuer_email",
        "issuer_bank_name",
        "issuer_bank_account",
        "issuer_iban",
        "issuer_swift_bic",
    )
    values = [
        value
        for field in fields
        if isinstance((value := getattr(invoice, field, None)), str)
    ]
    values.extend(
        description
        for item in list(getattr(invoice, "items", None) or [])
        if isinstance((description := getattr(item, "description", None)), str)
    )
    return values


def _validate_pdf_glyphs(invoice: "Invoice") -> None:
    glyphs = pdfmetrics.getFont(REGULAR_FONT_NAME).face.charToGlyph
    for value in _invoice_text_values(invoice):
        if any(not char.isspace() and ord(char) not in glyphs for char in value):
            raise UnsupportedPdfGlyphError


def _text_width(text: str, size: float, *, bold: bool = False) -> float:
    font_name = BOLD_FONT_NAME if bold else REGULAR_FONT_NAME
    return pdfmetrics.stringWidth(text, font_name, size)


def _split_token(
    token: str, width: float, size: float, *, bold: bool = False
) -> list[str]:
    parts: list[str] = []
    current = ""
    for char in token:
        candidate = current + char
        if current and _text_width(candidate, size, bold=bold) > width:
            parts.append(current)
            current = char
        else:
            current = candidate
    if current:
        parts.append(current)
    return parts or [""]


def _wrap(
    value: object, width: float, size: float, *, bold: bool = False
) -> list[str]:
    source = _text(value)
    if not source:
        return []
    lines: list[str] = []
    current = ""
    for raw_token in source.split():
        tokens = (
            _split_token(raw_token, width, size, bold=bold)
            if _text_width(raw_token, size, bold=bold) > width
            else [raw_token]
        )
        for token in tokens:
            candidate = token if not current else f"{current} {token}"
            if current and _text_width(candidate, size, bold=bold) > width:
                lines.append(current)
                current = token
            else:
                current = candidate
    if current:
        lines.append(current)
    return lines


def _wrap_preserving_newlines(
    value: object, width: float, size: float, *, bold: bool = False
) -> list[str]:
    source = _text(value)
    if not source:
        return []
    lines: list[str] = []
    for paragraph in source.splitlines():
        if paragraph.strip():
            lines.extend(_wrap(paragraph, width, size, bold=bold))
        else:
            lines.append("")
    return lines


def _number(value: object) -> str:
    return f"{_as_float(value):.2f}"


def _vat(value: object) -> str:
    rate = _as_float(value)
    if abs(rate) <= 1:
        rate *= 100
    return f"{rate:.2f}%"


def _normalize_logo(logo_bytes: bytes | None) -> tuple[bytes, int, int] | None:
    if not logo_bytes:
        return None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(logo_bytes)) as source:
                if source.format not in {"PNG", "JPEG", "WEBP"}:
                    return None
                width, height = source.size
                if (
                    width <= 0
                    or height <= 0
                    or width > MAX_IMAGE_DIMENSION
                    or height > MAX_IMAGE_DIMENSION
                ):
                    return None
                source.load()
                rgba = source.convert("RGBA")
                flattened = Image.new("RGB", rgba.size, "white")
                flattened.paste(rgba, mask=rgba.getchannel("A"))
                output = BytesIO()
                flattened.save(output, format="JPEG", quality=90, optimize=True)
                return output.getvalue(), width, height
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        UnidentifiedImageError,
        OSError,
        ValueError,
    ):
        return None


class _Page:
    def __init__(self) -> None:
        self.commands: list[tuple] = []

    def text(
        self,
        x: float,
        y: float,
        value: object,
        *,
        size: float = 9,
        bold: bool = False,
        align: str = "left",
    ) -> None:
        value = _text(value)
        if not value:
            return
        if align == "right":
            x -= _text_width(value, size, bold=bold)
        self.commands.append(("text", x, y, value, size, bold))

    def line(
        self, x1: float, y1: float, x2: float, y2: float, width: float = 0.5
    ) -> None:
        self.commands.append(("line", x1, y1, x2, y2, width))

    def fill_rect(
        self, x: float, y: float, width: float, height: float, gray: float
    ) -> None:
        self.commands.append(("fill_rect", x, y, width, height, gray))

    def image(self, x: float, y: float, width: float, height: float) -> None:
        self.commands.append(("image", x, y, width, height))


def _draw_wrapped(
    page: _Page,
    x: float,
    y: float,
    value: object,
    width: float,
    *,
    size: float = 9,
    bold: bool = False,
    line_height: float = 11,
) -> float:
    for line in _wrap(value, width, size, bold=bold):
        page.text(x, y, line, size=size, bold=bold)
        y -= line_height
    return y


def _table_header(page: _Page, y: float) -> float:
    page.fill_rect(LEFT, y - TABLE_HEADER_HEIGHT, RIGHT - LEFT, TABLE_HEADER_HEIGHT, 0.85)
    page.line(LEFT, y, RIGHT, y)
    page.line(LEFT, y - TABLE_HEADER_HEIGHT, RIGHT, y - TABLE_HEADER_HEIGHT)
    x = LEFT
    for label, width, align in TABLE_COLUMNS:
        page.text(
            x + 4 if align == "left" else x + width - 4,
            y - 13,
            label,
            size=TABLE_TEXT_SIZE,
            bold=True,
            align=align,
        )
        x += width
    return y - TABLE_HEADER_HEIGHT


def _continuation_header(page: _Page, invoice: "Invoice") -> float:
    page.text(LEFT, TOP, f"Faktura br: {invoice.invoice_number}", size=11, bold=True)
    page.text(RIGHT, TOP, "nastavak", size=8, align="right")
    page.line(LEFT, TOP - 8, RIGHT, TOP - 8, 0.8)
    return TOP - 24


def _row_values(item: object, index: int) -> list[str]:
    return [
        str(index),
        _text(getattr(item, "description", "")),
        _number(getattr(item, "quantity", 0)),
        _number(getattr(item, "unit_price", 0)),
        f"{_number(getattr(item, 'discount_percent', 0))}%",
        _vat(getattr(item, "vat_rate", 0)),
        _number(getattr(item, "total_amount", 0)),
    ]


def _row_lines(values: list[str]) -> list[list[str]]:
    return [
        _wrap(value, column[1] - 8, TABLE_TEXT_SIZE) or [""]
        for value, column in zip(values, TABLE_COLUMNS)
    ]


def _row_height(values: list[str]) -> float:
    return max(
        18.0,
        max(len(lines) for lines in _row_lines(values)) * TABLE_LINE_HEIGHT + 6,
    )


def _table_row(page: _Page, y: float, values: list[str]) -> float:
    height = _row_height(values)
    x = LEFT
    for lines, (_, width, align) in zip(_row_lines(values), TABLE_COLUMNS):
        line_y = y - 12
        for line in lines:
            page.text(
                x + 4 if align == "left" else x + width - 4,
                line_y,
                line,
                size=TABLE_TEXT_SIZE,
                align=align,
            )
            line_y -= TABLE_LINE_HEIGHT
        x += width
    page.line(LEFT, y - height, RIGHT, y - height, 0.35)
    return y - height


def render_invoice_pdf(invoice: "Invoice", logo_bytes: bytes | None = None) -> bytes:
    _validate_pdf_glyphs(invoice)
    logo = _normalize_logo(logo_bytes)
    pages = [_Page()]
    page = pages[0]

    if logo is not None:
        _, image_width, image_height = logo
        scale = min(LOGO_WIDTH / image_width, LOGO_HEIGHT / image_height, 1.0)
        draw_width = image_width * scale
        draw_height = image_height * scale
        page.image(
            LEFT + (LOGO_WIDTH - draw_width) / 2,
            TOP - LOGO_HEIGHT + (LOGO_HEIGHT - draw_height) / 2,
            draw_width,
            draw_height,
        )

    issuer_fields = [
        _text(getattr(invoice, "issuer_business_name", None)),
        _text(getattr(invoice, "issuer_address", None)),
    ]
    tax_id = _text(getattr(invoice, "issuer_tax_id", None))
    phone = _text(getattr(invoice, "issuer_phone", None))
    email = _text(getattr(invoice, "issuer_email", None))
    issuer_fields.extend(
        value
        for value in (
            f"JIB / PIB: {tax_id}" if tax_id else "",
            f"Telefon: {phone}" if phone else "",
            f"Email: {email}" if email else "",
        )
        if value
    )
    issuer_fields = [value for value in issuer_fields if value]
    issuer_y = TOP
    if issuer_fields:
        for index, value in enumerate(issuer_fields):
            issuer_y = _draw_wrapped(
                page,
                350,
                issuer_y,
                value,
                RIGHT - 350,
                size=10 if index == 0 else 8,
                bold=index == 0,
                line_height=11,
            )
    else:
        _draw_wrapped(
            page, 350, issuer_y, LEGACY_ISSUER_MESSAGE, RIGHT - 350, size=8
        )

    header_bottom = min(TOP - LOGO_HEIGHT - 12, issuer_y - 8)
    page.line(LEFT, header_bottom, RIGHT, header_bottom, 0.8)
    y = header_bottom - 18
    page.text(LEFT, y, "Kupac", size=8, bold=True)
    y -= 14
    y = _draw_wrapped(
        page, LEFT, y, getattr(invoice, "buyer_name", ""), 245, size=10, bold=True
    )
    if _text(getattr(invoice, "buyer_address", None)):
        y = _draw_wrapped(
            page, LEFT, y, getattr(invoice, "buyer_address"), 245, size=8
        )
    buyer_tax_id = _text(getattr(invoice, "buyer_tax_id", None))
    if getattr(invoice, "buyer_type", "UNSPECIFIED") == "BUSINESS" and buyer_tax_id:
        y = _draw_wrapped(
            page, LEFT, y, f"JIB/PIB: {buyer_tax_id}", 245, size=8
        )

    meta_y = header_bottom - 18
    page.text(350, meta_y, f"Faktura br: {invoice.invoice_number}", size=12, bold=True)
    page.text(350, meta_y - 18, f"Datum fakture: {invoice.issue_date}", size=8)
    if getattr(invoice, "due_date", None):
        page.text(350, meta_y - 31, f"Rok placanja: {invoice.due_date}", size=8)

    y = _table_header(page, min(y, meta_y - 42) - 16)
    items = list(getattr(invoice, "items", None) or [])
    if items:
        for index, item in enumerate(items, start=1):
            values = _row_values(item, index)
            if y - _row_height(values) < BOTTOM + 20:
                page = _Page()
                pages.append(page)
                y = _table_header(page, _continuation_header(page, invoice))
            y = _table_row(page, y, values)
    else:
        page.text(LEFT + 4, y - 13, "Nema evidentiranih stavki", size=8)
        y -= 20
        page.line(LEFT, y, RIGHT, y, 0.35)

    bank_values = []
    for label, field in (
        ("Banka", "issuer_bank_name"),
        ("Racun", "issuer_bank_account"),
        ("IBAN", "issuer_iban"),
        ("SWIFT/BIC", "issuer_swift_bic"),
    ):
        value = _text(getattr(invoice, field, None))
        if value:
            bank_values.append(f"{label}: {value}")
    bank_height = (
        sum(max(1, len(_wrap(value, 300, 8))) * 11 for value in bank_values) + 14
        if bank_values
        else 0
    )
    if y - (78 + bank_height) < BOTTOM:
        page = _Page()
        pages.append(page)
        y = _continuation_header(page, invoice)

    y -= 18
    page.line(350, y + 8, RIGHT, y + 8, 0.8)
    page.text(
        RIGHT,
        y,
        f"Osnovica: {_number(getattr(invoice, 'total_base', 0))} KM",
        size=9,
        align="right",
    )
    page.text(
        RIGHT,
        y - 14,
        f"Ukupan PDV: {_number(getattr(invoice, 'total_vat', 0))} KM",
        size=9,
        align="right",
    )
    page.text(
        RIGHT,
        y - 31,
        f"Ukupno: {_number(getattr(invoice, 'total_amount', 0))} KM",
        size=11,
        bold=True,
        align="right",
    )
    y -= 58

    if bank_values:
        page.text(LEFT, y, "Instrukcije za uplatu", size=9, bold=True)
        y -= 14
        for value in bank_values:
            y = _draw_wrapped(page, LEFT, y, value, 300, size=8)

    note_lines = _wrap_preserving_newlines(
        getattr(invoice, "note", None), RIGHT - LEFT, 8
    )
    if note_lines:
        y -= 12
        if y - 25 < BOTTOM:
            page = _Page()
            pages.append(page)
            y = _continuation_header(page, invoice)
        page.text(LEFT, y, "Napomena", size=9, bold=True)
        y -= 14
        for line in note_lines:
            if y < BOTTOM:
                page = _Page()
                pages.append(page)
                y = _continuation_header(page, invoice)
            if line:
                page.text(LEFT, y, line, size=8)
            y -= 11

    for number, current_page in enumerate(pages, start=1):
        current_page.text(
            RIGHT,
            25,
            f"Strana {number} / {len(pages)}",
            size=7,
            align="right",
        )

    output = BytesIO()
    document = Canvas(
        output,
        pagesize=(PAGE_WIDTH, PAGE_HEIGHT),
        pageCompression=0,
        pdfVersion=(1, 4),
    )
    image = ImageReader(BytesIO(logo[0])) if logo is not None else None

    for current_page in pages:
        for command in current_page.commands:
            kind, *arguments = command
            if kind == "text":
                x, y, value, size, bold = arguments
                font_name = BOLD_FONT_NAME if bold else REGULAR_FONT_NAME
                document.setFont(font_name, size)
                document.drawString(x, y, value)
            elif kind == "line":
                x1, y1, x2, y2, width = arguments
                document.setLineWidth(width)
                document.line(x1, y1, x2, y2)
            elif kind == "fill_rect":
                x, y, width, height, gray = arguments
                document.saveState()
                document.setFillGray(gray)
                document.rect(x, y, width, height, stroke=0, fill=1)
                document.restoreState()
            elif kind == "image" and image is not None:
                x, y, width, height = arguments
                document.drawImage(
                    image,
                    x,
                    y,
                    width=width,
                    height=height,
                    preserveAspectRatio=True,
                    mask="auto",
                )
            else:
                raise ValueError(f"Unknown PDF drawing command: {kind}")
        document.showPage()

    document.save()
    return output.getvalue()
