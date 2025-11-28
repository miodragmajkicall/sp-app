from __future__ import annotations

from datetime import date
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
from sqlalchemy import select, func
    # NOTE: func koristi se za year/month ekstrakcije i count
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_session as _get_session_dep
from app.models import InputInvoice
from app.schemas.input_invoice import (
    InputInvoiceCreate,
    InputInvoiceRead,
    InputInvoiceListResponse,
)
from app.tenant_security import require_tenant_code, ensure_tenant_exists

router = APIRouter(
    tags=["input-invoices"],
)


# ======================================================
#  TENANT HELPERS – SHARED LOGIKA
# ======================================================


def _require_tenant(x_tenant_code: Optional[str]) -> str:
    """
    Osigurava da je X-Tenant-Code header postavljen.
    Ako nedostaje, baca HTTP 400 sa porukom `Missing X-Tenant-Code header`.

    Implementacija delegira na shared helper iz `app.tenant_security`
    da bi svi moduli imali identično ponašanje.
    """
    return require_tenant_code(x_tenant_code)


def _ensure_tenant_exists(db: Session, code: str) -> None:
    """
    Pobrini se da u bazi postoji red u tabeli tenants sa zadatim `code`.

    Kroz shared helper `ensure_tenant_exists` dobijamo jedno centralno mjesto
    za kreiranje minimalnog tenanta kada radimo demo/test scenarije.
    """
    ensure_tenant_exists(db, code)


# ======================================================
#  CREATE
# ======================================================


@router.post(
    "/input-invoices",
    response_model=InputInvoiceRead,
    status_code=status.HTTP_201_CREATED,
    summary="Kreiraj novu ulaznu fakturu (račun dobavljača)",
    description=(
        "Kreira **novu ulaznu fakturu** (račun dobavljača) za konkretnog tenanta.\n\n"
        "Tipični primjeri:\n"
        "- račun za zakup prostora,\n"
        "- račun za struju, vodu, internet,\n"
        "- račun dobavljača za robu / materijal.\n\n"
        "Ključne napomene:\n"
        "- `invoice_number` mora biti jedinstven **po dobavljaču i tenant-u**;\n"
        "- iznosi (`total_base`, `total_vat`, `total_amount`) trenutno dolaze iz klijenta "
        "(kasnije se može dodati automatski obračun);\n"
        "- tenant se određuje preko `X-Tenant-Code` header-a."
    ),
    responses={
        201: {
            "description": "Ulazna faktura je uspješno kreirana.",
            "content": {
                "application/json": {
                    "example": {
                        "id": 1,
                        "tenant_code": "t-demo",
                        "supplier_name": "Elektrodistribucija Banja Luka",
                        "supplier_tax_id": "1234567890000",
                        "supplier_address": "Kralja Petra I Karađorđevića 15, Banja Luka",
                        "invoice_number": "2025-INV-001",
                        "issue_date": "2025-11-01",
                        "due_date": "2025-11-15",
                        "total_base": "100.00",
                        "total_vat": "17.00",
                        "total_amount": "117.00",
                        "currency": "BAM",
                        "note": "Račun za električnu energiju za oktobar.",
                        "created_at": "2025-11-28T10:00:00+00:00",
                    }
                }
            },
        },
        400: {
            "description": "Nedostaje `X-Tenant-Code` header ili payload nije validan.",
        },
        409: {
            "description": (
                "Pokušaj kreiranja duplog računa za istog dobavljača i tenant-a "
                "(kombinacija tenant_code + supplier_name + invoice_number već postoji)."
            ),
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Input invoice already exists for this supplier and tenant"
                    }
                }
            },
        },
    },
)
def create_input_invoice(
    payload: InputInvoiceCreate,
    db: Session = Depends(_get_session_dep),
    x_tenant_code: Optional[str] = Header(
        None,
        alias="X-Tenant-Code",
        description=(
            "Šifra tenanta za kojeg se kreira ulazna faktura.\n"
            "Primjer: `frizer-mika`, `t-demo`."
        ),
    ),
) -> InputInvoice:
    """
    Kreira novu ulaznu fakturu (račun dobavljača) za zadatog tenanta.

    - Jedinstvenost: (tenant_code, supplier_name, invoice_number)
    - Iznosi dolaze iz payload-a (za sada nema automatskog obračuna).
    """
    tenant = _require_tenant(x_tenant_code)
    _ensure_tenant_exists(db, tenant)

    data = payload.model_dump()

    obj = InputInvoice(
        tenant_code=tenant,
        **data,
    )

    db.add(obj)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Input invoice already exists for this supplier and tenant",
        )

    db.refresh(obj)
    return obj


@router.post(
    "/input-invoices/",
    response_model=InputInvoiceRead,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
def create_input_invoice_slash(
    payload: InputInvoiceCreate,
    db: Session = Depends(_get_session_dep),
    x_tenant_code: Optional[str] = Header(None, alias="X-Tenant-Code"),
) -> InputInvoice:
    """
    Alias ruta za POST /input-invoices/ (sa kosom crtom na kraju),
    radi izbjegavanja 307 redirect-a u testovima/klijentu.
    """
    return create_input_invoice(payload=payload, db=db, x_tenant_code=x_tenant_code)


# ======================================================
#  LIST (klasična lista)
# ======================================================


@router.get(
    "/input-invoices",
    response_model=List[InputInvoiceRead],
    summary="Lista ulaznih faktura (troškova) za tenanta",
    description=(
        "Vraća listu ulaznih faktura (računa dobavljača) za zadatog tenanta.\n\n"
        "Podržani filteri:\n"
        "- `date_from` / `date_to` – opseg po `issue_date` (uključivo);\n"
        "- `supplier_name` – prefiks naziva dobavljača (npr. 'Elektro');\n"
        "- `limit` i `offset` – jednostavna paginacija.\n\n"
        "Sortiranje: najnovije fakture su prve "
        "(`issue_date` silazno, pa `id` silazno)."
    ),
)
def list_input_invoices(
    db: Session = Depends(_get_session_dep),
    x_tenant_code: Optional[str] = Header(
        None,
        alias="X-Tenant-Code",
        description="Šifra tenanta čije ulazne fakture vraćamo.",
    ),
    date_from: Optional[date] = Query(
        None,
        description="Početni datum (issue_date) filtera (YYYY-MM-DD, uključivo).",
        examples=["2025-01-01"],
    ),
    date_to: Optional[date] = Query(
        None,
        description="Završni datum (issue_date) filtera (YYYY-MM-DD, uključivo).",
        examples=["2025-01-31"],
    ),
    supplier_name: Optional[str] = Query(
        None,
        description="Filtriranje po nazivu dobavljača (prefiks, npr. 'Elektro').",
    ),
    limit: int = Query(
        50,
        ge=1,
        le=200,
        description="Maksimalan broj zapisa (paginacija).",
    ),
    offset: int = Query(
        0,
        ge=0,
        description="Offset za paginaciju (broj zapisa koje preskačemo).",
    ),
) -> List[InputInvoice]:
    """
    Vraća listu ulaznih faktura za zadatog tenanta,
    sa opcionim datumsko-dobavljač filterima i paginacijom.
    """
    tenant = _require_tenant(x_tenant_code)

    stmt = select(InputInvoice).where(InputInvoice.tenant_code == tenant)

    if date_from is not None:
        stmt = stmt.where(InputInvoice.issue_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(InputInvoice.issue_date <= date_to)
    if supplier_name:
        stmt = stmt.where(InputInvoice.supplier_name.ilike(f"{supplier_name}%"))

    stmt = (
        stmt.order_by(InputInvoice.issue_date.desc(), InputInvoice.id.desc())
        .limit(limit)
        .offset(offset)
    )

    rows = db.execute(stmt).scalars().unique().all()
    return list(rows)


@router.get(
    "/input-invoices/",
    response_model=List[InputInvoiceRead],
    include_in_schema=False,
)
def list_input_invoices_slash(
    db: Session = Depends(_get_session_dep),
    x_tenant_code: Optional[str] = Header(None, alias="X-Tenant-Code"),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    supplier_name: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> List[InputInvoice]:
    """
    Alias ruta za GET /input-invoices/ (sa kosom crtom na kraju).
    """
    return list_input_invoices(
        db=db,
        x_tenant_code=x_tenant_code,
        date_from=date_from,
        date_to=date_to,
        supplier_name=supplier_name,
        limit=limit,
        offset=offset,
    )


# ======================================================
#  LIST UI (total + items za tabelu)
# ======================================================


@router.get(
    "/input-invoices/list",
    response_model=InputInvoiceListResponse,
    summary="UI lista ulaznih faktura (total + items)",
    description=(
        "UI-friendly lista ulaznih faktura za tabelu:\n"
        "- vraća objekt sa `total` i `items` listom,\n"
        "- podržava filtere `year`, `month`, `supplier_name`, `limit`, `offset`.\n\n"
        "`total` je ukupan broj zapisa koji zadovoljavaju filtere (bez obzira na limit),\n"
        "dok `items` sadrži jednu stranicu podataka za prikaz u UI-ju."
    ),
    responses={
        200: {
            "description": "Uspješno vraćena lista ulaznih faktura za UI tabelu.",
            "content": {
                "application/json": {
                    "example": {
                        "total": 2,
                        "items": [
                            {
                                "id": 1,
                                "tenant_code": "t-demo",
                                "supplier_name": "Elektrodistribucija Banja Luka",
                                "invoice_number": "2025-INV-001",
                                "issue_date": "2025-11-01",
                                "due_date": "2025-11-15",
                                "total_base": "100.00",
                                "total_vat": "17.00",
                                "total_amount": "117.00",
                                "currency": "BAM",
                                "created_at": "2025-11-28T10:00:00+00:00",
                            },
                            {
                                "id": 2,
                                "tenant_code": "t-demo",
                                "supplier_name": "Telekom Srpske",
                                "invoice_number": "2025-INV-002",
                                "issue_date": "2025-11-05",
                                "due_date": "2025-11-20",
                                "total_base": "50.00",
                                "total_vat": "8.50",
                                "total_amount": "58.50",
                                "currency": "BAM",
                                "created_at": "2025-11-28T11:30:00+00:00",
                            },
                        ],
                    }
                }
            },
        },
        400: {
            "description": "Nedostaje `X-Tenant-Code` header ili su filter parametri nevalidni.",
        },
    },
)
def list_input_invoices_ui(
    db: Session = Depends(_get_session_dep),
    x_tenant_code: Optional[str] = Header(
        None,
        alias="X-Tenant-Code",
        description="Šifra tenanta čije ulazne fakture prikazujemo u UI-ju.",
    ),
    year: Optional[int] = Query(
        None,
        ge=2000,
        le=2100,
        description="Godina za filter po `issue_date` (npr. 2025).",
    ),
    month: Optional[int] = Query(
        None,
        ge=1,
        le=12,
        description="Mjesec za filter po `issue_date` (1–12).",
    ),
    supplier_name: Optional[str] = Query(
        None,
        description="Prefiks naziva dobavljača (npr. 'Elektro').",
    ),
    limit: int = Query(
        50,
        ge=1,
        le=200,
        description="Maksimalan broj redova u jednoj stranici.",
    ),
    offset: int = Query(
        0,
        ge=0,
        description="Offset za paginaciju (broj redova koje preskačemo).",
    ),
) -> InputInvoiceListResponse:
    """
    UI lista ulaznih faktura – vraća total + items.
    """
    tenant = _require_tenant(x_tenant_code)

    base_filters = [InputInvoice.tenant_code == tenant]

    if year is not None:
        base_filters.append(func.extract("year", InputInvoice.issue_date) == year)
    if month is not None:
        base_filters.append(func.extract("month", InputInvoice.issue_date) == month)
    if supplier_name:
        base_filters.append(InputInvoice.supplier_name.ilike(f"{supplier_name}%"))

    # total (bez limita/offseta)
    total_stmt = select(func.count()).select_from(InputInvoice).where(*base_filters)
    total = db.execute(total_stmt).scalar_one()

    # page items
    items_stmt = (
        select(InputInvoice)
        .where(*base_filters)
        .order_by(InputInvoice.issue_date.desc(), InputInvoice.id.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = db.execute(items_stmt).scalars().all()

    return InputInvoiceListResponse(
        total=int(total),
        items=rows,
    )


@router.get(
    "/input-invoices/list/",
    include_in_schema=False,
)
def list_input_invoices_ui_slash(
    db: Session = Depends(_get_session_dep),
    x_tenant_code: Optional[str] = Header(None, alias="X-Tenant-Code"),
    year: Optional[int] = Query(None, ge=2000, le=2100),
    month: Optional[int] = Query(None, ge=1, le=12),
    supplier_name: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """
    Alias za /input-invoices/list sa kosom crtom na kraju.
    """
    return list_input_invoices_ui(
        db=db,
        x_tenant_code=x_tenant_code,
        year=year,
        month=month,
        supplier_name=supplier_name,
        limit=limit,
        offset=offset,
    )


# ======================================================
#  GET BY ID
# ======================================================


@router.get(
    "/input-invoices/{invoice_id}",
    response_model=InputInvoiceRead,
    summary="Dohvati jednu ulaznu fakturu po ID-u",
    description=(
        "Dohvata jednu ulaznu fakturu (račun dobavljača) po njenom ID-u.\n\n"
        "Ako faktura ne postoji ili ne pripada datom tenant-u, vraća se 404."
    ),
    responses={
        404: {
            "description": (
                "Ulazna faktura nije pronađena za zadati ID/tenant kombinaciju."
            ),
            "content": {
                "application/json": {
                    "example": {"detail": "Input invoice not found"}
                }
            },
        }
    },
)
def get_input_invoice(
    invoice_id: int,
    db: Session = Depends(_get_session_dep),
    x_tenant_code: Optional[str] = Header(
        None,
        alias="X-Tenant-Code",
        description="Šifra tenanta kojem ulazna faktura mora pripadati.",
    ),
) -> InputInvoice:
    """
    Vraća jednu ulaznu fakturu po ID-u.

    Ako faktura ne postoji ili ne pripada zadatom tenant-u, vraća se 404.
    """
    tenant = _require_tenant(x_tenant_code)

    stmt = select(InputInvoice).where(
        InputInvoice.id == invoice_id,
        InputInvoice.tenant_code == tenant,
    )
    obj = db.execute(stmt).scalars().first()
    if not obj:
        raise HTTPException(status_code=404, detail="Input invoice not found")
    return obj
