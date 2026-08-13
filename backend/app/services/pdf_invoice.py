from __future__ import annotations

from io import BytesIO
import warnings
from typing import TYPE_CHECKING

from PIL import Image, UnidentifiedImageError

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


def _as_float(value) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _escape_pdf_text(text: str) -> str:
    text = text.translate(
        str.maketrans(
            {
                "\u010d": "c",
                "\u0107": "c",
                "\u0161": "s",
                "\u0111": "d",
                "\u017e": "z",
                "\u010c": "C",
                "\u0106": "C",
                "\u0160": "S",
                "\u0110": "D",
                "\u017d": "Z",
            }
        )
    )
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

def _text_width(text: str, size: float) -> float:
    return sum(0.28 if char in " ilI.,:;'" else 0.56 for char in text) * size


def _split_token(token: str, width: float, size: float) -> list[str]:
    parts: list[str] = []
    current = ""
    for char in token:
        candidate = current + char
        if current and _text_width(candidate, size) > width:
            parts.append(current)
            current = char
        else:
            current = candidate
    if current:
        parts.append(current)
    return parts or [""]


def _wrap(value: object, width: float, size: float) -> list[str]:
    source = _text(value)
    if not source:
        return []
    lines: list[str] = []
    current = ""
    for raw_token in source.split():
        tokens = (
            _split_token(raw_token, width, size)
            if _text_width(raw_token, size) > width
            else [raw_token]
        )
        for token in tokens:
            candidate = token if not current else f"{current} {token}"
            if current and _text_width(candidate, size) > width:
                lines.append(current)
                current = token
            else:
                current = candidate
    if current:
        lines.append(current)
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
        self.commands: list[str] = []

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
            x -= _text_width(value, size)
        font = "F2" if bold else "F1"
        escaped = _escape_pdf_text(value)
        self.commands.append(
            f"BT /{font} {size:.2f} Tf 1 0 0 1 {x:.2f} {y:.2f} Tm ({escaped}) Tj ET"
        )

    def line(
        self, x1: float, y1: float, x2: float, y2: float, width: float = 0.5
    ) -> None:
        self.commands.append(
            f"{width:.2f} w {x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S"
        )

    def fill_rect(
        self, x: float, y: float, width: float, height: float, gray: float
    ) -> None:
        self.commands.append(
            f"{gray:.2f} g {x:.2f} {y:.2f} {width:.2f} {height:.2f} re f 0 g"
        )

    def image(self, x: float, y: float, width: float, height: float) -> None:
        self.commands.append(
            f"q {width:.2f} 0 0 {height:.2f} {x:.2f} {y:.2f} cm /Im1 Do Q"
        )


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
    for line in _wrap(value, width, size):
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


class _PdfBuilder:
    def __init__(self) -> None:
        self.objects: list[bytes | None] = []

    def reserve(self) -> int:
        self.objects.append(None)
        return len(self.objects)

    def set(self, number: int, body: bytes | str) -> None:
        self.objects[number - 1] = (
            body.encode("latin-1") if isinstance(body, str) else body
        )

    def add(self, body: bytes | str) -> int:
        number = self.reserve()
        self.set(number, body)
        return number

    def build(self, root: int) -> bytes:
        buffer = BytesIO()
        buffer.write("%PDF-1.4\n%\xE2\xE3\xCF\xD3\n".encode("latin-1"))
        offsets = [0]
        for index, body in enumerate(self.objects, start=1):
            if body is None:
                raise ValueError(f"PDF object {index} is not initialized")
            offsets.append(buffer.tell())
            buffer.write(f"{index} 0 obj\n".encode("ascii"))
            buffer.write(body)
            buffer.write(b"\nendobj\n")
        xref = buffer.tell()
        buffer.write(f"xref\n0 {len(self.objects) + 1}\n".encode("ascii"))
        buffer.write(b"0000000000 65535 f \n")
        for offset in offsets[1:]:
            buffer.write(f"{offset:010d} 00000 n \n".encode("ascii"))
        buffer.write(
            (
                "trailer\n"
                f"<< /Size {len(self.objects) + 1} /Root {root} 0 R >>\n"
                "startxref\n"
                f"{xref}\n"
                "%%EOF\n"
            ).encode("ascii")
        )
        return buffer.getvalue()


def render_invoice_pdf(invoice: "Invoice", logo_bytes: bytes | None = None) -> bytes:
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

    for number, current_page in enumerate(pages, start=1):
        current_page.text(
            RIGHT,
            25,
            f"Strana {number} / {len(pages)}",
            size=7,
            align="right",
        )

    builder = _PdfBuilder()
    catalog = builder.reserve()
    pages_object = builder.reserve()
    regular_font = builder.add(
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
        "/Encoding /WinAnsiEncoding >>"
    )
    bold_font = builder.add(
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold "
        "/Encoding /WinAnsiEncoding >>"
    )
    image_object = None
    if logo is not None:
        jpeg_bytes, image_width, image_height = logo
        image_object = builder.add(
            (
                f"<< /Type /XObject /Subtype /Image /Width {image_width} "
                f"/Height {image_height} /ColorSpace /DeviceRGB "
                f"/BitsPerComponent 8 /Filter /DCTDecode "
                f"/Length {len(jpeg_bytes)} >>\nstream\n"
            ).encode("ascii")
            + jpeg_bytes
            + b"\nendstream"
        )

    page_objects = []
    for current_page in pages:
        stream = ("\n".join(current_page.commands) + "\n").encode("latin-1")
        content_object = builder.add(
            f"<< /Length {len(stream)} >>\nstream\n".encode("ascii")
            + stream
            + b"endstream"
        )
        resources = (
            f"/Font << /F1 {regular_font} 0 R /F2 {bold_font} 0 R >>"
        )
        if image_object is not None:
            resources += f" /XObject << /Im1 {image_object} 0 R >>"
        page_objects.append(
            builder.add(
                "<< /Type /Page "
                f"/Parent {pages_object} 0 R "
                f"/MediaBox [0 0 {PAGE_WIDTH:.0f} {PAGE_HEIGHT:.0f}] "
                f"/Contents {content_object} 0 R "
                f"/Resources << {resources} >> >>"
            )
        )

    kids = " ".join(f"{number} 0 R" for number in page_objects)
    builder.set(
        pages_object,
        f"<< /Type /Pages /Kids [{kids}] /Count {len(page_objects)} >>",
    )
    builder.set(catalog, f"<< /Type /Catalog /Pages {pages_object} 0 R >>")
    return builder.build(catalog)
