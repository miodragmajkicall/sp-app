# /home/miso/dev/sp-app-sp-app/backend/app/routes/promet.py
from __future__ import annotations

import io
from datetime import date
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_session as _get_session_dep
from app.models import CashEntry
from app.schemas.promet import PrometListResponse, PrometRow
from app.tenant_security import require_tenant_code, ensure_tenant_exists

router = APIRouter(
    tags=["promet"],
)


# ======================================================
#  TENANT HELPERI
# ======================================================


def _require_tenant(x_tenant_code: Optional[str]) -> str:
    return require_tenant_code(x_tenant_code)


def _ensure_tenant_exists(db: Session, code: str) -> None:
    ensure_tenant_exists(db, code)


# ======================================================
#  HELPER – bazni upit za KP (Knjiga prometa)
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
    Za prvu verziju Knjige prometa koristimo CashEntry kao izvor podataka.

    Trenutni model CashEntry sadrži:
      * tenant_code
      * entry_date (datum prometa / knjiženja)
      * description (opis / kratki partner)
      * amount (Decimal)
      * kind ('income' ili 'expense')
      * account ('cash' ili 'bank')

    U kasnijim iteracijama možemo:
    - filtrirati samo bezgotovinske transakcije (npr. account = 'bank'),
    - povezati sa brojem fakture i stvarnim partnerom.
    """

    stmt = select(CashEntry).where(CashEntry.tenant_code == tenant)

    if year is not None:
        stmt = stmt.where(func.extract("year", CashEntry.entry_date) == year)
    if month is not None:
        stmt = stmt.where(func.extract("month", CashEntry.entry_date) == month)

    if date_from is not None:
        stmt = stmt.where(CashEntry.entry_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(CashEntry.entry_date <= date_to)

    if partner_query:
        # Za sada filtriramo po opisu (description) kao proxy za partnera
        stmt = stmt.where(CashEntry.description.ilike(f"%{partner_query}%"))

    return stmt


def _cash_entry_to_promet_row(entry: CashEntry) -> PrometRow:
    """
    Mapiranje jednog CashEntry zapisa u PrometRow za KP-1042.
    """

    # Datum prometa – koristimo entry_date iz modela
    entry_date = getattr(entry, "entry_date", None)
    if entry_date is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="CashEntry nema popunjen entry_date.",
        )

    # Broj dokumenta – za sada nemamo direktno polje u modelu,
    # pa koristimo ID kao fallback (CE-<id>).
    entry_id = getattr(entry, "id", None)
    document_number = f"CE-{entry_id}" if entry_id is not None else "CE-N/A"

    # Naziv partnera – za V1 koristimo description kao kratki opis / partnera
    partner_name = getattr(entry, "description", None) or "N/A"

    raw_amount = getattr(entry, "amount", Decimal("0"))
    if not isinstance(raw_amount, Decimal):
        try:
            raw_amount = Decimal(str(raw_amount))
        except Exception:
            raw_amount = Decimal("0")

    kind = getattr(entry, "kind", None)
    # Konvencija: prihodi pozitivni, rashodi negativni
    if kind == "expense":
        signed_amount = -raw_amount
    else:
        signed_amount = raw_amount

    note_parts: List[str] = []
    if kind:
        note_parts.append(f"Vrsta: {kind}")
    account = getattr(entry, "account", None)
    if account:
        note_parts.append(f"Račun: {account}")
    description = getattr(entry, "description", None)
    if description:
        note_parts.append(description)
    note = " | ".join(note_parts) if note_parts else None

    return PrometRow(
        date=entry_date,
        document_number=document_number,
        partner_name=str(partner_name),
        amount=signed_amount,
        note=note,
    )


# ======================================================
#  LISTA ZA UI – /promet
# ======================================================


@router.get(
    "/promet",
    response_model=PrometListResponse,
    summary="Lista prometa (KP-1042) za UI tabelu",
    description=(
        "UI-friendly lista za Knjigu prometa (KP-1042).\n\n"
        "Podržani filteri:\n"
        "- `year` i `month` – filtriranje po godini/mjesecu `entry_date`,\n"
        "- `date_from` / `date_to` – opseg datuma (uključivo, preko `entry_date`),\n"
        "- `partner_query` – filter po opisu (substring, case-insensitive).\n\n"
        "Paginacija:\n"
        "- Može se koristiti `page` + `page_size` (1-based), ili direktno `limit` + `offset`.\n"
        "- Ako je `page` zadat, `limit`/`offset` se ignorišu."
    ),
    responses={
        200: {
            "description": "Uspješno vraćena lista prometa.",
        },
        400: {
            "description": "Nedostaje `X-Tenant-Code` header ili su filter parametri nevalidni.",
        },
    },
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
        description="Filter po opisu (case-insensitive, substring).",
    ),
    page: Optional[int] = Query(
        None,
        ge=1,
        description="Broj stranice (1-based). Ako je zadat, koristi se zajedno sa `page_size`.",
    ),
    page_size: Optional[int] = Query(
        None,
        ge=1,
        le=200,
        description="Broj stavki po stranici kada se koristi `page`.",
    ),
    limit: int = Query(
        50,
        ge=1,
        le=500,
        description="Maksimalan broj stavki u odgovoru (koristi se ako `page` nije zadat).",
    ),
    offset: int = Query(
        0,
        ge=0,
        description="Offset za rezultate (koristi se ako `page` nije zadat).",
    ),
) -> PrometListResponse:
    tenant = _require_tenant(x_tenant_code)
    _ensure_tenant_exists(db, tenant)

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

    # paginacija – ako je zadat page, ima prednost nad limit/offset
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
        base_stmt.order_by(CashEntry.entry_date.desc(), CashEntry.id.desc())
        .limit(query_limit)
        .offset(query_offset)
    )

    cash_rows: List[CashEntry] = db.execute(items_stmt).scalars().all()
    promet_items: List[PrometRow] = [
        _cash_entry_to_promet_row(entry) for entry in cash_rows
    ]

    return PrometListResponse(total=total, items=promet_items)


# ======================================================
#  EXPORT – /promet/export (CSV)
# ======================================================


@router.get(
    "/promet/export",
    summary="Export Knjige prometa (CSV za Excel)",
    response_class=StreamingResponse,
    description=(
        "Export Knjige prometa (KP-1042) za zadatog tenanta u CSV format "
        "koji se može direktno otvoriti u Excel-u.\n\n"
        "Podržani filteri su isti kao i za `/promet`:\n"
        "- `year`, `month`, `date_from`, `date_to`, `partner_query`.\n\n"
        "Format: delimiter `;`, UTF-8 sa BOM radi korektnog prikaza u Excel-u."
    ),
)
def export_promet(
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
    _ensure_tenant_exists(db, tenant)

    base_stmt = _build_promet_base_stmt(
        tenant=tenant,
        year=year,
        month=month,
        date_from=date_from,
        date_to=date_to,
        partner_query=partner_query,
    )

    base_stmt = base_stmt.order_by(CashEntry.entry_date.asc(), CashEntry.id.asc())
    cash_rows: List[CashEntry] = db.execute(base_stmt).scalars().all()

    # Priprema CSV sadržaja (Excel-friendly, delimiter ';', UTF-8 sa BOM)
    output = io.StringIO()
    # Header red
    output.write("Datum;Broj dokumenta;Partner;Iznos;Napomena\n")

    for entry in cash_rows:
        row = _cash_entry_to_promet_row(entry)

        date_str = row.date.isoformat()
        doc_no = row.document_number or ""
        partner = row.partner_name or ""
        amount_str = f"{row.amount:.2f}"
        note_str = row.note or ""

        line = (
            f"{date_str};"
            f"{doc_no};"
            f"{partner};"
            f"{amount_str};"
            f"{note_str}\n"
        )
        output.write(line)

    csv_bytes = ("\ufeff" + output.getvalue()).encode("utf-8")  # BOM za Excel
    buffer = io.BytesIO(csv_bytes)

    filename = "promet-export.csv"
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
    }

    return StreamingResponse(
        buffer,
        media_type="text/csv; charset=utf-8",
        headers=headers,
    )
