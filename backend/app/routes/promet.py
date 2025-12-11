# /home/miso/dev/sp-app/sp-app/backend/app/routes/promet.py
from __future__ import annotations

import io
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_session as _get_session_dep
from app.models import CashEntry, Invoice
from app.schemas.promet import PrometListResponse, PrometRow
from app.services.pdf_promet import render_promet_pdf
from app.tenant_security import require_tenant_code

router = APIRouter(
    tags=["promet"],
)


# ======================================================
#  TENANT HELPER
# ======================================================


def _require_tenant(x_tenant_code: Optional[str]) -> str:
    return require_tenant_code(x_tenant_code)


# ======================================================
#  HELPER – bazni SELECT za Knjigu prometa
# ======================================================


def _build_promet_base_stmt(
    tenant: str,
    year: Optional[int],
    month: Optional[int],
    date_from: Optional[date],
    date_to: Optional[date],
    partner_query: Optional[str],
):
    """
    Gradi bazni SELECT za Knjigu prometa.

    Pravila:
    - koristimo CashEntry kao izvor bezgotovinskog prometa:
        kind = 'income'
        account = 'bank'
        invoice_id IS NOT NULL
    - join na Invoice radi broja dokumenta i naziva kupca,
    - datum = entry_date (datum bezgotovinskog prometa na bankovnom računu).
    """
    date_col = CashEntry.entry_date

    base_stmt = (
        select(
            date_col.label("date"),
            Invoice.invoice_number.label("document_number"),
            Invoice.buyer_name.label("partner_name"),
            CashEntry.amount.label("amount"),
            CashEntry.description.label("note"),
        )
        .join(
            Invoice,
            (Invoice.id == CashEntry.invoice_id)
            & (Invoice.tenant_code == CashEntry.tenant_code),
        )
        .where(
            CashEntry.tenant_code == tenant,
            CashEntry.kind == "income",
            CashEntry.account == "bank",
            CashEntry.invoice_id.is_not(None),
        )
    )

    # Filtriranje po godini/mjesecu (preko entry_date)
    if year is not None:
        base_stmt = base_stmt.where(func.extract("year", date_col) == year)
    if month is not None:
        base_stmt = base_stmt.where(func.extract("month", date_col) == month)

    # Filtriranje po periodu (entry_date od/do)
    if date_from is not None:
        base_stmt = base_stmt.where(date_col >= date_from)
    if date_to is not None:
        base_stmt = base_stmt.where(date_col <= date_to)

    # Filtriranje po kupcu/dobavljaču (naziv partnera)
    if partner_query:
        base_stmt = base_stmt.where(
            Invoice.buyer_name.ilike(f"%{partner_query}%"),
        )

    return base_stmt


# ======================================================
#  LIST FOR UI – /promet
# ======================================================


@router.get(
    "/promet",
    response_model=PrometListResponse,
    summary="Knjiga prometa (KP-1042) – lista za UI",
    description=(
        "Vraća podatke za Knjigu prometa (KP-1042 stil) za jednog tenanta.\n\n"
        "Izvor podataka su CashEntry zapisi sa:\n"
        "- kind = 'income',\n"
        "- account = 'bank',\n"
        "- invoice_id IS NOT NULL (vezano za izlaznu fakturu).\n\n"
        "Podržani filteri:\n"
        "- year / month – po entry_date,\n"
        "- date_from / date_to – opseg po entry_date,\n"
        "- partner_query – filter po nazivu kupca (substring, case-insensitive).\n\n"
        "Paginacija:\n"
        "- Može se koristiti page + page_size ili direktno limit + offset."
    ),
)
def list_promet(
    db: Session = Depends(_get_session_dep),
    x_tenant_code: Optional[str] = Header(
        None,
        alias="X-Tenant-Code",
    ),
    year: Optional[int] = Query(None, ge=1900, le=2100),
    month: Optional[int] = Query(None, ge=1, le=12),
    date_from: Optional[date] = Query(
        None,
        description="Početni datum opsega (entry_date >= date_from).",
    ),
    date_to: Optional[date] = Query(
        None,
        description="Završni datum opsega (entry_date <= date_to).",
    ),
    partner_query: Optional[str] = Query(
        None,
        description="Filter po nazivu kupca/dobavljača (case-insensitive, substring).",
    ),
    page: Optional[int] = Query(
        None,
        ge=1,
        description="Broj stranice (1-based). Ako je zadat, koristi se sa page_size.",
    ),
    page_size: Optional[int] = Query(
        None,
        ge=1,
        le=500,
        description="Broj stavki po stranici kada se koristi page.",
    ),
    limit: int = Query(
        50,
        ge=1,
        le=500,
        description="Maksimalan broj stavki u odgovoru (koristi se ako page nije zadat).",
    ),
    offset: int = Query(
        0,
        ge=0,
        description="Offset za rezultate (koristi se ako page nije zadat).",
    ),
) -> PrometListResponse:
    tenant = _require_tenant(x_tenant_code)

    base_stmt = _build_promet_base_stmt(
        tenant=tenant,
        year=year,
        month=month,
        date_from=date_from,
        date_to=date_to,
        partner_query=partner_query,
    )

    # total
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total: int = db.execute(count_stmt).scalar_one()

    # paginacija
    if page is not None:
        effective_page_size = page_size or limit
        if effective_page_size <= 0:
            effective_page_size = 50
        query_limit = effective_page_size
        query_offset = (page - 1) * effective_page_size
    else:
        query_limit = limit
        query_offset = offset

    items_stmt = (
        base_stmt.order_by(CashEntry.entry_date.desc(), Invoice.id.desc())
        .limit(query_limit)
        .offset(query_offset)
    )
    rows = db.execute(items_stmt).all()

    items: List[PrometRow] = []
    for row in rows:
        # row je SQLAlchemy Row; pristupamo po label-ovima
        items.append(
            PrometRow(
                date=row.date,
                document_number=row.document_number,
                partner_name=row.partner_name,
                amount=row.amount,
                note=row.note,
            )
        )

    return PrometListResponse(total=total, items=items)


# ======================================================
#  EXPORT PDF – /promet/export-pdf
# ======================================================


@router.get(
    "/promet/export-pdf",
    summary="Knjiga prometa (KP-1042) – PDF export",
    response_class=StreamingResponse,
    description=(
        "Generiše PDF izvještaj Knjige prometa (KP-1042 stil) za zadatog tenanta i filtere.\n\n"
        "Podaci se baziraju na CashEntry zapisima (kind='income', account='bank', invoice_id IS NOT NULL) "
        "i vezanim izlaznim fakturama."
    ),
)
def export_promet_pdf(
    db: Session = Depends(_get_session_dep),
    x_tenant_code: Optional[str] = Header(
        None,
        alias="X-Tenant-Code",
    ),
    year: Optional[int] = Query(None, ge=1900, le=2100),
    month: Optional[int] = Query(None, ge=1, le=12),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    partner_query: Optional[str] = Query(None),
) -> StreamingResponse:
    tenant = _require_tenant(x_tenant_code)

    base_stmt = _build_promet_base_stmt(
        tenant=tenant,
        year=year,
        month=month,
        date_from=date_from,
        date_to=date_to,
        partner_query=partner_query,
    )

    base_stmt = base_stmt.order_by(CashEntry.entry_date.asc(), Invoice.id.asc())
    rows = db.execute(base_stmt).all()

    # period label za zaglavlje
    if year is not None and month is not None:
        period_label = f"{month:02d}.{year}"
    elif year is not None:
        period_label = str(year)
    elif date_from and date_to:
        period_label = f"{date_from.isoformat()} do {date_to.isoformat()}"
    elif date_from:
        period_label = f"Od {date_from.isoformat()}"
    elif date_to:
        period_label = f"Do {date_to.isoformat()}"
    else:
        period_label = None

    pdf_bytes = render_promet_pdf(
        tenant_code=tenant,
        rows=rows,
        period_label=period_label,
    )
    buffer = io.BytesIO(pdf_bytes)

    filename = "promet-kp-1042.pdf"
    headers = {
        "Content-Disposition": f'inline; filename="{filename}"',
    }

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers=headers,
    )
