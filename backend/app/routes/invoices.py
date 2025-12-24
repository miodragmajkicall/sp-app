# /home/miso/dev/sp-app/sp-app/backend/app/routes/invoices.py
from __future__ import annotations

import io
from datetime import date
from decimal import Decimal
from typing import List, Optional

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Query,
    Response,
    status,
)
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func, text
    # NOTE: text is used in _ensure_is_paid_column
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_session as _get_session_dep
from app.models import Invoice, InvoiceItem
from app.schemas.invoice import (
    InvoiceCreate,
    InvoiceRead,
    InvoiceRowItem,
    InvoiceListResponse,
)
from app.tenant_security import require_tenant_code, ensure_tenant_exists
from app.services.pdf_invoice import render_invoice_pdf

router = APIRouter(
    tags=["invoices"],
)


# ======================================================
#  TENANT HELPERS
# ======================================================


def _require_tenant(x_tenant_code: Optional[str]) -> str:
    return require_tenant_code(x_tenant_code)


def _ensure_tenant_exists(db: Session, code: str) -> None:
    ensure_tenant_exists(db, code)


# ======================================================
#  SCHEMA SAFETY – osiguranje da postoji is_paid kolona
# ======================================================

_IS_PAID_COLUMN_CHECKED: bool = False


def _ensure_is_paid_column(db: Session) -> None:
    """
    Jednostavan zaštitni mehanizam:

    Ako kolona `is_paid` ne postoji u tabeli `invoices`, dodajemo je
    kroz raw SQL. Ovo omogućava da testovi i razvojni DB nastave
    da rade čak i ako Alembic migracija nije pokrenuta.

    U produkciji ćemo ovo zamijeniti čistom Alembic migracijom.
    """
    global _IS_PAID_COLUMN_CHECKED
    if _IS_PAID_COLUMN_CHECKED:
        return

    db.execute(
        text(
            """
            ALTER TABLE invoices
            ADD COLUMN IF NOT EXISTS is_paid boolean NOT NULL DEFAULT false
            """
        )
    )
    db.commit()
    _IS_PAID_COLUMN_CHECKED = True


# ======================================================
#  CREATE
# ======================================================


@router.post(
    "/invoices",
    response_model=InvoiceRead,
    status_code=status.HTTP_201_CREATED,
    summary="Kreiraj novu fakturu",
    description=(
        "Kreira novu izlaznu fakturu za zadatog tenanta.\n\n"
        "Tenant se određuje iz `X-Tenant-Code` headera, dok se stavke fakture "
        "šalju u polju `items`.\n\n"
        "Backend za svaku stavku računa osnovicu, PDV i ukupan iznos, a zatim "
        "i agregate (`total_base`, `total_vat`, `total_amount`) na nivou fakture."
    ),
    responses={
        201: {
            "description": "Faktura je uspješno kreirana.",
            "content": {
                "application/json": {
                    "example": {
                        "id": 1,
                        "tenant_code": "t-demo",
                        "invoice_number": "2025-001",
                        "issue_date": "2025-11-21",
                        "due_date": "2025-12-21",
                        "buyer_name": "Frizer Salon Milica",
                        "buyer_address": "Kralja Petra I 12, Banja Luka",
                        "total_base": "25.00",
                        "total_vat": "4.25",
                        "total_amount": "29.25",
                        "is_paid": False,
                        "items": [
                            {
                                "id": 10,
                                "description": "Muško šišanje",
                                "quantity": "1",
                                "unit_price": "10.00",
                                "vat_rate": "0.17",
                                "base_amount": "10.00",
                                "vat_amount": "1.70",
                                "total_amount": "11.70",
                            },
                            {
                                "id": 11,
                                "description": "Pranje + feniranje",
                                "quantity": "1",
                                "unit_price": "15.00",
                                "vat_rate": "0.17",
                                "base_amount": "15.00",
                                "vat_amount": "2.55",
                                "total_amount": "17.55",
                            },
                        ],
                    }
                }
            },
        },
        400: {
            "description": "Nedostaje `X-Tenant-Code` header ili payload nije validan.",
        },
        409: {
            "description": "Broj fakture već postoji za datog tenanta.",
            "content": {
                "application/json": {
                    "example": {"detail": "Invoice number already exists for this tenant"}
                }
            },
        },
    },
)
def create_invoice(
    payload: InvoiceCreate,
    db: Session = Depends(_get_session_dep),
    x_tenant_code: Optional[str] = Header(
        None,
        alias="X-Tenant-Code",
    ),
) -> Invoice:
    tenant = _require_tenant(x_tenant_code)

    _ensure_tenant_exists(db, tenant)
    _ensure_is_paid_column(db)

    data = payload.model_dump()
    items_data = data.pop("items", [])

    if not items_data:
        raise HTTPException(
            status_code=400,
            detail="Invoice must contain at least one item",
        )

    total_base = Decimal("0.00")
    total_vat = Decimal("0.00")
    total_amount = Decimal("0.00")

    item_models: List[InvoiceItem] = []

    for item in items_data:
        qty = Decimal(str(item["quantity"]))
        unit_price = Decimal(str(item["unit_price"]))
        vat_rate = Decimal(str(item["vat_rate"]))

        base_amount = qty * unit_price
        vat_amount = base_amount * vat_rate
        line_total = base_amount + vat_amount

        total_base += base_amount
        total_vat += vat_amount
        total_amount += line_total

        item_models.append(
            InvoiceItem(
                description=item["description"],
                quantity=qty,
                unit_price=unit_price,
                vat_rate=vat_rate,
                base_amount=base_amount,
                vat_amount=vat_amount,
                total_amount=line_total,
            )
        )

    invoice = Invoice(
        tenant_code=tenant,
        invoice_number=data["invoice_number"],
        issue_date=data["issue_date"],
        due_date=data.get("due_date"),
        buyer_name=data["buyer_name"],
        buyer_address=data.get("buyer_address"),
        total_base=total_base,
        total_vat=total_vat,
        total_amount=total_amount,
        # is_paid ostaje default False (kolona postoji u bazi)
        items=item_models,
    )

    db.add(invoice)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Invoice number already exists for this tenant",
        )

    db.refresh(invoice)
    return invoice


@router.post(
    "/invoices/",
    response_model=InvoiceRead,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
def create_invoice_slash(
    payload: InvoiceCreate,
    db: Session = Depends(_get_session_dep),
    x_tenant_code: Optional[str] = Header(
        None,
        alias="X-Tenant-Code",
    ),
) -> Invoice:
    return create_invoice(payload=payload, db=db, x_tenant_code=x_tenant_code)


# ======================================================
#  LIST – stari API
# ======================================================


@router.get(
    "/invoices",
    response_model=List[InvoiceRead],
    summary="Lista faktura za tenanta",
    description=(
        "Vraća listu faktura za zadatog tenanta uz osnovne filtere i paginaciju.\n\n"
        "Podržani filteri:\n"
        "- `date_from` / `date_to` – opseg po `issue_date` (uključivo),\n"
        "- `buyer_name` – prefiks naziva kupca (npr. 'Frizer').\n\n"
        "Sortiranje: najnovije fakture su prve (`issue_date` ↓ pa `id` ↓)."
    ),
)
def list_invoices(
    db: Session = Depends(_get_session_dep),
    x_tenant_code: Optional[str] = Header(
        None,
        alias="X-Tenant-Code",
    ),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    buyer_name: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> List[Invoice]:
    tenant = _require_tenant(x_tenant_code)

    stmt = select(Invoice).where(Invoice.tenant_code == tenant)

    if date_from is not None:
        stmt = stmt.where(Invoice.issue_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(Invoice.issue_date <= date_to)
    if buyer_name:
        # Za stari API buyer_name tretiramo kao prefiks, zbog testova
        stmt = stmt.where(Invoice.buyer_name.ilike(f"{buyer_name}%"))

    stmt = (
        stmt.order_by(Invoice.issue_date.desc(), Invoice.id.desc())
        .limit(limit)
        .offset(offset)
    )

    rows = db.execute(stmt).scalars().unique().all()
    return list(rows)


@router.get(
    "/invoices/",
    response_model=List[InvoiceRead],
    include_in_schema=False,
)
def list_invoices_slash(
    db: Session = Depends(_get_session_dep),
    x_tenant_code: Optional[str] = Header(
        None,
        alias="X-Tenant-Code",
    ),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    buyer_name: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> List[Invoice]:
    return list_invoices(
        db=db,
        x_tenant_code=x_tenant_code,
        date_from=date_from,
        date_to=date_to,
        buyer_name=buyer_name,
        limit=limit,
        offset=offset,
    )


# ======================================================
#  HELPER ZA FILTERE NA UI LISTI
# ======================================================


def _build_invoices_base_stmt_for_ui(
    tenant: str,
    year: Optional[int],
    month: Optional[int],
    unpaid_only: bool,
    date_from: Optional[date],
    date_to: Optional[date],
    buyer_query: Optional[str],
):
    """
    Zajednički helper za /invoices/list i /invoices/export.
    """
    base_stmt = select(Invoice).where(Invoice.tenant_code == tenant)

    # Filtriranje po godini/mjesecu (issue_date)
    if year is not None:
        base_stmt = base_stmt.where(func.extract("year", Invoice.issue_date) == year)
    if month is not None:
        base_stmt = base_stmt.where(func.extract("month", Invoice.issue_date) == month)

    # Filtriranje po periodu (issue_date od/do)
    if date_from is not None:
        base_stmt = base_stmt.where(Invoice.issue_date >= date_from)
    if date_to is not None:
        base_stmt = base_stmt.where(Invoice.issue_date <= date_to)

    # Filtriranje po kupcu (case-insensitive, substring)
    if buyer_query:
        base_stmt = base_stmt.where(
            Invoice.buyer_name.ilike(f"%{buyer_query}%"),
        )

    # Filtriranje po statusu plaćanja
    if unpaid_only:
        base_stmt = base_stmt.where(Invoice.is_paid.is_(False))

    return base_stmt


# ======================================================
#  LIST FOR UI – /invoices/list
# ======================================================


@router.get(
    "/invoices/list",
    response_model=InvoiceListResponse,
    summary="Lista faktura za UI tabelu",
    description=(
        "UI-friendly lista faktura za jednog tenanta.\n\n"
        "Vraća objekt sa:\n"
        "- `total` – ukupan broj faktura koje zadovoljavaju filtere,\n"
        "- `items` – jedna stranica podataka za UI tabelu.\n\n"
        "Podržani filteri:\n"
        "- `year` i `month` – filtriranje po `issue_date` godini/mjesecu,\n"
        "- `date_from` / `date_to` – opseg po `issue_date` (uključivo),\n"
        "- `buyer_query` – filter po nazivu kupca (substring, case-insensitive),\n"
        "- `unpaid_only` – ako je `true`, vraća samo neplaćene fakture.\n\n"
        "Paginacija:\n"
        "- Može se koristiti `page` + `page_size` (1-based), ili direktno `limit` + `offset`.\n"
        "- Ako je `page` zadat, `limit`/`offset` se ignorišu."
    ),
    responses={
        200: {
            "description": "Uspješno vraćena lista faktura za UI tabelu.",
        },
        400: {
            "description": "Nedostaje `X-Tenant-Code` header ili su filter parametri nevalidni.",
        },
    },
)
def list_invoices_ui(
    db: Session = Depends(_get_session_dep),
    x_tenant_code: Optional[str] = Header(
        None,
        alias="X-Tenant-Code",
    ),
    year: Optional[int] = Query(None, ge=1900, le=2100),
    month: Optional[int] = Query(None, ge=1, le=12),
    unpaid_only: bool = Query(
        False,
        description="Ako je True, vraća samo neplaćene fakture.",
    ),
    date_from: Optional[date] = Query(
        None,
        description="Početni datum opsega (issue_date >= date_from).",
    ),
    date_to: Optional[date] = Query(
        None,
        description="Završni datum opsega (issue_date <= date_to).",
    ),
    buyer_query: Optional[str] = Query(
        None,
        description="Filter po nazivu kupca (case-insensitive, substring).",
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
        20,
        ge=1,
        le=200,
        description="Maksimalan broj faktura u odgovoru (koristi se ako `page` nije zadat).",
    ),
    offset: int = Query(
        0,
        ge=0,
        description="Offset za rezultate (koristi se ako `page` nije zadat).",
    ),
) -> InvoiceListResponse:
    tenant = _require_tenant(x_tenant_code)

    _ensure_is_paid_column(db)

    base_stmt = _build_invoices_base_stmt_for_ui(
        tenant=tenant,
        year=year,
        month=month,
        unpaid_only=unpaid_only,
        date_from=date_from,
        date_to=date_to,
        buyer_query=buyer_query,
    )

    # total
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total: int = db.execute(count_stmt).scalar_one()

    # paginacija – ako je zadat page, on ima prednost nad limit/offset
    if page is not None:
        effective_page_size = page_size or limit
        if effective_page_size <= 0:
            effective_page_size = 20
        query_limit = effective_page_size
        query_offset = (page - 1) * effective_page_size
    else:
        query_limit = limit
        query_offset = offset

    items_stmt = (
        base_stmt.order_by(Invoice.issue_date.desc(), Invoice.id.desc())
        .limit(query_limit)
        .offset(query_offset)
    )
    rows = db.execute(items_stmt).scalars().all()

    return InvoiceListResponse(total=total, items=list(rows))


# ======================================================
#  EXPORT LISTE – /invoices/export
# ======================================================


@router.get(
    "/invoices/export",
    summary="Export liste izlaznih faktura (Excel/CSV)",
    response_class=StreamingResponse,
    description=(
        "Exportuje listu izlaznih faktura za zadatog tenanta u CSV format koji "
        "se može direktno otvoriti u Excel-u.\n\n"
        "Podržani filteri su isti kao i za `/invoices/list`:\n"
        "- `year`, `month`, `date_from`, `date_to`, `buyer_query`, `unpaid_only`.\n\n"
        "Napomena: trenutno je podržan format `excel` (CSV, delimiter `;`)."
    ),
)
def export_invoices(
    db: Session = Depends(_get_session_dep),
    x_tenant_code: Optional[str] = Header(
        None,
        alias="X-Tenant-Code",
    ),
    year: Optional[int] = Query(None, ge=1900, le=2100),
    month: Optional[int] = Query(None, ge=1, le=12),
    unpaid_only: bool = Query(False),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    buyer_query: Optional[str] = Query(None),
    format: str = Query(
        "excel",
        pattern="^(excel|csv)$",
        description="Format eksportovanog fajla. Trenutno podržano: 'excel' (CSV kompatibilan sa Excelom).",
    ),
) -> StreamingResponse:
    tenant = _require_tenant(x_tenant_code)
    _ensure_is_paid_column(db)

    base_stmt = _build_invoices_base_stmt_for_ui(
        tenant=tenant,
        year=year,
        month=month,
        unpaid_only=unpaid_only,
        date_from=date_from,
        date_to=date_to,
        buyer_query=buyer_query,
    )

    base_stmt = base_stmt.order_by(Invoice.issue_date.desc(), Invoice.id.desc())
    rows: List[Invoice] = db.execute(base_stmt).scalars().all()

    # Priprema CSV sadržaja (Excel-friendly, delimiter ';', UTF-8 sa BOM)
    output = io.StringIO()
    # Header red
    output.write(
        "Broj fakture;Datum izdavanja;Rok plaćanja;Kupac;Ukupan iznos;Plaćena\n"
    )

    for inv in rows:
        invoice_number = inv.invoice_number or ""
        issue_date_str = inv.issue_date.isoformat() if inv.issue_date else ""
        due_date_str = inv.due_date.isoformat() if inv.due_date else ""
        buyer_name = inv.buyer_name or ""
        total_amount = f"{inv.total_amount:.2f}" if inv.total_amount is not None else ""
        is_paid_str = "DA" if inv.is_paid else "NE"

        line = (
            f"{invoice_number};"
            f"{issue_date_str};"
            f"{due_date_str};"
            f"{buyer_name};"
            f"{total_amount};"
            f"{is_paid_str}\n"
        )
        output.write(line)

    csv_bytes = ("\ufeff" + output.getvalue()).encode("utf-8")  # BOM za Excel
    buffer = io.BytesIO(csv_bytes)

    filename = "invoices-export.csv"
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
    }

    return StreamingResponse(
        buffer,
        media_type="text/csv; charset=utf-8",
        headers=headers,
    )


# ======================================================
#  MARK PAID
# ======================================================


@router.post(
    "/invoices/{invoice_id}/mark-paid",
    response_model=InvoiceRead,
    summary="Označi fakturu kao plaćenu",
    description=(
        "Postavlja polje `is_paid` na `true` za fakturu određenog tenanta.\n\n"
        "Ako je faktura već plaćena, endpoint je idempotentan – samo vraća postojeće stanje.\n"
        "Ako faktura ne postoji ili ne pripada tenant-u, vraća se 404."
    ),
    responses={
        200: {
            "description": "Faktura je označena kao plaćena (ili je već bila plaćena).",
            "content": {
                "application/json": {
                    "example": {
                        "id": 1,
                        "tenant_code": "t-demo",
                        "invoice_number": "2025-001",
                        "issue_date": "2025-11-21",
                        "due_date": "2025-12-21",
                        "buyer_name": "Frizer Salon Milica",
                        "buyer_address": "Kralja Petra I 12, Banja Luka",
                        "total_base": "25.00",
                        "total_vat": "4.25",
                        "total_amount": "29.25",
                        "is_paid": True,
                        "items": [
                            {
                                "id": 10,
                                "description": "Muško šišanje",
                                "quantity": "1",
                                "unit_price": "10.00",
                                "vat_rate": "0.17",
                                "base_amount": "10.00",
                                "vat_amount": "1.70",
                                "total_amount": "11.70",
                            }
                        ],
                    }
                }
            },
        },
        404: {
            "description": "Faktura ne postoji ili ne pripada datom tenant-u.",
            "content": {
                "application/json": {
                    "example": {"detail": "Invoice not found"}
                }
            },
        },
    },
)
def mark_invoice_paid(
    invoice_id: int,
    db: Session = Depends(_get_session_dep),
    x_tenant_code: Optional[str] = Header(
        None,
        alias="X-Tenant-Code",
    ),
) -> Invoice:
    tenant = _require_tenant(x_tenant_code)

    _ensure_is_paid_column(db)

    stmt = select(Invoice).where(
        Invoice.id == invoice_id,
        Invoice.tenant_code == tenant,
    )
    invoice = db.execute(stmt).scalars().first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if not invoice.is_paid:
        invoice.is_paid = True
        db.add(invoice)
        db.commit()
        db.refresh(invoice)

    return invoice


# ======================================================
#  GET BY ID
# ======================================================


@router.get(
    "/invoices/{invoice_id}",
    response_model=InvoiceRead,
    summary="Dohvati jednu fakturu po ID-u",
)
def get_invoice(
    invoice_id: int,
    db: Session = Depends(_get_session_dep),
    x_tenant_code: Optional[str] = Header(
        None,
        alias="X-Tenant-Code",
    ),
) -> Invoice:
    tenant = _require_tenant(x_tenant_code)

    stmt = select(Invoice).where(
        Invoice.id == invoice_id,
        Invoice.tenant_code == tenant,
    )
    obj = db.execute(stmt).scalars().first()
    if not obj:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return obj


# ======================================================
#  DELETE
# ======================================================


@router.delete(
    "/invoices/{invoice_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Obriši fakturu",
    response_class=Response,
)
def delete_invoice(
    invoice_id: int,
    db: Session = Depends(_get_session_dep),
    x_tenant_code: Optional[str] = Header(
        None,
        alias="X-Tenant-Code",
    ),
) -> Response:
    """
    Briše fakturu za zadatog tenanta.

    Ako je poreski period (godina-mjesec issue_date fakture) već finalizovan
    putem TAX modula, SQLAlchemy event u modelima će baciti
    FinalizedPeriodModificationError. Taj exception **ne hvatamo ovdje**,
    već ga puštamo da ode do globalnog handlera u main.py koji vraća 400.
    """
    tenant = _require_tenant(x_tenant_code)

    stmt = select(Invoice).where(
        Invoice.id == invoice_id,
        Invoice.tenant_code == tenant,
    )
    obj = db.execute(stmt).scalars().first()
    if not obj:
        raise HTTPException(status_code=404, detail="Invoice not found")

    db.delete(obj)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ======================================================
#  PDF EXPORT – pojedinačna faktura
# ======================================================


@router.get(
    "/invoices/{invoice_id}/pdf",
    summary="Generiši PDF verziju fakture",
    response_class=StreamingResponse,
    description=(
        "Generiše PDF verziju fakture i vraća je kao `application/pdf` odgovor.\n\n"
        "Tipični scenariji:\n"
        "- direktan prikaz u browseru,\n"
        "- download i slanje fakture klijentu e-mailom.\n\n"
        "Ako faktura ne postoji ili ne pripada datom tenant-u, vraća se 404."
    ),
    responses={
        200: {
            "description": "PDF fakture je uspješno generisan.",
            "content": {
                "application/pdf": {
                    "schema": {"type": "string", "format": "binary"}
                }
            },
        },
        404: {
            "description": "Faktura nije pronađena za zadati ID/tenant kombinaciju.",
            "content": {
                "application/json": {
                    "example": {"detail": "Invoice not found"}
                }
            },
        },
    },
)
def get_invoice_pdf(
    invoice_id: int,
    db: Session = Depends(_get_session_dep),
    x_tenant_code: Optional[str] = Header(
        None,
        alias="X-Tenant-Code",
    ),
) -> StreamingResponse:
    tenant = _require_tenant(x_tenant_code)

    stmt = select(Invoice).where(
        Invoice.id == invoice_id,
        Invoice.tenant_code == tenant,
    )
    invoice = db.execute(stmt).scalars().first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    pdf_bytes = render_invoice_pdf(invoice)
    buffer = io.BytesIO(pdf_bytes)

    filename = f"invoice-{invoice.invoice_number or invoice.id}.pdf"
    headers = {
        "Content-Disposition": f'inline; filename="{filename}"',
    }

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers=headers,
    )
