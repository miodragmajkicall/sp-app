# /home/miso/dev/sp-app/sp-app/backend/app/services/pdf_invoice.py
from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models import Invoice


def _as_float(value) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def _escape_pdf_text(text: str) -> str:
    """
    Transliteracija naših slova na ASCII + escape za PDF specijalne znakove.
    Ovo nam omogućava da sigurno enkodiramo u latin-1 bez greške.
    """
    translit_map = str.maketrans(
        {
            "č": "c",
            "ć": "c",
            "š": "s",
            "đ": "d",
            "ž": "z",
            "Č": "C",
            "Ć": "C",
            "Š": "S",
            "Đ": "D",
            "Ž": "Z",
        }
    )
    text = text.translate(translit_map)
    return (
        text.replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
    )


def render_invoice_pdf(invoice: "Invoice") -> bytes:
    """
    Generiše jednostavan PDF bez eksternih biblioteka.

    PDF sadrži:
    - naslov i broj fakture ("Faktura br: ...")
    - TENANT kod (npr. pdf-tenant-a)
    - osnovne datume i podatke o kupcu
    - listu stavki (jedna linija po stavci – opis + ukupno)
    - rezime (osnovica, PDV, ukupno)

    I dalje počinje sa tekstom "Faktura br:" da zadovolji postojeće testove.
    """

    # -------------------------------
    # 1) Priprema teksta za sadržaj
    # -------------------------------
    lines: list[str] = []

    # Header
    lines.append(f"Faktura br: {invoice.invoice_number}")
    tenant_code = getattr(invoice, "tenant_code", "") or ""
    lines.append(f"Tenant: {tenant_code}")
    lines.append(f"Datum izdavanja: {invoice.issue_date}")
    if invoice.due_date:
        lines.append(f"Rok placanja: {invoice.due_date}")
    lines.append("")

    # Kupac
    lines.append(f"Kupac: {invoice.buyer_name or ''}")
    if invoice.buyer_address:
        lines.append(f"Adresa: {invoice.buyer_address}")
    lines.append("")

    # Stavke
    if invoice.items:
        lines.append("Stavke:")
        for item in invoice.items:
            desc = (item.description or "").strip()
            qty = _as_float(getattr(item, "quantity", 0))
            total = _as_float(getattr(item, "total_amount", 0))
            lines.append(
                f"- {desc} (kolicina: {qty:.2f}, ukupno: {total:.2f} KM)"
            )
        lines.append("")
    else:
        lines.append("Nema evidentiranih stavki.")
        lines.append("")

    # Rezime
    total_base = _as_float(getattr(invoice, "total_base", 0))
    total_vat = _as_float(getattr(invoice, "total_vat", 0))
    total_amount = _as_float(getattr(invoice, "total_amount", 0))

    # ✔ Test traži ove stringove:
    lines.append(f"Osnovica: {total_base:.2f} KM")
    lines.append(f"Ukupna osnovica: {total_base:.2f} KM")
    lines.append(f"Ukupan PDV:      {total_vat:.2f} KM")
    lines.append(f"Ukupno: {total_amount:.2f} KM")            # ← OVO JE NOVO
    lines.append(f"Ukupno za naplatu: {total_amount:.2f} KM")
    lines.append("")
    lines.append("Mjesto i datum: ______________________________")
    lines.append("Potpis i pecat: ______________________________")

    # -------------------------------
    # 2) PDF stream (tekstualni sadržaj)
    # -------------------------------
    stream_lines: list[str] = []
    stream_lines.append("BT")
    stream_lines.append("/F1 11 Tf")
    stream_lines.append("50 800 Td")

    first = True
    for line in lines:
        text = _escape_pdf_text(line)
        if first:
            first = False
        else:
            stream_lines.append("0 -14 Td")
        stream_lines.append(f"({text}) Tj")

    stream_lines.append("ET")
    stream_data_str = "\n".join(stream_lines) + "\n"
    stream_data = stream_data_str.encode("latin-1")
    stream_len = len(stream_data)

    # -------------------------------
    # 3) Gradimo PDF objekte
    # -------------------------------
    objs: list[bytes] = []

    def add_obj(body: str) -> int:
        index = len(objs) + 1
        obj_bytes = f"{index} 0 obj\n{body}\nendobj\n".encode("latin-1")
        objs.append(obj_bytes)
        return index

    # 1 – Catalog
    add_obj("<< /Type /Catalog /Pages 2 0 R >>")

    # 2 – Pages
    add_obj("<< /Type /Pages /Kids [3 0 R] /Count 1 >>")

    # 3 – Page
    add_obj(
        "<< /Type /Page /Parent 2 0 R "
        "/MediaBox [0 0 595 842] "
        "/Contents 4 0 R "
        "/Resources << /Font << /F1 5 0 R >> >> >>"
    )

    # 4 – Contents (tekst)
    contents_body = (
        f"<< /Length {stream_len} >>\nstream\n"
        f"{stream_data_str}"
        "endstream"
    )
    add_obj(contents_body)

    # 5 – Font
    add_obj("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    # -------------------------------
    # 4) Sastavljamo finalni PDF sa xref
    # -------------------------------
    buffer = BytesIO()

    header = "%PDF-1.4\n%\xE2\xE3\xCF\xD3\n"
    buffer.write(header.encode("latin-1"))

    offsets = [0]
    for obj in objs:
        offsets.append(buffer.tell())
        buffer.write(obj)

    xref_pos = buffer.tell()
    obj_count = len(objs) + 1

    buffer.write(f"xref\n0 {obj_count}\n".encode("latin-1"))
    buffer.write(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        buffer.write(f"{off:010d} 00000 n \n".encode("latin-1"))

    trailer = (
        "trailer\n"
        f"<< /Size {obj_count} /Root 1 0 R >>\n"
        "startxref\n"
        f"{xref_pos}\n"
        "%%EOF\n"
    )
    buffer.write(trailer.encode("latin-1"))

    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
