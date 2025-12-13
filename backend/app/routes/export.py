# /home/miso/dev/sp-app/sp-app/backend/app/routes/export.py
from __future__ import annotations

from datetime import date
from io import BytesIO
from typing import List, Optional
import zipfile

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_session as _get_session_dep
from app.tenant_security import ensure_tenant_exists, require_tenant_code

router = APIRouter(tags=["export"])


# ======================================================
#  SCHEMAS
# ======================================================


class ExportInspectionRequest(BaseModel):
    from_date: date
    to_date: date

    include_outgoing_invoices_pdf: bool = True
    include_input_invoices_pdf: bool = True
    include_kpr_pdf: bool = True
    include_promet_pdf: bool = True
    include_cash_bank_pdf: bool = True
    include_taxes_pdf: bool = True


# ======================================================
#  PDF HELPERS (MINIMAL, ROBUST)
# ======================================================


def _escape_pdf_text(text: str) -> str:
    """
    PDF je ovdje "minimalni text PDF", pa moramo osigurati da tekst moze u latin-1.

    - transliteracija dijakritike
    - zamjena tipografskih crtica/navodnika sa ASCII varijantama
    - escape za PDF string literal
    """
    # tipografske crte i navodnici -> ASCII
    text = (
        text.replace("\u2013", "-")  # en dash
        .replace("\u2014", "-")  # em dash
        .replace("\u2019", "'")  # right single quote
        .replace("\u2018", "'")  # left single quote
        .replace("\u201c", '"')  # left double quote
        .replace("\u201d", '"')  # right double quote
        .replace("\u00a0", " ")  # nbsp
    )

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

    # PDF string escaping
    return (
        text.replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
    )


def _build_simple_text_pdf(lines: List[str]) -> bytes:
    """
    Minimalni PDF generator bez eksternih biblioteka.
    Bitno: ne smije puknuti na unicode -> encode latin-1 uz errors='replace'.
    """
    stream_lines: List[str] = []
    stream_lines.append("BT")
    stream_lines.append("/F1 11 Tf")
    stream_lines.append("50 800 Td")

    first = True
    for line in lines:
        safe = _escape_pdf_text(line)
        if first:
            first = False
        else:
            stream_lines.append("0 -14 Td")
        stream_lines.append(f"({safe}) Tj")

    stream_lines.append("ET")

    stream_data_str = "\n".join(stream_lines) + "\n"
    stream_data = stream_data_str.encode("latin-1", errors="replace")
    stream_len = len(stream_data)

    objs: List[bytes] = []

    def add_obj(body: str) -> int:
        idx = len(objs) + 1
        objs.append(f"{idx} 0 obj\n{body}\nendobj\n".encode("latin-1"))
        return idx

    # 1 - Catalog
    add_obj("<< /Type /Catalog /Pages 2 0 R >>")
    # 2 - Pages
    add_obj("<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    # 3 - Page
    add_obj(
        "<< /Type /Page /Parent 2 0 R "
        "/MediaBox [0 0 595 842] "
        "/Contents 4 0 R "
        "/Resources << /Font << /F1 5 0 R >> >> >>"
    )
    # 4 - Contents
    add_obj(
        f"<< /Length {stream_len} >>\nstream\n"
        f"{stream_data_str}"
        "endstream"
    )
    # 5 - Font
    add_obj("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    buffer = BytesIO()
    buffer.write("%PDF-1.4\n%\xE2\xE3\xCF\xD3\n".encode("latin-1"))

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


def _dummy_pdf(title: str) -> bytes:
    # ASCII-only placeholder linije (bez dijakritike i bez en-dash)
    return _build_simple_text_pdf(
        [
            title,
            "",
            "(PDF generator jos nije implementiran - placeholder)",
        ]
    )


# ======================================================
#  EXPORT: INSPECTION ZIP
# ======================================================


def _period_suffix(from_date: date, to_date: date) -> str:
    return f"{from_date.isoformat()}_{to_date.isoformat()}"


def _zip_filename(tenant: str, from_date: date, to_date: date) -> str:
    return f"inspection-{tenant}-{_period_suffix(from_date, to_date)}.zip"


def _add_pdf(zf: zipfile.ZipFile, path_in_zip: str, title: str) -> None:
    zf.writestr(path_in_zip, _dummy_pdf(title))


@router.post(
    "/export/inspection",
    summary="ZIP export za inspekciju (PDF bundle)",
)
def export_inspection_zip(
    payload: ExportInspectionRequest,
    db: Session = Depends(_get_session_dep),
    x_tenant_code: Optional[str] = Header(None, alias="X-Tenant-Code"),
) -> StreamingResponse:
    tenant = require_tenant_code(x_tenant_code)
    ensure_tenant_exists(db, tenant)

    # Validacija perioda (test ocekuje 400 kad je from_date > to_date)
    if payload.from_date > payload.to_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid period: from_date cannot be after to_date",
        )

    suffix = _period_suffix(payload.from_date, payload.to_date)

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        if payload.include_outgoing_invoices_pdf:
            _add_pdf(
                zf,
                f"01_invoices_outgoing/outgoing_invoices_{suffix}.pdf",
                "Izlazne fakture",
            )

        if payload.include_input_invoices_pdf:
            _add_pdf(
                zf,
                f"02_invoices_incoming/input_invoices_{suffix}.pdf",
                "Ulazni racuni",
            )

        if payload.include_kpr_pdf:
            _add_pdf(
                zf,
                f"03_kpr/KPR_{suffix}.pdf",
                "KPR (Knjiga prihoda i rashoda)",
            )

        if payload.include_promet_pdf:
            _add_pdf(
                zf,
                f"04_promet/knjiga_prometa_{suffix}.pdf",
                "Knjiga prometa",
            )

        if payload.include_cash_bank_pdf:
            _add_pdf(
                zf,
                f"05_cash_bank/cash_bank_{suffix}.pdf",
                "Cash/Bank",
            )

        if payload.include_taxes_pdf:
            _add_pdf(
                zf,
                f"06_taxes/taxes_{suffix}.pdf",
                "Porezi",
            )

    buffer.seek(0)

    filename = _zip_filename(tenant, payload.from_date, payload.to_date)
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}

    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers=headers,
    )
