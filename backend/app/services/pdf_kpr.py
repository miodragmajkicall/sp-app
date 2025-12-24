from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from io import BytesIO
from typing import Iterable, List

from . import pdf_invoice  # koristimo pomoćne funkcije za PDF formatiranje
from app.schemas.kpr import KprRowItem


@dataclass
class KprPeriod:
    year: int
    month: int | None = None  # ako je None → godišnji KPR


def _escape(text: str) -> str:
    # Reuse logike iz pdf_invoice
    return pdf_invoice._escape_pdf_text(text)


def render_kpr_pdf(
    tenant_code: str,
    period: KprPeriod,
    rows: Iterable[KprRowItem],
) -> bytes:
    """
    Generiše PDF Knjige prihoda i rashoda (KPR) za datog tenanta i period.

    - Ako je period.month postavljen → mjesečni KPR.
    - Ako je period.month None        → godišnji KPR.

    PDF je jednostavan tekstualni layout, ali dovoljno jasan za inspekciju:
    - zaglavlje sa tenant-om i periodom,
    - tabela sa redovima (datum, vrsta, kategorija, kupac/dobavljač, broj dok., iznos),
    - zbir prihoda, zbir rashoda i neto.
    """
    rows_list: List[KprRowItem] = list(rows)

    total_income = sum(r.amount for r in rows_list if r.kind == "income")
    total_expense = sum(r.amount for r in rows_list if r.kind == "expense")
    net = total_income - total_expense

    lines: List[str] = []

    # 1) Header
    lines.append("KNJIGA PRIHODA I RASHODA (KPR)")
    lines.append(f"Tenant: {tenant_code or 'N/A'}")

    if period.month is not None:
        lines.append(f"Period: {period.year:04d}-{period.month:02d}")
    else:
        lines.append(f"Period: {period.year:04d} (cijela godina)")
    lines.append("")

    # 2) Legend
    lines.append("Legenda vrsta:")
    lines.append("  income  = prihod")
    lines.append("  expense = rashod")
    lines.append("")
    lines.append(
        "Datum       Vrsta     Kategorija      Kupac/Dobavljac           Br.dok.     Iznos (BAM)"
    )
    lines.append(
        "----------------------------------------------------------------------------------------"
    )

    if rows_list:
        for r in rows_list:
            datum_str = r.date.isoformat()
            kind_str = r.kind[:7]
            cat = (r.category or "")[:12]
            cp = (r.counterparty or "")[:23]
            doc_no = (r.document_number or "")[:10]
            amount = f"{r.amount:.2f}"

            line = f"{datum_str:10} {kind_str:7} {cat:12} {cp:23} {doc_no:10} {amount:>11}"
            lines.append(line)
    else:
        lines.append("(Nema stavki u zadatom periodu)")

    lines.append(
        "----------------------------------------------------------------------------------------"
    )
    lines.append(f"Ukupni prihodi: {total_income:.2f} BAM")
    lines.append(f"Ukupni rashodi: {total_expense:.2f} BAM")
    lines.append(f"Neto rezultat:  {net:.2f} BAM")
    lines.append("")

    # PDF stream (isti princip kao u pdf_invoice)
    stream_lines: List[str] = []
    stream_lines.append("BT")
    stream_lines.append("/F1 11 Tf")
    stream_lines.append("50 800 Td")

    first = True
    for line in lines:
        text = _escape(line)
        if first:
            first = False
        else:
            stream_lines.append("0 -14 Td")
        stream_lines.append(f"({text}) Tj")

    stream_lines.append("ET")
    stream_data_str = "\n".join(stream_lines) + "\n"
    stream_data = stream_data_str.encode("latin-1")
    stream_len = len(stream_data)

    objs: List[bytes] = []

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
    # 4 – Contents
    contents_body = (
        f"<< /Length {stream_len} >>\nstream\n"
        f"{stream_data_str}"
        "endstream"
    )
    add_obj(contents_body)
    # 5 – Font
    add_obj("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

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
