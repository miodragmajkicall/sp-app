# /home/miso/dev/sp-app/sp-app/backend/app/routes/export.py
from __future__ import annotations

import io
import zipfile
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Header, Body, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_session as _get_session_dep
from app.tenant_security import require_tenant_code

router = APIRouter(
    prefix="/export",
    tags=["reports"],
)


# ======================================================
#  SCHEMA
# ======================================================

class ExportInspectionRequest(BaseModel):
    from_date: date = Field(..., description="Početni datum (YYYY-MM-DD)")
    to_date: date = Field(..., description="Završni datum (YYYY-MM-DD)")

    include_outgoing_invoices_pdf: bool = True
    include_input_invoices_pdf: bool = True
    include_kpr_pdf: bool = True
    include_promet_pdf: bool = True
    include_cash_bank_pdf: bool = True
    include_taxes_pdf: bool = True


# ======================================================
#  HELPERS
# ======================================================

def _require_tenant(x_tenant_code: Optional[str]) -> str:
    return require_tenant_code(x_tenant_code)


def _dummy_pdf(title: str) -> bytes:
    """
    Privremeni PDF placeholder.
    U sljedećem koraku ovo mapiramo na prave PDF generatore.
    """
    content = f"""
    {title}

    (PDF generator još nije implementiran – placeholder)
    """
    return content.encode("utf-8")


# ======================================================
#  EXPORT – INSPECTION ZIP
# ======================================================

@router.post(
    "/inspection",
    summary="Izvoz svih dokumenata za inspekciju (ZIP)",
    description=(
        "Kreira ZIP arhivu sa svim relevantnim dokumentima za inspekciju:\n\n"
        "- izlazne fakture (PDF)\n"
        "- ulazne račune (PDF)\n"
        "- KPR (PDF)\n"
        "- knjigu prometa (PDF)\n"
        "- kasa/banka izvještaj (PDF)\n"
        "- poreze i doprinose (PDF)\n\n"
        "Period se definiše sa `from_date` i `to_date`."
    ),
)
def export_inspection_zip(
    payload: ExportInspectionRequest = Body(...),
    x_tenant_code: Optional[str] = Header(None, alias="X-Tenant-Code"),
    db: Session = Depends(_get_session_dep),
) -> Response:
    tenant = _require_tenant(x_tenant_code)

    if payload.from_date > payload.to_date:
        raise HTTPException(
            status_code=400,
            detail="from_date ne može biti poslije to_date",
        )

    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        period_label = f"{payload.from_date}_{payload.to_date}"

        if payload.include_outgoing_invoices_pdf:
            zf.writestr(
                f"01_invoices_outgoing/outgoing_invoices_{period_label}.pdf",
                _dummy_pdf("Izlazne fakture"),
            )

        if payload.include_input_invoices_pdf:
            zf.writestr(
                f"02_invoices_incoming/input_invoices_{period_label}.pdf",
                _dummy_pdf("Ulazni računi"),
            )

        if payload.include_kpr_pdf:
            zf.writestr(
                f"03_kpr/KPR_{period_label}.pdf",
                _dummy_pdf("Knjiga prihoda i rashoda (KPR)"),
            )

        if payload.include_promet_pdf:
            zf.writestr(
                f"04_promet/knjiga_prometa_{period_label}.pdf",
                _dummy_pdf("Knjiga prometa"),
            )

        if payload.include_cash_bank_pdf:
            zf.writestr(
                f"05_cash_bank/cash_bank_{period_label}.pdf",
                _dummy_pdf("Kasa / Banka"),
            )

        if payload.include_taxes_pdf:
            zf.writestr(
                f"06_taxes/taxes_{period_label}.pdf",
                _dummy_pdf("Porezi i doprinosi"),
            )

    buffer.seek(0)

    filename = f"inspection-{tenant}-{payload.from_date}_{payload.to_date}.zip"

    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
