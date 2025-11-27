from __future__ import annotations

from io import BytesIO
from typing import List

from app.models import Invoice, InvoiceItem


def _escape_pdf_text(text: str | None) -> str:
    """
    Escapuje specijalne karaktere za PDF string literale.
    """
    if text is None:
        return ""
    return (
        text.replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
    )


def render_invoice_pdf(invoice: Invoice) -> bytes:
    """
    Generiše jednostavan, ali validan PDF za prikaz fakture.

    Namjerno nema eksternih zavisnosti (npr. reportlab), već ručno sklapa
    minimalan PDF sa jednim page-om i tekstom koji opisuje fakturu.
    """

    buffer = BytesIO()

    # PDF header
    buffer.write(b"%PDF-1.4\n")
    buffer.write(b"%\xe2\xe3\xcf\xd3\n")  # binary marker

    # Pomoćne strukture za praćenje offseta objekata
    offsets: List[int] = [0]  # index 0 je dummy, objekti idu od 1

    def write_obj(obj_num: int, content: str) -> None:
        offsets.append(buffer.tell())
        buffer.write(f"{obj_num} 0 obj\n".encode("ascii"))
        buffer.write(content.encode("ascii"))
        buffer.write(b"\nendobj\n")

    def write_obj_bytes(obj_num: int, data: bytes) -> None:
        offsets.append(buffer.tell())
        buffer.write(f"{obj_num} 0 obj\n".encode("ascii"))
        buffer.write(data)
        buffer.write(b"\nendobj\n")

    # 1) Catalog
    write_obj(1, "<< /Type /Catalog /Pages 2 0 R >>")

    # 2) Pages
    write_obj(2, "<< /Type /Pages /Kids [3 0 R] /Count 1 >>")

    # 3) Page
    write_obj(
        3,
        (
            "<< /Type /Page "
            "/Parent 2 0 R "
            "/MediaBox [0 0 595 842] "
            "/Contents 4 0 R "
            "/Resources << /Font << /F1 5 0 R >> >> >>"
        ),
    )

    # 4) Contents (tekstualni sadržaj stranice)
    lines: list[str] = []
    lines.append("BT")
    lines.append("/F1 11 Tf")

    y = 800

    def add_line(text: str) -> None:
        nonlocal y
        lines.append(f"50 {y} Td")
        lines.append(f"({_escape_pdf_text(text)}) Tj")
        y -= 14

    # Header fakture
    add_line(f"Faktura br: {invoice.invoice_number}")
    add_line(f"Tenant: {invoice.tenant_code}")
    add_line(f"Izdato: {invoice.issue_date}")
    if invoice.due_date:
        add_line(f"Rok plaćanja: {invoice.due_date}")

    y -= 10
    add_line(f"Kupac: {invoice.buyer_name or '-'}")
    if invoice.buyer_address:
        add_line(f"Adresa: {invoice.buyer_address}")

    # Stavke
    y -= 20
    add_line("Stavke:")

    for item in invoice.items or []:
        line = (
            f"- {item.description}  x {item.quantity}  "
            f"@ {item.unit_price:.2f}  = {item.total_amount:.2f}"
        )
        add_line(line)

    # Sumarni dio
    y -= 20
    add_line(f"Osnovica: {invoice.total_base:.2f}")
    add_line(f"PDV: {invoice.total_vat:.2f}")
    add_line(f"Ukupno: {invoice.total_amount:.2f} BAM")

    y -= 20
    add_line("Generisano putem sp-app API-ja")

    lines.append("ET")

    stream_body = "\n".join(lines).encode("ascii")
    stream_data = (
        f"<< /Length {len(stream_body)} >>\nstream\n".encode("ascii")
        + stream_body
        + b"\nendstream"
    )

    write_obj_bytes(4, stream_data)

    # 5) Font definicija
    write_obj(
        5,
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    )

    # XREF tabela
    xref_start = buffer.tell()
    obj_count = 5  # objekti 1-5

    buffer.write(f"xref\n0 {obj_count + 1}\n".encode("ascii"))
    buffer.write(b"0000000000 65535 f \n")

    # offsets[1] odgovara objektu 1, itd.
    for off in offsets[1:]:
        buffer.write(f"{off:010d} 00000 n \n".encode("ascii"))

    # Trailer
    buffer.write(
        (
            "trailer\n"
            f"<< /Size {obj_count + 1} /Root 1 0 R >>\n"
            "startxref\n"
            f"{xref_start}\n"
            "%%EOF\n"
        ).encode("ascii")
    )

    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
