# /home/miso/dev/sp-app/sp-app/backend/app/services/pdf_promet.py
from __future__ import annotations

from datetime import date
from decimal import Decimal
from io import BytesIO
from typing import Any, Iterable, Mapping, Optional


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def _escape_pdf_text(text: str) -> str:
    """
    Transliteracija naših slova na ASCII + escape za PDF specijalne znakove.
    Omogućava sigurno enkodiranje u latin-1 bez greške.
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


def _get_row_value(row: Any, key: str, default: Any = None) -> Any:
    """
    Helper koji omogućava da rows budu ili dict, ili Pydantic/BaseModel,
    ili SQLAlchemy objekti. Prvo pokušava .get, zatim getattr.
    """
    if isinstance(row, Mapping):
        return row.get(key, default)
    return getattr(row, key, default)


def render_promet_pdf(
    tenant_code: str,
    rows: Iterable[Any],
    period_label: Optional[str] = None,
) -> bytes:
    """
    Generiše jednostavan PDF izvještaj za Knjigu prometa (KP-1042 stil).

    Parametri:
    - tenant_code: kod tenanta (npr. 't-demo'),
    - rows: iterabilna kolekcija redova, gdje svaki red ima polja:
        - date (datetime.date),
        - document_number (str),
        - partner_name (str),
        - amount (Decimal ili float),
        - note (str, opcionalno),
    - period_label: tekstualni opis perioda (npr. '01.2025' ili '2025-01-01 do 2025-01-31').

    Struktura:
    - zaglavlje: naziv izvještaja + tenant + period,
    - tabela: Datum | Broj dokumenta | Kupac/Dobavljač | Iznos | Napomena,
    - suma: Ukupno: XX.XX KM.
    """

    lines: list[str] = []

    # ---------------------------------
    # 1) Header – naziv izvještaja
    # ---------------------------------
    lines.append("KNJIGA PROMETA (KP-1042)")
    lines.append("SP-APP – evidencija bezgotovinskog prometa")
    lines.append(f"Tenant: {tenant_code or ''}")
    if period_label:
        lines.append(f"Period: {period_label}")
    lines.append("")

    # ---------------------------------
    # 2) Tabela – header
    # ---------------------------------
    lines.append("--------------------------------------------------------------------------")
    lines.append(
        "Datum       Broj dok.        Kupac/Dobavljac                 Iznos      Napomena"
    )
    lines.append("--------------------------------------------------------------------------")

    total_amount = Decimal("0.00")

    has_rows = False
    for row in rows:
        has_rows = True

        d: date = _get_row_value(row, "date")
        doc_no: str = _get_row_value(row, "document_number", "") or ""
        partner_name: str = _get_row_value(row, "partner_name", "") or ""
        amount = _get_row_value(row, "amount", Decimal("0.00"))
        note: str = _get_row_value(row, "note", "") or ""

        # Sigurno u Decimal -> float
        if not isinstance(amount, Decimal):
            try:
                amount = Decimal(str(amount))
            except Exception:
                amount = Decimal("0.00")

        total_amount += amount

        date_str = d.isoformat() if isinstance(d, date) else ""
        short_doc = doc_no[:14]
        short_partner = partner_name[:25]
        short_note = note[:20]

        line = (
            f"{date_str:10} "
            f"{short_doc:14} "
            f"{short_partner:25} "
            f"{_as_float(amount):9.2f} "
            f"{short_note}"
        )
        lines.append(line)

    if not has_rows:
        lines.append("(Nema evidentiranih stavki prometa u zadatom periodu)")

    lines.append("--------------------------------------------------------------------------")
    lines.append("")
    lines.append(f"Ukupno: {total_amount:.2f} KM")
    lines.append("")

    # ---------------------------------
    # 3) Potpis / mjesto i datum (generički)
    # ---------------------------------
    lines.append("Mjesto i datum: ______________________________")
    lines.append("Potpis:        ______________________________")

    # ---------------------------------
    # 4) PDF text stream
    # ---------------------------------
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

    # ---------------------------------
    # 5) PDF objekti
    # ---------------------------------
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

    # ---------------------------------
    # 6) Sastavljanje finalnog PDF-a sa xref
    # ---------------------------------
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
