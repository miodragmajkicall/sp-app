# /home/miso/dev/sp-app/sp-app/backend/app/routes/input_invoices.py
from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
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
from app.models import (
    CashEntry,
    FinalizedPeriodModificationError,
    InputInvoice,
)
from app.services.input_invoice_recognition import (
    resolve_stored_input_invoice_recognition,
)
from app.services.period_guard import ensure_period_open
from app.schemas.input_invoice import (
    InputInvoiceCreate,
    InputInvoiceListResponse,
    InputInvoicePaymentCreate,
    InputInvoicePaymentRead,
    InputInvoiceRead,
    InputInvoiceUpdate,
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


_MONEY_QUANT = Decimal("0.01")


def _money_2(value: Decimal) -> Decimal:
    return value.quantize(_MONEY_QUANT, rounding=ROUND_HALF_UP)


def _validate_input_invoice_amounts(
    *,
    total_base: Decimal,
    total_vat: Decimal,
    total_amount: Decimal,
) -> None:
    expected_total = _money_2(_money_2(total_base) + _money_2(total_vat))
    actual_total = _money_2(total_amount)

    if expected_total != actual_total:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="total_amount must equal total_base + total_vat",
        )


def _validate_input_invoice_dates(
    *,
    issue_date: date | None,
    due_date: date | None,
) -> None:
    if (
        issue_date is not None
        and due_date is not None
        and due_date < issue_date
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="due_date cannot be before issue_date",
        )


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
        "- `posting_date` može biti različit od `issue_date` (datum knjiženja);\n"
        "- tenant se određuje preko `X-Tenant-Code` header-a."
    ),
    responses={  # type: ignore[assignment]
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
                        "posting_date": "2025-11-01",
                        "due_date": "2025-11-15",
                        "expense_category": "Komunalije",
                        "is_tax_deductible": True,
                        "is_paid": False,
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
    - Ako `posting_date` nije zadat, postavlja se na `issue_date`.
    """
    tenant = _require_tenant(x_tenant_code)
    _ensure_tenant_exists(db, tenant)

    data = payload.model_dump()

    # Finansijska lifecycle polja su server-authoritative.
    # U trenutnoj V3 fazi ulazne fakture vode se isključivo u BAM,
    # a status plaćanja mijenja se samo kroz payment lifecycle.
    data["currency"] = "BAM"
    data["is_paid"] = False

    _validate_input_invoice_amounts(
        total_base=data["total_base"],
        total_vat=data["total_vat"],
        total_amount=data["total_amount"],
    )

    _validate_input_invoice_dates(
        issue_date=data["issue_date"],
        due_date=data.get("due_date"),
    )

    # Ako datum knjiženja nije eksplicitno postavljen, koristi datum dokumenta
    if not data.get("posting_date") and data.get("issue_date"):
        data["posting_date"] = data["issue_date"]

    # Prazna kategorija troška se tretira kao None
    if data.get("expense_category") == "":
        data["expense_category"] = None

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
        "- podržava filtere `year`, `month`, `supplier_name`, `expense_category`, `limit`, `offset`.\n\n"
        "`total` je ukupan broj zapisa koji zadovoljavaju filtere (bez obzira na limit),\n"
        "dok `items` sadrži jednu stranicu podataka za prikaz u UI-ju."
    ),
    responses={  # type: ignore[assignment]
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
                                "posting_date": "2025-11-01",
                                "expense_category": "Komunalije",
                                "is_tax_deductible": True,
                                "is_paid": False,
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
                                "posting_date": "2025-11-05",
                                "expense_category": "Telekom usluge",
                                "is_tax_deductible": True,
                                "is_paid": True,
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
    expense_category: Optional[str] = Query(
        None,
        description="Filter po kategoriji troška (npr. 'Gorivo', 'Komunalije').",
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
    if expense_category:
        base_filters.append(InputInvoice.expense_category == expense_category)

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
    expense_category: Optional[str] = Query(None),
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
        expense_category=expense_category,
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
    responses={  # type: ignore[assignment]
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


# ======================================================
#  UPDATE
# ======================================================


@router.put(
    "/input-invoices/{invoice_id}",
    response_model=InputInvoiceRead,
    summary="Ažuriraj postojeću ulaznu fakturu",
    description=(
        "Ažurira postojeću ulaznu fakturu za zadatog tenanta.\n\n"
        "Podržava djelimične izmjene preko `InputInvoiceUpdate` šeme:\n"
        "- moguće je promijeniti dobavljača, broj, datume, kategoriju, poresku priznatost i napomenu;\n"
        "- finansijska polja moguće je mijenjati dok faktura nema povezano plaćanje;\n"
        "- status plaćanja je server-authoritative i mijenja se isključivo kroz payment lifecycle;\n"
        "- polja relevantna za priznavanje provjeravaju finalizaciju prema periodu integriteta fakture."
    ),
    responses={  # type: ignore[assignment]
        200: {
            "description": "Ulazna faktura je uspješno ažurirana.",
        },
        400: {
            "description": (
                "Poslovna greška – pokušaj izmjene podataka relevantnih za priznavanje "
                "u već finalizovanom periodu integriteta."
            ),
            "content": {
                "application/json": {
                    "example": {
                        "detail": (
                            "Cannot modify data for finalized tax period 2025-01 for "
                            "tenant t-demo."
                        )
                    }
                }
            },
        },
        404: {
            "description": "Ulazna faktura nije pronađena za dati ID/tenant.",
        },
        409: {
            "description": (
                "Pokušaj promjene na kombinaciju (tenant_code, supplier_name, invoice_number) "
                "koja već postoji."
            ),
        },
    },
)
def update_input_invoice(
    invoice_id: int,
    payload: InputInvoiceUpdate,
    db: Session = Depends(_get_session_dep),
    x_tenant_code: Optional[str] = Header(
        None,
        alias="X-Tenant-Code",
        description="Šifra tenanta kojem ulazna faktura mora pripadati.",
    ),
) -> InputInvoice:
    """
    Djelimično ažurira postojeću ulaznu fakturu.

    - Ako faktura ne postoji ili ne pripada tenantu → 404.
    - Izmjene polja relevantnih za priznavanje provjeravaju period integriteta fakture.
    - Finansijska polja plaćene fakture ne mogu se mijenjati dok se plaćanje ne poništi.
    - Ako dođe do unique konflikta → 409.
    """
    tenant = _require_tenant(x_tenant_code)

    stmt = select(InputInvoice).where(
        InputInvoice.id == invoice_id,
        InputInvoice.tenant_code == tenant,
    )
    obj = db.execute(stmt).scalars().first()
    if not obj:
        raise HTTPException(status_code=404, detail="Input invoice not found")

    update_data = payload.model_dump(exclude_unset=True)

    required_non_nullable_fields = {
        "supplier_name",
        "invoice_number",
        "issue_date",
        "is_tax_deductible",
    }
    updated_required_fields = required_non_nullable_fields.intersection(update_data)
    if any(update_data[field] is None for field in updated_required_fields):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Input invoice required fields cannot be null",
        )

    amount_fields = {
        "total_base",
        "total_vat",
        "total_amount",
    }
    updated_amount_fields = amount_fields.intersection(update_data)
    if any(update_data[field] is None for field in updated_amount_fields):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Input invoice amounts cannot be null",
        )

    _validate_input_invoice_dates(
        issue_date=update_data.get("issue_date", obj.issue_date),
        due_date=update_data.get("due_date", obj.due_date),
    )

    payment_sensitive_fields = {
        "total_base",
        "total_vat",
        "total_amount",
    }

    finalized_sensitive_fields = {
        "supplier_name",
        "supplier_tax_id",
        "invoice_number",
        "issue_date",
        "posting_date",
        "expense_category",
        "is_tax_deductible",
    }

    if finalized_sensitive_fields.intersection(update_data):
        recognition = resolve_stored_input_invoice_recognition(db, obj)
        try:
            ensure_period_open(
                db,
                tenant_code=tenant,
                period_date=recognition.integrity_date,
            )
        except FinalizedPeriodModificationError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    if payment_sensitive_fields.intersection(update_data):
        linked_payment_id = db.execute(
            select(CashEntry.id).where(
                CashEntry.tenant_code == tenant,
                CashEntry.input_invoice_id == invoice_id,
            )
        ).scalar_one_or_none()
        if linked_payment_id is not None:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Financial fields of a paid input invoice cannot be changed; "
                    "remove the payment first"
                ),
            )

    if updated_amount_fields:
        _validate_input_invoice_amounts(
            total_base=update_data.get("total_base", obj.total_base),
            total_vat=update_data.get("total_vat", obj.total_vat),
            total_amount=update_data.get("total_amount", obj.total_amount),
        )

    # Prazna kategorija troška se tretira kao None
    if update_data.get("expense_category") == "":
        update_data["expense_category"] = None

    for field_name, value in update_data.items():
        setattr(obj, field_name, value)

    try:
        db.commit()
    except FinalizedPeriodModificationError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Input invoice already exists for this supplier and tenant",
        )

    db.refresh(obj)
    return obj


# ======================================================
#  PAYMENT
# ======================================================


@router.post(
    "/input-invoices/{invoice_id}/payment",
    response_model=InputInvoicePaymentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Evidentiraj puno plaćanje ulazne fakture",
)
def create_input_invoice_payment(
    invoice_id: int,
    payload: InputInvoicePaymentCreate,
    db: Session = Depends(_get_session_dep),
    x_tenant_code: Optional[str] = Header(
        None,
        alias="X-Tenant-Code",
        description="Šifra tenanta kojem ulazna faktura mora pripadati.",
    ),
) -> InputInvoicePaymentRead:
    tenant = _require_tenant(x_tenant_code)

    invoice = db.execute(
        select(InputInvoice).where(
            InputInvoice.id == invoice_id,
            InputInvoice.tenant_code == tenant,
        )
    ).scalars().first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Input invoice not found")

    existing_payment_id = db.execute(
        select(CashEntry.id).where(
            CashEntry.tenant_code == tenant,
            CashEntry.input_invoice_id == invoice_id,
        )
    ).scalar_one_or_none()
    if existing_payment_id is not None:
        raise HTTPException(
            status_code=409,
            detail="Input invoice payment already exists",
        )

    try:
        ensure_period_open(
            db,
            tenant_code=tenant,
            period_date=payload.payment_date,
        )
    except FinalizedPeriodModificationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    payment = CashEntry(
        tenant_code=tenant,
        entry_date=payload.payment_date,
        kind="expense",
        amount=invoice.total_amount,
        account=payload.account,
        recognition_class=None,
        tax_treatment=None,
        invoice_id=None,
        input_invoice_id=invoice.id,
        description=payload.note,
    )

    db.add(payment)
    invoice.is_paid = True
    db.add(invoice)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Input invoice payment already exists",
        )

    db.refresh(payment)

    return InputInvoicePaymentRead(
        id=payment.id,
        payment_date=payment.entry_date,
        account=payment.account,
        amount=payment.amount,
        note=payment.description,
    )

# ======================================================
#  PAYMENT GET
# ======================================================


@router.get(
    "/input-invoices/{invoice_id}/payment",
    response_model=InputInvoicePaymentRead,
    summary="Dohvati evidentirano plaćanje ulazne fakture",
)
def get_input_invoice_payment(
    invoice_id: int,
    db: Session = Depends(_get_session_dep),
    x_tenant_code: Optional[str] = Header(
        None,
        alias="X-Tenant-Code",
        description="Šifra tenanta kojem ulazna faktura mora pripadati.",
    ),
) -> InputInvoicePaymentRead:
    tenant = _require_tenant(x_tenant_code)

    invoice = db.execute(
        select(InputInvoice.id).where(
            InputInvoice.id == invoice_id,
            InputInvoice.tenant_code == tenant,
        )
    ).scalar_one_or_none()
    if invoice is None:
        raise HTTPException(status_code=404, detail="Input invoice not found")

    payment = db.execute(
        select(CashEntry).where(
            CashEntry.tenant_code == tenant,
            CashEntry.input_invoice_id == invoice_id,
        )
    ).scalars().first()
    if not payment:
        raise HTTPException(
            status_code=404,
            detail="Input invoice payment not found",
        )

    return InputInvoicePaymentRead(
        id=payment.id,
        payment_date=payment.entry_date,
        account=payment.account,
        amount=payment.amount,
        note=payment.description,
    )

# ======================================================
#  PAYMENT DELETE / UNDO
# ======================================================


@router.delete(
    "/input-invoices/{invoice_id}/payment",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Poništi evidentirano plaćanje ulazne fakture",
)
def delete_input_invoice_payment(
    invoice_id: int,
    db: Session = Depends(_get_session_dep),
    x_tenant_code: Optional[str] = Header(
        None,
        alias="X-Tenant-Code",
        description="Šifra tenanta kojem ulazna faktura mora pripadati.",
    ),
) -> Response:
    tenant = _require_tenant(x_tenant_code)

    invoice = db.execute(
        select(InputInvoice).where(
            InputInvoice.id == invoice_id,
            InputInvoice.tenant_code == tenant,
        )
    ).scalars().first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Input invoice not found")

    payment = db.execute(
        select(CashEntry).where(
            CashEntry.tenant_code == tenant,
            CashEntry.input_invoice_id == invoice_id,
        )
    ).scalars().first()
    if not payment:
        raise HTTPException(
            status_code=404,
            detail="Input invoice payment not found",
        )

    try:
        ensure_period_open(
            db,
            tenant_code=tenant,
            period_date=payment.entry_date,
        )
    except FinalizedPeriodModificationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    db.delete(payment)
    invoice.is_paid = False
    db.add(invoice)

    try:
        db.commit()
    except FinalizedPeriodModificationError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))

    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ======================================================
#  DELETE
# ======================================================


@router.delete(
    "/input-invoices/{invoice_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Obriši ulaznu fakturu",
    description=(
        "Briše ulaznu fakturu za zadatog tenanta.\n\n"
        "Ako faktura ne postoji ili ne pripada tenantu → 404.\n"
        "Ako faktura ima povezano plaćanje → 409.\n"
        "Ako je period integriteta fakture finalizovan → 400."
    ),
    responses={  # type: ignore[assignment]
        204: {
            "description": "Ulazna faktura je uspješno obrisana.",
        },
        400: {
            "description": (
                "Poslovna greška – pokušaj brisanja ulazne fakture za finalizovan period integriteta."
            ),
            "content": {
                "application/json": {
                    "example": {
                        "detail": (
                            "Cannot modify data for finalized tax period 2025-01 for "
                            "tenant t-demo."
                        )
                    }
                }
            },
        },
        404: {
            "description": "Ulazna faktura nije pronađena za dati ID/tenant.",
        },
        409: {
            "description": (
                "Ulazna faktura ima povezano plaćanje i ne može biti obrisana "
                "dok se plaćanje ne poništi."
            ),
        },
    },
)
def delete_input_invoice(
    invoice_id: int,
    db: Session = Depends(_get_session_dep),
    x_tenant_code: Optional[str] = Header(
        None,
        alias="X-Tenant-Code",
        description="Šifra tenanta kojem ulazna faktura mora pripadati.",
    ),
) -> Response:
    """
    Briše jednu ulaznu fakturu.

    - 404 ako faktura ne postoji ili ne pripada tenantu.
    - 409 ako faktura ima povezano plaćanje.
    - 400 ako je period integriteta fakture finalizovan.
    """
    tenant = _require_tenant(x_tenant_code)

    stmt = select(InputInvoice).where(
        InputInvoice.id == invoice_id,
        InputInvoice.tenant_code == tenant,
    )
    obj = db.execute(stmt).scalars().first()
    if not obj:
        raise HTTPException(status_code=404, detail="Input invoice not found")

    linked_payment_id = db.execute(
        select(CashEntry.id).where(
            CashEntry.tenant_code == tenant,
            CashEntry.input_invoice_id == invoice_id,
        )
    ).scalar_one_or_none()
    if linked_payment_id is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                "Input invoice with an existing payment cannot be deleted; "
                "remove the payment first"
            ),
        )

    recognition = resolve_stored_input_invoice_recognition(db, obj)
    try:
        ensure_period_open(
            db,
            tenant_code=tenant,
            period_date=recognition.integrity_date,
        )
    except FinalizedPeriodModificationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    try:
        db.delete(obj)
        db.commit()
    except FinalizedPeriodModificationError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))

    return Response(status_code=status.HTTP_204_NO_CONTENT)
